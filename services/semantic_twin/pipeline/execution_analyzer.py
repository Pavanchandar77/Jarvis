"""Execution Analyzer — approximate control-flow and execution order."""

from __future__ import annotations

import time
from collections import deque

from ..schema import EdgeKind, NodeKind
from .context import PipelineContext


class ExecutionAnalyzerStage:
    name = "execution_analyzer"

    def run(self, ctx: PipelineContext) -> None:
        t0 = time.perf_counter()
        g = ctx.graph

        # Seed entrypoints: routes, application main-like functions, first components
        entry_ids = []
        for n in g.nodes_by_kind(NodeKind.ROUTE.value):
            entry_ids.append(n.id)
        for n in g.nodes_by_kind(NodeKind.API_ENDPOINT.value):
            entry_ids.append(n.id)
        for n in g.nodes():
            if n.kind in (NodeKind.FUNCTION.value, NodeKind.METHOD.value) and n.name in (
                "main", "handler", "app", "run", "bootstrap", "createApp",
            ):
                entry_ids.append(n.id)

        if not entry_ids:
            # Fall back to module-level functions with no callers
            callees = set()
            for e in g.edges():
                if e.kind == EdgeKind.CALLS.value:
                    callees.add(e.target)
            for n in g.nodes():
                if n.kind in (NodeKind.FUNCTION.value, NodeKind.COMPONENT.value) and n.id not in callees:
                    entry_ids.append(n.id)
                    if len(entry_ids) >= 5:
                        break

        ctx.extras["entrypoints"] = list(dict.fromkeys(entry_ids))
        app_id = ctx.extras.get("app_node_id")
        if app_id and g.has_node(app_id):
            g.get_node(app_id).attributes["entrypoints"] = list(ctx.extras["entrypoints"])

        # BFS assign execution_order
        order = 0
        visited = set()
        q = deque()
        for eid in entry_ids:
            if eid not in visited:
                q.append(eid)
                visited.add(eid)

        while q:
            nid = q.popleft()
            node = g.get_node(nid)
            if node:
                node.execution_order = order
                order += 1
            for e in g.outgoing_edges(
                nid,
                kinds={
                    EdgeKind.CALLS.value,
                    EdgeKind.RENDERS.value,
                    EdgeKind.ROUTES_TO.value,
                    EdgeKind.DATA_FLOWS_TO.value,
                },
            ):
                if e.target not in visited:
                    visited.add(e.target)
                    q.append(e.target)

        # Detect simple data-flow via shared state reads/writes (heuristic name match)
        state_nodes = {n.name: n.id for n in g.nodes_by_kind(NodeKind.STATE_ATOM.value)}
        for n in g.nodes():
            if n.kind not in (
                NodeKind.FUNCTION.value,
                NodeKind.METHOD.value,
                NodeKind.COMPONENT.value,
                NodeKind.HOOK.value,
            ):
                continue
            text = (n.attributes or {}).get("signature", "") + " " + n.name
            for sname, sid in state_nodes.items():
                if sname in text or sname in (n.description or ""):
                    g.add_edge(EdgeKind.READS_STATE.value, n.id, sid)

        ctx.stage_metrics[self.name] = time.perf_counter() - t0
