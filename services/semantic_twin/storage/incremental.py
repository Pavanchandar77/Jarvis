"""Incremental update strategy — dirty-set computation and delta patches."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..ids import file_content_hash
from ..models import SemanticTwin
from ..schema import EdgeKind


def compute_file_hashes(app_root: Path, rel_paths: Optional[List[str]] = None) -> Dict[str, str]:
    root = app_root.resolve()
    hashes: Dict[str, str] = {}
    if rel_paths is not None:
        paths = rel_paths
    else:
        paths = []
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    rel = p.relative_to(root).as_posix()
                except ValueError:
                    continue
                paths.append(rel)
    for rel in paths:
        abs_path = root / rel
        if not abs_path.is_file():
            continue
        try:
            hashes[rel.replace("\\", "/")] = file_content_hash(abs_path.read_bytes())
        except OSError:
            continue
    return hashes


def dirty_set(
    twin: SemanticTwin,
    current_hashes: Dict[str, str],
    explicit_changed: Optional[List[str]] = None,
) -> Tuple[Set[str], Set[str]]:
    """
    Return (changed_or_added_files, deleted_files).
    """
    old = dict(twin.indexes.file_hashes or {})
    current = {k.replace("\\", "/"): v for k, v in current_hashes.items()}
    old = {k.replace("\\", "/"): v for k, v in old.items()}

    changed: Set[str] = set()
    deleted: Set[str] = set()

    if explicit_changed:
        for f in explicit_changed:
            changed.add(f.replace("\\", "/"))

    for path, h in current.items():
        if old.get(path) != h:
            changed.add(path)
    for path in old:
        if path not in current:
            deleted.add(path)

    # Expand via import reverse edges (module-level dependents)
    expanded = set(changed)
    node_map = twin.node_map()
    file_of = {}
    for n in twin.nodes:
        if n.source_file:
            file_of[n.id] = n.source_file.replace("\\", "/")

    # Map file → module node ids
    by_file = twin.indexes.by_file or {}
    reverse_imports: Dict[str, Set[str]] = {}
    for e in twin.edges:
        if e.kind not in (EdgeKind.IMPORTS.value, EdgeKind.DEPENDS_ON.value):
            continue
        src_file = file_of.get(e.source)
        tgt_file = file_of.get(e.target)
        if src_file and tgt_file:
            reverse_imports.setdefault(tgt_file, set()).add(src_file)

    frontier = list(changed)
    depth = 0
    max_depth = 2
    while frontier and depth < max_depth:
        nxt = []
        for f in frontier:
            for dep in reverse_imports.get(f, ()):
                if dep not in expanded:
                    expanded.add(dep)
                    nxt.append(dep)
        frontier = nxt
        depth += 1

    return expanded, deleted


def build_delta_patch(
    older: SemanticTwin,
    newer: SemanticTwin,
) -> Dict:
    old_n = {n.id for n in older.nodes}
    new_n = {n.id for n in newer.nodes}
    old_e = {e.id for e in older.edges}
    new_e = {e.id for e in newer.edges}
    return {
        "from_revision": older.content_revision,
        "to_revision": newer.content_revision,
        "content_hash_before": older.content_hash,
        "content_hash_after": newer.content_hash,
        "added_nodes": sorted(new_n - old_n),
        "removed_nodes": sorted(old_n - new_n),
        "added_edges": sorted(new_e - old_e),
        "removed_edges": sorted(old_e - new_e),
        "file_hashes": dict(newer.indexes.file_hashes or {}),
    }
