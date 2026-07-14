"""Runtime event ingestion — enrich existing graph nodes."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..models import SemanticNode, SemanticTwin, SuggestedImprovement
from ..schema import NodeKind

logger = logging.getLogger(__name__)

# In-memory ring buffers per twin (also flushed into node attributes)
_RUNTIME_BUFFERS: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
_MAX_EVENTS = 500


class RuntimeEventIngestor:
    """
    Attach runtime knowledge to twin nodes.

    Event types:
      app.launch, route.execute, api.request, component.render,
      state.transition, error, warning, perf.metric
    """

    EVENT_TYPES = frozenset({
        "app.launch",
        "route.execute",
        "api.request",
        "component.render",
        "state.transition",
        "error",
        "warning",
        "perf.metric",
    })

    def __init__(self, twin_service=None) -> None:
        self.twin_service = twin_service

    def ingest(
        self,
        twin_id: str,
        event: Dict[str, Any],
        *,
        persist: bool = False,
        owner: Optional[str] = None,
    ) -> Dict[str, Any]:
        etype = event.get("type") or event.get("event_type") or ""
        if etype not in self.EVENT_TYPES:
            # Allow custom types but tag them
            etype = etype or "custom"
        payload = {
            "type": etype,
            "ts": event.get("ts") or time.time(),
            "node_id": event.get("node_id"),
            "name": event.get("name"),
            "path": event.get("path"),
            "method": event.get("method"),
            "duration_ms": event.get("duration_ms"),
            "status": event.get("status"),
            "message": event.get("message"),
            "metrics": event.get("metrics") or {},
            "attributes": event.get("attributes") or {},
        }
        buf = _RUNTIME_BUFFERS[twin_id]
        buf.append(payload)
        if len(buf) > _MAX_EVENTS:
            del buf[: len(buf) - _MAX_EVENTS]

        matched = None
        if self.twin_service and persist:
            try:
                twin = self.twin_service.load(twin_id, owner=owner, include_graph=True)
                matched = self._enrich(twin, payload)
                # Soft-persist: update node attributes only via save
                if matched:
                    self.twin_service.repo.save(twin)
            except Exception as exc:
                logger.debug("runtime enrich failed: %s", exc)

        return {
            "ok": True,
            "twin_id": twin_id,
            "event": payload,
            "matched_node_id": matched,
            "buffered": len(_RUNTIME_BUFFERS[twin_id]),
        }

    def list_events(self, twin_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        buf = _RUNTIME_BUFFERS.get(twin_id) or []
        return buf[-limit:]

    def _enrich(self, twin: SemanticTwin, event: Dict[str, Any]) -> Optional[str]:
        node = self._resolve_node(twin, event)
        if not node:
            return None
        runtime = dict((node.attributes or {}).get("runtime") or {})
        history = list(runtime.get("events") or [])
        history.append({
            "type": event["type"],
            "ts": event["ts"],
            "duration_ms": event.get("duration_ms"),
            "status": event.get("status"),
            "message": (event.get("message") or "")[:300],
        })
        runtime["events"] = history[-50:]
        runtime["last_seen"] = event["ts"]
        runtime["hit_count"] = int(runtime.get("hit_count") or 0) + 1
        if event.get("duration_ms") is not None:
            samples = list(runtime.get("latency_samples_ms") or [])
            samples.append(float(event["duration_ms"]))
            samples = samples[-100:]
            runtime["latency_samples_ms"] = samples
            runtime["latency_p50"] = sorted(samples)[len(samples) // 2]
            runtime["latency_max"] = max(samples)
        if event["type"] in ("error", "warning"):
            runtime["last_error"] = (event.get("message") or event["type"])[:500]
            if event["type"] == "error":
                node.suggested_improvements = list(node.suggested_improvements or [])
                node.suggested_improvements.append(
                    SuggestedImprovement(
                        summary=f"Runtime error observed: {(event.get('message') or '')[:120]}",
                        rationale="Captured from live application telemetry.",
                        impact="high",
                        effort="medium",
                        category="maintainability",
                    )
                )
                # Cap improvements
                node.suggested_improvements = node.suggested_improvements[-10:]
        node.attributes = dict(node.attributes or {})
        node.attributes["runtime"] = runtime
        # Light difficulty nudge for hot paths
        hits = runtime["hit_count"]
        if hits > 20 and event.get("duration_ms") and float(event["duration_ms"]) > 200:
            node.difficulty_score = min(1.0, max(node.difficulty_score, 0.55))
        return node.id

    def _resolve_node(self, twin: SemanticTwin, event: Dict[str, Any]) -> Optional[SemanticNode]:
        if event.get("node_id"):
            return twin.node_map().get(event["node_id"])
        name = (event.get("name") or "").lower()
        path = (event.get("path") or "").lower()
        method = (event.get("method") or "").upper()
        etype = event.get("type") or ""

        candidates = twin.nodes
        if etype in ("api.request", "route.execute"):
            kinds = {NodeKind.API_ENDPOINT.value, NodeKind.ROUTE.value}
            candidates = [n for n in twin.nodes if n.kind in kinds]
        elif etype == "component.render":
            candidates = [n for n in twin.nodes if n.kind in (NodeKind.COMPONENT.value, NodeKind.PAGE.value)]
        elif etype == "state.transition":
            candidates = [n for n in twin.nodes if n.kind.startswith("state_")]

        for n in candidates:
            if name and n.name.lower() == name:
                return n
            attrs = n.attributes or {}
            if path and str(attrs.get("path_pattern") or attrs.get("path") or "").lower() == path:
                return n
            if path and method and n.name.upper().startswith(method) and path in n.name.lower():
                return n
            if path and n.source_file and path in n.source_file.replace("\\", "/").lower():
                return n
        # Fuzzy name contains
        if name:
            for n in candidates:
                if name in n.name.lower():
                    return n
        return None
