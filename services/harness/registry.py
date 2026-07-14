"""Harness implementation registry — engine plugins register here."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Type

from .base import CodingHarness


class HarnessRegistry:
    """Maps harness_id → factory/class for CodingHarness implementations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._factories: Dict[str, callable] = {}
        self._meta: Dict[str, Dict] = {}

    def register(
        self,
        harness_id: str,
        factory,
        *,
        display_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        with self._lock:
            self._factories[harness_id] = factory
            self._meta[harness_id] = {
                "harness_id": harness_id,
                "display_name": display_name or harness_id,
                "metadata": dict(metadata or {}),
            }

    def unregister(self, harness_id: str) -> None:
        with self._lock:
            self._factories.pop(harness_id, None)
            self._meta.pop(harness_id, None)

    def create(self, harness_id: str) -> CodingHarness:
        with self._lock:
            factory = self._factories.get(harness_id)
            if not factory:
                raise KeyError(f"unknown harness: {harness_id}")
            return factory()

    def available(self) -> List[Dict]:
        with self._lock:
            return list(self._meta.values())

    def has(self, harness_id: str) -> bool:
        return harness_id in self._factories


# Process-wide default registry
DEFAULT_REGISTRY = HarnessRegistry()
