"""Project ↔ Semantic Twin registry — automatic registration after generation."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProjectRecord:
    project_id: str
    name: str
    app_root: str
    twin_id: Optional[str] = None
    owner: Optional[str] = None
    session_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_revision: int = 0
    status: str = "active"  # active | archived
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectRecord":
        return cls(
            project_id=data["project_id"],
            name=data.get("name") or data["project_id"],
            app_root=data["app_root"],
            twin_id=data.get("twin_id"),
            owner=data.get("owner"),
            session_id=data.get("session_id"),
            created_at=float(data.get("created_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
            last_revision=int(data.get("last_revision") or 0),
            status=data.get("status") or "active",
            metadata=dict(data.get("metadata") or {}),
        )


class ProjectRegistry:
    """JSON-backed registry of Spark projects and their Semantic Twins."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._projects: Dict[str, ProjectRecord] = {}
        self._by_root: Dict[str, str] = {}  # normalized root → project_id
        self._by_twin: Dict[str, str] = {}  # twin_id → project_id
        self._load()

    def _norm(self, root: str) -> str:
        return os.path.normcase(os.path.realpath(root))

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for row in data.get("projects") or []:
                rec = ProjectRecord.from_dict(row)
                self._projects[rec.project_id] = rec
                self._by_root[self._norm(rec.app_root)] = rec.project_id
                if rec.twin_id:
                    self._by_twin[rec.twin_id] = rec.project_id
        except Exception as exc:
            logger.warning("Failed to load project registry: %s", exc)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "projects": [p.to_dict() for p in self._projects.values()],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def register(
        self,
        *,
        project_id: str,
        name: str,
        app_root: str,
        twin_id: Optional[str] = None,
        owner: Optional[str] = None,
        session_id: Optional[str] = None,
        revision: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProjectRecord:
        with self._lock:
            existing = self._projects.get(project_id)
            if existing:
                existing.name = name or existing.name
                existing.app_root = app_root
                if twin_id:
                    existing.twin_id = twin_id
                if owner is not None:
                    existing.owner = owner
                if session_id:
                    existing.session_id = session_id
                if revision:
                    existing.last_revision = revision
                if metadata:
                    existing.metadata.update(metadata)
                existing.updated_at = time.time()
                rec = existing
            else:
                rec = ProjectRecord(
                    project_id=project_id,
                    name=name,
                    app_root=app_root,
                    twin_id=twin_id,
                    owner=owner,
                    session_id=session_id,
                    last_revision=revision,
                    metadata=dict(metadata or {}),
                )
                self._projects[project_id] = rec
            self._by_root[self._norm(app_root)] = project_id
            if rec.twin_id:
                self._by_twin[rec.twin_id] = project_id
            self._save()
            return rec

    def bind_twin(self, project_id: str, twin_id: str, revision: int = 0) -> Optional[ProjectRecord]:
        with self._lock:
            rec = self._projects.get(project_id)
            if not rec:
                return None
            rec.twin_id = twin_id
            if revision:
                rec.last_revision = revision
            rec.updated_at = time.time()
            self._by_twin[twin_id] = project_id
            self._save()
            return rec

    def get(self, project_id: str) -> Optional[ProjectRecord]:
        return self._projects.get(project_id)

    def by_root(self, app_root: str) -> Optional[ProjectRecord]:
        pid = self._by_root.get(self._norm(app_root))
        return self._projects.get(pid) if pid else None

    def by_twin(self, twin_id: str) -> Optional[ProjectRecord]:
        pid = self._by_twin.get(twin_id)
        return self._projects.get(pid) if pid else None

    def list(
        self,
        *,
        owner: Optional[str] = None,
        status: str = "active",
    ) -> List[ProjectRecord]:
        out = []
        for rec in self._projects.values():
            if status and rec.status != status:
                continue
            if owner is not None and rec.owner is not None and rec.owner != owner:
                continue
            out.append(rec)
        out.sort(key=lambda r: r.updated_at, reverse=True)
        return out

    def find_root_for_path(self, file_path: str) -> Optional[ProjectRecord]:
        """Return the registered project whose app_root contains file_path."""
        try:
            real = os.path.realpath(file_path)
        except OSError:
            return None
        best: Optional[ProjectRecord] = None
        best_len = -1
        for rec in self._projects.values():
            root = self._norm(rec.app_root)
            if real == root or real.startswith(root + os.sep):
                if len(root) > best_len:
                    best = rec
                    best_len = len(root)
        return best
