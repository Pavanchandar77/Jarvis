"""Debounced continuous synchronization of file changes → twin.update."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ContinuousSync:
    """
    Batches file-change notifications per twin and applies incremental updates.

    File Saved → dirty set → debounced → twin_service.update(...)
    """

    def __init__(
        self,
        twin_service,
        *,
        debounce_s: float = 1.5,
        on_updated: Optional[Callable] = None,
    ) -> None:
        self.twin_service = twin_service
        self.debounce_s = debounce_s
        self.on_updated = on_updated
        self._lock = threading.RLock()
        # twin_id → {app_root, owner, paths, timer}
        self._pending: Dict[str, Dict] = {}

    def notify(
        self,
        *,
        twin_id: str,
        app_root: str,
        rel_path: str,
        owner: Optional[str] = None,
    ) -> None:
        with self._lock:
            slot = self._pending.get(twin_id)
            if not slot:
                slot = {
                    "app_root": app_root,
                    "owner": owner,
                    "paths": set(),
                    "timer": None,
                }
                self._pending[twin_id] = slot
            slot["paths"].add(rel_path.replace("\\", "/"))
            slot["app_root"] = app_root
            if owner is not None:
                slot["owner"] = owner
            timer = slot.get("timer")
            if timer is not None:
                try:
                    timer.cancel()
                except Exception:
                    pass
            t = threading.Timer(self.debounce_s, self._flush, args=(twin_id,))
            t.daemon = True
            slot["timer"] = t
            t.start()

    def flush_now(self, twin_id: str) -> Optional[object]:
        return self._flush(twin_id)

    def _flush(self, twin_id: str):
        with self._lock:
            slot = self._pending.pop(twin_id, None)
        if not slot:
            return None
        paths: Set[str] = slot["paths"]
        app_root = slot["app_root"]
        owner = slot.get("owner")
        if not paths:
            return None
        try:
            twin = self.twin_service.update(
                twin_id,
                app_root,
                changed_files=sorted(paths),
                owner=owner,
                force_full=False,
                persist=True,
            )
            logger.info(
                "Continuous twin sync twin=%s files=%d rev=%s",
                twin_id,
                len(paths),
                twin.content_revision,
            )
            if self.on_updated:
                try:
                    self.on_updated(twin, sorted(paths))
                except Exception:
                    pass
            return twin
        except Exception as exc:
            logger.warning("Continuous twin sync failed for %s: %s", twin_id, exc)
            return None
