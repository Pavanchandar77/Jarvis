"""Index builders for Semantic Twin graphs."""

from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import SemanticNode, SemanticEdge, TwinIndexes


def build_indexes(
    nodes: List["SemanticNode"],
    edges: List["SemanticEdge"],
    file_hashes: Dict[str, str] | None = None,
) -> "TwinIndexes":
    from ..models import TwinIndexes
    from ..schema import NodeKind

    by_file: Dict[str, List[str]] = {}
    by_kind: Dict[str, List[str]] = {}
    by_name: Dict[str, List[str]] = {}
    adjacency_out: Dict[str, List[str]] = {}
    adjacency_in: Dict[str, List[str]] = {}
    concepts: Dict[str, str] = {}

    for n in nodes:
        kind = n.kind if isinstance(n.kind, str) else n.kind.value
        by_kind.setdefault(kind, []).append(n.id)
        name_key = n.name.lower()
        by_name.setdefault(name_key, []).append(n.id)
        if n.source_file:
            path = n.source_file.replace("\\", "/")
            by_file.setdefault(path, []).append(n.id)
        if kind == NodeKind.CONCEPT.value:
            slug = (n.attributes or {}).get("slug") or n.name.lower()
            concepts[str(slug)] = n.id
        adjacency_out.setdefault(n.id, [])
        adjacency_in.setdefault(n.id, [])

    for e in edges:
        adjacency_out.setdefault(e.source, []).append(e.id)
        adjacency_in.setdefault(e.target, []).append(e.id)

    return TwinIndexes(
        by_file=by_file,
        by_kind=by_kind,
        by_name=by_name,
        adjacency_out=adjacency_out,
        adjacency_in=adjacency_in,
        concepts=concepts,
        file_hashes=dict(file_hashes or {}),
    )
