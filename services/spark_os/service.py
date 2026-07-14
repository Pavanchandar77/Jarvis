"""
SparkOSService — unified facade for all Phase-2 OS capabilities.

Everything flows through SemanticTwinService; no parallel source-of-truth.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.semantic_twin.models import GenerationManifest, SemanticTwin
from services.semantic_twin.service import SemanticTwinService

from .agents.workspace import AgentWorkspace
from .architecture.compiler import ArchitectureCompiler
from .architecture.designer import ArchitectureDesigner
from .architecture.sync import ArchitectureTwinSync
from .events import OSEventLog
from .marketplace.catalog import ArchitectureMarketplace
from .memory.org_memory import OrgKnowledgeMemory
from .models import LivingRequirement
from .refactor.pipeline import RefactorPipeline
from .requirements.graph import RequirementGraph
from .requirements.tracer import RequirementTracer
from .review.engine import ArchitectureReviewEngine
from .runtime.visualization import RuntimeVisualizer
from .simulation.engine import SimulationEngine
from .timemachine.engine import ProjectTimeMachine

logger = logging.getLogger(__name__)


class SparkOSService:
    def __init__(
        self,
        twin_service: SemanticTwinService,
        *,
        os_dir: str | Path,
        integration=None,
    ) -> None:
        self.twins = twin_service
        self.integration = integration
        self.os_dir = Path(os_dir)
        self.os_dir.mkdir(parents=True, exist_ok=True)

        arch_dir = self.os_dir / "architectures"
        self.designer = ArchitectureDesigner(arch_dir)
        self.compiler = ArchitectureCompiler()
        self.arch_sync = ArchitectureTwinSync()
        self.requirements = RequirementGraph()
        self.req_tracer = RequirementTracer()
        self.review = ArchitectureReviewEngine()
        self.agents = AgentWorkspace(self.os_dir / "agent_workspaces")
        self.events = OSEventLog(self.os_dir)
        timeline = integration.timeline if integration else None
        self.timemachine = ProjectTimeMachine(timeline, event_log=self.events) if timeline else None
        self.simulation = SimulationEngine(self.os_dir / "simulations")
        self.memory = OrgKnowledgeMemory(self.os_dir / "org_memory")
        runtime_ingestor = integration.runtime if integration else None
        self.runtime_viz = RuntimeVisualizer(runtime_ingestor)
        self.marketplace = ArchitectureMarketplace(self.designer)
        self.refactor = RefactorPipeline(
            self.os_dir / "refactors",
            self.simulation,
            self.review,
        )

    # ── Capability 1: Architecture-first ──────────────────────────────

    def design_architecture(self, name: str, **kwargs) -> Dict[str, Any]:
        spec = self.designer.create(name, **kwargs)
        pid = kwargs.get("project_id") or "global"
        self.events.emit(pid, "arch.designed", {"architecture_id": spec.architecture_id})
        return spec.to_dict()

    def compile_architecture(
        self,
        architecture_id: str,
        target_root: str,
        *,
        owner: Optional[str] = None,
        generate_twin: bool = True,
        run_review: bool = True,
    ) -> Dict[str, Any]:
        spec = self.designer.load(architecture_id)
        if not spec:
            raise FileNotFoundError(f"architecture not found: {architecture_id}")

        # Org memory guidance
        mem = self.memory.inject_for_generation(spec.name + " " + " ".join(n.kind for n in spec.nodes[:10]))
        compiled = self.compiler.compile(spec, target_root=target_root, write=True)
        manifest = GenerationManifest.from_dict(compiled["manifest"])
        manifest.metadata = {**(manifest.metadata or {}), **mem}

        result: Dict[str, Any] = {
            "architecture_id": architecture_id,
            "compiled": {k: v for k, v in compiled.items() if k != "file_contents"},
            "org_memory": mem,
        }

        twin = None
        if generate_twin:
            twin = self.twins.generate(
                target_root,
                manifest,
                application_id=spec.project_id or architecture_id[:16],
                application_name=spec.name,
                owner=owner,
                persist=True,
            )
            twin = self.arch_sync.apply_spec_to_twin(twin, spec)
            twin = self.requirements.from_manifest(twin)
            if run_review:
                report = self.review.review(twin, attach_to_twin=True)
                result["review"] = report.to_dict()
                self.memory.learn_from_twin(twin, review=report.to_dict())
            else:
                self.memory.learn_from_twin(twin)
            self.twins.repo.save(twin)
            spec.twin_id = twin.twin_id
            self.designer.save(spec)
            if self.integration:
                self.integration.registry.register(
                    project_id=twin.application_id,
                    name=spec.name,
                    app_root=str(Path(target_root).resolve()),
                    twin_id=twin.twin_id,
                    owner=owner,
                    revision=twin.content_revision,
                )
                self.integration.timeline.record(twin, trigger="arch_compile", label=f"compile {spec.name}")
                self.agents.bootstrap(twin.application_id, twin)
            result["twin_id"] = twin.twin_id
            result["twin_meta"] = twin.meta.to_dict()
            self.events.emit(
                twin.application_id,
                "arch.compiled",
                {"architecture_id": architecture_id, "twin_id": twin.twin_id, "files": compiled["files"]},
            )
        return result

    # ── Capability 2: Living requirements ─────────────────────────────

    def link_requirement(
        self,
        twin_id: str,
        requirement: Dict[str, Any],
        *,
        owner: Optional[str] = None,
    ) -> Dict[str, Any]:
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        req = LivingRequirement(
            id=requirement["id"] if "id" in requirement else requirement.get("text", "req")[:32],
            text=requirement.get("text") or "",
            requested_by=requirement.get("requested_by", "user"),
            prompt_id=requirement.get("prompt_id"),
            artifact_ids=list(requirement.get("artifact_ids") or []),
            priority=requirement.get("priority", "medium"),
        )
        twin = self.requirements.upsert_requirements(twin, [req])
        self.twins.repo.save(twin)
        self.events.emit(twin.application_id, "req.linked", {"requirement_id": req.id})
        return {"ok": True, "requirement": req.to_dict()}

    def trace_requirement(self, twin_id: str, requirement_id: str, *, owner: Optional[str] = None) -> Dict[str, Any]:
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        return self.req_tracer.trace(twin, requirement_id)

    def list_requirements(self, twin_id: str, *, owner: Optional[str] = None) -> Dict[str, Any]:
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        twin = self.requirements.from_manifest(twin)
        reqs = self.requirements.extract_from_twin(twin)
        return {"twin_id": twin_id, "requirements": [r.to_dict() for r in reqs]}

    # ── Capability 3: Design review ───────────────────────────────────

    def review_architecture(self, twin_id: str, *, owner: Optional[str] = None, persist: bool = True) -> Dict[str, Any]:
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        report = self.review.review(twin, attach_to_twin=persist)
        if persist:
            self.twins.repo.save(twin)
            self.memory.learn_from_twin(twin, review=report.to_dict())
        self.events.emit(twin.application_id, "review.completed", {
            "review_id": report.review_id,
            "overall": report.overall,
        })
        return report.to_dict()

    # ── Capability 4: Multi-agent ─────────────────────────────────────

    def agent_bootstrap(self, twin_id: str, *, owner: Optional[str] = None) -> Dict[str, Any]:
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        state = self.agents.bootstrap(twin.application_id, twin)
        self.twins.repo.save(twin)
        return state

    def agent_status(self, project_id: str) -> Dict[str, Any]:
        return self.agents.status(project_id)

    # ── Capability 5: Time machine ────────────────────────────────────

    def timeline_history(self, twin_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.timemachine:
            return {"twin_id": twin_id, "versions": [], "error": "timeline unavailable"}
        return self.timemachine.history(twin_id, project_id=project_id)

    def timeline_scrub(self, twin_id: str, revision: int, prior: Optional[int] = None) -> Dict[str, Any]:
        if not self.timemachine:
            return {"error": "timeline unavailable"}
        return self.timemachine.scrub(twin_id, revision, prior_revision=prior)

    # ── Capability 6: Simulation ──────────────────────────────────────

    def simulate(self, twin_id: str, proposal: str, *, owner: Optional[str] = None, focus_node_id: Optional[str] = None) -> Dict[str, Any]:
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        report = self.simulation.simulate(twin, proposal, focus_node_id=focus_node_id)
        self.events.emit(twin.application_id, "sim.completed", {
            "simulation_id": report.simulation_id,
            "risk": report.risk_level,
        })
        return report.to_dict()

    # ── Capability 7: Org memory ──────────────────────────────────────

    def memory_retrieve(self, query: str, **kwargs) -> Dict[str, Any]:
        return {"hits": self.memory.retrieve(query, **kwargs)}

    def memory_learn(self, twin_id: str, *, owner: Optional[str] = None) -> Dict[str, Any]:
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        learned = self.memory.learn_from_twin(twin)
        self.events.emit(twin.application_id, "memory.learned", {"count": len(learned)})
        return {"learned": [p.to_dict() for p in learned]}

    # ── Capability 8: Runtime viz ─────────────────────────────────────

    def runtime_visualization(self, twin_id: str, *, owner: Optional[str] = None) -> Dict[str, Any]:
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        return self.runtime_viz.live_overlay(twin)

    # ── Capability 9: Marketplace ─────────────────────────────────────

    def marketplace_list(self, **kwargs) -> Dict[str, Any]:
        return {"architectures": self.marketplace.list(**kwargs)}

    def marketplace_get(self, slug: str) -> Dict[str, Any]:
        item = self.marketplace.get(slug)
        if not item:
            raise FileNotFoundError(slug)
        return item

    def marketplace_use(self, slug: str, *, owner: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
        result = self.marketplace.instantiate(slug, name=name, owner=owner)
        if not result:
            raise FileNotFoundError(slug)
        return result

    # ── Capability 10: Refactor ───────────────────────────────────────

    def refactor_catalog(self) -> Dict[str, Any]:
        return {"transformations": self.refactor.catalog()}

    def refactor_propose(self, twin_id: str, transformation: str, *, owner: Optional[str] = None) -> Dict[str, Any]:
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        plan = self.refactor.propose(twin, transformation)
        self.events.emit(twin.application_id, "refactor.proposed", {"plan_id": plan.plan_id})
        return plan.to_dict()

    def refactor_pipeline(
        self,
        twin_id: str,
        transformation: str,
        *,
        owner: Optional[str] = None,
        apply_meta: bool = True,
    ) -> Dict[str, Any]:
        """Full: analyze/simulate/review/estimate/migrate/validate/update twin meta."""
        twin = self.twins.load(twin_id, owner=owner, include_graph=True)
        plan = self.refactor.propose(twin, transformation)
        risk = self.refactor.estimate_risk(plan.plan_id)
        migration = self.refactor.generate_migration(plan.plan_id)
        validation = self.refactor.validate(plan.plan_id, twin)
        if apply_meta:
            twin = self.refactor.apply_to_twin_metadata(plan.plan_id, twin)
            self.twins.repo.save(twin)
        return {
            "plan": self.refactor.load(plan.plan_id),
            "risk": risk,
            "migration": migration,
            "validation": validation,
        }

    def agent_message(self, project_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        from .agents.protocol import AgentProtocol
        proto = AgentProtocol()
        msg = proto.create(
            from_agent=message.get("from_agent") or "system",
            to_agent=message.get("to_agent") or "broadcast",
            type=message.get("type") or "info",
            region_node_ids=message.get("region_node_ids"),
            payload=message.get("payload"),
            requires_approval=bool(message.get("requires_approval")),
        )
        result = self.agents.post_message(project_id, msg)
        self.events.emit(project_id, "agent.intent", {"message_id": msg.id, "type": msg.type})
        return result
