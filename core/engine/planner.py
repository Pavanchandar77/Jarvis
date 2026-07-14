# core/engine/planner.py
"""Spark Execution Planner.

Analyses a model's architecture, size, and the host's hardware profile to
produce an ExecutionPlan -- a declarative description of *how* the model
should be loaded and served rather than simply *which backend* to use.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .memory import MemoryMap, MemoryPlanner, MemoryTier

logger = logging.getLogger("spark.engine.planner")


class ExecutionStrategy(Enum):
    """High-level execution strategies that Spark can employ."""
    RESIDENT     = auto()  # Model fits entirely in VRAM or RAM
    GPU_OFFLOAD  = auto()  # Partial VRAM + spill to RAM
    STREAM       = auto()  # Hierarchical: hot set in RAM, cold on SSD
    HYBRID       = auto()  # VRAM + RAM + SSD combined
    DISTRIBUTED  = auto()  # Multi-device / multi-node (future)
    NO_FIT       = auto()  # Cannot execute with available resources


@dataclass
class ExecutionPlan:
    """Declarative plan describing how a model will execute."""
    # Identity
    model_name: str = ""
    model_params_b: float = 0.0
    is_moe: bool = False

    # Strategy
    strategy: ExecutionStrategy = ExecutionStrategy.NO_FIT
    quantisation: str = "Q4_K_M"

    # Memory layout
    memory_map: Optional[MemoryMap] = None

    # Estimated performance
    estimated_tps: float = 0.0
    estimated_ttft_ms: float = 0.0   # Time to first token

    # Context
    context_length: int = 4096
    max_batch_size: int = 1

    # Backend hint (the planner may suggest a preferred serving backend)
    backend_hint: str = ""           # "llamacpp" | "vllm" | "mlx" | ""

    # Streaming-specific
    streaming_enabled: bool = False
    prefetch_enabled: bool = True
    cache_persistent: bool = True

    # Diagnostics
    notes: List[str] = field(default_factory=list)

    @property
    def viable(self) -> bool:
        return self.strategy != ExecutionStrategy.NO_FIT


# ── Quantisation bytes-per-parameter ──
_QUANT_BPP = {
    "Q2_K":   0.3125,
    "Q3_K_S": 0.4375,
    "Q3_K_M": 0.4375,
    "Q4_0":   0.5,
    "Q4_K_S": 0.5,
    "Q4_K_M": 0.5625,
    "Q5_K_S": 0.625,
    "Q5_K_M": 0.6875,
    "Q6_K":   0.75,
    "Q8_0":   1.0,
    "INT4":   0.5,
    "INT8":   1.0,
    "FP8":    1.0,
    "FP16":   2.0,
    "BF16":   2.0,
    "F32":    4.0,
}


def _estimate_footprint_gb(params_b: float, quant: str) -> float:
    """Rough model weight size in GB for a given param count and quant."""
    bpp = _QUANT_BPP.get(quant, 0.5625)  # Default Q4_K_M
    return params_b * bpp


def _estimate_tps(
    model_footprint_gb: float,
    memory_map: MemoryMap,
    params_b: float,
    is_moe: bool,
) -> float:
    """Estimate tokens/second from effective bandwidth and model size."""
    bw = memory_map.estimated_bandwidth_gbps
    if bw <= 0 or model_footprint_gb <= 0:
        return 0.0

    # Active params that must be read per token
    active_gb = memory_map.working_set_gb
    if active_gb <= 0:
        active_gb = model_footprint_gb

    efficiency = 0.55  # Overhead factor
    raw_tps = (bw / active_gb) * efficiency
    if is_moe:
        raw_tps *= 0.80  # MoE routing overhead

    return max(0.01, raw_tps)


class ExecutionPlanner:
    """The brain of Spark's inference engine.

    Takes model metadata + system hardware -> produces an ExecutionPlan.
    Model-architecture agnostic: works with any open-weight model.
    """

    def __init__(self):
        self._memory_planner = MemoryPlanner()

    def plan(
        self,
        model: Dict[str, Any],
        system_info: Dict[str, Any],
        target_quant: Optional[str] = None,
        target_context: Optional[int] = None,
    ) -> ExecutionPlan:
        """Produce an execution plan for the given model on the given hardware.

        Args:
            model: Model metadata dict (from hf_models.json or HF API).
            system_info: Hardware dict (from detect_system()).
            target_quant: Explicit quantisation override, or None for auto.
            target_context: Explicit context-length cap.
        """
        name = model.get("name", "unknown")
        params_raw = model.get("parameters_raw", 0)
        params_b = params_raw / 1e9 if params_raw else 0
        is_moe = model.get("is_moe", False)
        model_ctx = model.get("context_length", 4096) or 4096
        ctx = min(model_ctx, target_context) if target_context and target_context > 0 else model_ctx

        # Choose quantisation
        quant = target_quant or self._pick_quant(model, system_info)

        # Estimate model footprint
        footprint_gb = _estimate_footprint_gb(params_b, quant)

        # Profile system memory hierarchy
        self._memory_planner.profile_system(system_info)

        # Plan memory placement
        mmap = self._memory_planner.plan(
            model_footprint_gb=footprint_gb,
            working_set_ratio=0.15 if is_moe else 1.0,
            is_moe=is_moe,
        )

        # Map MemoryMap strategy -> ExecutionStrategy
        strategy, backend_hint = self._resolve_strategy(mmap, system_info)

        # Estimate performance
        tps = _estimate_tps(footprint_gb, mmap, params_b, is_moe)

        notes = []
        if mmap.needs_streaming:
            ssd_gb = mmap.placement.get(MemoryTier.SSD, 0) or mmap.placement.get(MemoryTier.HDD, 0)
            notes.append(
                f"Streaming {ssd_gb:.0f} GB from {'SSD' if MemoryTier.SSD in mmap.placement else 'HDD'}, "
                f"{mmap.resident_gb:.1f} GB pinned in RAM"
            )
        if strategy == ExecutionStrategy.NO_FIT:
            notes.append(
                f"Model requires {footprint_gb:.1f} GB but no memory tier has enough space"
            )

        return ExecutionPlan(
            model_name=name,
            model_params_b=round(params_b, 1),
            is_moe=is_moe,
            strategy=strategy,
            quantisation=quant,
            memory_map=mmap,
            estimated_tps=round(tps, 2),
            context_length=ctx,
            backend_hint=backend_hint,
            streaming_enabled=mmap.needs_streaming,
            prefetch_enabled=mmap.needs_streaming,
            cache_persistent=mmap.needs_streaming,
            notes=notes,
        )

    # ── Private helpers ──

    def _pick_quant(self, model: Dict[str, Any], system_info: Dict[str, Any]) -> str:
        """Auto-select quantisation based on model + hardware."""
        native = (model.get("quantization") or "").upper()
        
        ram_gb = system_info.get("total_ram_gb", 0)
        params_raw = model.get("parameters_raw", 0)
        params_b = params_raw / 1e9 if params_raw else 0

        # If native is a standard unquantized format, check if it fits in RAM.
        # If not, we should use a quantized representation (default Q4_K_M) for streaming/CPU execution.
        if native in ("BF16", "FP16", "F16", "FP32", "F32"):
            est_native_size = _estimate_footprint_gb(params_b, native)
            if est_native_size > ram_gb:
                return "Q4_K_M"
            return native

        # If model ships prequantized, respect that
        if native in _QUANT_BPP:
            return native

        gpu_count = system_info.get("gpu_count", 0) or 0
        # Multi-GPU rigs use BF16 (vLLM sharding)
        if gpu_count >= 2:
            return "BF16"

        # Default: Q4_K_M (best quality/size ratio for single-device)
        return "Q4_K_M"

    def _resolve_strategy(
        self,
        mmap: MemoryMap,
        system_info: Dict[str, Any],
    ) -> tuple:
        """Map a MemoryMap strategy string to an ExecutionStrategy + backend hint."""
        backend = (system_info.get("backend") or "").lower()
        has_gpu = system_info.get("has_gpu", False)
        is_mac = "apple" in backend or system_info.get("unified_memory", False)

        if mmap.strategy == "no_fit":
            return ExecutionStrategy.NO_FIT, ""

        if mmap.strategy == "stream":
            # Streaming runtime -- Spark's own hierarchical engine
            # Backend hint: llamacpp with mmap for now; future: native Spark loader
            return ExecutionStrategy.STREAM, "llamacpp"

        # Resident strategies
        if mmap.strategy == "resident":
            if MemoryTier.VRAM in mmap.placement and not MemoryTier.RAM in mmap.placement:
                return ExecutionStrategy.RESIDENT, "vllm" if not is_mac else "mlx"
            if MemoryTier.VRAM in mmap.placement and MemoryTier.RAM in mmap.placement:
                return ExecutionStrategy.GPU_OFFLOAD, "llamacpp"
            # CPU-only
            return ExecutionStrategy.RESIDENT, "llamacpp"

        return ExecutionStrategy.RESIDENT, "llamacpp"
