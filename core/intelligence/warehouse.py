# core/intelligence/warehouse.py
"""Spark Unified Performance Warehouse.

Aggregates all execution traces, routing logs, validation outcomes, cache rates,
and system telemetry into a centralized queryable analytics store.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spark.intelligence.warehouse")


@dataclass
class TransactionRecord:
    """A full transaction log of an inference execution run."""
    transaction_id: str
    timestamp: float
    model_name: str
    strategy: str
    intent: str
    tokens_generated: int
    latency_ms: float
    cache_hit_rate: float
    stalls: int
    stall_time_ms: float
    success: bool
    user_feedback: Optional[int] = None  # 1 = positive, 0 = negative


class PerformanceWarehouse:
    """Manages recording and querying historical execution metrics."""

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir:
            self._persist_dir = Path(os.path.expanduser(persist_dir))
        else:
            self._persist_dir = Path.home() / ".spark" / "warehouse"

        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._persist_dir / "transactions.json"
        self._records: List[TransactionRecord] = []
        self._load_records()

    def record_transaction(self, record: TransactionRecord) -> None:
        """Log a new transaction to the warehouse analytics store."""
        self._records.append(record)
        self._save_records()

    def get_records(self) -> List[TransactionRecord]:
        return list(self._records)

    def get_model_metrics(self, model_name: str) -> Dict[str, Any]:
        """Aggregate performance characteristics for a specific model."""
        matches = [r for r in self._records if r.model_name == model_name]
        if not matches:
            return {}

        total = len(matches)
        successes = sum(1 for r in matches if r.success)
        avg_latency = sum(r.latency_ms for r in matches) / total
        avg_tps = sum(r.tokens_generated / (r.latency_ms / 1000.0) for r in matches if r.latency_ms > 0) / total

        return {
            "total_runs": total,
            "success_rate": successes / total,
            "avg_latency_ms": round(avg_latency, 1),
            "avg_tps": round(avg_tps, 2),
        }

    # -- Persistence --

    def _load_records(self) -> None:
        if self._db_path.is_file():
            try:
                data = json.loads(self._db_path.read_text(encoding="utf-8"))
                self._records = [TransactionRecord(**r) for r in data]
                logger.info("Warehouse: loaded %d transaction records.", len(self._records))
            except Exception as e:
                logger.warning("Failed to load warehouse records: %s", e)

    def _save_records(self) -> None:
        try:
            # Keep last 500 records to prevent file bloat
            raw = [asdict(r) for r in self._records[-500:]]
            self._db_path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save warehouse records: %s", e)
