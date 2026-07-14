# core/intelligence/meta_router.py
"""Spark Meta-Router.

Routes incoming tasks to distinct specialized routing policies (e.g., Code-Router,
Reasoning-Router, summarisation-Router) depending on intent classification.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .policy import ExecutionPolicy, PolicyEngine

logger = logging.getLogger("spark.intelligence.meta_router")


class MetaRouter:
    """Intelligently matches task intents to specialized routing strategies."""

    def __init__(self, policy_engine: Optional[PolicyEngine] = None):
        self._policy_engine = policy_engine or PolicyEngine()

    def select_routing_policy(self, intent: str) -> ExecutionPolicy:
        """Select the optimal routing policy based on request classification."""
        logger.info("Meta-Router: Selecting routing strategy for intent '%s'...", intent)
        
        if intent == "coding":
            # Select policy tuned for code syntax and DAG planning
            return self._policy_engine.get_policy("coding_routing")
        elif intent == "reasoning":
            # Select policy tuned for logic verification and CoT depth
            return self._policy_engine.get_policy("reasoning_routing")
        else:
            # Select standard general routing
            return self._policy_engine.get_policy("routing")
