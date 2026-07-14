"""Harness Manager — start/stop engines and sessions without knowing engine type."""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from .base import (
    CodingHarness,
    EngineHandle,
    HarnessEvent,
    HarnessSession,
    HarnessStatus,
)
from .registry import DEFAULT_REGISTRY, HarnessRegistry
from .session_manager import HarnessSessionManager

logger = logging.getLogger(__name__)


class HarnessManager:
    """
    Single entrypoint Spark uses for coding engines.

    Spark code paths must call HarnessManager — never OpenCodeHarness.
    """

    def __init__(
        self,
        session_store_path: str,
        registry: Optional[HarnessRegistry] = None,
    ) -> None:
        self.registry = registry or DEFAULT_REGISTRY
        self.sessions = HarnessSessionManager(session_store_path)
        self._lock = threading.RLock()
        self._handles: Dict[str, EngineHandle] = {}
        self._engines: Dict[str, CodingHarness] = {}  # handle_id → instance

    def list_harnesses(self) -> List[Dict[str, Any]]:
        return self.registry.available()

    async def start(
        self,
        harness_id: str,
        workspace_id: str,
        repo_root: str,
        *,
        owner: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> EngineHandle:
        engine = self.registry.create(harness_id)
        handle = await engine.start(
            workspace_id,
            repo_root,
            owner=owner,
            config=config,
        )
        with self._lock:
            self._handles[handle.handle_id] = handle
            self._engines[handle.handle_id] = engine
        logger.info(
            "Harness started id=%s workspace=%s handle=%s",
            harness_id,
            workspace_id,
            handle.handle_id,
        )
        return handle

    async def stop(self, handle_id: str) -> None:
        with self._lock:
            handle = self._handles.get(handle_id)
            engine = self._engines.get(handle_id)
        if not handle or not engine:
            return
        await engine.stop(handle)
        with self._lock:
            self._handles.pop(handle_id, None)
            self._engines.pop(handle_id, None)

    async def create_session(
        self,
        handle_id: str,
        *,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HarnessSession:
        handle, engine = self._require(handle_id)
        engine_session = await engine.create_session(
            handle, model=model, metadata=metadata
        )
        # Normalize through Spark session manager (engine may return partial)
        session = self.sessions.create(
            handle_id=handle.handle_id,
            workspace_id=handle.workspace_id,
            harness_id=handle.harness_id,
            external_id=engine_session.external_id or engine_session.session_id,
            model=model or engine_session.model,
            metadata={**(engine_session.metadata or {}), **(metadata or {})},
        )
        # Keep engine session_id linkage
        session.metadata["engine_session_id"] = engine_session.session_id
        self.sessions.update(session)
        return session

    async def send(
        self,
        session_id: str,
        message: str,
        *,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        session = self.sessions.get(session_id)
        if not session:
            raise KeyError(f"session not found: {session_id}")
        _, engine = self._require(session.handle_id)
        # Reconstruct engine-facing session with external id
        engine_session = HarnessSession(
            session_id=session.metadata.get("engine_session_id") or session.external_id or session.session_id,
            handle_id=session.handle_id,
            workspace_id=session.workspace_id,
            harness_id=session.harness_id,
            external_id=session.external_id,
            model=session.model,
            status=session.status,
            metadata=session.metadata,
        )
        await engine.send(engine_session, message, attachments=attachments)

    async def stream(self, session_id: str) -> AsyncIterator[HarnessEvent]:
        session = self.sessions.get(session_id)
        if not session:
            raise KeyError(f"session not found: {session_id}")
        _, engine = self._require(session.handle_id)
        engine_session = HarnessSession(
            session_id=session.metadata.get("engine_session_id") or session.external_id or session.session_id,
            handle_id=session.handle_id,
            workspace_id=session.workspace_id,
            harness_id=session.harness_id,
            external_id=session.external_id,
            model=session.model,
            status=session.status,
            metadata=session.metadata,
        )
        async for ev in engine.stream(engine_session):
            # Rewrite to Spark session id for consumers
            yield HarnessEvent(
                type=ev.type,
                session_id=session_id,
                payload=ev.payload,
                ts=ev.ts,
            )

    async def cancel(self, session_id: str) -> None:
        session = self.sessions.cancel(session_id)
        if not session:
            return
        try:
            _, engine = self._require(session.handle_id)
            engine_session = HarnessSession(
                session_id=session.metadata.get("engine_session_id") or session.session_id,
                handle_id=session.handle_id,
                workspace_id=session.workspace_id,
                harness_id=session.harness_id,
                external_id=session.external_id,
                model=session.model,
                status="cancelled",
                metadata=session.metadata,
            )
            await engine.cancel(engine_session)
        except Exception as exc:
            logger.debug("cancel harness session: %s", exc)

    async def status(self, handle_id: str) -> HarnessStatus:
        handle, engine = self._require(handle_id)
        return await engine.status(handle)

    def get_handle(self, handle_id: str) -> Optional[EngineHandle]:
        return self._handles.get(handle_id)

    def handles_for_workspace(self, workspace_id: str) -> List[EngineHandle]:
        return [h for h in self._handles.values() if h.workspace_id == workspace_id]

    def _require(self, handle_id: str):
        with self._lock:
            handle = self._handles.get(handle_id)
            engine = self._engines.get(handle_id)
        if not handle or not engine:
            raise KeyError(f"handle not found: {handle_id}")
        return handle, engine
