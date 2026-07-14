"""Semantic Analyzer — bind symbols, classify roles, build symbol table."""

from __future__ import annotations

import time
from typing import Dict

from .context import PipelineContext


class SemanticAnalyzerStage:
    name = "semantic_analyzer"

    def run(self, ctx: PipelineContext) -> None:
        t0 = time.perf_counter()
        # Map short names → qualified names (last writer wins; fine for Phase 0)
        short_to_qn: Dict[str, str] = {}
        for forest in ctx.forests.values():
            for sym in forest.symbols:
                short_to_qn[sym.name] = sym.qualified_name
                short_to_qn[sym.qualified_name] = sym.qualified_name
            for comp in forest.components:
                short_to_qn[comp.name] = comp.name

        ctx.extras["short_to_qn"] = short_to_qn

        # Resolve call sites to qualified names when possible
        for forest in ctx.forests.values():
            for call in forest.calls:
                qn = short_to_qn.get(call.callee_name)
                if qn:
                    call.attributes["resolved_qualified"] = qn

        # Language summary
        langs = sorted({f.language for f in ctx.forests.values()})
        ctx.extras["languages"] = langs
        ctx.stage_metrics[self.name] = time.perf_counter() - t0
