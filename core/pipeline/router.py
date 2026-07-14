# core/pipeline/router.py
"""Spark Pipeline Intelligent Model Router.

Selects the optimal model for a task based on capability requirements, hardware
capacities, and historical DNA telemetry. Avoids resource over-allocation by
routing simple tasks to smaller models.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .capability import RequiredCapabilities
from core.engine.fingerprint import HardwareFingerprinter, HardwareProfile
from core.engine.dna import ExecutionDNADatabase

logger = logging.getLogger("spark.pipeline.router")


class ModelRouter:
    """Orchestrates model selection based on capabilities and hardware profile constraints."""

    def __init__(
        self,
        fingerprinter: Optional[HardwareFingerprinter] = None,
        dna_db: Optional[ExecutionDNADatabase] = None,
    ):
        self._fingerprinter = fingerprinter or HardwareFingerprinter()
        self._dna_db = dna_db or ExecutionDNADatabase()

    def route_task(
        self,
        capabilities: RequiredCapabilities,
        models_registry: List[Dict[str, Any]],
        system_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Choose the optimal model matching the task's capability demands."""
        hw = self._fingerprinter.get_profile()
        
        candidates = []
        for model in models_registry:
            name = model.get("name", "")
            dna = self._dna_db.get_dna(name)
            
            # Check context size eligibility
            model_ctx = model.get("context_length", 2048) or 2048
            if model_ctx < capabilities.min_context_window:
                continue

            # Weight candidates by parameter sizing & success history
            params_raw = model.get("parameters_raw", 0)
            params_b = params_raw / 1e9 if params_raw else 0
            
            score = 100.0
            
            # Routing logic: prefer smaller models for simple tasks, larger for complex
            if capabilities.code_generation or capabilities.planning:
                # Code generation needs reasoning power (prefer >30B parameters)
                if params_b < 30.0:
                    score -= 40.0
            else:
                # General task: prefer small models (<15B parameters) to save memory/latency
                if params_b > 15.0:
                    score -= 30.0

            # Boost models with successful history DNA
            if dna.runs_completed > 0:
                score += min(dna.average_tps * 2.0, 20.0)

            candidates.append((score, model))

        if not candidates:
            # Fallback to the first model in registry
            logger.warning("Pipeline Router: No registry candidate met criteria, using default fallback.")
            return models_registry[0]

        # Sort candidates (highest score first)
        candidates.sort(key=lambda x: x[0], reverse=True)
        chosen = candidates[0][1]
        
        logger.info(
            "Pipeline Router: Routed task to model '%s' (score: %.1f)",
            chosen.get("name"), candidates[0][0]
        )
        return chosen
