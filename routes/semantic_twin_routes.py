"""HTTP routes for the Semantic Twin subsystem."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)


class GenerateBody(BaseModel):
    app_root: str
    application_id: Optional[str] = None
    application_name: Optional[str] = None
    twin_id: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None
    persist: bool = True


class UpdateBody(BaseModel):
    app_root: str
    changed_files: Optional[List[str]] = None
    manifest_delta: Optional[Dict[str, Any]] = None
    force_full: bool = False
    persist: bool = True


class SearchBody(BaseModel):
    q: str = ""
    kinds: Optional[List[str]] = None
    limit: int = 20
    mode: Optional[str] = None


class ExplainBody(BaseModel):
    node_id: str
    mode: str = "intermediate"


class TraceExecutionBody(BaseModel):
    entry_id: str
    max_depth: int = 30


class TraceDependencyBody(BaseModel):
    node_id: str
    direction: str = "downstream"
    max_depth: int = 10


class ConceptBody(BaseModel):
    q: str = ""
    limit: int = 20


class QuizBody(BaseModel):
    node_ids: Optional[List[str]] = None
    difficulty: Optional[float] = None
    count: int = 5


class TutorialBody(BaseModel):
    focus_node_id: Optional[str] = None
    max_steps: int = 8


class SimulateBody(BaseModel):
    proposal: str
    focus_node_id: Optional[str] = None


class CompareBody(BaseModel):
    from_revision: int = 0
    to_revision: Optional[int] = None


class RuntimeEventBody(BaseModel):
    type: str
    node_id: Optional[str] = None
    name: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None
    duration_ms: Optional[float] = None
    status: Optional[str] = None
    message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None
    persist: bool = True


class RegisterProjectBody(BaseModel):
    app_root: str
    name: Optional[str] = None
    project_id: Optional[str] = None
    generate_twin: bool = True


def setup_semantic_twin_routes(service, integration=None) -> APIRouter:
    """
    service: SemanticTwinService
    integration: optional IntegrationService (Phase 1)
    """
    router = APIRouter(prefix="/api/semantic-twin", tags=["semantic_twin"])

    def _owner(request: Request) -> Optional[str]:
        return get_current_user(request)

    def _load(twin_id: str, owner: Optional[str], include_graph: bool = True):
        try:
            return service.load(twin_id, owner=owner, include_graph=include_graph)
        except FileNotFoundError:
            raise HTTPException(404, "Twin not found")
        except PermissionError:
            raise HTTPException(404, "Twin not found")
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    def _safe_app_root(app_root: str) -> Path:
        root = Path(app_root).expanduser().resolve()
        if not root.is_dir():
            raise HTTPException(400, f"app_root is not a directory: {app_root}")
        return root

    @router.post("/generate")
    def generate(request: Request, body: GenerateBody):
        owner = _owner(request)
        root = _safe_app_root(body.app_root)
        from services.semantic_twin.models import GenerationManifest

        manifest = (
            GenerationManifest.from_dict(body.manifest)
            if body.manifest
            else GenerationManifest.empty()
        )
        try:
            twin = service.generate(
                root,
                manifest,
                application_id=body.application_id,
                application_name=body.application_name,
                owner=owner,
                twin_id=body.twin_id,
                persist=body.persist,
            )
        except FileNotFoundError as exc:
            raise HTTPException(400, str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Semantic Twin generate failed")
            raise HTTPException(500, f"generate failed: {exc}")
        return twin.to_dict(include_graph=True)

    @router.get("")
    @router.get("/")
    def list_twins(request: Request):
        owner = _owner(request)
        return {"twins": service.list(owner=owner)}

    # Phase-1 project registry (must be registered BEFORE /{twin_id})
    @router.get("/projects/list")
    def list_projects(request: Request):
        if integration is None:
            raise HTTPException(503, "Semantic Twin integration not available")
        owner = _owner(request)
        rows = integration.registry.list(owner=owner)
        return {
            "projects": [
                {
                    **r.to_dict(),
                    "explorer_url": f"/semantic-twin?twin={r.twin_id}" if r.twin_id else None,
                }
                for r in rows
            ]
        }

    @router.post("/projects/register")
    def register_project(request: Request, body: RegisterProjectBody):
        if integration is None:
            raise HTTPException(503, "Semantic Twin integration not available")
        owner = _owner(request)
        root = _safe_app_root(body.app_root)
        project_id = body.project_id or integration.tracker.project_id_for_root(str(root))
        name = body.name or root.name
        twin_id = None
        twin_meta = None
        if body.generate_twin:
            from services.semantic_twin.models import GenerationManifest
            twin = service.generate(
                root,
                GenerationManifest.empty(),
                application_id=project_id,
                application_name=name,
                owner=owner,
                persist=True,
            )
            twin_id = twin.twin_id
            twin_meta = twin.meta.to_dict()
            integration.timeline.record(twin, trigger="register", label=f"register {name}")
            integration.registry.register(
                project_id=project_id,
                name=name,
                app_root=str(root),
                twin_id=twin_id,
                owner=owner,
                revision=twin.content_revision,
            )
        else:
            integration.registry.register(
                project_id=project_id,
                name=name,
                app_root=str(root),
                twin_id=None,
                owner=owner,
            )
        rec = integration.registry.get(project_id)
        return {
            "project": rec.to_dict() if rec else None,
            "twin_id": twin_id,
            "meta": twin_meta,
        }

    @router.get("/projects/{project_id}")
    def get_project(request: Request, project_id: str):
        if integration is None:
            raise HTTPException(503, "Semantic Twin integration not available")
        owner = _owner(request)
        rec = integration.registry.get(project_id)
        if not rec:
            raise HTTPException(404, "Project not found")
        if owner is not None and rec.owner is not None and rec.owner != owner:
            raise HTTPException(404, "Project not found")
        return rec.to_dict()

    @router.get("/{twin_id}")
    def get_twin(request: Request, twin_id: str, include: Optional[str] = None):
        owner = _owner(request)
        include_graph = include == "graph" or include == "full"
        twin = _load(twin_id, owner, include_graph=include_graph)
        return twin.to_dict(include_graph=include_graph)

    @router.get("/{twin_id}/graph")
    def get_graph(request: Request, twin_id: str):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        return {
            "twin_id": twin.twin_id,
            "content_revision": twin.content_revision,
            "nodes": [n.to_dict() for n in twin.nodes],
            "edges": [e.to_dict() for e in twin.edges],
            "indexes": twin.indexes.to_dict(),
        }

    @router.delete("/{twin_id}")
    def delete_twin(request: Request, twin_id: str):
        owner = _owner(request)
        try:
            service.delete(twin_id, owner=owner)
        except FileNotFoundError:
            raise HTTPException(404, "Twin not found")
        except PermissionError:
            raise HTTPException(404, "Twin not found")
        return {"ok": True, "twin_id": twin_id}

    @router.post("/{twin_id}/update")
    def update_twin(request: Request, twin_id: str, body: UpdateBody):
        owner = _owner(request)
        root = _safe_app_root(body.app_root)
        try:
            twin = service.update(
                twin_id,
                root,
                changed_files=body.changed_files,
                manifest_delta=body.manifest_delta,
                owner=owner,
                force_full=body.force_full,
                persist=body.persist,
            )
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc))
        except PermissionError:
            raise HTTPException(404, "Twin not found")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Semantic Twin update failed")
            raise HTTPException(500, f"update failed: {exc}")
        return twin.to_dict(include_graph=True)

    @router.post("/{twin_id}/search")
    def search(request: Request, twin_id: str, body: SearchBody):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        return service.api(twin).search(body.q, kinds=body.kinds, limit=body.limit, mode=body.mode)

    @router.post("/{twin_id}/explain")
    def explain(request: Request, twin_id: str, body: ExplainBody):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        try:
            return service.api(twin).explain(body.node_id, mode=body.mode)
        except KeyError:
            raise HTTPException(404, "Node not found")

    @router.post("/{twin_id}/trace/execution")
    def trace_execution(request: Request, twin_id: str, body: TraceExecutionBody):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        return service.api(twin).trace_execution(body.entry_id, max_depth=body.max_depth)

    @router.post("/{twin_id}/trace/dependency")
    def trace_dependency(request: Request, twin_id: str, body: TraceDependencyBody):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        return service.api(twin).trace_dependency(
            body.node_id, direction=body.direction, max_depth=body.max_depth
        )

    @router.post("/{twin_id}/concepts")
    def find_concept(request: Request, twin_id: str, body: ConceptBody):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        return service.api(twin).find_concept(body.q, limit=body.limit)

    @router.post("/{twin_id}/quiz")
    def quiz(request: Request, twin_id: str, body: QuizBody):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        return service.api(twin).generate_quiz(
            node_ids=body.node_ids, difficulty=body.difficulty, count=body.count
        )

    @router.post("/{twin_id}/tutorial")
    def tutorial(request: Request, twin_id: str, body: TutorialBody):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        return service.api(twin).generate_tutorial(
            focus_node_id=body.focus_node_id, max_steps=body.max_steps
        )

    @router.post("/{twin_id}/simulate")
    def simulate(request: Request, twin_id: str, body: SimulateBody):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        return service.api(twin).simulate_modification(
            body.proposal, focus_node_id=body.focus_node_id
        )

    @router.post("/{twin_id}/compare")
    def compare(request: Request, twin_id: str, body: CompareBody):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        return service.api(twin).compare_versions(
            body.from_revision, to_revision=body.to_revision
        )

    @router.get("/{twin_id}/node/{node_id}")
    def get_node(request: Request, twin_id: str, node_id: str):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        node = twin.node_map().get(node_id)
        if not node:
            raise HTTPException(404, "Node not found")
        return node.to_dict()

    @router.get("/{twin_id}/story/{node_id}")
    def story(request: Request, twin_id: str, node_id: str):
        owner = _owner(request)
        twin = _load(twin_id, owner, include_graph=True)
        try:
            return {"node_id": node_id, "steps": service.api(twin).story_for_node(node_id)}
        except KeyError:
            raise HTTPException(404, "Node not found")

    # Phase-1 timeline + runtime (path-specific suffixes on /{twin_id}/…)
    @router.get("/{twin_id}/timeline")
    def timeline(request: Request, twin_id: str):
        if integration is None:
            raise HTTPException(503, "Semantic Twin integration not available")
        owner = _owner(request)
        _load(twin_id, owner, include_graph=False)
        versions = integration.timeline.list_versions(twin_id)
        return {"twin_id": twin_id, "versions": versions}

    @router.get("/{twin_id}/timeline/{revision}")
    def timeline_version(request: Request, twin_id: str, revision: int):
        if integration is None:
            raise HTTPException(503, "Semantic Twin integration not available")
        owner = _owner(request)
        _load(twin_id, owner, include_graph=False)
        entry = integration.timeline.get_version(twin_id, revision)
        if not entry:
            raise HTTPException(404, "Version not found")
        return entry

    @router.get("/{twin_id}/timeline/diff/{from_rev}/{to_rev}")
    def timeline_diff(request: Request, twin_id: str, from_rev: int, to_rev: int):
        if integration is None:
            raise HTTPException(503, "Semantic Twin integration not available")
        owner = _owner(request)
        _load(twin_id, owner, include_graph=False)
        diff = integration.timeline.get_diff(twin_id, from_rev, to_rev)
        if not diff:
            raise HTTPException(404, "Diff not found")
        return diff

    @router.post("/{twin_id}/runtime")
    def runtime_event(request: Request, twin_id: str, body: RuntimeEventBody):
        if integration is None:
            raise HTTPException(503, "Semantic Twin integration not available")
        owner = _owner(request)
        _load(twin_id, owner, include_graph=False)
        return integration.runtime.ingest(
            twin_id,
            body.model_dump(),
            persist=body.persist,
            owner=owner,
        )

    @router.get("/{twin_id}/runtime")
    def list_runtime(request: Request, twin_id: str, limit: int = 100):
        if integration is None:
            raise HTTPException(503, "Semantic Twin integration not available")
        owner = _owner(request)
        _load(twin_id, owner, include_graph=False)
        return {
            "twin_id": twin_id,
            "events": integration.runtime.list_events(twin_id, limit=limit),
        }

    return router
