"""Graph traversal primitives — cycle-safe BFS/DFS."""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from ..schema import DEPENDENCY_EDGE_KINDS, EXECUTION_EDGE_KINDS, EdgeKind

if TYPE_CHECKING:
    from .knowledge_graph import KnowledgeGraph
    from ..models import SemanticTwin, SemanticEdge, SemanticNode


class GraphQuery:
    """Traversal helpers over KnowledgeGraph or SemanticTwin."""

    def __init__(
        self,
        nodes: Dict[str, "SemanticNode"],
        edges: Dict[str, "SemanticEdge"],
        adjacency_out: Dict[str, List[str]],
        adjacency_in: Dict[str, List[str]],
    ) -> None:
        self.nodes = nodes
        self.edges = edges
        self.adjacency_out = adjacency_out
        self.adjacency_in = adjacency_in

    @classmethod
    def from_graph(cls, graph: "KnowledgeGraph") -> "GraphQuery":
        nodes = {n.id: n for n in graph.nodes()}
        edges = {e.id: e for e in graph.edges()}
        adj_out: Dict[str, List[str]] = {}
        adj_in: Dict[str, List[str]] = {}
        for e in edges.values():
            adj_out.setdefault(e.source, []).append(e.id)
            adj_in.setdefault(e.target, []).append(e.id)
        return cls(nodes, edges, adj_out, adj_in)

    @classmethod
    def from_twin(cls, twin: "SemanticTwin") -> "GraphQuery":
        nodes = twin.node_map()
        edges = twin.edge_map()
        return cls(
            nodes,
            edges,
            twin.indexes.adjacency_out,
            twin.indexes.adjacency_in,
        )

    def bfs(
        self,
        start: str,
        *,
        direction: str = "out",
        kinds: Optional[Set[str]] = None,
        max_depth: int = 20,
    ) -> Tuple[List[str], List[str]]:
        """
        BFS from start.
        direction: 'out' | 'in' | 'both'
        Returns (node_ids in visit order, edge_ids traversed).
        """
        if start not in self.nodes:
            return [], []
        visited: Set[str] = {start}
        order: List[str] = [start]
        edge_ids: List[str] = []
        q: deque[Tuple[str, int]] = deque([(start, 0)])

        while q:
            cur, depth = q.popleft()
            if depth >= max_depth:
                continue
            candidates: List[str] = []
            if direction in ("out", "both"):
                candidates.extend(self.adjacency_out.get(cur, []))
            if direction in ("in", "both"):
                candidates.extend(self.adjacency_in.get(cur, []))
            for eid in candidates:
                e = self.edges.get(eid)
                if not e:
                    continue
                if kinds is not None and e.kind not in kinds:
                    continue
                nxt = e.target if e.source == cur else e.source
                # For pure out-walk, always follow target; for in, source
                if direction == "out":
                    nxt = e.target
                elif direction == "in":
                    nxt = e.source
                if nxt in visited:
                    continue
                visited.add(nxt)
                order.append(nxt)
                edge_ids.append(eid)
                q.append((nxt, depth + 1))
        return order, edge_ids

    def trace_execution(
        self, entry_id: str, max_depth: int = 30
    ) -> Tuple[List[Tuple[str, int]], List[str]]:
        """
        Follow execution edges preferring nodes with lower execution_order.
        Returns ([(node_id, order)], edge_ids).
        """
        kinds = {k.value for k in EXECUTION_EDGE_KINDS}
        if entry_id not in self.nodes:
            return [], []

        steps: List[Tuple[str, int]] = []
        edge_ids: List[str] = []
        visited: Set[str] = set()
        stack: List[Tuple[str, int]] = [(entry_id, 0)]

        while stack:
            cur, depth = stack.pop()
            if cur in visited or depth > max_depth:
                continue
            visited.add(cur)
            steps.append((cur, depth))
            outs = []
            for eid in self.adjacency_out.get(cur, []):
                e = self.edges.get(eid)
                if e and e.kind in kinds and e.target not in visited:
                    tgt = self.nodes.get(e.target)
                    ord_key = (
                        tgt.execution_order
                        if tgt and tgt.execution_order is not None
                        else 10_000
                    )
                    outs.append((ord_key, eid, e.target))
            outs.sort(key=lambda x: x[0], reverse=True)  # pop lowest order last → process first
            for _, eid, tgt in outs:
                edge_ids.append(eid)
                stack.append((tgt, depth + 1))
        return steps, edge_ids

    def trace_dependency(
        self,
        root_id: str,
        direction: str = "downstream",
        max_depth: int = 10,
    ) -> Tuple[List[str], List[str]]:
        kinds = {k.value for k in DEPENDENCY_EDGE_KINDS}
        if direction == "upstream":
            return self.bfs(root_id, direction="in", kinds=kinds, max_depth=max_depth)
        if direction == "downstream":
            return self.bfs(root_id, direction="out", kinds=kinds, max_depth=max_depth)
        # both
        out_n, out_e = self.bfs(root_id, direction="out", kinds=kinds, max_depth=max_depth)
        in_n, in_e = self.bfs(root_id, direction="in", kinds=kinds, max_depth=max_depth)
        seen = set()
        nodes: List[str] = []
        for n in out_n + in_n:
            if n not in seen:
                seen.add(n)
                nodes.append(n)
        edges = list(dict.fromkeys(out_e + in_e))
        return nodes, edges
