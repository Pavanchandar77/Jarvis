"""In-memory multi-index knowledge graph."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from ..ids import new_edge_id
from ..models import SemanticEdge, SemanticNode, TwinIndexes
from ..schema import EdgeKind, NodeKind, ACYCLIC_EDGE_KINDS
from .indexes import build_indexes


class GraphInvariantError(ValueError):
    """Raised when a graph mutation would violate schema invariants."""


class KnowledgeGraph:
    """Mutable graph used during pipeline construction."""

    def __init__(self) -> None:
        self._nodes: Dict[str, SemanticNode] = {}
        self._edges: Dict[str, SemanticEdge] = {}
        self._out: Dict[str, List[str]] = {}
        self._in: Dict[str, List[str]] = {}
        self.file_hashes: Dict[str, str] = {}

    # ── mutations ─────────────────────────────────────────────────────────

    def add_node(self, node: SemanticNode, replace: bool = False) -> SemanticNode:
        if node.id in self._nodes and not replace:
            return self._nodes[node.id]
        self._nodes[node.id] = node
        self._out.setdefault(node.id, [])
        self._in.setdefault(node.id, [])
        return node

    def get_node(self, node_id: str) -> Optional[SemanticNode]:
        return self._nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            return
        edge_ids = list(self._out.get(node_id, [])) + list(self._in.get(node_id, []))
        for eid in set(edge_ids):
            self.remove_edge(eid)
        self._nodes.pop(node_id, None)
        self._out.pop(node_id, None)
        self._in.pop(node_id, None)

    def remove_nodes_for_files(self, files: Iterable[str]) -> Set[str]:
        """Remove all code nodes whose source_file is in files. Returns removed ids."""
        targets = {f.replace("\\", "/") for f in files}
        removed: Set[str] = set()
        for nid, node in list(self._nodes.items()):
            if node.source_file and node.source_file.replace("\\", "/") in targets:
                removed.add(nid)
                self.remove_node(nid)
        return removed

    def add_edge(
        self,
        kind: str,
        source: str,
        target: str,
        weight: float = 1.0,
        attributes: Optional[dict] = None,
        edge_id: Optional[str] = None,
        allow_missing: bool = False,
    ) -> Optional[SemanticEdge]:
        if source not in self._nodes or target not in self._nodes:
            if allow_missing:
                return None
            raise GraphInvariantError(
                f"Edge endpoints missing: {source!r} → {target!r} ({kind})"
            )
        eid = edge_id or new_edge_id(kind, source, target)
        if eid in self._edges:
            return self._edges[eid]

        # Cycle check for acyclic kinds
        try:
            ek = EdgeKind(kind)
        except ValueError:
            ek = None
        if ek in ACYCLIC_EDGE_KINDS and self._would_cycle(source, target, kind):
            # Soft-skip rather than abort pipeline
            return None

        edge = SemanticEdge(
            id=eid,
            kind=kind,
            source=source,
            target=target,
            weight=weight,
            attributes=dict(attributes or {}),
        )
        self._edges[eid] = edge
        self._out.setdefault(source, []).append(eid)
        self._in.setdefault(target, []).append(eid)

        # Keep denormalized dependency lists fresh for structural deps
        if kind in (EdgeKind.DEPENDS_ON.value, EdgeKind.IMPORTS.value, EdgeKind.CALLS.value):
            src = self._nodes[source]
            tgt = self._nodes[target]
            if target not in src.dependencies:
                src.dependencies.append(target)
            if source not in tgt.dependents:
                tgt.dependents.append(source)
        return edge

    def remove_edge(self, edge_id: str) -> None:
        edge = self._edges.pop(edge_id, None)
        if not edge:
            return
        if edge_id in self._out.get(edge.source, []):
            self._out[edge.source].remove(edge_id)
        if edge_id in self._in.get(edge.target, []):
            self._in[edge.target].remove(edge_id)

    def _would_cycle(self, source: str, target: str, kind: str) -> bool:
        """True if adding source→target of this kind creates a cycle among same-kind edges."""
        if source == target:
            return True
        # BFS from target following same-kind outs; if we reach source, cycle
        seen: Set[str] = set()
        stack = [target]
        while stack:
            cur = stack.pop()
            if cur == source:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            for eid in self._out.get(cur, []):
                e = self._edges.get(eid)
                if e and e.kind == kind:
                    stack.append(e.target)
        return False

    # ── queries ───────────────────────────────────────────────────────────

    def nodes(self) -> List[SemanticNode]:
        return list(self._nodes.values())

    def edges(self) -> List[SemanticEdge]:
        return list(self._edges.values())

    def nodes_by_kind(self, kind: str) -> List[SemanticNode]:
        return [n for n in self._nodes.values() if n.kind == kind]

    def nodes_for_file(self, path: str) -> List[SemanticNode]:
        path = path.replace("\\", "/")
        return [
            n for n in self._nodes.values()
            if n.source_file and n.source_file.replace("\\", "/") == path
        ]

    def outgoing_edges(self, node_id: str, kinds: Optional[Set[str]] = None) -> List[SemanticEdge]:
        result = []
        for eid in self._out.get(node_id, []):
            e = self._edges.get(eid)
            if e and (kinds is None or e.kind in kinds):
                result.append(e)
        return result

    def incoming_edges(self, node_id: str, kinds: Optional[Set[str]] = None) -> List[SemanticEdge]:
        result = []
        for eid in self._in.get(node_id, []):
            e = self._edges.get(eid)
            if e and (kinds is None or e.kind in kinds):
                result.append(e)
        return result

    def find_by_name(self, name: str) -> List[SemanticNode]:
        key = name.lower()
        return [n for n in self._nodes.values() if n.name.lower() == key]

    def find_by_qualified(self, qualified: str) -> Optional[SemanticNode]:
        for n in self._nodes.values():
            if (n.attributes or {}).get("qualified_name") == qualified:
                return n
        return None

    def validate(self) -> List[str]:
        """Return list of invariant violations (empty if healthy)."""
        issues: List[str] = []
        for e in self._edges.values():
            if e.source not in self._nodes:
                issues.append(f"edge {e.id}: missing source {e.source}")
            if e.target not in self._nodes:
                issues.append(f"edge {e.id}: missing target {e.target}")
        return issues

    def build_indexes(self) -> TwinIndexes:
        return build_indexes(self.nodes(), self.edges(), self.file_hashes)

    def snapshot(self) -> Tuple[List[SemanticNode], List[SemanticEdge], TwinIndexes]:
        nodes = self.nodes()
        edges = self.edges()
        return nodes, edges, build_indexes(nodes, edges, self.file_hashes)
