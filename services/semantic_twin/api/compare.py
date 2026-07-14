"""compareVersions — revision diff helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from ..models import SemanticTwin


def compare_twins(
    older: SemanticTwin,
    newer: SemanticTwin,
) -> Dict[str, Any]:
    old_nodes = {n.id: n for n in older.nodes}
    new_nodes = {n.id: n for n in newer.nodes}
    old_edges = {e.id for e in older.edges}
    new_edges = {e.id for e in newer.edges}

    added_nodes = sorted(set(new_nodes) - set(old_nodes))
    removed_nodes = sorted(set(old_nodes) - set(new_nodes))
    modified_nodes: List[str] = []
    for nid in set(old_nodes) & set(new_nodes):
        a, b = old_nodes[nid], new_nodes[nid]
        if (
            a.name != b.name
            or a.purpose != b.purpose
            or a.description != b.description
            or a.difficulty_score != b.difficulty_score
            or (a.attributes or {}) != (b.attributes or {})
        ):
            modified_nodes.append(nid)

    added_edges = sorted(new_edges - old_edges)
    removed_edges = sorted(old_edges - new_edges)

    summary = (
        f"r{older.content_revision} → r{newer.content_revision}: "
        f"+{len(added_nodes)} nodes, -{len(removed_nodes)} nodes, "
        f"~{len(modified_nodes)} modified; "
        f"+{len(added_edges)} edges, -{len(removed_edges)} edges."
    )

    return {
        "from_revision": older.content_revision,
        "to_revision": newer.content_revision,
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "modified_nodes": sorted(modified_nodes),
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "summary": summary,
    }


def compare_node_edge_sets(
    from_revision: int,
    to_revision: int,
    old_node_ids: Set[str],
    new_node_ids: Set[str],
    old_edge_ids: Set[str],
    new_edge_ids: Set[str],
    modified_nodes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    added_nodes = sorted(new_node_ids - old_node_ids)
    removed_nodes = sorted(old_node_ids - new_node_ids)
    added_edges = sorted(new_edge_ids - old_edge_ids)
    removed_edges = sorted(old_edge_ids - new_edge_ids)
    mod = list(modified_nodes or [])
    summary = (
        f"r{from_revision} → r{to_revision}: "
        f"+{len(added_nodes)}/-{len(removed_nodes)} nodes, "
        f"+{len(added_edges)}/-{len(removed_edges)} edges."
    )
    return {
        "from_revision": from_revision,
        "to_revision": to_revision,
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "modified_nodes": mod,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "summary": summary,
    }
