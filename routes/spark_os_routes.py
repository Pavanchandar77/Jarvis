"""HTTP API for Spark Software Operating System (Phase 2)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)


class DesignBody(BaseModel):
    name: str
    description: str = ""
    project_id: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    services: Optional[List[str]] = None
    apis: Optional[List[Dict[str, str]]] = None
    databases: Optional[List[str]] = None


class CompileBody(BaseModel):
    architecture_id: str
    target_root: str
    generate_twin: bool = True
    run_review: bool = True


class RequirementBody(BaseModel):
    id: Optional[str] = None
    text: str
    requested_by: str = "user"
    prompt_id: Optional[str] = None
    artifact_ids: Optional[List[str]] = None
    priority: str = "medium"


class AgentMsgBody(BaseModel):
    from_agent: str
    to_agent: str = "broadcast"
    type: str = "info"
    region_node_ids: Optional[List[str]] = None
    payload: Optional[Dict[str, Any]] = None
    requires_approval: bool = False


class SimulateBody(BaseModel):
    proposal: str
    focus_node_id: Optional[str] = None


class RefactorBody(BaseModel):
    transformation: str
    full_pipeline: bool = True


def setup_spark_os_routes(os_service) -> APIRouter:
    router = APIRouter(prefix="/api/os", tags=["spark_os"])

    def _owner(request: Request) -> Optional[str]:
        return get_current_user(request)

    def _err(exc: Exception):
        if isinstance(exc, FileNotFoundError):
            raise HTTPException(404, str(exc))
        if isinstance(exc, PermissionError):
            raise HTTPException(404, "Not found")
        if isinstance(exc, ValueError):
            raise HTTPException(400, str(exc))
        logger.exception("Spark OS error")
        raise HTTPException(500, str(exc))

    # ── Architecture ──────────────────────────────────────────────────

    @router.post("/architecture")
    def design(request: Request, body: DesignBody):
        owner = _owner(request)
        try:
            if body.services:
                spec = os_service.designer.from_template(
                    body.name,
                    services=body.services,
                    apis=body.apis,
                    databases=body.databases,
                    owner=owner,
                )
                if body.project_id:
                    spec.project_id = body.project_id
                    os_service.designer.save(spec)
                return spec.to_dict()
            return os_service.design_architecture(
                body.name,
                description=body.description,
                owner=owner,
                project_id=body.project_id,
                nodes=body.nodes,
                edges=body.edges,
            )
        except Exception as e:
            _err(e)

    @router.get("/architecture")
    def list_arch(request: Request):
        owner = _owner(request)
        return {"architectures": [s.to_dict() for s in os_service.designer.list(owner=owner)]}

    @router.get("/architecture/{architecture_id}")
    def get_arch(request: Request, architecture_id: str):
        spec = os_service.designer.load(architecture_id)
        if not spec:
            raise HTTPException(404, "Architecture not found")
        return spec.to_dict()

    @router.post("/architecture/compile")
    def compile_arch(request: Request, body: CompileBody):
        owner = _owner(request)
        try:
            return os_service.compile_architecture(
                body.architecture_id,
                body.target_root,
                owner=owner,
                generate_twin=body.generate_twin,
                run_review=body.run_review,
            )
        except Exception as e:
            _err(e)

    # ── Requirements ──────────────────────────────────────────────────

    @router.get("/requirements/{twin_id}")
    def list_reqs(request: Request, twin_id: str):
        try:
            return os_service.list_requirements(twin_id, owner=_owner(request))
        except Exception as e:
            _err(e)

    @router.post("/requirements/{twin_id}")
    def link_req(request: Request, twin_id: str, body: RequirementBody):
        try:
            return os_service.link_requirement(
                twin_id,
                body.model_dump(),
                owner=_owner(request),
            )
        except Exception as e:
            _err(e)

    @router.get("/requirements/{twin_id}/trace/{requirement_id}")
    def trace_req(request: Request, twin_id: str, requirement_id: str):
        try:
            return os_service.trace_requirement(twin_id, requirement_id, owner=_owner(request))
        except Exception as e:
            _err(e)

    # ── Review ────────────────────────────────────────────────────────

    @router.post("/review/{twin_id}")
    def review(request: Request, twin_id: str):
        try:
            return os_service.review_architecture(twin_id, owner=_owner(request))
        except Exception as e:
            _err(e)

    # ── Agents ────────────────────────────────────────────────────────

    @router.post("/agents/{twin_id}/bootstrap")
    def agent_boot(request: Request, twin_id: str):
        try:
            return os_service.agent_bootstrap(twin_id, owner=_owner(request))
        except Exception as e:
            _err(e)

    @router.get("/agents/{project_id}/status")
    def agent_status(request: Request, project_id: str):
        return os_service.agent_status(project_id)

    @router.post("/agents/{project_id}/message")
    def agent_msg(request: Request, project_id: str, body: AgentMsgBody):
        return os_service.agent_message(project_id, body.model_dump())

    @router.post("/agents/{project_id}/approve/{message_id}")
    def agent_approve(request: Request, project_id: str, message_id: str):
        return os_service.agents.approve(project_id, message_id)

    # ── Time machine ──────────────────────────────────────────────────

    @router.get("/timeline/{twin_id}")
    def timeline(request: Request, twin_id: str, project_id: Optional[str] = None):
        return os_service.timeline_history(twin_id, project_id=project_id)

    @router.get("/timeline/{twin_id}/scrub/{revision}")
    def scrub(request: Request, twin_id: str, revision: int, prior: Optional[int] = None):
        return os_service.timeline_scrub(twin_id, revision, prior=prior)

    # ── Simulation ────────────────────────────────────────────────────

    @router.post("/simulate/{twin_id}")
    def simulate(request: Request, twin_id: str, body: SimulateBody):
        try:
            return os_service.simulate(
                twin_id,
                body.proposal,
                owner=_owner(request),
                focus_node_id=body.focus_node_id,
            )
        except Exception as e:
            _err(e)

    # ── Org memory ────────────────────────────────────────────────────

    @router.get("/memory/search")
    def memory_search(request: Request, q: str = "", limit: int = 15):
        return os_service.memory_retrieve(q, limit=limit)

    @router.post("/memory/learn/{twin_id}")
    def memory_learn(request: Request, twin_id: str):
        try:
            return os_service.memory_learn(twin_id, owner=_owner(request))
        except Exception as e:
            _err(e)

    # ── Runtime viz ───────────────────────────────────────────────────

    @router.get("/runtime/{twin_id}/visualization")
    def runtime_viz(request: Request, twin_id: str):
        try:
            return os_service.runtime_visualization(twin_id, owner=_owner(request))
        except Exception as e:
            _err(e)

    # ── Marketplace ───────────────────────────────────────────────────

    @router.get("/marketplace")
    def market_list(request: Request, category: Optional[str] = None, q: Optional[str] = None):
        return os_service.marketplace_list(category=category, q=q)

    @router.get("/marketplace/{slug}")
    def market_get(request: Request, slug: str):
        try:
            return os_service.marketplace_get(slug)
        except Exception as e:
            _err(e)

    @router.post("/marketplace/{slug}/use")
    def market_use(request: Request, slug: str, name: Optional[str] = None):
        try:
            return os_service.marketplace_use(slug, owner=_owner(request), name=name)
        except Exception as e:
            _err(e)

    # ── Refactor ──────────────────────────────────────────────────────

    @router.get("/refactor/catalog")
    def refactor_catalog(request: Request):
        return os_service.refactor_catalog()

    @router.post("/refactor/{twin_id}")
    def refactor(request: Request, twin_id: str, body: RefactorBody):
        try:
            if body.full_pipeline:
                return os_service.refactor_pipeline(
                    twin_id, body.transformation, owner=_owner(request)
                )
            return os_service.refactor_propose(
                twin_id, body.transformation, owner=_owner(request)
            )
        except Exception as e:
            _err(e)

    # ── Health / overview ─────────────────────────────────────────────

    @router.get("/status")
    def status(request: Request):
        return {
            "ok": True,
            "capabilities": [
                "architecture_first",
                "living_requirements",
                "design_review",
                "multi_agent",
                "time_machine",
                "simulation",
                "org_memory",
                "runtime_visualization",
                "marketplace",
                "autonomous_refactoring",
            ],
            "canonical_model": "semantic_twin",
        }

    return router
