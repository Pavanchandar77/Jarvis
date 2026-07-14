"""On-disk Twin Package format (JSON + JSONL)."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import SemanticEdge, SemanticNode, SemanticTwin, TwinIndexes


def twin_dir(base: Path, twin_id: str) -> Path:
    # Prevent path traversal
    safe = "".join(c for c in twin_id if c.isalnum() or c in "-_")
    if not safe or safe != twin_id:
        raise ValueError(f"invalid twin_id: {twin_id!r}")
    return base / safe


def write_twin_package(base: Path, twin: SemanticTwin) -> Path:
    """Atomically write a twin package under base/{twin_id}/."""
    base.mkdir(parents=True, exist_ok=True)
    final = twin_dir(base, twin.twin_id)
    tmp_parent = base / f".tmp-{twin.twin_id}"
    if tmp_parent.exists():
        shutil.rmtree(tmp_parent, ignore_errors=True)
    tmp_parent.mkdir(parents=True)

    try:
        (tmp_parent / "graph").mkdir()
        (tmp_parent / "indexes").mkdir()
        (tmp_parent / "manifest").mkdir()
        (tmp_parent / "deltas").mkdir(exist_ok=True)

        header = twin.to_dict(include_graph=False)
        # Keep lightweight node/edge counts already in meta
        _write_json(tmp_parent / "twin.json", header)

        _write_jsonl(tmp_parent / "graph" / "nodes.jsonl", [n.to_dict() for n in twin.nodes])
        _write_jsonl(tmp_parent / "graph" / "edges.jsonl", [e.to_dict() for e in twin.edges])

        idx = twin.indexes.to_dict()
        for key, value in idx.items():
            _write_json(tmp_parent / "indexes" / f"{key}.json", value)

        _write_json(tmp_parent / "manifest" / "generation.json", twin.manifest.to_dict())
        _write_jsonl(
            tmp_parent / "manifest" / "prompts.jsonl",
            [p.to_dict() for p in twin.manifest.prompts],
        )
        _write_jsonl(
            tmp_parent / "manifest" / "decisions.jsonl",
            [d.to_dict() for d in twin.manifest.decisions],
        )

        # Atomic replace
        if final.exists():
            # Preserve deltas directory if present
            old_deltas = final / "deltas"
            if old_deltas.is_dir():
                shutil.copytree(old_deltas, tmp_parent / "deltas", dirs_exist_ok=True)
            backup = base / f".old-{twin.twin_id}"
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
            final.replace(backup)
            tmp_parent.replace(final)
            shutil.rmtree(backup, ignore_errors=True)
        else:
            tmp_parent.replace(final)
        return final
    except Exception:
        shutil.rmtree(tmp_parent, ignore_errors=True)
        raise


def read_twin_package(base: Path, twin_id: str, include_graph: bool = True) -> SemanticTwin:
    root = twin_dir(base, twin_id)
    if not (root / "twin.json").is_file():
        raise FileNotFoundError(f"twin not found: {twin_id}")

    header = _read_json(root / "twin.json")
    if include_graph:
        nodes = [SemanticNode.from_dict(n) for n in _read_jsonl(root / "graph" / "nodes.jsonl")]
        edges = [SemanticEdge.from_dict(e) for e in _read_jsonl(root / "graph" / "edges.jsonl")]
    else:
        nodes, edges = [], []

    # Rebuild indexes from files if present
    indexes_data: Dict[str, Any] = {}
    idx_dir = root / "indexes"
    if idx_dir.is_dir():
        for p in idx_dir.glob("*.json"):
            indexes_data[p.stem] = _read_json(p)
    header["indexes"] = indexes_data
    header["nodes"] = [n.to_dict() for n in nodes] if include_graph else header.get("nodes", [])
    header["edges"] = [e.to_dict() for e in edges] if include_graph else header.get("edges", [])

    # Prefer manifest from dedicated file
    gen_path = root / "manifest" / "generation.json"
    if gen_path.is_file():
        header["manifest"] = _read_json(gen_path)

    twin = SemanticTwin.from_dict(header)
    if include_graph:
        twin.nodes = nodes
        twin.edges = edges
        if indexes_data:
            twin.indexes = TwinIndexes.from_dict(indexes_data)
    return twin


def write_delta(base: Path, twin_id: str, revision: int, patch: Dict[str, Any]) -> None:
    root = twin_dir(base, twin_id)
    delta_dir = root / "deltas"
    delta_dir.mkdir(parents=True, exist_ok=True)
    _write_json(delta_dir / f"{revision}.patch.json", patch)


def list_delta_revisions(base: Path, twin_id: str) -> List[int]:
    root = twin_dir(base, twin_id) / "deltas"
    if not root.is_dir():
        return []
    revs = []
    for p in root.glob("*.patch.json"):
        try:
            revs.append(int(p.name.split(".")[0]))
        except ValueError:
            continue
    return sorted(revs)


def delete_twin_package(base: Path, twin_id: str) -> None:
    root = twin_dir(base, twin_id)
    if root.exists():
        shutil.rmtree(root)


def list_twin_ids(base: Path) -> List[str]:
    if not base.is_dir():
        return []
    ids = []
    for p in base.iterdir():
        if p.is_dir() and not p.name.startswith(".") and (p / "twin.json").is_file():
            ids.append(p.name)
    return sorted(ids)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
                f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
