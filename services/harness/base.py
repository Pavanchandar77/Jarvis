"""Generic Coding Harness interface — OpenCode/Claude Code/Codex implement this."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class EngineHandle:
    """Opaque handle to a running harness engine process/instance."""
    handle_id: str
    harness_id: str  # e.g. "opencode", "claude_code", "codex"
    workspace_id: str
    endpoint: Optional[str] = None  # HTTP base when applicable
    pid: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handle_id": self.handle_id,
            "harness_id": self.harness_id,
            "workspace_id": self.workspace_id,
            "endpoint": self.endpoint,
            "pid": self.pid,
            "metadata": dict(self.metadata),
        }


@dataclass
class HarnessSession:
    """Coding session owned by a harness, linked to a Spark workspace."""
    session_id: str
    handle_id: str
    workspace_id: str
    harness_id: str
    external_id: Optional[str] = None  # engine-native session id
    model: Optional[str] = None
    status: str = "active"  # active | idle | cancelled | error
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "handle_id": self.handle_id,
            "workspace_id": self.workspace_id,
            "harness_id": self.harness_id,
            "external_id": self.external_id,
            "model": self.model,
            "status": self.status,
            "metadata": dict(self.metadata),
        }


@dataclass
class HarnessEvent:
    """Normalized event from any harness."""
    type: str  # message.delta | tool.start | tool.end | file.changed | status | error | done
    session_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "session_id": self.session_id,
            "payload": dict(self.payload),
            "ts": self.ts,
        }


@dataclass
class HarnessStatus:
    handle_id: str
    harness_id: str
    state: str  # stopped | starting | running | unhealthy | error
    detail: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handle_id": self.handle_id,
            "harness_id": self.harness_id,
            "state": self.state,
            "detail": self.detail,
            "metadata": dict(self.metadata),
        }


@runtime_checkable
class CodingHarness(Protocol):
    """
    Stable Spark interface for coding engines.

    Implementations: OpenCodeHarness, (future) ClaudeCodeHarness, CodexHarness.
    Spark subsystems must only depend on this protocol — never on engine types.
    """

    harness_id: str
    display_name: str

    async def start(
        self,
        workspace_id: str,
        repo_root: str,
        *,
        owner: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> EngineHandle: ...

    async def stop(self, handle: EngineHandle) -> None: ...

    async def create_session(
        self,
        handle: EngineHandle,
        *,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> HarnessSession: ...

    async def send(
        self,
        session: HarnessSession,
        message: str,
        *,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> None: ...

    def stream(self, session: HarnessSession) -> AsyncIterator[HarnessEvent]: ...

    async def cancel(self, session: HarnessSession) -> None: ...

    async def status(self, handle: EngineHandle) -> HarnessStatus: ...
