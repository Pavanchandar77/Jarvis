# core/engine/prefetch.py
"""Spark Predictive Prefetch Engine.

Predicts which weights/tensors the model will need next based on execution graph
topology, sequential layer order, expert transitions (for MoE), and historical
access patterns. Loads them asynchronously to eliminate I/O blocking.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .scheduler import StreamingScheduler, TensorBlock
from .loader import TensorLoader, LoadRequest

logger = logging.getLogger("spark.engine.prefetch")


@dataclass
class PrefetchStats:
    """Metrics tracking prefetch engine performance."""
    prefetches_requested: int = 0
    prefetches_completed: int = 0
    prefetches_failed: int = 0
    bytes_prefetched: int = 0
    prefetch_hits: int = 0         # Prefetched blocks that were actually used
    prefetch_misses: int = 0       # Prefetched blocks evicted before use
    total_stalls: int = 0          # Number of times execution blocked on I/O
    total_stall_time_ms: float = 0.0


class PredictivePrefetchEngine:
    """Predicts and preloads model blocks asynchronously before execution.

    Maintains a history of layer and expert transitions to learn which paths
    through the model are most frequent. Under MoE, it builds a simple Markov
    transition map to predict which expert will be needed next based on the
    current active expert.
    """

    def __init__(
        self,
        scheduler: StreamingScheduler,
        loader: TensorLoader,
        source_path: str,
    ):
        self._scheduler = scheduler
        self._loader = loader
        self._source_path = source_path
        
        # Async tasks and queues
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._active_preloads: Set[str] = set()

        # Prediction models
        self._last_expert: int = -1
        # Markov transition transition_counts: current_expert -> {next_expert: count}
        self._expert_transitions: Dict[int, Dict[int, int]] = {}
        # Tracks which prefetched blocks are currently sitting in cache unused
        self._unused_prefetches: Set[str] = set()

        # Telemetry
        self.stats = PrefetchStats()

    def start(self) -> None:
        """Start the background prefetch worker loop."""
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._prefetch_loop())
            logger.info("Predictive Prefetch Engine started.")

    async def stop(self) -> None:
        """Stop the background prefetch worker loop."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Predictive Prefetch Engine stopped.")

    def predict_next_blocks(self, current_layer: int, current_expert: int = -1) -> List[str]:
        """Predict the next block IDs needed for execution.

        Uses sequential layer order + MoE Markov transition prediction.
        """
        predictions: List[str] = []

        # 1. Predict sequential layers
        depth = self._scheduler.prefetch_hint(current_layer)
        predictions.extend(depth)

        # 2. Predict MoE experts
        if current_expert != -1:
            # Update Markov transition weights
            if self._last_expert != -1:
                trans = self._expert_transitions.setdefault(self._last_expert, {})
                trans[current_expert] = trans.get(current_expert, 0) + 1

            self._last_expert = current_expert

            # Predict next expert based on transition probabilities
            trans_from_current = self._expert_transitions.get(current_expert)
            if trans_from_current:
                best_next = max(trans_from_current, key=trans_from_current.get)
                # Suggest expert block for the upcoming layers
                for layer_idx in range(current_layer + 1, current_layer + 3):
                    predictions.append(f"layer.{layer_idx}.expert.{best_next}")

        return predictions

    def trigger_prefetch(self, block_ids: List[str]) -> None:
        """Queue blocks for asynchronous background preloading."""
        for bid in block_ids:
            if bid not in self._active_preloads and bid not in self._scheduler._resident:
                self._queue.put_nowait(bid)
                self._active_preloads.add(bid)
                self.stats.prefetches_requested += 1

    def record_actual_use(self, block_id: str) -> None:
        """Record when a block is actually accessed by the execution engine.

        Helps track prefetch hit vs miss rates.
        """
        if block_id in self._unused_prefetches:
            self.stats.prefetch_hits += 1
            self._unused_prefetches.remove(block_id)

    def record_eviction(self, block_id: str) -> None:
        """Record when a block is evicted from memory."""
        if block_id in self._unused_prefetches:
            self.stats.prefetch_misses += 1
            self._unused_prefetches.remove(block_id)

    def record_stall(self, duration_ms: float) -> None:
        """Record an execution stall (waiting for storage)."""
        self.stats.total_stalls += 1
        self.stats.total_stall_time_ms += duration_ms

    # -- Background Workers --

    async def _prefetch_loop(self) -> None:
        while True:
            try:
                block_id = await self._queue.get()
                # Double check residency
                if block_id in self._scheduler._resident:
                    self._active_preloads.discard(block_id)
                    self._queue.task_done()
                    continue

                # Trigger load in thread pool
                loop = asyncio.get_running_loop()
                t0 = time.perf_counter()
                
                req = LoadRequest(
                    block_ids=[block_id],
                    source_path=self._source_path,
                    async_allowed=True,
                )
                
                # Perform load asynchronously
                results = await loop.run_in_executor(None, self._loader.load, req)
                
                elapsed = (time.perf_counter() - t0) * 1000
                for r in results:
                    if r.success:
                        self.stats.prefetches_completed += 1
                        self.stats.bytes_prefetched += r.size_bytes
                        self._scheduler.prepare([block_id])  # Register as resident
                        self._unused_prefetches.add(block_id)
                    else:
                        self.stats.prefetches_failed += 1

                self._active_preloads.discard(block_id)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in prefetch worker: %s", e)
