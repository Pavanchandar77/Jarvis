"""
Workspace Manager — project lifecycle owner.

Harnesses edit code. This manager owns:
  repository lifecycle, worktrees, branches, session registry linkage,
  Semantic Twin registration, Runtime association, Knowledge Memory,
  active harness, project metadata (via WorkspaceManifest).
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.harness.manager import HarnessManager

from .manifest import WorkspaceManifest
from .registry import WorkspaceRegistry

logger = logging.getLogger(__name__)


class WorkspaceManager:
    def __init__(
        self,
        registry: WorkspaceRegistry,
        harness_manager: HarnessManager,
        *,
        twin_integration=None,
        spark_os=None,
    ) -> None:
        self.registry = registry
        self.harness = harness_manager
        self.twin_integration = twin_integration
        self.spark_os = spark_os

    # ── lifecycle ─────────────────────────────────────────────────────

    def create(
        self,
        name: str,
        repo_root: str,
        *,
        owner: Optional[str] = None,
        runtime_profile: str = "default",
        active_model: Optional[str] = None,
        active_harness: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        init_git: bool = False,
    ) -> WorkspaceManifest:
        root = Path(repo_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        if init_git and not (root / ".git").exists():
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=str(root),
                    check=False,
                    capture_output=True,
                )
            except Exception:
                pass

        existing = self.registry.by_root(str(root))
        if existing:
            existing.name = name or existing.name
            if owner is not None:
                existing.owner = owner
            if active_model:
                existing.active_model = active_model
            if active_harness:
                existing.active_harness = active_harness
            if metadata:
                existing.metadata.update(metadata)
            self.registry.save(existing)
            return existing

        branch = self._git_branch(str(root))
        manifest = WorkspaceManifest.create(
            name=name,
            repo_root=str(root),
            owner=owner,
            runtime_profile=runtime_profile,
            active_model=active_model,
            active_harness=active_harness,
            branch=branch,
            knowledge_memory_id="org",  # default org memory namespace
            metadata=dict(metadata or {}),
        )
        self.registry.save(manifest)
        logger.info("Workspace created id=%s root=%s", manifest.workspace_id, root)
        return manifest

    def get(self, workspace_id: str) -> Optional[WorkspaceManifest]:
        return self.registry.get(workspace_id)

    def list(self, *, owner: Optional[str] = None) -> List[WorkspaceManifest]:
        return self.registry.list(owner=owner)

    def update(self, workspace_id: str, **fields: Any) -> WorkspaceManifest:
        m = self.registry.get(workspace_id)
        if not m:
            raise KeyError(f"workspace not found: {workspace_id}")
        for k, v in fields.items():
            if hasattr(m, k) and v is not None:
                setattr(m, k, v)
        self.registry.save(m)
        return m

    def archive(self, workspace_id: str) -> WorkspaceManifest:
        return self.update(workspace_id, status="archived")

    # ── associations ──────────────────────────────────────────────────

    def bind_twin(
        self,
        workspace_id: str,
        twin_id: str,
        *,
        project_id: Optional[str] = None,
        application_id: Optional[str] = None,
    ) -> WorkspaceManifest:
        m = self.update(
            workspace_id,
            twin_id=twin_id,
            project_id=project_id,
            application_id=application_id or project_id,
        )
        # Mirror into Phase-1 project registry when available
        if self.twin_integration and m.repo_root:
            try:
                self.twin_integration.registry.register(
                    project_id=project_id or workspace_id,
                    name=m.name,
                    app_root=m.repo_root,
                    twin_id=twin_id,
                    owner=m.owner,
                )
            except Exception as exc:
                logger.debug("bind twin registry: %s", exc)
        return m

    def bind_runtime(
        self,
        workspace_id: str,
        *,
        runtime_profile: Optional[str] = None,
        active_model: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ) -> WorkspaceManifest:
        return self.update(
            workspace_id,
            runtime_profile=runtime_profile,
            active_model=active_model,
            endpoint_url=endpoint_url,
        )

    def bind_harness(
        self,
        workspace_id: str,
        harness_id: str,
        *,
        handle_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> WorkspaceManifest:
        return self.update(
            workspace_id,
            active_harness=harness_id,
            harness_handle_id=handle_id,
            harness_session_id=session_id,
        )

    def set_agents(self, workspace_id: str, agents: List[str]) -> WorkspaceManifest:
        return self.update(workspace_id, active_agents=list(agents))

    # ── harness orchestration (via HarnessManager only) ───────────────

    async def start_harness(
        self,
        workspace_id: str,
        harness_id: Optional[str] = None,
        *,
        owner: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        m = self.registry.get(workspace_id)
        if not m:
            raise KeyError(f"workspace not found: {workspace_id}")
        hid = harness_id or m.active_harness
        if not hid:
            available = self.harness.list_harnesses()
            if not available:
                raise RuntimeError("no harnesses registered")
            hid = available[0]["harness_id"]

        cfg = dict(config or {})
        # Pass Spark runtime routing hints without coupling to OpenCode
        if m.active_model:
            cfg.setdefault("model", m.active_model)
        if m.endpoint_url:
            cfg.setdefault("spark_endpoint", m.endpoint_url)
        if m.twin_id:
            cfg.setdefault("twin_id", m.twin_id)
        cfg.setdefault("workspace_id", m.workspace_id)
        cfg.setdefault("owner", owner or m.owner)

        handle = await self.harness.start(
            hid,
            m.workspace_id,
            m.repo_root,
            owner=owner or m.owner,
            config=cfg,
        )
        self.bind_harness(workspace_id, hid, handle_id=handle.handle_id)
        return {"manifest": self.registry.get(workspace_id).to_dict(), "handle": handle.to_dict()}

    async def stop_harness(self, workspace_id: str) -> WorkspaceManifest:
        m = self.registry.get(workspace_id)
        if not m:
            raise KeyError(f"workspace not found: {workspace_id}")
        if m.harness_handle_id:
            await self.harness.stop(m.harness_handle_id)
        return self.update(
            workspace_id,
            harness_handle_id=None,
            harness_session_id=None,
        )

    async def create_coding_session(
        self,
        workspace_id: str,
        *,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        m = self.registry.get(workspace_id)
        if not m:
            raise KeyError(f"workspace not found: {workspace_id}")
        if not m.harness_handle_id:
            started = await self.start_harness(workspace_id)
            m = self.registry.get(workspace_id)
        session = await self.harness.create_session(
            m.harness_handle_id,
            model=model or m.active_model,
            metadata={"workspace_id": workspace_id, "twin_id": m.twin_id},
        )
        self.bind_harness(
            workspace_id,
            m.active_harness or session.harness_id,
            handle_id=m.harness_handle_id,
            session_id=session.session_id,
        )
        return {
            "session": session.to_dict(),
            "manifest": self.registry.get(workspace_id).to_dict(),
        }

    # ── twin ensure ───────────────────────────────────────────────────

    def ensure_twin(self, workspace_id: str, *, owner: Optional[str] = None) -> WorkspaceManifest:
        """Register/generate Semantic Twin for workspace root if missing."""
        m = self.registry.get(workspace_id)
        if not m:
            raise KeyError(f"workspace not found: {workspace_id}")
        if m.twin_id:
            return m
        if not self.twin_integration:
            return m
        from services.semantic_twin.models import GenerationManifest

        try:
            twin = self.twin_integration.twin_service.generate(
                m.repo_root,
                GenerationManifest(
                    generation_id=f"ws-{workspace_id[:12]}",
                    user_prompt=f"Workspace {m.name}",
                    metadata={"workspace_id": workspace_id, "source": "workspace_manager"},
                ),
                application_id=workspace_id,
                application_name=m.name,
                owner=owner or m.owner,
                persist=True,
            )
            self.bind_twin(workspace_id, twin.twin_id, project_id=workspace_id, application_id=twin.application_id)
            if self.twin_integration.timeline:
                self.twin_integration.timeline.record(
                    twin, trigger="workspace_ensure", label=f"workspace {m.name}"
                )
        except Exception as exc:
            logger.warning("ensure_twin failed for %s: %s", workspace_id, exc)
        return self.registry.get(workspace_id)

    def on_files_changed(
        self,
        workspace_id: str,
        paths: List[str],
        *,
        owner: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Harness-agnostic file change notification → twin continuous sync."""
        m = self.registry.get(workspace_id)
        if not m:
            raise KeyError(f"workspace not found: {workspace_id}")
        if not m.twin_id or not self.twin_integration:
            return {"ok": False, "reason": "no twin"}
        rels = []
        root = os.path.realpath(m.repo_root)
        for p in paths:
            try:
                real = os.path.realpath(p)
                if real == root or real.startswith(root + os.sep):
                    rels.append(os.path.relpath(real, root).replace("\\", "/"))
                else:
                    rels.append(p.replace("\\", "/"))
            except Exception:
                rels.append(p)
        for rel in rels:
            self.twin_integration.sync.notify(
                twin_id=m.twin_id,
                app_root=m.repo_root,
                rel_path=rel,
                owner=owner or m.owner,
            )
        return {"ok": True, "paths": rels, "twin_id": m.twin_id}

    def _git_branch(self, root: str) -> Optional[str]:
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode == 0:
                return r.stdout.strip() or None
        except Exception:
            pass
        return None
