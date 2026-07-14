"""Version timeline — architectural evolution across twin revisions."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..api.compare import compare_twins
from ..models import SemanticTwin

logger = logging.getLogger(__name__)


class VersionTimeline:
    """
    Stores lightweight version snapshots + diffs for a twin.

    Layout:
      {base}/{twin_id}/timeline/
        index.json
        v{revision}.json   # meta + graph summary (not full nodes for scale)
        diff_{from}_{to}.json
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir)

    def _dir(self, twin_id: str) -> Path:
        safe = "".join(c for c in twin_id if c.isalnum() or c in "-_")
        if safe != twin_id:
            raise ValueError("invalid twin_id")
        d = self.base / safe / "timeline"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def record(
        self,
        twin: SemanticTwin,
        *,
        prior: Optional[SemanticTwin] = None,
        label: str = "",
        trigger: str = "generate",
    ) -> Dict[str, Any]:
        tdir = self._dir(twin.twin_id)
        entry = {
            "revision": twin.content_revision,
            "content_hash": twin.content_hash,
            "label": label or f"r{twin.content_revision}",
            "trigger": trigger,
            "ts": time.time(),
            "node_count": twin.meta.node_count,
            "edge_count": twin.meta.edge_count,
            "languages": list(twin.meta.languages or []),
            "tech_stack": list(twin.meta.tech_stack or []),
            "kinds": _kind_histogram(twin),
            "concepts": [
                n.name for n in twin.nodes if n.kind == "concept"
            ][:50],
        }
        self._write_json(tdir / f"v{twin.content_revision}.json", entry)

        diff = None
        if prior is not None:
            diff = compare_twins(prior, twin)
            # Concept / dependency extras
            old_concepts = {n.name for n in prior.nodes if n.kind == "concept"}
            new_concepts = {n.name for n in twin.nodes if n.kind == "concept"}
            diff["concept_diff"] = {
                "added": sorted(new_concepts - old_concepts),
                "removed": sorted(old_concepts - new_concepts),
            }
            old_deps = {
                (e.source, e.target, e.kind)
                for e in prior.edges
                if e.kind in ("depends_on", "imports", "calls")
            }
            new_deps = {
                (e.source, e.target, e.kind)
                for e in twin.edges
                if e.kind in ("depends_on", "imports", "calls")
            }
            diff["dependency_diff"] = {
                "added": len(new_deps - old_deps),
                "removed": len(old_deps - new_deps),
            }
            self._write_json(
                tdir / f"diff_{prior.content_revision}_{twin.content_revision}.json",
                diff,
            )

        index = self._read_json(tdir / "index.json") or {"versions": []}
        versions = [v for v in index.get("versions") or [] if v.get("revision") != twin.content_revision]
        versions.append({
            "revision": twin.content_revision,
            "content_hash": twin.content_hash,
            "label": entry["label"],
            "trigger": trigger,
            "ts": entry["ts"],
            "node_count": entry["node_count"],
            "edge_count": entry["edge_count"],
        })
        versions.sort(key=lambda v: v["revision"])
        index["versions"] = versions
        index["latest"] = twin.content_revision
        self._write_json(tdir / "index.json", index)
        return entry

    def list_versions(self, twin_id: str) -> List[Dict[str, Any]]:
        try:
            tdir = self._dir(twin_id)
        except ValueError:
            return []
        index = self._read_json(tdir / "index.json") or {}
        return list(index.get("versions") or [])

    def get_version(self, twin_id: str, revision: int) -> Optional[Dict[str, Any]]:
        try:
            tdir = self._dir(twin_id)
        except ValueError:
            return None
        return self._read_json(tdir / f"v{revision}.json")

    def get_diff(self, twin_id: str, from_rev: int, to_rev: int) -> Optional[Dict[str, Any]]:
        try:
            tdir = self._dir(twin_id)
        except ValueError:
            return None
        return self._read_json(tdir / f"diff_{from_rev}_{to_rev}.json")

    def _write_json(self, path: Path, data: Any) -> None:
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

    def _read_json(self, path: Path) -> Optional[Any]:
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


def _kind_histogram(twin: SemanticTwin) -> Dict[str, int]:
    h: Dict[str, int] = {}
    for n in twin.nodes:
        h[n.kind] = h.get(n.kind, 0) + 1
    return h
