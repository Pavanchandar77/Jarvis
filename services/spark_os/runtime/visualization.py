"""Live Runtime Visualization — animate execution over Twin architecture."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.semantic_twin.graph.query import GraphQuery
from services.semantic_twin.models import SemanticTwin
from services.semantic_twin.schema import NodeKind

from ..models import RuntimeFrame


class RuntimeVisualizer:
    """
    Build animation frames:
    User → Frontend → State → API → Database → Jobs → Response → Rendering
    using twin topology + optional runtime events.
    """

    STAGES = (
        "user", "frontend", "state", "api", "database", "jobs", "response", "render",
    )

    def __init__(self, runtime_ingestor=None) -> None:
        self.runtime = runtime_ingestor

    def build_path(
        self,
        twin: SemanticTwin,
        *,
        entry_node_id: Optional[str] = None,
    ) -> List[RuntimeFrame]:
        node_map = twin.node_map()
        q = GraphQuery.from_twin(twin)

        components = [n for n in twin.nodes if n.kind in (NodeKind.COMPONENT.value, NodeKind.PAGE.value)]
        apis = [n for n in twin.nodes if n.kind in (NodeKind.API_ENDPOINT.value, NodeKind.ROUTE.value)]
        state = [n for n in twin.nodes if n.kind.startswith("state_")]
        tables = [n for n in twin.nodes if n.kind == NodeKind.TABLE.value]
        events = [n for n in twin.nodes if n.kind in (NodeKind.EVENT.value, NodeKind.EVENT_HANDLER.value)]

        entry = entry_node_id
        if not entry and components:
            entry = components[0].id
        if not entry and apis:
            entry = apis[0].id
        if not entry and twin.meta.entrypoints:
            entry = twin.meta.entrypoints[0]

        exec_nodes = []
        exec_edges = []
        if entry:
            steps, edges = q.trace_execution(entry, max_depth=15)
            exec_nodes = [s[0] for s in steps]
            exec_edges = edges

        # Runtime highlights
        events_rt = []
        if self.runtime:
            events_rt = self.runtime.list_events(twin.twin_id, limit=50)
        slow_ids = set()
        fail_ids = set()
        for ev in events_rt:
            if ev.get("duration_ms") and float(ev["duration_ms"]) > 200 and ev.get("node_id"):
                slow_ids.add(ev["node_id"])
            if ev.get("type") in ("error", "warning") and ev.get("node_id"):
                fail_ids.add(ev["node_id"])

        def highlight(ids: List[str]) -> str:
            if any(i in fail_ids for i in ids):
                return "failure"
            if any(i in slow_ids for i in ids):
                return "slow"
            return "normal"

        frames: List[RuntimeFrame] = []
        frames.append(RuntimeFrame(0, "user", [], [], "User interaction", highlight="normal"))
        frames.append(RuntimeFrame(
            1, "frontend",
            [c.id for c in components[:5]] or ([entry] if entry else []),
            [],
            "Frontend / UI",
            highlight=highlight([c.id for c in components[:5]]),
        ))
        frames.append(RuntimeFrame(
            2, "state",
            [s.id for s in state[:5]],
            [],
            "State transition",
            highlight=highlight([s.id for s in state[:5]]),
        ))
        frames.append(RuntimeFrame(
            3, "api",
            [a.id for a in apis[:8]] or exec_nodes[:5],
            exec_edges[:10],
            "API request",
            highlight=highlight([a.id for a in apis[:8]]),
        ))
        frames.append(RuntimeFrame(
            4, "database",
            [t.id for t in tables[:5]],
            [],
            "Database access",
            highlight=highlight([t.id for t in tables[:5]]),
        ))
        frames.append(RuntimeFrame(
            5, "jobs",
            [e.id for e in events[:5]],
            [],
            "Background jobs / events",
            highlight=highlight([e.id for e in events[:5]]),
        ))
        frames.append(RuntimeFrame(
            6, "response",
            exec_nodes[-3:] if exec_nodes else [a.id for a in apis[:2]],
            [],
            "Response assembly",
        ))
        frames.append(RuntimeFrame(
            7, "render",
            [c.id for c in components[:3]],
            [],
            "Rendering",
            highlight=highlight([c.id for c in components[:3]]),
        ))
        return frames

    def live_overlay(self, twin: SemanticTwin) -> Dict[str, Any]:
        frames = self.build_path(twin)
        events = self.runtime.list_events(twin.twin_id, limit=30) if self.runtime else []
        bottlenecks = [
            e for e in events
            if e.get("duration_ms") and float(e["duration_ms"]) > 200
        ]
        failures = [e for e in events if e.get("type") in ("error", "warning")]
        return {
            "twin_id": twin.twin_id,
            "frames": [f.to_dict() for f in frames],
            "recent_events": events,
            "bottlenecks": bottlenecks,
            "failures": failures,
            "path_label": "User → Frontend → State → API → DB → Jobs → Response → Render",
        }
