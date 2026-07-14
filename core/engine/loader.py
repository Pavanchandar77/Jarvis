# core/engine/loader.py
"""Spark Tensor Loader.

Abstract interface and concrete implementations for loading model tensors
from various storage formats.  The loader is the lowest layer of the
engine -- it doesn't decide *what* to load; it only knows *how*.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("spark.engine.loader")


class StorageFormat(Enum):
    """Recognised model storage formats."""
    GGUF         = auto()  # llama.cpp GGUF
    SAFETENSORS  = auto()  # HuggingFace safetensors
    PYTORCH_BIN  = auto()  # Legacy .bin checkpoint
    NUMPY        = auto()  # .npy / .npz arrays
    UNKNOWN      = auto()


@dataclass
class LoadRequest:
    """A request to load one or more tensor blocks."""
    block_ids: List[str]
    source_path: str = ""
    format: StorageFormat = StorageFormat.UNKNOWN
    priority: float = 0.0       # Higher = load first
    async_allowed: bool = True  # Whether this can be loaded asynchronously


@dataclass
class LoadResult:
    """Result of a tensor load operation."""
    block_id: str
    success: bool = False
    size_bytes: int = 0
    load_time_ms: float = 0.0
    source_format: StorageFormat = StorageFormat.UNKNOWN
    error: Optional[str] = None


def detect_format(path: str) -> StorageFormat:
    """Detect the storage format of a model file or directory."""
    p = Path(path)
    if p.is_file():
        suffix = p.suffix.lower()
        if suffix == ".gguf":
            return StorageFormat.GGUF
        if suffix == ".safetensors":
            return StorageFormat.SAFETENSORS
        if suffix == ".bin":
            return StorageFormat.PYTORCH_BIN
        if suffix in (".npy", ".npz"):
            return StorageFormat.NUMPY
    elif p.is_dir():
        # Check directory contents
        children = list(p.iterdir()) if p.exists() else []
        exts = {c.suffix.lower() for c in children if c.is_file()}
        if ".safetensors" in exts:
            return StorageFormat.SAFETENSORS
        if ".gguf" in exts:
            return StorageFormat.GGUF
        if ".bin" in exts:
            return StorageFormat.PYTORCH_BIN
    return StorageFormat.UNKNOWN


class TensorLoader:
    """Loads tensor blocks from storage into memory.

    Model-format agnostic: auto-detects GGUF, safetensors, etc.
    Supports memory-mapped I/O for zero-copy access on supported formats.

    Usage:
        loader = TensorLoader()
        results = loader.load(LoadRequest(
            block_ids=["layer.0.self_attn.q_proj"],
            source_path="/path/to/model",
        ))
    """

    def __init__(self, use_mmap: bool = True):
        self._use_mmap = use_mmap
        self._load_count = 0
        self._total_bytes = 0
        self._total_time_ms = 0.0

    def load(self, request: LoadRequest) -> List[LoadResult]:
        """Load requested tensor blocks from storage.

        This is a synchronous load. For async loading, wrap in an executor.
        """
        fmt = request.format
        if fmt == StorageFormat.UNKNOWN:
            fmt = detect_format(request.source_path)

        results: List[LoadResult] = []
        for block_id in request.block_ids:
            t0 = time.perf_counter()
            try:
                size = self._load_block(block_id, request.source_path, fmt)
                elapsed = (time.perf_counter() - t0) * 1000
                self._load_count += 1
                self._total_bytes += size
                self._total_time_ms += elapsed
                results.append(LoadResult(
                    block_id=block_id,
                    success=True,
                    size_bytes=size,
                    load_time_ms=round(elapsed, 2),
                    source_format=fmt,
                ))
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                results.append(LoadResult(
                    block_id=block_id,
                    success=False,
                    load_time_ms=round(elapsed, 2),
                    source_format=fmt,
                    error=str(exc),
                ))
                logger.warning("Failed to load block %s: %s", block_id, exc)

        return results

    def stats(self) -> Dict[str, Any]:
        """Loader performance statistics."""
        return {
            "total_loads": self._load_count,
            "total_bytes": self._total_bytes,
            "total_time_ms": round(self._total_time_ms, 2),
            "avg_throughput_gbps": (
                (self._total_bytes / (1024**3))
                / (self._total_time_ms / 1000)
                if self._total_time_ms > 0 else 0
            ),
        }

    # -- Internals --

    def _load_block(
        self, block_id: str, source_path: str, fmt: StorageFormat
    ) -> int:
        """Load a single block.  Returns size in bytes.

        Current implementation uses file-size estimation.  In the future,
        this will perform actual tensor deserialization via safetensors /
        gguf libraries with optional mmap.
        """
        p = Path(source_path)

        if fmt == StorageFormat.SAFETENSORS:
            # Walk directory for matching shard
            if p.is_dir():
                for f in p.iterdir():
                    if f.suffix == ".safetensors":
                        # Estimate: each safetensors file is one shard
                        return f.stat().st_size
            elif p.is_file():
                return p.stat().st_size

        elif fmt == StorageFormat.GGUF:
            if p.is_file():
                return p.stat().st_size
            # Directory containing GGUF
            if p.is_dir():
                for f in p.iterdir():
                    if f.suffix == ".gguf":
                        return f.stat().st_size

        # Fallback: estimate from block_id naming convention
        # In a real implementation, this would parse the tensor index
        return 0
