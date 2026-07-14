"""Autonomous Refactoring — analyze → simulate → review → risk → migrate → validate → twin."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.semantic_twin.models import SemanticTwin

from ..models import RefactorPlan
from ..simulation.engine import SimulationEngine
from ..review.engine import ArchitectureReviewEngine
from ..storage.store import ensure_dir, read_json, write_json


_TRANSFORMATIONS = {
    "monolith_to_microservices": {
        "title": "Convert monolith to microservices",
        "steps": [
            "Identify bounded contexts from modules/packages",
            "Extract service boundaries and data ownership",
            "Introduce API gateway / BFF",
            "Split databases per context",
            "Add inter-service contracts and observability",
        ],
    },
    "modularize_frontend": {
        "title": "Modularize frontend",
        "steps": [
            "Map components to feature domains",
            "Extract shared design system",
            "Introduce lazy-loaded route modules",
            "Isolate state per feature",
        ],
    },
    "rest_to_graphql": {
        "title": "Replace REST with GraphQL",
        "steps": [
            "Inventory REST endpoints",
            "Design GraphQL schema",
            "Add gateway and resolvers",
            "Deprecate REST with dual-run period",
        ],
    },
    "migrate_sql": {
        "title": "Migrate SQL database",
        "steps": [
            "Capture schema and query inventory",
            "Plan dual-write / expand-contract",
            "Migrate data with validation",
            "Cut over connections",
        ],
    },
    "introduce_cqrs": {
        "title": "Introduce CQRS",
        "steps": [
            "Separate read/write models",
            "Add command handlers",
            "Build read projections",
            "Align APIs with commands/queries",
        ],
    },
    "event_sourcing": {
        "title": "Event sourcing",
        "steps": [
            "Define domain events",
            "Introduce event store",
            "Rebuild projections",
            "Retire mutable state paths",
        ],
    },
    "introduce_caching": {
        "title": "Introduce caching",
        "steps": [
            "Profile hot read paths",
            "Choose cache keys and TTLs",
            "Add invalidation strategy",
            "Measure hit rate and consistency",
        ],
    },
}


class RefactorPipeline:
    def __init__(
        self,
        store_dir: str | Path,
        simulation: SimulationEngine,
        review: ArchitectureReviewEngine,
    ) -> None:
        self.store = ensure_dir(store_dir)
        self.simulation = simulation
        self.review = review

    def catalog(self) -> List[Dict[str, Any]]:
        return [
            {"id": k, "title": v["title"], "steps": v["steps"]}
            for k, v in _TRANSFORMATIONS.items()
        ]

    def propose(
        self,
        twin: SemanticTwin,
        transformation: str,
        *,
        custom_steps: Optional[List[str]] = None,
    ) -> RefactorPlan:
        meta = _TRANSFORMATIONS.get(transformation) or {
            "title": transformation,
            "steps": custom_steps or [f"Apply transformation: {transformation}"],
        }
        sim = self.simulation.simulate(
            twin,
            f"Architectural transformation: {meta['title']}",
            persist=True,
        )
        # Review current twin as baseline risk context
        report = self.review.review(twin, attach_to_twin=False)

        plan = RefactorPlan(
            plan_id=uuid.uuid4().hex,
            twin_id=twin.twin_id,
            transformation=transformation,
            steps=[
                {"order": i + 1, "title": s, "status": "pending"}
                for i, s in enumerate(meta["steps"])
            ],
            simulation=sim.to_dict(),
            review=report.to_dict(),
            risk_level=sim.risk_level if sim.risk_level != "low" else (
                "high" if report.overall < 0.5 else "medium" if report.overall < 0.7 else "low"
            ),
            status="proposed",
            metadata={"title": meta["title"], "baseline_score": report.overall},
        )
        write_json(self.store / f"{plan.plan_id}.json", plan.to_dict())
        return plan

    def estimate_risk(self, plan_id: str) -> Dict[str, Any]:
        data = read_json(self.store / f"{plan_id}.json")
        if not data:
            return {"error": "plan not found"}
        sim = data.get("simulation") or {}
        review = data.get("review") or {}
        return {
            "plan_id": plan_id,
            "risk_level": data.get("risk_level"),
            "simulation_risk": sim.get("risk_level"),
            "effort_days": sim.get("estimated_effort_days"),
            "broken_apis": sim.get("broken_apis"),
            "review_overall": review.get("overall"),
            "recommendation": (
                "Proceed with phased migration and feature flags"
                if data.get("risk_level") != "high"
                else "Require architect approval and staged rollout"
            ),
        }

    def generate_migration(self, plan_id: str) -> Dict[str, Any]:
        data = read_json(self.store / f"{plan_id}.json")
        if not data:
            return {"error": "plan not found"}
        data["status"] = "migrating"
        for step in data.get("steps") or []:
            step["status"] = "planned"
            step["artifacts"] = [
                f"migration/{_slug(step.get('title', 'step'))}.md",
            ]
        migration = {
            "plan_id": plan_id,
            "files": [
                {
                    "path": f"migration/{i+1:02d}_{_slug(s.get('title', 'step'))}.md",
                    "content": f"# {s.get('title')}\n\nStatus: planned\n\nGenerated by Spark Refactor Pipeline.\n",
                }
                for i, s in enumerate(data.get("steps") or [])
            ],
            "checklist": [s.get("title") for s in data.get("steps") or []],
        }
        data["migration"] = migration
        write_json(self.store / f"{plan_id}.json", data)
        return migration

    def validate(self, plan_id: str, twin: SemanticTwin) -> Dict[str, Any]:
        data = read_json(self.store / f"{plan_id}.json")
        if not data:
            return {"error": "plan not found"}
        report = self.review.review(twin, attach_to_twin=False)
        baseline = (data.get("metadata") or {}).get("baseline_score", 0.5)
        improved = report.overall >= baseline - 0.05
        data["status"] = "validated" if improved else "proposed"
        data["validation"] = {
            "baseline": baseline,
            "current": report.overall,
            "passed": improved,
            "findings": len(report.findings),
        }
        write_json(self.store / f"{plan_id}.json", data)
        return data["validation"]

    def apply_to_twin_metadata(self, plan_id: str, twin: SemanticTwin) -> SemanticTwin:
        """Mark twin with applied refactor (no code write — orchestration leaves writes to agents)."""
        data = read_json(self.store / f"{plan_id}.json")
        if not data:
            return twin
        data["status"] = "applied"
        write_json(self.store / f"{plan_id}.json", data)
        twin.manifest.metadata = dict(twin.manifest.metadata or {})
        twin.manifest.metadata["last_refactor_plan"] = plan_id
        twin.manifest.metadata["last_refactor"] = data.get("transformation")
        return twin

    def load(self, plan_id: str) -> Optional[Dict[str, Any]]:
        return read_json(self.store / f"{plan_id}.json")


def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")[:40] or "step"
