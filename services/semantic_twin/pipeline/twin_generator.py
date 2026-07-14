"""Twin Generator — package graph into SemanticTwin + compose views."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from ..api.views import ViewComposer
from ..ids import content_hash, new_twin_id
from ..models import (
    SEMANTIC_TWIN_SCHEMA_VERSION,
    SemanticTwin,
    TwinMeta,
)
from ..provenance.design_decisions import inject_design_decisions
from ..provenance.prompt_provenance import inject_prompt_provenance
from .context import PipelineContext


class TwinGeneratorStage:
    name = "twin_generator"

    def run(self, ctx: PipelineContext) -> None:
        t0 = time.perf_counter()

        # Provenance nodes/edges
        inject_prompt_provenance(ctx)
        inject_design_decisions(ctx)

        # Multi-audience views
        ViewComposer().compose_all(ctx.graph)

        nodes, edges, indexes = ctx.graph.snapshot()
        languages = list(ctx.extras.get("languages") or [])
        entrypoints = list(ctx.extras.get("entrypoints") or [])

        # Coverage summary from test nodes
        tests = [n for n in nodes if n.kind == "test"]
        gaps = [n for n in nodes if n.kind == "coverage_gap"]

        meta = TwinMeta(
            application_id=ctx.application_id,
            application_name=ctx.application_name or ctx.application_id,
            entrypoints=entrypoints,
            tech_stack=list(ctx.manifest.tech_stack or []),
            node_count=len(nodes),
            edge_count=len(edges),
            languages=languages,
            coverage_summary={
                "tests": len(tests),
                "gaps": len(gaps),
                "estimated_ratio": (len(tests) / max(1, len([n for n in nodes if n.kind in ("function", "method", "component")]))) if nodes else 0.0,
            },
            stage_metrics=dict(ctx.stage_metrics),
        )

        twin_id = ctx.twin_id or new_twin_id()
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        twin = SemanticTwin(
            twin_id=twin_id,
            application_id=ctx.application_id,
            schema_version=SEMANTIC_TWIN_SCHEMA_VERSION,
            content_revision=int(ctx.extras.get("content_revision") or 1),
            content_hash="",  # filled below
            created_at=ctx.extras.get("created_at") or now,
            updated_at=now,
            owner=ctx.owner,
            manifest=ctx.manifest,
            nodes=nodes,
            edges=edges,
            indexes=indexes,
            meta=meta,
        )

        # Canonical hash
        payload = json.dumps(
            {
                "nodes": [n.to_dict() for n in nodes],
                "edges": [e.to_dict() for e in edges],
                "manifest": ctx.manifest.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        twin.content_hash = content_hash(payload)
        ctx.extras["twin"] = twin
        ctx.stage_metrics[self.name] = time.perf_counter() - t0
