# core/engine/intent_cache.py
"""Spark Intent-Based Cache Manager.

Categorises inference requests into high-level user intents (coding, reasoning,
summarisation, math, translation) to dynamically adjust cache sizes, prefetch
depths, and pin optimal model hot zones.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Set

from .cache import CacheManager

logger = logging.getLogger("spark.engine.intent_cache")


class UserIntent(Enum):
    GENERAL       = auto()
    CODING        = auto()
    REASONING     = auto()
    MATHEMATICS   = auto()
    SUMMARISATION = auto()
    TRANSLATION   = auto()


@dataclass
class IntentPolicy:
    """Cache tuning parameters defined per intent."""
    intent: UserIntent
    base_cache_budget_bytes: int
    prefetch_depth: int
    pin_attention_blocks: bool
    pin_first_n_layers: int
    pin_last_n_layers: int
    moe_experts_warm_count: int


class IntentBasedCacheManager:
    """Adapts CacheManager behavior based on the semantic intent of the query."""

    def __init__(self, cache_manager: CacheManager):
        self._cache_mgr = cache_manager
        self._current_intent = UserIntent.GENERAL
        
        # Load default policy parameters per intent
        self._policies: Dict[UserIntent, IntentPolicy] = {
            UserIntent.GENERAL: IntentPolicy(
                intent=UserIntent.GENERAL,
                base_cache_budget_bytes=2 * 1024**3,
                prefetch_depth=2,
                pin_attention_blocks=False,
                pin_first_n_layers=1,
                pin_last_n_layers=1,
                moe_experts_warm_count=2,
            ),
            UserIntent.CODING: IntentPolicy(
                intent=UserIntent.CODING,
                base_cache_budget_bytes=4 * 1024**3,  # Double cache size for heavy routing
                prefetch_depth=3,
                pin_attention_blocks=True,
                pin_first_n_layers=3,
                pin_last_n_layers=2,
                moe_experts_warm_count=8,  # Pin coding-specific experts
            ),
            UserIntent.REASONING: IntentPolicy(
                intent=UserIntent.REASONING,
                base_cache_budget_bytes=3 * 1024**3,
                prefetch_depth=4,  # Deep prefetch for long thinking traces
                pin_attention_blocks=True,
                pin_first_n_layers=4,
                pin_last_n_layers=2,
                moe_experts_warm_count=4,
            ),
            UserIntent.SUMMARISATION: IntentPolicy(
                intent=UserIntent.SUMMARISATION,
                base_cache_budget_bytes=5 * 1024**3,  # Large KV cache budget
                prefetch_depth=2,
                pin_attention_blocks=True,            # Keep attention keys warm
                pin_first_n_layers=2,
                pin_last_n_layers=4,                  # Pin decoding layers
                moe_experts_warm_count=2,
            ),
        }

    def detect_intent(self, prompt: str) -> UserIntent:
        """Classify a prompt into a UserIntent category using keyword heuristics."""
        prompt_lower = prompt.lower()
        
        # Code heuristics
        if any(w in prompt_lower for w in ["def ", "class ", "import ", "python", "javascript", "code", "bug", "rust", "compile"]):
            self._current_intent = UserIntent.CODING
        # Math heuristics
        elif any(w in prompt_lower for w in ["solve", "equation", "theorem", "math", "calculus", "integral", "derivative"]):
            self._current_intent = UserIntent.MATHEMATICS
        # Reasoning heuristics
        elif any(w in prompt_lower for w in ["think step by step", "reason", "logic", "conclude", "analyze", "why does"]):
            self._current_intent = UserIntent.REASONING
        # Summarisation heuristics
        elif any(w in prompt_lower for w in ["summarize", "tldr", "abstract", "shorten", "outline", "digest"]):
            self._current_intent = UserIntent.SUMMARISATION
        else:
            self._current_intent = UserIntent.GENERAL

        logger.info("Intent Cache: classified workload as %s", self._current_intent.name)
        return self._current_intent

    def apply_policy(self, intent: UserIntent, total_layers: int) -> List[str]:
        """Generate a list of block IDs that should be pinned based on the active policy."""
        policy = self._policies.get(intent, self._policies[UserIntent.GENERAL])
        pins = []

        # Pin First N Layers
        for i in range(policy.pin_first_n_layers):
            pins.append(f"layer.{i}.attention")
            pins.append(f"layer.{i}.mlp")

        # Pin Last N Layers
        for i in range(total_layers - policy.pin_last_n_layers, total_layers):
            pins.append(f"layer.{i}.attention")
            pins.append(f"layer.{i}.mlp")

        # Pin Attention projections
        if policy.pin_attention_blocks:
            for i in range(total_layers):
                pins.append(f"layer.{i}.self_attn.q_proj")
                pins.append(f"layer.{i}.self_attn.o_proj")

        return pins
