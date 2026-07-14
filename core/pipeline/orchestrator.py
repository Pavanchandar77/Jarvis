# core/pipeline/orchestrator.py
"""Spark Multi-Model Orchestrator.

Implements complex multi-model interaction patterns (sequential pipelines, parallel
execution, draft-validation, reviews) based on the task DAG layout.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .planner import TaskNode

logger = logging.getLogger("spark.pipeline.orchestrator")


@dataclass
class OrchestrationStep:
    """A planned execution step for the orchestrator."""
    step_id: str
    target_model_name: str
    action: str                       # draft | validate | review | synthesize
    status: str = "pending"


class MultiModelOrchestrator:
    """Orchestrates sequential or parallel execution runs over multiple routed models."""

    def plan_topology(
        self,
        dag: List[TaskNode],
        primary_model: Dict[str, Any],
        validator_model: Optional[Dict[str, Any]] = None,
    ) -> List[OrchestrationStep]:
        """Convert a task DAG into a concrete multi-model execution sequence."""
        steps = []
        val_name = validator_model.get("name") if validator_model else primary_model.get("name", "unknown")
        prim_name = primary_model.get("name", "unknown")

        for node in dag:
            # For complex coding or design tasks, schedule a draft-verification loop
            if node.task_id in ("write_backend_code", "write_frontend_code", "design_architecture"):
                steps.append(OrchestrationStep(
                    step_id=f"{node.task_id}_draft",
                    target_model_name=prim_name,
                    action="draft"
                ))
                steps.append(OrchestrationStep(
                    step_id=f"{node.task_id}_validate",
                    target_model_name=val_name,
                    action="validate"
                ))
            else:
                # Standard sequential execution step
                steps.append(OrchestrationStep(
                    step_id=node.task_id,
                    target_model_name=prim_name,
                    action="draft"
                ))

        logger.info("Multi-Model Orchestrator: planned execution topology with %d steps.", len(steps))
        return steps
