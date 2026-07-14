"""Compose the seven viewing modes for every node."""

from __future__ import annotations

from typing import Dict

from ..graph.knowledge_graph import KnowledgeGraph
from ..models import SemanticNode, ViewContent
from ..schema import ALL_VIEWING_MODES, CODE_NODE_KINDS, NodeKind, ViewingMode


class ViewComposer:
    def compose_all(self, graph: KnowledgeGraph) -> None:
        for node in graph.nodes():
            self.compose_node(node, graph)

    def compose_node(self, node: SemanticNode, graph: KnowledgeGraph | None = None) -> None:
        views: Dict[str, ViewContent] = {}
        for mode in ALL_VIEWING_MODES:
            views[mode.value] = self._view_for(node, mode, graph)
        node.views = views

    def ensure_mode(self, node: SemanticNode, mode: str, graph: KnowledgeGraph | None = None) -> ViewContent:
        if mode in node.views:
            return node.views[mode]
        try:
            vm = ViewingMode(mode)
        except ValueError:
            vm = ViewingMode.INTERMEDIATE
        content = self._view_for(node, vm, graph)
        node.views[mode] = content
        return content

    def _view_for(
        self,
        node: SemanticNode,
        mode: ViewingMode,
        graph: KnowledgeGraph | None,
    ) -> ViewContent:
        kind = node.kind
        name = node.name
        purpose = node.purpose or node.description or name
        why = node.why_exists or purpose
        deps = len(node.dependencies)
        dependents = len(node.dependents)
        sig = (node.attributes or {}).get("signature") or ""
        loc = ""
        if node.source_file:
            loc = node.source_file
            if node.source_location:
                loc += f":{node.source_location.start_line}"

        if mode == ViewingMode.BEGINNER:
            return ViewContent(
                mode=mode.value,
                title=f"What is {name}?",
                body=(
                    f"Think of **{name}** as a labeled piece of the app. "
                    f"Its job is: {purpose} "
                    f"It exists because: {why} "
                    f"You do not need to know programming jargon to explore it — "
                    f"click related pieces to see how it connects to the rest of the system."
                ),
                bullets=[
                    f"Kind: {kind.replace('_', ' ')}",
                    f"It works with {deps} other piece(s).",
                    f"{dependents} other piece(s) rely on it." if dependents else "Nothing else relies on it yet.",
                ],
                code_refs=[loc] if loc else [],
            )

        if mode == ViewingMode.INTERMEDIATE:
            return ViewContent(
                mode=mode.value,
                title=f"{name} — implementation",
                body=(
                    f"`{name}` is a `{kind}`."
                    + (f" Signature: `{sig}`." if sig else "")
                    + f" Purpose: {purpose} Assumptions: this node was extracted from "
                    f"source and linked via the twin pipeline (imports/calls/routes)."
                ),
                bullets=[
                    f"Dependencies: {deps}",
                    f"Dependents: {dependents}",
                    f"Difficulty: {node.difficulty_score:.2f}",
                    f"Source: {loc or 'n/a'}",
                ],
                code_refs=[loc] if loc else [],
                metrics={"deps": deps, "dependents": dependents},
            )

        if mode == ViewingMode.SENIOR:
            tradeoffs = (node.attributes or {}).get("trade_offs") or []
            return ViewContent(
                mode=mode.value,
                title=f"{name} — architecture",
                body=(
                    f"Architectural role of `{name}` ({kind}): {why} "
                    f"Coupling: fan-in={dependents}, fan-out={deps}. "
                    f"Prefer changing this node only with an understanding of its dependents. "
                    + ("Trade-offs: " + "; ".join(map(str, tradeoffs)) if tradeoffs else "")
                ),
                bullets=[
                    f"Kind: {kind}",
                    f"Fan-in/out: {dependents}/{deps}",
                    f"Created by: {node.created_by}",
                    f"Prompt: {node.prompt_id or 'inferred'}",
                ] + [f"Improvement: {s.summary}" for s in (node.suggested_improvements or [])[:3]],
                metrics={"fan_in": dependents, "fan_out": deps, "difficulty": node.difficulty_score},
            )

        if mode == ViewingMode.RUNTIME:
            order = node.execution_order
            return ViewContent(
                mode=mode.value,
                title=f"{name} — runtime",
                body=(
                    f"At runtime, `{name}` participates in the approximate control-flow "
                    f"with execution order **{order if order is not None else 'unscheduled'}**. "
                    f"The explorer can animate call/render edges leaving this node."
                ),
                bullets=[
                    f"Execution order: {order if order is not None else 'n/a'}",
                    f"Outbound call-like edges will pulse during animation.",
                ],
                metrics={"execution_order": order if order is not None else -1},
            )

        if mode == ViewingMode.AI_REASONING:
            return ViewContent(
                mode=mode.value,
                title=f"Why the model created {name}",
                body=(
                    f"The model introduced `{name}` because: {why} "
                    f"Linked prompt id: `{node.prompt_id or 'none'}`. "
                    f"Created by: `{node.created_by}`. "
                    f"Explore design_decision nodes for rejected alternatives."
                ),
                bullets=[
                    f"Prompt: {node.prompt_id or 'n/a'}",
                    f"Purpose: {purpose}",
                ],
            )

        if mode == ViewingMode.PERFORMANCE:
            async_flag = bool((node.attributes or {}).get("async"))
            return ViewContent(
                mode=mode.value,
                title=f"{name} — performance",
                body=(
                    f"Complexity proxy for `{name}`: difficulty={node.difficulty_score:.2f}, "
                    f"fan-out={deps}. "
                    + ("This symbol is async — watch for unbounded concurrency and missing timeouts. " if async_flag else "")
                    + "Hot paths typically sit on nodes with high fan-in and non-trivial execution order."
                ),
                bullets=[
                    f"Difficulty score: {node.difficulty_score:.2f}",
                    f"Async: {async_flag}",
                    f"Dependents (fan-in): {dependents}",
                ],
                metrics={
                    "difficulty": node.difficulty_score,
                    "fan_out": deps,
                    "fan_in": dependents,
                },
                warnings=["Heuristic analysis — not a profiler sample."] if kind in {k.value for k in CODE_NODE_KINDS} else [],
            )

        # SECURITY
        warnings = []
        if kind in (NodeKind.API_ENDPOINT.value, NodeKind.ROUTE.value):
            warnings.append("Network-facing surface — validate authz, input, and rate limits.")
        if "auth" in name.lower() or "password" in (node.description or "").lower():
            warnings.append("Credential-adjacent logic — avoid logging secrets.")
        return ViewContent(
            mode=mode.value,
            title=f"{name} — security",
            body=(
                f"Attack surface considerations for `{name}` ({kind}): "
                f"review trust boundaries, input validation, and least privilege. "
                f"{why}"
            ),
            bullets=[
                f"Kind: {kind}",
                f"Dependents that could be confused deputies: {dependents}",
            ] + [s.summary for s in (node.suggested_improvements or []) if s.category == "security"][:3],
            warnings=warnings,
        )
