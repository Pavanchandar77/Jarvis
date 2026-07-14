"""Inject design decision and alternative nodes."""

from __future__ import annotations

from ..ids import decision_node_id, stable_node_id
from ..models import SemanticNode
from ..schema import EdgeKind, NodeKind
from ..pipeline.context import PipelineContext


def inject_design_decisions(ctx: PipelineContext) -> None:
    g = ctx.graph
    app_id = ctx.extras.get("app_node_id")

    for dec in ctx.manifest.decisions or []:
        did = decision_node_id(dec.id)
        g.add_node(
            SemanticNode(
                id=did,
                kind=NodeKind.DESIGN_DECISION.value,
                name=dec.title,
                description=dec.rationale,
                purpose=f"Chose: {dec.chosen}",
                why_exists="Records the AI's architectural choice and trade-offs.",
                created_by="ai",
                prompt_id=dec.prompt_id,
                attributes={
                    "chosen": dec.chosen,
                    "trade_offs": list(dec.trade_offs or []),
                    "related_node_ids": list(dec.related_node_ids or []),
                },
                difficulty_score=0.5,
            ),
            replace=True,
        )
        if app_id:
            g.add_edge(EdgeKind.CONTAINS.value, app_id, did)

        for alt in dec.alternatives or []:
            aid = stable_node_id(NodeKind.ALTERNATIVE.value, None, f"{dec.id}:{alt.id}")
            g.add_node(
                SemanticNode(
                    id=aid,
                    kind=NodeKind.ALTERNATIVE.value,
                    name=alt.title,
                    description=alt.summary,
                    purpose=alt.why_rejected,
                    why_exists="Surfaces rejected alternatives for learning and redesign.",
                    created_by="ai",
                    prompt_id=dec.prompt_id,
                    attributes={
                        "why_rejected": alt.why_rejected,
                        "when_preferable": alt.when_preferable,
                        "decision_id": dec.id,
                    },
                    difficulty_score=0.45,
                ),
                replace=True,
            )
            g.add_edge(EdgeKind.ALTERNATIVE_TO.value, aid, did)
            if app_id:
                g.add_edge(EdgeKind.CONTAINS.value, app_id, aid)

        for rid in dec.related_node_ids or []:
            if g.has_node(rid):
                g.add_edge(EdgeKind.DECIDED_BY.value, rid, did)
