"""Trace requirement → planning → decision → component → API → DB → tests → deploy."""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set

from services.semantic_twin.models import SemanticTwin
from services.semantic_twin.schema import NodeKind

from .graph import TRACE_ORDER


class RequirementTracer:
    def trace(
        self,
        twin: SemanticTwin,
        requirement_id: str,
        *,
        max_depth: int = 12,
    ) -> Dict[str, Any]:
        node_map = twin.node_map()
        # Resolve requirement node
        root = None
        for n in twin.nodes:
            if n.kind != NodeKind.REQUIREMENT.value:
                continue
            if n.id == requirement_id or (n.attributes or {}).get("raw_id") == requirement_id:
                root = n
                break
            if requirement_id in n.id or requirement_id in (n.name or ""):
                root = n
                break
        if not root:
            return {"error": "requirement not found", "requirement_id": requirement_id}

        # BFS undirected via adjacency for related artifacts
        adj: Dict[str, Set[str]] = {n.id: set() for n in twin.nodes}
        edge_map = {}
        for e in twin.edges:
            adj.setdefault(e.source, set()).add(e.target)
            adj.setdefault(e.target, set()).add(e.source)
            edge_map[(e.source, e.target)] = e.id
            edge_map[(e.target, e.source)] = e.id

        visited: Set[str] = {root.id}
        order: List[str] = [root.id]
        q = deque([(root.id, 0)])
        while q:
            cur, depth = q.popleft()
            if depth >= max_depth:
                continue
            for nxt in adj.get(cur, ()):
                if nxt in visited:
                    continue
                visited.add(nxt)
                order.append(nxt)
                q.append((nxt, depth + 1))

        # Also pull same-prompt nodes
        if root.prompt_id:
            for n in twin.nodes:
                if n.prompt_id == root.prompt_id and n.id not in visited:
                    order.append(n.id)
                    visited.add(n.id)

        stages: Dict[str, List[Dict[str, Any]]] = {k: [] for k in TRACE_ORDER}
        stages["other"] = []
        chain = []
        for nid in order:
            n = node_map.get(nid)
            if not n:
                continue
            item = {
                "id": n.id,
                "name": n.name,
                "kind": n.kind,
                "purpose": n.purpose,
                "why_exists": n.why_exists,
                "prompt_id": n.prompt_id,
                "source_file": n.source_file,
            }
            chain.append(item)
            if n.kind in stages:
                stages[n.kind].append(item)
            else:
                stages["other"].append(item)

        # Impact: dependents of linked components
        impact = []
        for item in chain:
            n = node_map.get(item["id"])
            if not n:
                continue
            for dep in n.dependents[:10]:
                dn = node_map.get(dep)
                if dn:
                    impact.append({"id": dn.id, "name": dn.name, "kind": dn.kind})

        return {
            "requirement_id": root.id,
            "requirement_text": root.description or root.purpose,
            "requested_by": (root.attributes or {}).get("requested_by"),
            "prompt_id": root.prompt_id,
            "chain": chain,
            "stages": stages,
            "what_breaks_if_changed": impact[:40],
            "narrative": self._narrative(root, stages),
        }

    def _narrative(self, root, stages: Dict[str, List]) -> str:
        parts = [
            f"Requirement: {root.description or root.purpose}.",
            f"Requested by: {(root.attributes or {}).get('requested_by', 'user')}.",
        ]
        if stages.get("prompt"):
            parts.append(f"Linked to {len(stages['prompt'])} prompt(s).")
        if stages.get("design_decision"):
            parts.append(f"Informed by {len(stages['design_decision'])} design decision(s).")
        code = len(stages.get("component", [])) + len(stages.get("function", [])) + len(stages.get("api_endpoint", []))
        parts.append(f"Satisfied by ~{code} code/API artifact(s).")
        if stages.get("table"):
            parts.append(f"Touches {len(stages['table'])} data store(s).")
        if stages.get("test"):
            parts.append(f"Covered by {len(stages['test'])} test node(s).")
        return " ".join(parts)
