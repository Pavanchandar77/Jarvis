# core/engine/fabric.py
"""Spark Universal Memory Fabric.

Abstracts heterogeneous hardware memory partitions (GPU VRAM, System RAM, SSD,
NUMA nodes, remote network storage) into a single unified logical address space
for model execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .memory import MemoryTier

logger = logging.getLogger("spark.engine.fabric")


@dataclass
class MemoryPage:
    """An allocated block of memory inside the logical fabric."""
    page_id: str
    size_bytes: int
    current_tier: MemoryTier
    pinned: bool = False
    ref_count: int = 0


class UniversalMemoryFabric:
    """Aggregates multi-tier hardware partitions into a unified memory space.

    Allows higher-level schedulers to allocate pages and transition them
    between fast VRAM/RAM tiers and slow SSD/CXL tiers transparently without managing
    OS-level memory details directly.
    """

    def __init__(self):
        self._pages: Dict[str, MemoryPage] = {}
        self._tier_allocation_bytes: Dict[MemoryTier, int] = {
            MemoryTier.VRAM: 0,
            MemoryTier.RAM: 0,
            MemoryTier.SSD: 0,
            MemoryTier.HDD: 0,
            MemoryTier.REMOTE: 0,
        }

    def allocate(self, page_id: str, size_bytes: int, initial_tier: MemoryTier) -> MemoryPage:
        """Reserve a memory partition inside a specific hardware tier."""
        if page_id in self._pages:
            self.free(page_id)

        page = MemoryPage(page_id=page_id, size_bytes=size_bytes, current_tier=initial_tier)
        self._pages[page_id] = page
        self._tier_allocation_bytes[initial_tier] += size_bytes
        logger.debug("Fabric: Allocated %s (%.1f MB) in %s", page_id, size_bytes / (1024**2), initial_tier.name)
        return page

    def free(self, page_id: str) -> None:
        """Evict and free page allocations from the fabric."""
        page = self._pages.pop(page_id, None)
        if page:
            self._tier_allocation_bytes[page.current_tier] -= page.size_bytes
            logger.debug("Fabric: Freed %s from %s", page_id, page.current_tier.name)

    def migrate(self, page_id: str, target_tier: MemoryTier) -> bool:
        """Transition allocation blocks between storage tiers (e.g. SSD -> VRAM)."""
        page = self._pages.get(page_id)
        if not page:
            return False

        if page.current_tier == target_tier:
            return True

        # Subtract from old, add to new
        self._tier_allocation_bytes[page.current_tier] -= page.size_bytes
        self._tier_allocation_bytes[target_tier] += page.size_bytes
        
        logger.debug(
            "Fabric: Migrated %s from %s to %s",
            page_id, page.current_tier.name, target_tier.name
        )
        page.current_tier = target_tier
        return True

    def get_tier_usage_gb(self, tier: MemoryTier) -> float:
        """Query raw usage metric for a specific tier."""
        return self._tier_allocation_bytes.get(tier, 0) / (1024**3)

    def stats(self) -> Dict[str, Any]:
        """Compile a snapshot of the logical fabric layout."""
        return {
            "total_pages": len(self._pages),
            "usage_gb": {tier.name: self.get_tier_usage_gb(tier) for tier in MemoryTier},
        }
