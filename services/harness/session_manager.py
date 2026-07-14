"""Harness session registry — Spark-owned mapping of sessions across engines."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from .base import HarnessSession


class HarnessSessionManager:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._sessions: Dict[str, HarnessSession] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for row in data.get("sessions") or []:
                s = HarnessSession(
                    session_id=row["session_id"],
                    handle_id=row["handle_id"],
                    workspace_id=row["workspace_id"],
                    harness_id=row["harness_id"],
                    external_id=row.get("external_id"),
                    model=row.get("model"),
                    status=row.get("status") or "active",
                    metadata=dict(row.get("metadata") or {}),
                )
                self._sessions[s.session_id] = s
        except Exception:
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sessions": [s.to_dict() for s in self._sessions.values()]}
        text = json.dumps(payload, indent=2)
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

    def create(
        self,
        *,
        handle_id: str,
        workspace_id: str,
        harness_id: str,
        external_id: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> HarnessSession:
        sid = uuid.uuid4().hex
        session = HarnessSession(
            session_id=sid,
            handle_id=handle_id,
            workspace_id=workspace_id,
            harness_id=harness_id,
            external_id=external_id,
            model=model,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._sessions[sid] = session
            self._save()
        return session

    def get(self, session_id: str) -> Optional[HarnessSession]:
        return self._sessions.get(session_id)

    def update(self, session: HarnessSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session
            self._save()

    def list(
        self,
        *,
        workspace_id: Optional[str] = None,
        harness_id: Optional[str] = None,
    ) -> List[HarnessSession]:
        out = []
        for s in self._sessions.values():
            if workspace_id and s.workspace_id != workspace_id:
                continue
            if harness_id and s.harness_id != harness_id:
                continue
            out.append(s)
        return out

    def cancel(self, session_id: str) -> Optional[HarnessSession]:
        s = self._sessions.get(session_id)
        if not s:
            return None
        s.status = "cancelled"
        self.update(s)
        return s
