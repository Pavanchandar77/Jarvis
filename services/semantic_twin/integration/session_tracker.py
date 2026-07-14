"""Per-session / per-workspace generation tracking."""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .manifest_builder import ManifestBuilder


def _norm(path: str) -> str:
    try:
        return os.path.normcase(os.path.realpath(path))
    except OSError:
        return os.path.normcase(os.path.abspath(path))


@dataclass
class GenerationSession:
    session_key: str  # session_id or synthetic
    session_id: Optional[str]
    owner: Optional[str]
    workspace: Optional[str]
    model: Optional[str]
    backend: str = ""
    builder: ManifestBuilder = field(default=None)  # type: ignore[assignment]
    written_paths: Set[str] = field(default_factory=set)
    dirty_rel_paths: Set[str] = field(default_factory=set)
    app_root: Optional[str] = None
    project_id: Optional[str] = None
    twin_id: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    finalized: bool = False

    def note_write(self, abs_path: str) -> None:
        real = _norm(abs_path)
        self.written_paths.add(real)
        root = self.app_root or self.workspace
        if root:
            root_n = _norm(root)
            if real.startswith(root_n + os.sep) or real == root_n:
                rel = os.path.relpath(real, root_n).replace("\\", "/")
                self.dirty_rel_paths.add(rel)
                self.builder.record_tool(
                    tool="write_file",
                    path=rel,
                    exit_code=0,
                )
                return
        # No workspace: use absolute path as key; root inferred later
        self.builder.record_tool(tool="write_file", path=real, exit_code=0)
        self.dirty_rel_paths.add(real)

    def infer_app_root(self) -> Optional[str]:
        if self.workspace and os.path.isdir(self.workspace):
            self.app_root = _norm(self.workspace)
            return self.app_root
        if self.app_root and os.path.isdir(self.app_root):
            return self.app_root
        if not self.written_paths:
            return None
        # Common parent of written files
        paths = list(self.written_paths)
        try:
            common = os.path.commonpath(paths)
        except ValueError:
            return None
        # Prefer a directory that looks like a project (has multiple files or known markers)
        if os.path.isfile(common):
            common = os.path.dirname(common)
        # Walk up if common is too shallow (e.g. drive root) and only one file
        if len(paths) == 1:
            common = os.path.dirname(paths[0])
        # Avoid registering system roots
        if common in ("/", "\\") or re_is_drive_root(common):
            common = os.path.dirname(paths[0]) if paths else common
        self.app_root = _norm(common)
        return self.app_root


def re_is_drive_root(path: str) -> bool:
    n = path.rstrip("\\/")
    # Windows drive root C: or C:\
    if len(n) == 2 and n[1] == ":":
        return True
    if len(n) == 3 and n[1] == ":" and n[2] in "\\/":
        return True
    return False


class SessionTracker:
    """In-memory tracker of active generation sessions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, GenerationSession] = {}

    def _key(self, session_id: Optional[str], owner: Optional[str], workspace: Optional[str]) -> str:
        if session_id:
            return f"sess:{session_id}"
        if workspace:
            return f"ws:{_norm(workspace)}"
        return f"anon:{owner or 'none'}:{uuid.uuid4().hex[:8]}"

    def start(
        self,
        *,
        session_id: Optional[str],
        owner: Optional[str],
        workspace: Optional[str],
        model: Optional[str] = None,
        backend: str = "",
        user_prompt: str = "",
        planning_prompt: str = "",
        approved_plan: str = "",
    ) -> GenerationSession:
        key = self._key(session_id, owner, workspace)
        with self._lock:
            existing = self._sessions.get(key)
            if existing and not existing.finalized:
                # Refresh prompt context if new turn
                if user_prompt and not existing.builder.user_prompt:
                    existing.builder.user_prompt = user_prompt
                return existing
            builder = ManifestBuilder(
                session_id=session_id,
                owner=owner,
                model=model,
                backend=backend,
                user_prompt=user_prompt,
                planning_prompt=planning_prompt,
                approved_plan=approved_plan,
            )
            gs = GenerationSession(
                session_key=key,
                session_id=session_id,
                owner=owner,
                workspace=workspace,
                model=model,
                backend=backend,
                builder=builder,
                app_root=_norm(workspace) if workspace else None,
            )
            self._sessions[key] = gs
            return gs

    def get(
        self,
        session_id: Optional[str] = None,
        owner: Optional[str] = None,
        workspace: Optional[str] = None,
        session_key: Optional[str] = None,
    ) -> Optional[GenerationSession]:
        with self._lock:
            if session_key:
                return self._sessions.get(session_key)
            key = self._key(session_id, owner, workspace)
            return self._sessions.get(key)

    def get_for_path(self, abs_path: str) -> Optional[GenerationSession]:
        real = _norm(abs_path)
        with self._lock:
            for gs in self._sessions.values():
                if gs.finalized:
                    continue
                root = gs.app_root or gs.workspace
                if root and (real == _norm(root) or real.startswith(_norm(root) + os.sep)):
                    return gs
                if real in gs.written_paths:
                    return gs
        return None

    def pop(self, session_key: str) -> Optional[GenerationSession]:
        with self._lock:
            return self._sessions.pop(session_key, None)

    def project_id_for_root(self, app_root: str) -> str:
        h = hashlib.sha256(_norm(app_root).encode("utf-8")).hexdigest()[:16]
        name = os.path.basename(app_root.rstrip("\\/")) or "project"
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)[:40]
        return f"{safe}-{h}"
