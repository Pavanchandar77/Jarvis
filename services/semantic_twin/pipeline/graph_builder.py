"""Knowledge Graph Builder — materialize nodes and structural edges."""

from __future__ import annotations

import time
from typing import Optional

from ..ids import stable_node_id, new_edge_id
from ..models import SemanticNode, SourceLocation
from ..schema import EdgeKind, NodeKind
from .context import PipelineContext

_KIND_MAP = {
    "function": NodeKind.FUNCTION.value,
    "method": NodeKind.METHOD.value,
    "class": NodeKind.CLASS.value,
    "hook": NodeKind.HOOK.value,
    "component": NodeKind.COMPONENT.value,
}


class GraphBuilderStage:
    name = "graph_builder"

    def run(self, ctx: PipelineContext) -> None:
        t0 = time.perf_counter()
        g = ctx.graph

        # Application root node
        app_id = stable_node_id(
            NodeKind.APPLICATION.value, None, ctx.application_id or "app"
        )
        g.add_node(
            SemanticNode(
                id=app_id,
                kind=NodeKind.APPLICATION.value,
                name=ctx.application_name or ctx.application_id or "Application",
                description=f"Generated application {ctx.application_name}",
                purpose="Root of the Semantic Twin for this application.",
                why_exists="Every twin is rooted in a single application node.",
                created_by="ai",
                attributes={
                    "tech_stack": list(ctx.manifest.tech_stack or []),
                    "entrypoints": [],
                },
            ),
            replace=True,
        )
        ctx.extras["app_node_id"] = app_id

        # Module nodes per source file
        module_ids = {}
        for rel, forest in ctx.forests.items():
            mid = stable_node_id(NodeKind.MODULE.value, rel, rel)
            module_ids[rel] = mid
            g.add_node(
                SemanticNode(
                    id=mid,
                    kind=NodeKind.MODULE.value,
                    name=rel.split("/")[-1],
                    description=f"Source module {rel}",
                    purpose=f"Holds definitions from {rel}",
                    why_exists="Modules partition the codebase by file.",
                    created_by="ai",
                    source_file=rel,
                    source_location=SourceLocation(1, max(1, len(ctx.sources[rel].content.splitlines()) if rel in ctx.sources else 1)),
                    attributes={"path": rel, "language": forest.language},
                    prompt_id=self._prompt_for(ctx, rel),
                ),
                replace=True,
            )
            g.add_edge(EdgeKind.CONTAINS.value, app_id, mid, allow_missing=False)

        # Symbols → nodes
        for rel, forest in ctx.forests.items():
            mid = module_ids[rel]
            for sym in forest.symbols:
                kind = _KIND_MAP.get(sym.kind, NodeKind.FUNCTION.value)
                nid = stable_node_id(
                    kind,
                    rel,
                    sym.qualified_name,
                    sym.location.start_line,
                    sym.location.end_line,
                )
                node = SemanticNode(
                    id=nid,
                    kind=kind,
                    name=sym.name,
                    description=sym.docstring or f"{kind} {sym.qualified_name}",
                    purpose=sym.docstring.split("\n")[0] if sym.docstring else f"Implements {sym.name}",
                    why_exists=f"Declared in {rel} as part of the generated application.",
                    created_by="ai",
                    prompt_id=self._prompt_for(ctx, rel),
                    source_file=rel,
                    source_location=SourceLocation(
                        start_line=sym.location.start_line,
                        end_line=sym.location.end_line,
                        start_col=sym.location.start_col,
                        end_col=sym.location.end_col,
                    ),
                    difficulty_score=self._difficulty(sym),
                    attributes={
                        "qualified_name": sym.qualified_name,
                        "signature": sym.signature,
                        "async": sym.is_async,
                        "parent": sym.parent,
                        **(sym.attributes or {}),
                    },
                )
                g.add_node(node, replace=True)
                g.add_edge(EdgeKind.CONTAINS.value, mid, nid)
                ctx.symbol_table[sym.qualified_name] = nid
                ctx.symbol_table[f"{rel}::{sym.qualified_name}"] = nid
                ctx.symbol_table[sym.name] = nid

            for comp in forest.components:
                cid = stable_node_id(
                    NodeKind.COMPONENT.value, rel, comp.name, comp.line, comp.end_line or comp.line
                )
                if not g.has_node(cid):
                    g.add_node(
                        SemanticNode(
                            id=cid,
                            kind=NodeKind.COMPONENT.value,
                            name=comp.name,
                            description=f"UI component {comp.name}",
                            purpose=f"Renders {comp.name} UI",
                            why_exists="Component boundary for the interactive interface.",
                            created_by="ai",
                            prompt_id=self._prompt_for(ctx, rel),
                            source_file=rel,
                            source_location=SourceLocation(comp.line, comp.end_line or comp.line),
                            attributes={"framework": comp.framework, "qualified_name": comp.name},
                            difficulty_score=0.4,
                        ),
                        replace=True,
                    )
                    g.add_edge(EdgeKind.CONTAINS.value, mid, cid)
                    ctx.symbol_table[comp.name] = cid

            for route in forest.routes:
                rid = stable_node_id(
                    NodeKind.ROUTE.value, rel, f"{route.method}:{route.path_pattern}", route.line, route.line
                )
                g.add_node(
                    SemanticNode(
                        id=rid,
                        kind=NodeKind.ROUTE.value,
                        name=f"{route.method} {route.path_pattern}",
                        description=f"HTTP route {route.method} {route.path_pattern}",
                        purpose="Exposes an HTTP entrypoint to the application.",
                        why_exists="Routing connects external clients to handlers.",
                        created_by="ai",
                        prompt_id=self._prompt_for(ctx, rel),
                        source_file=rel,
                        source_location=SourceLocation(route.line, route.line),
                        attributes={
                            "method": route.method,
                            "path_pattern": route.path_pattern,
                            "handler_name": route.handler_name,
                        },
                        difficulty_score=0.35,
                    ),
                    replace=True,
                )
                g.add_edge(EdgeKind.CONTAINS.value, mid, rid)
                handler_id = ctx.symbol_table.get(route.handler_name)
                if handler_id:
                    g.add_edge(EdgeKind.ROUTES_TO.value, rid, handler_id)
                    # Also mark as API endpoint sibling
                    api_id = stable_node_id(
                        NodeKind.API_ENDPOINT.value,
                        rel,
                        f"{route.method}:{route.path_pattern}:api",
                        route.line,
                        route.line,
                    )
                    g.add_node(
                        SemanticNode(
                            id=api_id,
                            kind=NodeKind.API_ENDPOINT.value,
                            name=f"{route.method} {route.path_pattern}",
                            description="API endpoint",
                            purpose="Handles client requests for this route.",
                            why_exists="API graph node for network surface.",
                            created_by="ai",
                            prompt_id=self._prompt_for(ctx, rel),
                            source_file=rel,
                            source_location=SourceLocation(route.line, route.line),
                            attributes={
                                "method": route.method,
                                "path": route.path_pattern,
                            },
                        ),
                        replace=True,
                    )
                    g.add_edge(EdgeKind.CONTAINS.value, mid, api_id)
                    g.add_edge(EdgeKind.ROUTES_TO.value, api_id, handler_id)

            for st in forest.state:
                sid = stable_node_id(NodeKind.STATE_ATOM.value, rel, st.name, st.line, st.line)
                g.add_node(
                    SemanticNode(
                        id=sid,
                        kind=NodeKind.STATE_ATOM.value,
                        name=st.name,
                        description=f"State atom {st.name}",
                        purpose="Holds mutable application state.",
                        why_exists="State nodes power the state graph.",
                        created_by="ai",
                        source_file=rel,
                        source_location=SourceLocation(st.line, st.line),
                        attributes={"store_type": st.store_type},
                    ),
                    replace=True,
                )
                g.add_edge(EdgeKind.CONTAINS.value, mid, sid)

        # Imports → depends_on / imports edges between modules
        for rel, forest in ctx.forests.items():
            src_mod = module_ids.get(rel)
            if not src_mod:
                continue
            for imp in forest.imports:
                # Resolve relative module to a known file when possible
                target_mod = self._resolve_import_module(imp.module, module_ids, rel)
                if target_mod and target_mod != src_mod:
                    g.add_edge(EdgeKind.IMPORTS.value, src_mod, target_mod)
                    g.add_edge(EdgeKind.DEPENDS_ON.value, src_mod, target_mod)

        # Call graph
        for rel, forest in ctx.forests.items():
            for call in forest.calls:
                caller_id = ctx.symbol_table.get(call.caller_qualified) or ctx.symbol_table.get(
                    call.caller_qualified.split(".")[-1]
                )
                callee_qn = call.attributes.get("resolved_qualified") or call.callee_name
                callee_id = ctx.symbol_table.get(callee_qn) or ctx.symbol_table.get(call.callee_name)
                if caller_id and callee_id and caller_id != callee_id:
                    g.add_edge(
                        EdgeKind.CALLS.value,
                        caller_id,
                        callee_id,
                        attributes={"line": call.line, "file": rel},
                        edge_id=new_edge_id("calls", caller_id, callee_id, f"{rel}:{call.line}"),
                    )

        ctx.stage_metrics[self.name] = time.perf_counter() - t0

    def _prompt_for(self, ctx: PipelineContext, rel: str) -> Optional[str]:
        mapping = ctx.manifest.file_prompt_map or {}
        ids = mapping.get(rel) or mapping.get(rel.replace("/", "\\"))
        if ids:
            return ids[0]
        if ctx.manifest.prompts:
            return ctx.manifest.prompts[0].id
        return None

    def _difficulty(self, sym) -> float:
        score = 0.25
        if sym.is_async:
            score += 0.15
        if sym.kind in ("class", "component"):
            score += 0.1
        if len(sym.signature or "") > 80:
            score += 0.1
        if sym.docstring and len(sym.docstring) > 200:
            score += 0.05
        return min(1.0, score)

    def _resolve_import_module(self, module: str, module_ids: dict, source_rel: str) -> Optional[str]:
        if not module:
            return None
        # Direct path match
        candidates = [
            module.replace(".", "/") + ".py",
            module.replace(".", "/") + ".ts",
            module.replace(".", "/") + ".tsx",
            module.replace(".", "/") + ".js",
            module.replace(".", "/") + "/index.ts",
            module.replace(".", "/") + "/__init__.py",
        ]
        for c in candidates:
            if c in module_ids:
                return module_ids[c]
        # Basename match
        base = module.split(".")[-1].split("/")[-1]
        for path, mid in module_ids.items():
            if path.endswith(f"/{base}.py") or path.endswith(f"/{base}.ts") or path.endswith(f"/{base}.tsx"):
                return mid
            if path.endswith(f"{base}.py") or path.endswith(f"{base}.ts"):
                return mid
        return None
