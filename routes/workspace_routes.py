"""Workspace Manager + Harness Manager HTTP API.

Spark UI and plugins talk to workspaces/harnesses — never OpenCode directly.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)

_SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".next", ".turbo", "coverage", ".pytest_cache", ".spark",
}
_MAX_READ = 1_500_000


class CreateWorkspaceBody(BaseModel):
    name: str
    repo_root: str
    runtime_profile: str = "default"
    active_model: Optional[str] = None
    active_harness: Optional[str] = None
    init_git: bool = False
    metadata: Optional[Dict[str, Any]] = None


class BindTwinBody(BaseModel):
    twin_id: str
    project_id: Optional[str] = None


class BindRuntimeBody(BaseModel):
    runtime_profile: Optional[str] = None
    active_model: Optional[str] = None
    endpoint_url: Optional[str] = None


class StartHarnessBody(BaseModel):
    harness_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class SessionBody(BaseModel):
    model: Optional[str] = None


class SendBody(BaseModel):
    message: str


class FileChangedBody(BaseModel):
    """Harness-agnostic file change (OpenCode plugin posts here)."""
    workspace_id: str
    paths: List[str]
    session_id: Optional[str] = None
    tool: Optional[str] = None
    harness_id: Optional[str] = None


class WriteFileBody(BaseModel):
    path: str  # relative to workspace root
    content: str


def _safe_path(root: str, rel: str) -> Path:
    root_p = Path(root).resolve()
    rel = (rel or ".").replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise HTTPException(400, "path traversal denied")
    target = (root_p / rel).resolve()
    try:
        target.relative_to(root_p)
    except ValueError:
        raise HTTPException(400, "path outside workspace")
    return target


def setup_workspace_routes(workspace_manager, harness_manager) -> APIRouter:
    router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

    def _owner(request: Request) -> Optional[str]:
        return get_current_user(request)

    def _get(wid: str, owner: Optional[str]):
        m = workspace_manager.get(wid)
        if not m:
            raise HTTPException(404, "Workspace not found")
        if owner is not None and m.owner is not None and m.owner != owner:
            raise HTTPException(404, "Workspace not found")
        return m

    @router.get("")
    @router.get("/")
    def list_workspaces(request: Request):
        owner = _owner(request)
        return {
            "workspaces": [m.to_dict() for m in workspace_manager.list(owner=owner)],
            "harnesses": harness_manager.list_harnesses(),
        }

    @router.post("")
    def create_workspace(request: Request, body: CreateWorkspaceBody):
        owner = _owner(request)
        try:
            m = workspace_manager.create(
                body.name,
                body.repo_root,
                owner=owner,
                runtime_profile=body.runtime_profile,
                active_model=body.active_model,
                active_harness=body.active_harness,
                metadata=body.metadata,
                init_git=body.init_git,
            )
            return m.to_dict()
        except Exception as exc:
            logger.exception("create workspace")
            raise HTTPException(400, str(exc))

    @router.get("/{workspace_id}")
    def get_workspace(request: Request, workspace_id: str):
        return _get(workspace_id, _owner(request)).to_dict()

    @router.post("/{workspace_id}/twin")
    def bind_twin(request: Request, workspace_id: str, body: BindTwinBody):
        _get(workspace_id, _owner(request))
        m = workspace_manager.bind_twin(
            workspace_id, body.twin_id, project_id=body.project_id
        )
        return m.to_dict()

    @router.post("/{workspace_id}/twin/ensure")
    def ensure_twin(request: Request, workspace_id: str):
        _get(workspace_id, _owner(request))
        m = workspace_manager.ensure_twin(workspace_id, owner=_owner(request))
        return m.to_dict()

    @router.post("/{workspace_id}/runtime")
    def bind_runtime(request: Request, workspace_id: str, body: BindRuntimeBody):
        _get(workspace_id, _owner(request))
        m = workspace_manager.bind_runtime(
            workspace_id,
            runtime_profile=body.runtime_profile,
            active_model=body.active_model,
            endpoint_url=body.endpoint_url,
        )
        return m.to_dict()

    @router.post("/{workspace_id}/harness/start")
    async def start_harness(request: Request, workspace_id: str, body: StartHarnessBody):
        _get(workspace_id, _owner(request))
        try:
            return await workspace_manager.start_harness(
                workspace_id,
                body.harness_id,
                owner=_owner(request),
                config=body.config,
            )
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        except Exception as exc:
            logger.exception("start harness")
            raise HTTPException(500, str(exc))

    @router.post("/{workspace_id}/harness/stop")
    async def stop_harness(request: Request, workspace_id: str):
        _get(workspace_id, _owner(request))
        m = await workspace_manager.stop_harness(workspace_id)
        return m.to_dict()

    @router.post("/{workspace_id}/sessions")
    async def create_session(request: Request, workspace_id: str, body: SessionBody):
        _get(workspace_id, _owner(request))
        try:
            return await workspace_manager.create_coding_session(
                workspace_id, model=body.model
            )
        except Exception as exc:
            logger.exception("create session")
            raise HTTPException(500, str(exc))

    @router.post("/{workspace_id}/sessions/{session_id}/send")
    async def send_message(
        request: Request, workspace_id: str, session_id: str, body: SendBody
    ):
        _get(workspace_id, _owner(request))
        try:
            await harness_manager.send(session_id, body.message)
            return {"ok": True, "session_id": session_id}
        except KeyError:
            raise HTTPException(404, "Session not found")
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.post("/{workspace_id}/files-changed")
    def files_changed(request: Request, workspace_id: str, body: FileChangedBody):
        """Called by any harness plugin when files mutate."""
        _get(workspace_id, _owner(request))
        try:
            return workspace_manager.on_files_changed(
                workspace_id,
                body.paths,
                owner=_owner(request),
            )
        except Exception as exc:
            raise HTTPException(400, str(exc))

    # ── Coding Mode file surface (workspace-owned, harness-agnostic) ──

    @router.get("/{workspace_id}/files")
    def list_files(request: Request, workspace_id: str, path: str = ""):
        m = _get(workspace_id, _owner(request))
        target = _safe_path(m.repo_root, path or ".")
        if not target.exists():
            raise HTTPException(404, "path not found")
        if target.is_file():
            return {
                "path": path or target.name,
                "type": "file",
                "name": target.name,
                "size": target.stat().st_size,
            }
        entries = []
        try:
            for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if child.name.startswith(".") and child.name not in (".env.example",):
                    if child.name in (".git", ".spark"):
                        continue
                if child.is_dir() and child.name in _SKIP_DIRS:
                    continue
                rel = child.relative_to(Path(m.repo_root).resolve()).as_posix()
                entries.append({
                    "name": child.name,
                    "path": rel,
                    "type": "dir" if child.is_dir() else "file",
                    "size": child.stat().st_size if child.is_file() else None,
                })
        except OSError as exc:
            raise HTTPException(400, str(exc))
        return {"path": path or ".", "type": "dir", "entries": entries}

    @router.get("/{workspace_id}/file")
    def read_file(request: Request, workspace_id: str, path: str):
        m = _get(workspace_id, _owner(request))
        target = _safe_path(m.repo_root, path)
        if not target.is_file():
            raise HTTPException(404, "file not found")
        try:
            data = target.read_bytes()
        except OSError as exc:
            raise HTTPException(400, str(exc))
        if len(data) > _MAX_READ:
            raise HTTPException(400, "file too large")
        if b"\x00" in data[:1024]:
            raise HTTPException(400, "binary file")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
        return {
            "path": path.replace("\\", "/"),
            "content": text,
            "size": len(data),
        }

    @router.put("/{workspace_id}/file")
    def write_file(request: Request, workspace_id: str, body: WriteFileBody):
        m = _get(workspace_id, _owner(request))
        target = _safe_path(m.repo_root, body.path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body.content, encoding="utf-8")
        except OSError as exc:
            raise HTTPException(400, str(exc))
        # Twin continuous sync
        try:
            workspace_manager.on_files_changed(
                workspace_id, [str(target)], owner=_owner(request)
            )
        except Exception:
            pass
        return {"ok": True, "path": body.path.replace("\\", "/"), "size": len(body.content)}

    @router.get("/{workspace_id}/status")
    def workspace_status(request: Request, workspace_id: str):
        """Header strip for Coding Mode: harness, twin, runtime, model."""
        m = _get(workspace_id, _owner(request))
        twin_status = "missing"
        if m.twin_id:
            twin_status = "linked"
            try:
                if workspace_manager.twin_integration:
                    if workspace_manager.twin_integration.twin_service.repo.exists(m.twin_id):
                        twin_status = "ready"
            except Exception:
                twin_status = "linked"
        harness_state = "idle"
        if m.harness_handle_id:
            harness_state = "active"
        return {
            "manifest": m.to_dict(),
            "twin_status": twin_status,
            "harness_state": harness_state,
            "sync_status": "live" if twin_status == "ready" else "pending",
        }

    return router


def setup_harness_plugin_routes(workspace_manager) -> APIRouter:
    """
    Engine-agnostic plugin callback surface.

    OpenCode (or any harness) plugin posts here. Paths do not say "opencode"
    so future engines share the same contract.
    """
    router = APIRouter(prefix="/api/harness", tags=["harness"])

    def _owner(request: Request) -> Optional[str]:
        return get_current_user(request)

    @router.get("/engines")
    def engines():
        from services.harness.registry import DEFAULT_REGISTRY
        return {"engines": DEFAULT_REGISTRY.available()}

    @router.post("/file-changed")
    def file_changed(request: Request, body: FileChangedBody):
        owner = _owner(request)
        try:
            return workspace_manager.on_files_changed(
                body.workspace_id,
                body.paths,
                owner=owner,
            )
        except KeyError:
            raise HTTPException(404, "Workspace not found")
        except Exception as exc:
            raise HTTPException(400, str(exc))

    # Spark tools for harness plugins (proxy to Twin / OS / Runtime)
    class ToolProxyBody(BaseModel):
        action: str
        workspace_id: Optional[str] = None
        twin_id: Optional[str] = None
        payload: Dict[str, Any] = Field(default_factory=dict)

    @router.post("/tools/invoke")
    def invoke_tool(request: Request, body: ToolProxyBody):
        owner = _owner(request)
        twin_id = body.twin_id
        if not twin_id and body.workspace_id:
            m = workspace_manager.get(body.workspace_id)
            if m:
                twin_id = m.twin_id
        action = body.action
        payload = body.payload or {}

        # Twin tools
        if action.startswith("semantic.") or action.startswith("semantic_"):
            if not twin_id:
                raise HTTPException(400, "twin_id required")
            from services.semantic_twin.integration.hooks import get_integration_service
            integ = get_integration_service()
            if not integ:
                raise HTTPException(503, "twin integration unavailable")
            twin = integ.twin_service.load(twin_id, owner=owner, include_graph=True)
            api = integ.twin_service.api(twin)
            act = action.replace("semantic.", "").replace("semantic_", "")
            if act in ("search",):
                return api.search(payload.get("q") or "", limit=int(payload.get("limit") or 20))
            if act in ("explain",):
                return api.explain(payload["node_id"], mode=payload.get("mode") or "senior")
            if act in ("trace_execution", "traceExecution"):
                return api.trace_execution(payload.get("node_id") or payload.get("entry_id"))
            if act in ("trace_dependency", "traceDependency"):
                return api.trace_dependency(
                    payload["node_id"],
                    direction=payload.get("direction") or "downstream",
                )
            if act in ("find_concept", "findConcept"):
                return api.find_concept(payload.get("q") or "")
            raise HTTPException(400, f"unknown semantic action: {act}")

        # OS tools
        if action.startswith("architecture.") or action.startswith("simulation.") or action.startswith("knowledge."):
            from services.spark_os import SparkOSService
            # Resolve OS service from app state if attached
            os_svc = getattr(request.app.state, "spark_os", None)
            if not os_svc:
                raise HTTPException(503, "Spark OS unavailable")
            if action in ("architecture.review", "architecture_review"):
                if not twin_id:
                    raise HTTPException(400, "twin_id required")
                return os_svc.review_architecture(twin_id, owner=owner)
            if action in ("simulation.run", "simulation_run"):
                if not twin_id:
                    raise HTTPException(400, "twin_id required")
                return os_svc.simulate(twin_id, payload.get("proposal") or "", owner=owner)
            if action in ("knowledge.search", "knowledge_search"):
                return os_svc.memory_retrieve(payload.get("q") or "")
            raise HTTPException(400, f"unknown os action: {action}")

        if action in ("runtime.select_model", "runtime_select_model"):
            # Soft: return requested model binding (Spark settings remain source of truth)
            return {
                "ok": True,
                "model": payload.get("model"),
                "note": "Bind via workspace runtime profile; Spark Runtime schedules inference.",
            }

        raise HTTPException(400, f"unknown action: {action}")

    return router
