# core/engine/scheduler.py
"""Spark Streaming Scheduler.

Manages the streaming pipeline for models that exceed available RAM.
Decides which tensor blocks to load, evict, and prefetch based on the
model's execution graph and observed access patterns.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("spark.engine.scheduler")


@dataclass
class TensorBlock:
    """A contiguous chunk of model weights that can be loaded/evicted as a unit."""
    block_id: str           # e.g. "layer.12.self_attn.q_proj"
    size_bytes: int = 0
    layer_index: int = -1
    expert_index: int = -1  # -1 for dense layers
    priority: float = 0.0   # Higher = more important to keep resident
    pinned: bool = False     # True = never evict (hot region)


@dataclass
class SchedulerState:
    """Current state of the streaming scheduler."""
    resident_blocks: int = 0
    evicted_blocks: int = 0
    total_blocks: int = 0
    resident_bytes: int = 0
    budget_bytes: int = 0
    loads_total: int = 0
    evictions_total: int = 0
    cache_hit_rate: float = 0.0
    prefetch_queue_depth: int = 0


class StreamingScheduler:
    """Orchestrates tensor loading and eviction for streaming inference.

    The scheduler maintains a budget (max bytes in fast memory) and uses
    an LRU policy augmented with access-frequency boosting.  Blocks that
    are accessed repeatedly get their priority raised so they stay
    resident longer (adaptive hot-region pinning).

    Usage:
        scheduler = StreamingScheduler(budget_bytes=4 * 1024**3)  # 4 GB
        scheduler.register_blocks(blocks)
        # Before each forward pass:
        needed = scheduler.prepare(required_block_ids)
        # 'needed' contains LoadRequests for any non-resident blocks.
    """

    def __init__(
        self,
        budget_bytes: int = 4 * 1024**3,
        prefetch_depth: int = 2,
    ):
        self._budget = budget_bytes
        self._prefetch_depth = prefetch_depth

        # All known blocks
        self._blocks: Dict[str, TensorBlock] = {}

        # Currently resident in fast memory (ordered by last access)
        self._resident: OrderedDict[str, TensorBlock] = OrderedDict()
        self._resident_bytes: int = 0

        # Access counters for adaptive priority
        self._access_count: Dict[str, int] = {}
        self._access_time: Dict[str, float] = {}

        # Stats
        self._loads: int = 0
        self._evictions: int = 0
        self._hits: int = 0
        self._misses: int = 0

    def register_blocks(self, blocks: List[TensorBlock]) -> None:
        """Register the full set of tensor blocks for a model."""
        self._blocks = {b.block_id: b for b in blocks}
        self._access_count = {b.block_id: 0 for b in blocks}
        logger.info(
            "Scheduler: registered %d blocks (%.1f GB total)",
            len(blocks),
            sum(b.size_bytes for b in blocks) / (1024**3),
        )

    def prepare(self, required_ids: List[str]) -> List[str]:
        """Ensure required blocks are resident.  Returns IDs that need loading.

        Side effects:
            - Evicts lowest-priority blocks if budget would be exceeded.
            - Updates access stats.
            - Queues prefetch for upcoming layers.
        """
        to_load: List[str] = []

        for bid in required_ids:
            if bid in self._resident:
                # Cache hit -- move to end (most-recently-used)
                self._resident.move_to_end(bid)
                self._hits += 1
            else:
                # Cache miss -- schedule load
                to_load.append(bid)
                self._misses += 1

            # Update access stats
            self._access_count[bid] = self._access_count.get(bid, 0) + 1
            self._access_time[bid] = time.monotonic()

        # Evict to make room
        incoming_bytes = sum(
            self._blocks[bid].size_bytes for bid in to_load if bid in self._blocks
        )
        self._evict_to_fit(incoming_bytes)

        # Mark as resident
        for bid in to_load:
            block = self._blocks.get(bid)
            if block:
                self._resident[bid] = block
                self._resident_bytes += block.size_bytes
                self._loads += 1

        return to_load

    def prefetch_hint(self, current_layer: int) -> List[str]:
        """Suggest blocks to prefetch for upcoming layers."""
        hints: List[str] = []
        for i in range(1, self._prefetch_depth + 1):
            target_layer = current_layer + i
            for bid, block in self._blocks.items():
                if block.layer_index == target_layer and bid not in self._resident:
                    hints.append(bid)
        return hints

    def pin(self, block_ids: List[str]) -> None:
        """Pin blocks so they are never evicted (hot-region pinning)."""
        for bid in block_ids:
            if bid in self._blocks:
                self._blocks[bid].pinned = True
                logger.debug("Pinned block %s", bid)

    def unpin(self, block_ids: List[str]) -> None:
        """Remove pin from blocks."""
        for bid in block_ids:
            if bid in self._blocks:
                self._blocks[bid].pinned = False

    def state(self) -> SchedulerState:
        """Current scheduler state snapshot."""
        total = self._hits + self._misses
        return SchedulerState(
            resident_blocks=len(self._resident),
            evicted_blocks=len(self._blocks) - len(self._resident),
            total_blocks=len(self._blocks),
            resident_bytes=self._resident_bytes,
            budget_bytes=self._budget,
            loads_total=self._loads,
            evictions_total=self._evictions,
            cache_hit_rate=self._hits / total if total > 0 else 0.0,
            prefetch_queue_depth=self._prefetch_depth,
        )

    # -- Internals --

    def _evict_to_fit(self, incoming_bytes: int) -> None:
        """Evict lowest-priority blocks until budget accommodates incoming_bytes."""
        target = self._budget - incoming_bytes
        while self._resident_bytes > target and self._resident:
            # Pop least-recently-used that isn't pinned
            evicted = False
            for bid in list(self._resident.keys()):
                block = self._resident[bid]
                if block.pinned:
                    continue
                del self._resident[bid]
                self._resident_bytes -= block.size_bytes
                self._evictions += 1
                evicted = True
                break
            if not evicted:
                # All remaining blocks are pinned -- cannot evict further
                logger.warning(
                    "Scheduler: all resident blocks pinned, cannot free %.1f MB",
                    (self._resident_bytes - target) / (1024**2),
                )
                break

    def _priority_of(self, block_id: str) -> float:
        """Compute eviction priority (lower = evict first)."""
        count = self._access_count.get(block_id, 0)
        recency = self._access_time.get(block_id, 0)
        block = self._blocks.get(block_id)
        base = block.priority if block else 0
        return base + count * 0.1 + (recency * 0.001)
