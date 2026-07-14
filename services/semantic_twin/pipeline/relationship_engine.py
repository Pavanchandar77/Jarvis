"""Relationship Engine — cross-layer edges and denormalized lists."""

from __future__ import annotations

import time

from ..schema import EdgeKind
from .context import PipelineContext


class RelationshipEngineStage:
    name = "relationship_engine"

    def run(self, ctx: PipelineContext) -> None:
        t0 = time.perf_counter()
        g = ctx.graph

        # Rebuild denormalized dependencies/dependents from edges
        for n in g.nodes():
            n.dependencies = []
            n.dependents = []

        for e in g.edges():
            if e.kind in (
                EdgeKind.DEPENDS_ON.value,
                EdgeKind.IMPORTS.value,
                EdgeKind.CALLS.value,
                EdgeKind.READS_STATE.value,
                EdgeKind.WRITES_STATE.value,
            ):
                src = g.get_node(e.source)
                tgt = g.get_node(e.target)
                if src and e.target not in src.dependencies:
                    src.dependencies.append(e.target)
                if tgt and e.source not in tgt.dependents:
                    tgt.dependents.append(e.source)

        # Soft data-flow along call chains for API endpoints
        for n in g.nodes():
            if n.kind != "api_endpoint":
                continue
            for e in g.outgoing_edges(n.id, kinds={EdgeKind.ROUTES_TO.value, EdgeKind.CALLS.value}):
                g.add_edge(EdgeKind.DATA_FLOWS_TO.value, n.id, e.target, weight=0.5)

        issues = g.validate()
        if issues:
            ctx.errors.extend(issues[:50])

        ctx.stage_metrics[self.name] = time.perf_counter() - t0
