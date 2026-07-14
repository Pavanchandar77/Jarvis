"""OS-wide event log (append-only per project)."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class OSEventLog:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir) / "events"
        self.base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, project_id: str) -> Path:
        safe = "".join(c for c in project_id if c.isalnum() or c in "-_") or "default"
        return self.base / f"{safe}.jsonl"

    def emit(self, project_id: str, event_type: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        row = {
            "type": event_type,
            "ts": time.time(),
            "payload": payload or {},
        }
        with self._lock:
            path = self._path(project_id)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def list(self, project_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        path = self._path(project_id)
        if not path.is_file():
            return []
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows[-limit:]
