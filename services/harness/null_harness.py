"""NullHarness — in-process stub for tests and when no coding engine is installed."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from .base import EngineHandle, HarnessEvent, HarnessSession, HarnessStatus


class NullHarness:
    """Implements CodingHarness without external processes."""

    harness_id = "null"
    display_name = "Null Harness (stub)"

    def __init__(self) -> None:
        self._queues: Dict[str, asyncio.Queue] = {}
        self._running: Dict[str, bool] = {}

    async def start(
        self,
        workspace_id: str,
        repo_root: str,
        *,
        owner: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> EngineHandle:
        hid = uuid.uuid4().hex
        self._running[hid] = True
        return EngineHandle(
            handle_id=hid,
            harness_id=self.harness_id,
            workspace_id=workspace_id,
            endpoint=None,
            metadata={"repo_root": repo_root, "owner": owner, "mode": "null"},
        )

    async def stop(self, handle: EngineHandle) -> None:
        self._running[handle.handle_id] = False

    async def create_session(
        self,
        handle: EngineHandle,
        *,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HarnessSession:
        sid = uuid.uuid4().hex
        self._queues[sid] = asyncio.Queue()
        return HarnessSession(
            session_id=sid,
            handle_id=handle.handle_id,
            workspace_id=handle.workspace_id,
            harness_id=self.harness_id,
            external_id=sid,
            model=model or "null-model",
            metadata=dict(metadata or {}),
        )

    async def send(
        self,
        session: HarnessSession,
        message: str,
        *,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        q = self._queues.setdefault(session.session_id, asyncio.Queue())
        await q.put(
            HarnessEvent(
                type="message.delta",
                session_id=session.session_id,
                payload={"text": f"[null harness echo] {message}"},
                ts=time.time(),
            )
        )
        await q.put(
            HarnessEvent(
                type="done",
                session_id=session.session_id,
                payload={},
                ts=time.time(),
            )
        )

    async def stream(self, session: HarnessSession) -> AsyncIterator[HarnessEvent]:
        q = self._queues.setdefault(session.session_id, asyncio.Queue())
        while True:
            ev = await q.get()
            yield ev
            if ev.type in ("done", "error"):
                break

    async def cancel(self, session: HarnessSession) -> None:
        q = self._queues.setdefault(session.session_id, asyncio.Queue())
        await q.put(
            HarnessEvent(
                type="done",
                session_id=session.session_id,
                payload={"cancelled": True},
                ts=time.time(),
            )
        )

    async def status(self, handle: EngineHandle) -> HarnessStatus:
        running = self._running.get(handle.handle_id, False)
        return HarnessStatus(
            handle_id=handle.handle_id,
            harness_id=self.harness_id,
            state="running" if running else "stopped",
            detail="null harness",
        )
