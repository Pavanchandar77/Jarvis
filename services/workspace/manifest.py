"""Workspace Manifest — canonical Spark-owned project descriptor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class WorkspaceManifest:
    """
    Single source of project truth for all Spark subsystems.

    Nothing should read OpenCode (or any harness) configuration directly —
    consume this manifest instead.
    """

    workspace_id: str
    name: str
    repo_root: str
    owner: Optional[str] = None

    # Runtime
    runtime_profile: str = "default"
    active_model: Optional[str] = None
    endpoint_url: Optional[str] = None

    # Semantic Twin / Knowledge
    twin_id: Optional[str] = None
    knowledge_memory_id: Optional[str] = None
    application_id: Optional[str] = None

    # Harness
    active_harness: Optional[str] = None  # harness_id e.g. "opencode"
    harness_handle_id: Optional[str] = None
    harness_session_id: Optional[str] = None

    # Agents / OS
    active_agents: List[str] = field(default_factory=list)
    project_id: Optional[str] = None  # semantic twin project registry id

    # VCS
    branch: Optional[str] = None
    worktree: Optional[str] = None
    remote_url: Optional[str] = None

    # Metadata
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    status: str = "active"  # active | archived
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkspaceManifest":
        return cls(
            workspace_id=data["workspace_id"],
            name=data.get("name") or data["workspace_id"],
            repo_root=data["repo_root"],
            owner=data.get("owner"),
            runtime_profile=data.get("runtime_profile") or "default",
            active_model=data.get("active_model"),
            endpoint_url=data.get("endpoint_url"),
            twin_id=data.get("twin_id"),
            knowledge_memory_id=data.get("knowledge_memory_id"),
            application_id=data.get("application_id"),
            active_harness=data.get("active_harness"),
            harness_handle_id=data.get("harness_handle_id"),
            harness_session_id=data.get("harness_session_id"),
            active_agents=list(data.get("active_agents") or []),
            project_id=data.get("project_id"),
            branch=data.get("branch"),
            worktree=data.get("worktree"),
            remote_url=data.get("remote_url"),
            created_at=data.get("created_at") or _utcnow(),
            updated_at=data.get("updated_at") or _utcnow(),
            status=data.get("status") or "active",
            metadata=dict(data.get("metadata") or {}),
        )

    @classmethod
    def create(
        cls,
        name: str,
        repo_root: str,
        *,
        owner: Optional[str] = None,
        workspace_id: Optional[str] = None,
        **kwargs: Any,
    ) -> "WorkspaceManifest":
        return cls(
            workspace_id=workspace_id or uuid.uuid4().hex,
            name=name,
            repo_root=repo_root,
            owner=owner,
            **kwargs,
        )
