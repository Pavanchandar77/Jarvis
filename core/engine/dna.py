# core/engine/dna.py
"""Spark Execution DNA Database.

Keeps a persistent, model-specific execution profile (optimal quantisation,
best execution strategies, historical latencies, cache access rates, layer/expert
utilisations). Allows Spark to remember and adapt execution plans based on
prior run outcomes.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spark.engine.dna")


@dataclass
class ModelDNA:
    """Persistent execution fingerprint for a specific model."""
    model_id: str
    preferred_strategy: str = "resident"
    optimal_quantisation: str = "Q4_K_M"
    best_context_length: int = 4096
    cache_hit_ratio_avg: float = 0.0
    average_tps: float = 0.0
    latency_profile_ms: Dict[str, float] = field(default_factory=dict) # e.g. {"prefill": 120.0, "decoding": 22.0}
    layer_access_stats: Dict[str, float] = field(default_factory=dict) # e.g. {"layer.12": 0.8}
    expert_routing_frequencies: Dict[str, float] = field(default_factory=dict)
    runs_completed: int = 0
    last_run_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ExecutionDNADatabase:
    """Handles persistence and retrieval of model-specific execution DNA files."""

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir:
            self._persist_dir = Path(os.path.expanduser(persist_dir))
        else:
            self._persist_dir = Path.home() / ".spark" / "dna"

        self._persist_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, model_id: str) -> Path:
        safe_name = model_id.replace("/", "--").replace("\\", "--")
        return self._persist_dir / f"{safe_name}.dna.json"

    def get_dna(self, model_id: str) -> ModelDNA:
        """Fetch persistent DNA for a model, returns a default instance if missing."""
        path = self._file_path(model_id)
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return ModelDNA(**data)
            except Exception:
                pass
        return ModelDNA(model_id=model_id)

    def save_dna(self, dna: ModelDNA) -> None:
        """Persist updated DNA to disk."""
        path = self._file_path(dna.model_id)
        try:
            path.write_text(json.dumps(dna.to_dict(), indent=1), encoding="utf-8")
            logger.info("Saved Execution DNA profile: %s", path)
        except Exception as e:
            logger.warning("Failed to save Execution DNA profile: %s", e)

    def record_run(
        self,
        model_id: str,
        strategy: str,
        quantisation: str,
        tps: float,
        prefill_ms: float,
        cache_hit_rate: float,
    ) -> ModelDNA:
        """Incrementally update DNA statistics using telemetry from a completed run."""
        dna = self.get_dna(model_id)
        dna.runs_completed += 1
        dna.last_run_ts = os.time.time() if hasattr(os, 'time') else 0.0  # fallback
        import time
        dna.last_run_ts = time.time()

        # Update running averages
        n = dna.runs_completed
        dna.average_tps = round(((dna.average_tps * (n - 1)) + tps) / n, 2)
        dna.cache_hit_ratio_avg = round(((dna.cache_hit_ratio_avg * (n - 1)) + cache_hit_rate) / n, 3)

        # Update preferred run strategy if this one yielded better TPS
        if tps > dna.average_tps or dna.preferred_strategy == "resident":
            dna.preferred_strategy = strategy
            dna.optimal_quantisation = quantisation

        # Latency profile
        dna.latency_profile_ms["prefill"] = prefill_ms

        self.save_dna(dna)
        return dna
