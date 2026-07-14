# core/engine/cache.py
"""Spark Cache Manager.

A first-class caching subsystem that learns frequently accessed model
regions, supports adaptive hot-region pinning, predictive prefetch,
asynchronous loading, cache warming, and cross-session persistence.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("spark.engine.cache")


@dataclass
class CacheEntry:
    """Tracks access statistics for a single cacheable unit."""
    key: str                     # Tensor/layer/expert identifier
    access_count: int = 0
    last_access_ts: float = 0.0
    total_load_time_ms: float = 0.0
    size_bytes: int = 0
    pinned: bool = False         # Manually or automatically pinned
    hot: bool = False            # Automatically marked as hot

    @property
    def avg_load_time_ms(self) -> float:
        return self.total_load_time_ms / self.access_count if self.access_count else 0


@dataclass
class CacheStats:
    """Aggregate cache statistics."""
    total_entries: int = 0
    hot_entries: int = 0
    pinned_entries: int = 0
    total_accesses: int = 0
    total_bytes_cached: int = 0
    hit_rate: float = 0.0
    session_count: int = 0


class CacheManager:
    """Manages Spark's inference cache across sessions.

    Key capabilities:
        - Access pattern tracking per tensor/layer/expert
        - Automatic hot-region detection and pinning
        - Cross-session persistence via JSON state file
        - Cache warming: preload known-hot regions at startup
        - Eviction recommendations based on usage patterns

    Usage:
        cache = CacheManager(persist_path="~/.spark/cache")
        cache.load_state("my-model-id")

        # During inference:
        cache.record_access("layer.5.expert.3", size_bytes=4096, load_time_ms=2.1)

        # After session:
        cache.save_state("my-model-id")
    """

    # A key is considered "hot" if accessed >= this many times
    HOT_THRESHOLD = 10
    # Auto-pin keys accessed >= this many times
    AUTO_PIN_THRESHOLD = 50

    def __init__(self, persist_dir: Optional[str] = None):
        self._entries: Dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._session_count: int = 0

        # Persistence directory
        if persist_dir:
            self._persist_dir = Path(os.path.expanduser(persist_dir))
        else:
            self._persist_dir = Path.home() / ".spark" / "cache"

    def record_access(
        self,
        key: str,
        size_bytes: int = 0,
        load_time_ms: float = 0.0,
        was_hit: bool = False,
    ) -> CacheEntry:
        """Record an access to a cacheable unit."""
        if was_hit:
            self._hits += 1
        else:
            self._misses += 1

        entry = self._entries.get(key)
        if entry is None:
            entry = CacheEntry(key=key, size_bytes=size_bytes)
            self._entries[key] = entry

        entry.access_count += 1
        entry.last_access_ts = time.time()
        entry.total_load_time_ms += load_time_ms
        if size_bytes > 0:
            entry.size_bytes = size_bytes

        # Auto-promote to hot / pinned
        if entry.access_count >= self.AUTO_PIN_THRESHOLD and not entry.pinned:
            entry.pinned = True
            entry.hot = True
            logger.debug("Auto-pinned hot region: %s (%d accesses)", key, entry.access_count)
        elif entry.access_count >= self.HOT_THRESHOLD and not entry.hot:
            entry.hot = True

        return entry

    def get_hot_keys(self) -> List[str]:
        """Return keys that are marked as hot (frequently accessed)."""
        return [e.key for e in self._entries.values() if e.hot]

    def get_pinned_keys(self) -> List[str]:
        """Return keys that should be pinned in fast memory."""
        return [e.key for e in self._entries.values() if e.pinned]

    def get_warm_order(self) -> List[str]:
        """Return keys sorted by access frequency (descending) for cache warming."""
        return [
            e.key
            for e in sorted(
                self._entries.values(),
                key=lambda e: e.access_count,
                reverse=True,
            )
            if e.access_count > 0
        ]

    def recommend_eviction(self, count: int = 10) -> List[str]:
        """Recommend keys to evict (least accessed, not pinned)."""
        candidates = [
            e for e in self._entries.values()
            if not e.pinned
        ]
        candidates.sort(key=lambda e: (e.access_count, e.last_access_ts))
        return [e.key for e in candidates[:count]]

    def stats(self) -> CacheStats:
        """Aggregate cache statistics."""
        total = self._hits + self._misses
        return CacheStats(
            total_entries=len(self._entries),
            hot_entries=sum(1 for e in self._entries.values() if e.hot),
            pinned_entries=sum(1 for e in self._entries.values() if e.pinned),
            total_accesses=sum(e.access_count for e in self._entries.values()),
            total_bytes_cached=sum(e.size_bytes for e in self._entries.values()),
            hit_rate=self._hits / total if total > 0 else 0.0,
            session_count=self._session_count,
        )

    # -- Persistence --

    def _state_path(self, model_id: str) -> Path:
        safe_name = model_id.replace("/", "--")
        return self._persist_dir / f"{safe_name}.cache.json"

    def save_state(self, model_id: str) -> None:
        """Persist cache state to disk for cross-session continuity."""
        path = self._state_path(model_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "model_id": model_id,
            "session_count": self._session_count + 1,
            "saved_at": time.time(),
            "entries": {k: asdict(v) for k, v in self._entries.items()},
        }
        try:
            path.write_text(json.dumps(state, indent=1), encoding="utf-8")
            logger.info("Cache state saved: %s (%d entries)", path, len(self._entries))
        except Exception as exc:
            logger.warning("Failed to save cache state: %s", exc)

    def load_state(self, model_id: str) -> bool:
        """Load persisted cache state from disk."""
        path = self._state_path(model_id)
        if not path.is_file():
            return False

        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            self._session_count = state.get("session_count", 0)
            raw_entries = state.get("entries", {})
            for k, v in raw_entries.items():
                self._entries[k] = CacheEntry(**v)
            logger.info(
                "Cache state loaded: %s (%d entries, session %d)",
                path, len(self._entries), self._session_count,
            )
            return True
        except Exception as exc:
            logger.warning("Failed to load cache state: %s", exc)
            return False

    def clear(self) -> None:
        """Reset all cache state."""
        self._entries.clear()
        self._hits = 0
        self._misses = 0
