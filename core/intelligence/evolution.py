# core/intelligence/evolution.py
"""Spark Knowledge Evolution & Policy Promotion Pipeline.

Mines historical execution databases to discover successful orchestration topologies,
and automatically promotes candidate policies if offline benchmarks show improvements.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .policy import ExecutionPolicy, PolicyEngine
from .evaluator import OfflineEvaluator
from .warehouse import PerformanceWarehouse

logger = logging.getLogger("spark.intelligence.evolution")


@dataclass
class PromotionLog:
    """Audit log entry for a policy promotion event."""
    policy_id: str
    old_version: int
    new_version: int
    promotion_ts: float
    benchmark_score: float


class KnowledgeEvolutionEngine:
    """Mines traces for reusable topological patterns and promotes validated policies."""

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        evaluator: Optional[OfflineEvaluator] = None,
        warehouse: Optional[PerformanceWarehouse] = None,
    ):
        self._policy_engine = policy_engine or PolicyEngine()
        self._evaluator = evaluator or OfflineEvaluator()
        self._warehouse = warehouse or PerformanceWarehouse()
        self._promotion_history: List[PromotionLog] = []

    def run_evolution_cycle(self, policy_id: str, candidate: ExecutionPolicy) -> bool:
        """Run an autonomous check to promote candidate policies if they pass validation.

        - Executes offline benchmarks on the candidate.
        - Compares success rates against the current active policy.
        - If candidate performs better, it is promoted to production.
        """
        logger.info("Knowledge Evolution Engine: Starting evaluation cycle for '%s'...", policy_id)
        
        current = self._policy_engine.get_policy(policy_id)
        
        # 1. Benchmark current policy
        score_current = self._evaluator.run_benchmark(current).get("success_rate", 0.0)
        
        # 2. Benchmark candidate policy
        score_candidate = self._evaluator.run_benchmark(candidate).get("success_rate", 0.0)
        
        logger.info("Evaluation results: Current score: %.2f, Candidate score: %.2f", score_current, score_candidate)
        
        # 3. Promote only if candidate outperforms control
        if score_candidate > score_current:
            logger.info("Knowledge Evolution Engine: CANDIDATE PROMOTED to active policy!")
            self._policy_engine.update_policy(candidate)
            self._promotion_history.append(PromotionLog(
                policy_id=policy_id,
                old_version=current.version,
                new_version=candidate.version,
                promotion_ts=time.time(),
                benchmark_score=score_candidate
            ))
            return True
        else:
            logger.info("Knowledge Evolution Engine: Promotion rejected (Candidate did not beat control).")
            return False

    def get_promotion_logs(self) -> List[PromotionLog]:
        return list(self._promotion_history)
