# core/pipeline/reasoning.py
"""Spark Adaptive Reasoning Controller.

Tunes reasoning depth and refinement iterations dynamically based on task complexity
and budget metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("spark.pipeline.reasoning")


@dataclass
class ReasoningConfig:
    """Tuning parameters for the reasoning controller."""
    max_iterations: int
    enable_chain_of_thought: bool
    self_correction_threshold: float


class ReasoningController:
    """Controls the search and validation iterations during task execution."""

    def determine_config(self, complexity: float, budget: str) -> ReasoningConfig:
        # High complexity or high compute budget yields deeper reasoning iterations
        if complexity >= 0.7 or budget == "high":
            config = ReasoningConfig(
                max_iterations=4,
                enable_chain_of_thought=True,
                self_correction_threshold=0.85
            )
        elif complexity >= 0.4 or budget == "medium":
            config = ReasoningConfig(
                max_iterations=2,
                enable_chain_of_thought=True,
                self_correction_threshold=0.70
            )
        else:
            config = ReasoningConfig(
                max_iterations=1,
                enable_chain_of_thought=False,
                self_correction_threshold=0.0
            )
            
        logger.info(
            "Reasoning Controller: Selected config: max_iter=%d, cot=%s",
            config.max_iterations, config.enable_chain_of_thought
        )
        return config
