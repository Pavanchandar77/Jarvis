# core/engine/telemetry.py
"""Spark Execution Telemetry Subsystem.

Captures, structures, and logs performance telemetry for every inference run.
Tracks planning time, first-token latency (TTFT), tokens/sec, page/cache hits,
prefetch rates, I/O stalls, and peak memory usage. Persists metrics for
historical comparison and self-tuning.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spark.engine.telemetry")


@dataclass
class SessionTelemetry:
    """Telemetry captured for a single inference session/run."""
    session_id: str
    model_name: str
    strategy: str                    # resident | stream | hybrid | no_fit
    quantisation: str
    
    # Timing (seconds / milliseconds)
    start_ts: float = field(default_factory=time.time)
    planning_time_ms: float = 0.0
    first_token_latency_ms: float = 0.0
    total_time_ms: float = 0.0
    
    # Throughput
    tokens_generated: int = 0
    average_tps: float = 0.0
    peak_tps: float = 0.0
    
    # Memory Usage (GB)
    peak_ram_gb: float = 0.0
    peak_vram_gb: float = 0.0
    
    # I/O & Caching
    bytes_streamed: int = 0
    ssd_throughput_mbps: float = 0.0
    cache_hit_rate: float = 0.0
    cache_miss_rate: float = 0.0
    total_stalls: int = 0
    total_stall_time_ms: float = 0.0
    
    # Prefetch Engine
    prefetch_success_rate: float = 0.0
    prefetches_requested: int = 0
    prefetches_completed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TelemetrySubsystem:
    """Manages recording, persisting, and querying Spark runtimes telemetry."""

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir:
            self._persist_dir = Path(os.path.expanduser(persist_dir))
        else:
            self._persist_dir = Path.home() / ".spark" / "telemetry"

        self._active_sessions: Dict[str, SessionTelemetry] = {}

    def start_session(
        self,
        session_id: str,
        model_name: str,
        strategy: str,
        quantisation: str,
    ) -> SessionTelemetry:
        """Initialize and start a new session telemetry tracker."""
        telemetry = SessionTelemetry(
            session_id=session_id,
            model_name=model_name,
            strategy=strategy,
            quantisation=quantisation,
        )
        self._active_sessions[session_id] = telemetry
        return telemetry

    def get_session(self, session_id: str) -> Optional[SessionTelemetry]:
        return self._active_sessions.get(session_id)

    def record_first_token(self, session_id: str) -> None:
        """Record the completion of the first token (TTFT)."""
        tel = self._active_sessions.get(session_id)
        if tel:
            tel.first_token_latency_ms = (time.time() - tel.start_ts) * 1000

    def end_session(self, session_id: str, tokens_count: int = 0) -> Optional[SessionTelemetry]:
        """Finish recording a session and persist it to disk."""
        tel = self._active_sessions.pop(session_id, None)
        if not tel:
            return None

        tel.total_time_ms = (time.time() - tel.start_ts) * 1000
        tel.tokens_generated = tokens_count
        if tel.total_time_ms > 0 and tokens_count > 0:
            tel.average_tps = tokens_count / (tel.total_time_ms / 1000.0)

        # Persist session to telemetry logs
        self._persist(tel)
        return tel

    def get_history(self, model_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List historical telemetry runs, optionally filtered by model."""
        history = []
        if not self._persist_dir.is_dir():
            return history

        try:
            for f in sorted(self._persist_dir.iterdir(), key=os.path.getmtime, reverse=True):
                if f.suffix == ".json":
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        if model_name and data.get("model_name") != model_name:
                            continue
                        history.append(data)
                        if len(history) >= limit:
                            break
                    except Exception:
                        pass
        except Exception as e:
            logger.warning("Failed to read telemetry history: %s", e)

        return history

    def get_benchmarks(self, model_name: str) -> Dict[str, Any]:
        """Compile benchmarks of current session strategies vs previous runs."""
        history = self.get_history(model_name=model_name, limit=10)
        if not history:
            return {"runs": 0, "message": "No historical telemetry for this model."}

        strategies = {}
        for h in history:
            strat = h.get("strategy", "unknown")
            stats = strategies.setdefault(strat, {
                "tps": [], "ttft": [], "stalls": [], "hits": []
            })
            stats["tps"].append(h.get("average_tps", 0))
            stats["ttft"].append(h.get("first_token_latency_ms", 0))
            stats["stalls"].append(h.get("total_stalls", 0))
            stats["hits"].append(h.get("cache_hit_rate", 0))

        summary = {}
        for strat, data in strategies.items():
            count = len(data["tps"])
            summary[strat] = {
                "runs": count,
                "avg_tps": round(sum(data["tps"]) / count, 2),
                "avg_ttft_ms": round(sum(data["ttft"]) / count, 1),
                "avg_stalls": round(sum(data["stalls"]) / count, 1),
                "avg_cache_hit_rate": round(sum(data["hits"]) / count, 3),
            }

        return {
            "model_name": model_name,
            "total_recorded_runs": len(history),
            "benchmarks": summary,
        }

    # -- Persistence --

    def _persist(self, telemetry: SessionTelemetry) -> None:
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{telemetry.session_id}_{int(telemetry.start_ts)}"
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in ("-", "_"))
        path = self._persist_dir / f"{safe_name}.json"
        
        try:
            path.write_text(json.dumps(telemetry.to_dict(), indent=1), encoding="utf-8")
            logger.info("Telemetry persisted: %s", path)
        except Exception as e:
            logger.warning("Failed to persist telemetry: %s", e)
