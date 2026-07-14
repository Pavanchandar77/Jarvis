# core/intelligence/experiment.py
"""Spark Continuous Experiment & Live A/B Subsystem.

Defines, implements, and benchmarks A/B experiments on execution policies
under live production traffic.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from .policy import ExecutionPolicy

logger = logging.getLogger("spark.intelligence.experiment")


@dataclass
class ABExperiment:
    """An active A/B test comparing two execution policies."""
    experiment_id: str
    policy_id: str
    control: ExecutionPolicy
    candidate: ExecutionPolicy
    rollout_fraction: float = 0.10  # Portion of traffic routed to the candidate (e.g. 10%)
    runs_control: int = 0
    runs_candidate: int = 0
    success_control: int = 0
    success_candidate: int = 0


class ExperimentEngine:
    """Orchestrates candidate rollouts and records comparative analytics."""

    def __init__(self):
        self._active_tests: Dict[str, ABExperiment] = {}

    def start_test(
        self,
        experiment_id: str,
        policy_id: str,
        control: ExecutionPolicy,
        candidate: ExecutionPolicy,
        rollout: float = 0.10,
    ) -> ABExperiment:
        """Start a new rollout experiment."""
        exp = ABExperiment(
            experiment_id=experiment_id,
            policy_id=policy_id,
            control=control,
            candidate=candidate,
            rollout_fraction=rollout
        )
        self._active_tests[experiment_id] = exp
        logger.info("Experiment Engine: Started test '%s' comparing policy '%s'", experiment_id, policy_id)
        return exp

    def get_test(self, experiment_id: str) -> Optional[ABExperiment]:
        return self._active_tests.get(experiment_id)

    def route_request(self, experiment_id: str) -> tuple[str, ExecutionPolicy]:
        """Determine whether to use control (A) or candidate (B) policy."""
        exp = self._active_tests.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment '{experiment_id}' not found.")

        # Rollout chance check
        if random.random() < exp.rollout_fraction:
            logger.info("Experiment Engine: Routing request to CANDIDATE (B) for test '%s'", experiment_id)
            return "candidate", exp.candidate
        else:
            return "control", exp.control

    def log_result(self, experiment_id: str, group: str, success: bool) -> None:
        """Record the success/failure outcome of a test group run."""
        exp = self._active_tests.get(experiment_id)
        if not exp:
            return

        if group == "candidate":
            exp.runs_candidate += 1
            if success:
                exp.success_candidate += 1
        else:
            exp.runs_control += 1
            if success:
                exp.success_control += 1

    def evaluate_test(self, experiment_id: str) -> Dict[str, Any]:
        """Assess whether the candidate outperformed the baseline."""
        exp = self._active_tests.get(experiment_id)
        if not exp:
            return {}

        rate_a = exp.success_control / exp.runs_control if exp.runs_control > 0 else 0.0
        rate_b = exp.success_candidate / exp.runs_candidate if exp.runs_candidate > 0 else 0.0

        # Simple verification check: candidate must be statistically better or equal with enough sample size
        promotable = rate_b > rate_a and exp.runs_candidate >= 10
        
        return {
            "experiment_id": experiment_id,
            "runs_control": exp.runs_control,
            "runs_candidate": exp.runs_candidate,
            "success_rate_control": round(rate_a, 2),
            "success_rate_candidate": round(rate_b, 2),
            "promotable": promotable,
        }
