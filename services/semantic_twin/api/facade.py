"""TwinApiFacade — search, explain, trace*, quiz, tutorial, simulate, compare."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..graph.query import GraphQuery
from ..models import SemanticTwin, ViewContent
from ..schema import NodeKind, ViewingMode
from .compare import compare_twins
from .education import generate_quiz, generate_tutorial
from .simulation import simulate_modification
from .views import ViewComposer


class TwinApiFacade:
    """In-process API matching the TypeScript TwinApi contract."""

    def __init__(self, twin: SemanticTwin, prior: Optional[SemanticTwin] = None) -> None:
        self.twin = twin
        self.prior = prior
        self._query = GraphQuery.from_twin(twin)
        self._nodes = twin.node_map()
        self._composer = ViewComposer()

    def search(
        self,
        q: str,
        kinds: Optional[List[str]] = None,
        limit: int = 20,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        tokens = [t for t in re.split(r"\W+", (q or "").lower()) if t]
        kind_set = set(kinds or [])
        hits = []
        for n in self.twin.nodes:
            if kind_set and n.kind not in kind_set:
                continue
            blob = " ".join([
                n.name, n.kind, n.description, n.purpose, n.why_exists,
                " ".join(n.related_concepts),
                str((n.attributes or {}).get("qualified_name", "")),
            ]).lower()
            if tokens:
                score = sum(2.0 if t in n.name.lower() else 1.0 if t in blob else 0.0 for t in tokens)
                if score <= 0:
                    continue
            else:
                score = 0.1
            # Boost exact name
            if q and n.name.lower() == q.lower():
                score += 5
            snippet = n.purpose or n.description or n.why_exists or n.name
            if mode and mode in n.views:
                snippet = n.views[mode].body[:240]
            hits.append({
                "node_id": n.id,
                "name": n.name,
                "kind": n.kind,
                "score": score,
                "snippet": snippet[:240],
            })
        hits.sort(key=lambda h: h["score"], reverse=True)
        limited = hits[: max(1, min(limit, 100))]
        return {"hits": limited, "total": len(hits)}

    def explain(self, node_id: str, mode: str = "intermediate") -> Dict[str, Any]:
        node = self._nodes.get(node_id)
        if not node:
            raise KeyError(f"node not found: {node_id}")
        try:
            ViewingMode(mode)
        except ValueError:
            mode = ViewingMode.INTERMEDIATE.value
        content = node.views.get(mode)
        if not content:
            content = self._composer.ensure_mode(node, mode)
        related = []
        for rid in (node.dependencies[:5] + node.related_concepts[:5]):
            rn = self._nodes.get(rid)
            if rn:
                related.append({"id": rn.id, "name": rn.name, "kind": rn.kind})
        return {
            "node_id": node_id,
            "mode": mode,
            "content": content.to_dict() if isinstance(content, ViewContent) else content,
            "related": related,
        }

    def trace_execution(self, entry_id: str, max_depth: int = 30) -> Dict[str, Any]:
        steps_raw, edge_ids = self._query.trace_execution(entry_id, max_depth=max_depth)
        steps = []
        for nid, order in steps_raw:
            n = self._nodes.get(nid)
            if not n:
                continue
            steps.append({
                "node_id": nid,
                "name": n.name,
                "kind": n.kind,
                "order": order,
                "note": f"execution depth {order}",
            })
        return {"entry_id": entry_id, "steps": steps, "edges": edge_ids}

    def trace_dependency(
        self,
        node_id: str,
        direction: str = "downstream",
        max_depth: int = 10,
    ) -> Dict[str, Any]:
        if direction not in ("upstream", "downstream", "both"):
            direction = "downstream"
        nodes, edges = self._query.trace_dependency(node_id, direction=direction, max_depth=max_depth)
        return {
            "root_id": node_id,
            "direction": direction,
            "nodes": nodes,
            "edges": edges,
            "depth": max_depth,
        }

    def find_concept(self, query: str, limit: int = 20) -> Dict[str, Any]:
        return self.search(query, kinds=[NodeKind.CONCEPT.value], limit=limit)

    def generate_quiz(
        self,
        node_ids: Optional[List[str]] = None,
        difficulty: Optional[float] = None,
        count: int = 5,
    ) -> Dict[str, Any]:
        return generate_quiz(
            self.twin, node_ids=node_ids, difficulty=difficulty, count=count
        )

    def generate_tutorial(
        self,
        focus_node_id: Optional[str] = None,
        max_steps: int = 8,
    ) -> Dict[str, Any]:
        return generate_tutorial(
            self.twin, focus_node_id=focus_node_id, max_steps=max_steps
        )

    def simulate_modification(
        self,
        proposal: str,
        focus_node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return simulate_modification(self.twin, proposal, focus_node_id=focus_node_id)

    def compare_versions(
        self,
        from_revision: int,
        to_revision: Optional[int] = None,
        prior_twin: Optional[SemanticTwin] = None,
    ) -> Dict[str, Any]:
        older = prior_twin or self.prior
        if older is None:
            # Same twin self-diff at request — empty
            return {
                "from_revision": from_revision,
                "to_revision": to_revision or self.twin.content_revision,
                "added_nodes": [],
                "removed_nodes": [],
                "modified_nodes": [],
                "added_edges": [],
                "removed_edges": [],
                "summary": "No prior revision loaded for comparison.",
            }
        return compare_twins(older, self.twin)

    def story_for_node(self, node_id: str) -> List[Dict[str, Any]]:
        """Animation steps: Prompt → Requirement → Decision → Code → Runtime → Deps → Concepts."""
        node = self._nodes.get(node_id)
        if not node:
            raise KeyError(f"node not found: {node_id}")

        def nodes_of_kind_linked(kind: str) -> List[str]:
            found = []
            for e in self.twin.edges:
                if e.source == node_id or e.target == node_id:
                    other = e.target if e.source == node_id else e.source
                    on = self._nodes.get(other)
                    if on and on.kind == kind:
                        found.append(on.id)
            return found

        prompt_ids = nodes_of_kind_linked(NodeKind.PROMPT.value)
        if node.prompt_id:
            for n in self.twin.nodes:
                if n.kind == NodeKind.PROMPT.value and (
                    n.prompt_id == node.prompt_id or n.attributes.get("text_ref")
                ):
                    if n.id not in prompt_ids:
                        prompt_ids.append(n.id)

        req_ids = nodes_of_kind_linked(NodeKind.REQUIREMENT.value)
        dec_ids = nodes_of_kind_linked(NodeKind.DESIGN_DECISION.value)
        # also decisions via decided_by reverse
        for e in self.twin.edges:
            if e.kind == "decided_by" and e.source == node_id:
                dec_ids.append(e.target)

        exec_steps, exec_edges = self._query.trace_execution(node_id, max_depth=8)
        dep_nodes, dep_edges = self._query.trace_dependency(node_id, direction="downstream", max_depth=3)
        concept_ids = list(node.related_concepts or [])

        stages = [
            {
                "kind": "prompt",
                "node_ids": prompt_ids[:5],
                "edge_ids": [],
                "panel_mode": ViewingMode.AI_REASONING.value,
                "duration_ms": 900,
                "label": "Prompt",
            },
            {
                "kind": "requirement",
                "node_ids": req_ids[:5],
                "edge_ids": [],
                "panel_mode": ViewingMode.BEGINNER.value,
                "duration_ms": 800,
                "label": "Requirement",
            },
            {
                "kind": "design_decision",
                "node_ids": list(dict.fromkeys(dec_ids))[:5],
                "edge_ids": [],
                "panel_mode": ViewingMode.SENIOR.value,
                "duration_ms": 1000,
                "label": "Design decision",
            },
            {
                "kind": "generated_code",
                "node_ids": [node_id],
                "edge_ids": [],
                "panel_mode": ViewingMode.INTERMEDIATE.value,
                "duration_ms": 1000,
                "label": "Generated code",
            },
            {
                "kind": "runtime_execution",
                "node_ids": [s[0] for s in exec_steps[:12]],
                "edge_ids": exec_edges[:20],
                "panel_mode": ViewingMode.RUNTIME.value,
                "duration_ms": 1200,
                "label": "Runtime execution",
            },
            {
                "kind": "dependencies",
                "node_ids": dep_nodes[:15],
                "edge_ids": dep_edges[:25],
                "panel_mode": ViewingMode.SENIOR.value,
                "duration_ms": 1000,
                "label": "Dependencies",
            },
            {
                "kind": "related_concepts",
                "node_ids": concept_ids[:10],
                "edge_ids": [],
                "panel_mode": ViewingMode.BEGINNER.value,
                "duration_ms": 900,
                "label": "Related concepts",
            },
        ]
        return stages
