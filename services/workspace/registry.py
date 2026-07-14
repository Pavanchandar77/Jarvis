"""Persistent workspace registry (index of manifests)."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional

from .manifest import WorkspaceManifest


class WorkspaceRegistry:
    def __init__(self, index_path: str | Path, manifests_dir: str | Path) -> None:
        self.index_path = Path(index_path)
        self.manifests_dir = Path(manifests_dir)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._by_id: Dict[str, WorkspaceManifest] = {}
        self._by_root: Dict[str, str] = {}
        self._load()

    def _norm(self, root: str) -> str:
        return os.path.normcase(os.path.realpath(root))

    def _manifest_path(self, workspace_id: str) -> Path:
        safe = "".join(c for c in workspace_id if c.isalnum() or c in "-_")
        return self.manifests_dir / f"{safe}.json"

    def _load(self) -> None:
        for p in self.manifests_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                m = WorkspaceManifest.from_dict(data)
                self._by_id[m.workspace_id] = m
                self._by_root[self._norm(m.repo_root)] = m.workspace_id
            except Exception:
                continue

    def save(self, manifest: WorkspaceManifest) -> None:
        with self._lock:
            manifest.touch()
            self._by_id[manifest.workspace_id] = manifest
            self._by_root[self._norm(manifest.repo_root)] = manifest.workspace_id
            path = self._manifest_path(manifest.workspace_id)
            text = json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False)
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
            self._write_index()

    def _write_index(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "workspaces": [
                {
                    "workspace_id": m.workspace_id,
                    "name": m.name,
                    "repo_root": m.repo_root,
                    "twin_id": m.twin_id,
                    "active_harness": m.active_harness,
                    "status": m.status,
                    "updated_at": m.updated_at,
                }
                for m in self._by_id.values()
            ]
        }
        text = json.dumps(payload, indent=2)
        fd, tmp = tempfile.mkstemp(dir=str(self.index_path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, self.index_path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def get(self, workspace_id: str) -> Optional[WorkspaceManifest]:
        return self._by_id.get(workspace_id)

    def by_root(self, repo_root: str) -> Optional[WorkspaceManifest]:
        wid = self._by_root.get(self._norm(repo_root))
        return self._by_id.get(wid) if wid else None

    def list(self, *, owner: Optional[str] = None, status: str = "active") -> List[WorkspaceManifest]:
        out = []
        for m in self._by_id.values():
            if status and m.status != status:
                continue
            if owner is not None and m.owner is not None and m.owner != owner:
                continue
            out.append(m)
        out.sort(key=lambda x: x.updated_at, reverse=True)
        return out
