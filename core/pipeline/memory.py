# core/pipeline/memory.py
"""Spark Pipeline Memory & Feedback System.

Saves and indexes multi-model execution logs, successful/failed DAG topologies,
and user feedback to continuously optimize model routing decisions.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spark.pipeline.memory")


@dataclass
class PipelineRunRecord:
    """Historical record of an executed task DAG pipeline."""
    run_id: str
    timestamp: float
    query: str
    intent: str
    topology_size: int
    routing_decisions: Dict[str, str]  # task_id -> model_name
    latency_ms: float
    success: bool
    verification_errors: List[str]


class PipelineMemory:
    """Handles persistence of pipeline execution traces and learning tables."""

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir:
            self._persist_dir = Path(os.path.expanduser(persist_dir))
        else:
            self._persist_dir = Path.home() / ".spark"

        self._memory_path = self._persist_dir / "pipeline_memory.json"
        self._history: List[PipelineRunRecord] = []
        self._load_memory()

    def record_pipeline_run(self, record: PipelineRunRecord) -> None:
        """Append a run trace and persist the updated history."""
        self._history.append(record)
        self._save_memory()

    def get_routing_success_rate(self, model_name: str, intent: str) -> float:
        """Calculate historical success rate of a model for a specific intent."""
        matches = [
            r for r in self._history
            if r.intent == intent and any(m == model_name for m in r.routing_decisions.values())
        ]
        if not matches:
            return 1.0  # Default to 100% confidence for new candidates
            
        successes = sum(1 for r in matches if r.success)
        return successes / len(matches)

    # -- Persistence --

    def _load_memory(self) -> None:
        if self._memory_path.is_file():
            try:
                data = json.loads(self._memory_path.read_text(encoding="utf-8"))
                self._history = [PipelineRunRecord(**r) for r in data]
                logger.info("Pipeline Memory: loaded %d historical runs.", len(self._history))
            except Exception as e:
                logger.warning("Failed to load pipeline memory: %s", e)

    def _save_memory(self) -> None:
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        try:
            raw = [asdict(r) for r in self._history[-100:]] # Keep last 100 runs to prevent file bloat
            self._memory_path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
            logger.info("Saved pipeline memory to %s", self._memory_path)
        except Exception as e:
            logger.warning("Failed to save pipeline memory: %s", e)
