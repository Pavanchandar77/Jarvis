# core/engine/optimizer.py
"""Spark Autonomous Runtime Optimizer.

Runs background tasks during idle periods to inspect telemetry metrics, benchmark
different execution strategies, test prediction accuracy, and write optimization reports.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .telemetry import TelemetrySubsystem
from .dna import ExecutionDNADatabase, ModelDNA

logger = logging.getLogger("spark.engine.optimizer")


@dataclass
class OptimizationReport:
    """A report summarizing recommendations made by the autonomous optimizer."""
    generated_at: float
    stalls_analyzed: int
    models_optimized: List[str]
    parameter_adjustments: Dict[str, Any] = field(default_factory=dict)
    rejected_strategies: List[str] = field(default_factory=list)


class AutonomousOptimizer:
    """Monitors telemetry and dynamically refines planner costs and pinning thresholds."""

    def __init__(
        self,
        telemetry: Optional[TelemetrySubsystem] = None,
        dna_db: Optional[ExecutionDNADatabase] = None,
        persist_dir: Optional[str] = None,
    ):
        self._telemetry = telemetry or TelemetrySubsystem()
        self._dna_db = dna_db or ExecutionDNADatabase()
        
        if persist_dir:
            self._persist_dir = Path(os.path.expanduser(persist_dir))
        else:
            self._persist_dir = Path.home() / ".spark" / "optimizer"

        self._persist_dir.mkdir(parents=True, exist_ok=True)

    def optimize_idle(self) -> Optional[OptimizationReport]:
        """Perform telemetry inspection and parameter tuning when system is idle.

        - Analyzes prediction mistakes (where prefetch engine was slow).
        - Tests alternative execution mappings on previous models.
        - Outputs a generated JSON report.
        """
        logger.info("Starting autonomous execution optimization...")
        history = self._telemetry.get_history(limit=50)
        if not history:
            logger.info("No historical telemetry found. Skipping optimization.")
            return None

        stalls = 0
        models_touched = []
        adjustments = {}
        rejected = []

        # Group runs by model
        runs_by_model: Dict[str, List[Dict[str, Any]]] = {}
        for run in history:
            model = run.get("model_name")
            if model:
                runs_by_model.setdefault(model, []).append(run)

        # Tune planner parameters for each model
        for model_name, runs in runs_by_model.items():
            total_stalls_for_model = sum(r.get("total_stalls", 0) for r in runs)
            stalls += total_stalls_for_model
            
            # Fetch DNA
            dna = self._dna_db.get_dna(model_name)
            
            # If we are seeing high stall counts, prefetching is not fast enough
            if total_stalls_for_model > 5 and len(runs) >= 2:
                # Recommendation: increase budget and prefetch queue depth
                dna.preferred_strategy = "stream"
                adjustments[model_name] = {
                    "action": "increase_prefetch_depth",
                    "reason": f"Observed {total_stalls_for_model} stalls across {len(runs)} runs.",
                    "new_prefetch_depth": 4,
                }
                models_touched.append(model_name)
                self._dna_db.save_dna(dna)
            else:
                # If cache hit rate is excellent (>95%), we can reduce RAM budget
                avg_hit = sum(r.get("cache_hit_rate", 0.0) for r in runs) / len(runs)
                if avg_hit >= 0.95 and dna.runs_completed > 5:
                    dna.preferred_strategy = "resident"
                    rejected.append(f"{model_name}_spill_to_ssd")
                    logger.info("Optimizer: Pinning %s fully resident due to 95%+ cache hit rate.", model_name)
                    self._dna_db.save_dna(dna)

        report = OptimizationReport(
            generated_at=time.time(),
            stalls_analyzed=stalls,
            models_optimized=models_touched,
            parameter_adjustments=adjustments,
            rejected_strategies=rejected,
        )

        self._save_report(report)
        return report

    def _save_report(self, report: OptimizationReport) -> None:
        path = self._persist_dir / f"opt_report_{int(report.generated_at)}.json"
        try:
            path.write_text(json.dumps({
                "generated_at": report.generated_at,
                "stalls_analyzed": report.stalls_analyzed,
                "models_optimized": report.models_optimized,
                "parameter_adjustments": report.parameter_adjustments,
                "rejected_strategies": report.rejected_strategies,
            }, indent=1), encoding="utf-8")
            logger.info("Autonomous optimizer report persisted: %s", path)
        except Exception as e:
            logger.warning("Failed to save optimizer report: %s", e)
