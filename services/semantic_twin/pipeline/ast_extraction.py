"""AST Extraction stage — language plugins produce AstForest per file."""

from __future__ import annotations

import time

from .context import PipelineContext


class AstExtractionStage:
    name = "ast_extraction"

    def run(self, ctx: PipelineContext) -> None:
        t0 = time.perf_counter()
        for rel, src in ctx.sources.items():
            plugin = ctx.registry.resolve(rel, src.content)
            if not plugin:
                continue
            try:
                forest = plugin.extract_ast(rel, src.content)
                src.language = forest.language
                ctx.forests[rel] = forest
                if forest.errors:
                    ctx.errors.extend(f"{rel}: {e}" for e in forest.errors)
            except Exception as exc:  # noqa: BLE001 — partial-tolerant
                ctx.errors.append(f"{rel}: extract failed: {exc}")
        ctx.stage_metrics[self.name] = time.perf_counter() - t0
