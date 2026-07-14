"""Simulation Engine — pure graph impact analysis; never writes project source."""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Set

from services.semantic_twin.graph.query import GraphQuery
from services.semantic_twin.models import SemanticTwin
from services.semantic_twin.schema import NodeKind

from ..models import SimulationReport
from ..storage.store import ensure_dir, write_json
from pathlib import Path


class SimulationEngine:
    """
    Simulate architectural changes against the Twin only.

    Examples: delete service, move database, split microservice,
    replace auth, upgrade frameworks.
    """

    def __init__(self, store_dir: str | Path | None = None) -> None:
        self.store = ensure_dir(store_dir) if store_dir else None

    def simulate(
        self,
        twin: SemanticTwin,
        proposal: str,
        *,
        focus_node_id: Optional[str] = None,
        persist: bool = True,
    ) -> SimulationReport:
        q = GraphQuery.from_twin(twin)
        node_map = twin.node_map()
        proposal_l = (proposal or "").lower()

        roots = self._resolve_roots(twin, proposal_l, focus_node_id)
        affected: List[str] = []
        for root in roots:
            nodes, _ = q.trace_dependency(root, direction="upstream", max_depth=6)
            for n in nodes:
                if n not in affected:
                    affected.append(n)
            if root not in affected:
                affected.insert(0, root)

        impacted_files: Set[str] = set()
        impacted_services: Set[str] = set()
        broken_apis: List[str] = []
        broken_tests: List[str] = []
        security: List[str] = []
        perf: Dict[str, Any] = {"latency_risk": "low", "notes": []}

        for nid in affected:
            n = node_map.get(nid)
            if not n:
                continue
            if n.source_file:
                impacted_files.add(n.source_file)
            if n.kind in (NodeKind.MODULE.value, NodeKind.PACKAGE.value, NodeKind.COMPONENT.value):
                impacted_services.add(n.name)
            if n.kind in (NodeKind.API_ENDPOINT.value, NodeKind.ROUTE.value):
                broken_apis.append(n.name)
            if n.kind == NodeKind.TEST.value:
                broken_tests.append(n.name)
            if n.kind == NodeKind.SECURITY_SURFACE.value or "auth" in n.name.lower():
                security.append(f"Security-sensitive: {n.name}")
            if n.difficulty_score >= 0.65 or (n.attributes or {}).get("async"):
                perf["notes"].append(f"Hot/complex: {n.name}")

        if len(affected) > 25 or len(broken_apis) > 5:
            risk = "high"
            complexity = "high"
            effort = 5.0 + len(affected) * 0.15
        elif len(affected) > 8:
            risk = "medium"
            complexity = "medium"
            effort = 2.0 + len(affected) * 0.1
        else:
            risk = "low"
            complexity = "low"
            effort = 0.5 + len(affected) * 0.05

        if any(k in proposal_l for k in ("auth", "security", "password", "token")):
            risk = "high"
            security.append("Authentication/authorization change — full threat review required.")
        if any(k in proposal_l for k in ("microservice", "split", "database", "migrate")):
            complexity = "high"
            effort = max(effort, 8.0)
            perf["latency_risk"] = "medium"
            perf["notes"].append("Distributed change may add network hops.")

        if broken_apis:
            perf["latency_risk"] = "medium" if perf["latency_risk"] == "low" else perf["latency_risk"]

        report = SimulationReport(
            simulation_id=uuid.uuid4().hex,
            twin_id=twin.twin_id,
            proposal=proposal,
            risk_level=risk,
            impacted_files=sorted(impacted_files)[:100],
            impacted_services=sorted(impacted_services)[:50],
            broken_apis=broken_apis[:40],
            broken_tests=broken_tests[:40],
            performance=perf,
            security=security[:20],
            migration_complexity=complexity,
            estimated_effort_days=round(effort, 1),
            affected_node_ids=affected[:200],
            narrative=self._narrative(proposal, risk, affected, broken_apis, effort),
        )

        if persist and self.store:
            write_json(self.store / f"{report.simulation_id}.json", report.to_dict())
        return report

    def _resolve_roots(self, twin: SemanticTwin, proposal_l: str, focus: Optional[str]) -> List[str]:
        if focus and any(n.id == focus for n in twin.nodes):
            return [focus]
        roots = []
        for n in twin.nodes:
            if n.name.lower() in proposal_l:
                roots.append(n.id)
            elif n.kind == NodeKind.API_ENDPOINT.value and "api" in proposal_l:
                roots.append(n.id)
        # keyword actions
        if "delete" in proposal_l or "remove" in proposal_l:
            for n in twin.nodes:
                if n.kind in (NodeKind.MODULE.value, NodeKind.PACKAGE.value, NodeKind.COMPONENT.value):
                    if any(tok in n.name.lower() for tok in re.findall(r"[a-z_]{3,}", proposal_l)):
                        roots.append(n.id)
        if not roots and twin.meta.entrypoints:
            roots = list(twin.meta.entrypoints)[:3]
        if not roots and twin.nodes:
            roots = [twin.nodes[0].id]
        # unique preserve order
        seen = set()
        out = []
        for r in roots:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out[:10]

    def _narrative(self, proposal, risk, affected, apis, effort) -> str:
        return (
            f"Simulation (no source modified): {proposal}\n"
            f"Risk: {risk}. Affected nodes: {len(affected)}. "
            f"APIs at risk: {len(apis)}. Estimated effort: {effort} engineer-days."
        )
