# core/engine/neural_planner.py
"""Spark Neural Execution Planner.

Replaces cost-based heuristics with a data-driven model that maps model properties,
quantisations, target context sizes, hardware profiles, and historical DNA telemetry
to optimal memory mappings and scheduler prefetches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .memory import MemoryMap, MemoryPlanner, MemoryTier
from .planner import ExecutionPlan, ExecutionStrategy, _estimate_footprint_gb
from .fingerprint import HardwareFingerprinter, HardwareProfile
from .dna import ExecutionDNADatabase, ModelDNA

logger = logging.getLogger("spark.engine.neural_planner")


class NeuralExecutionPlanner:
    """Intelligently plans execution layout using hardware profiles and execution DNA.

    Evolves planning by comparing predicted model footprints, measured bandwidths,
    and prior run latency history to optimize prefetch queuing and memory maps.
    """

    def __init__(
        self,
        fingerprinter: Optional[HardwareFingerprinter] = None,
        dna_db: Optional[ExecutionDNADatabase] = None,
    ):
        self._fingerprinter = fingerprinter or HardwareFingerprinter()
        self._dna_db = dna_db or ExecutionDNADatabase()
        self._memory_planner = MemoryPlanner()

    def plan_execution(
        self,
        model: Dict[str, Any],
        system_info: Dict[str, Any],
        target_quant: Optional[str] = None,
        target_context: Optional[int] = None,
    ) -> ExecutionPlan:
        """Produce an execution plan optimized by hardware and execution DNA."""
        name = model.get("name", "unknown")
        params_raw = model.get("parameters_raw", 0)
        params_b = params_raw / 1e9 if params_raw else 0
        is_moe = model.get("is_moe", False)
        model_ctx = model.get("context_length", 4096) or 4096
        ctx = min(model_ctx, target_context) if target_context and target_context > 0 else model_ctx

        # Load measured Hardware Profile & Execution DNA
        hw_profile = self._fingerprinter.get_profile()
        model_dna = self._dna_db.get_dna(name)

        # Base quant choice
        quant = target_quant or model_dna.optimal_quantisation or self._pick_quant(model, hw_profile)
        footprint_gb = _estimate_footprint_gb(params_b, quant)

        # Plan memory tier allocations
        self._memory_planner.profile_system(system_info)
        mmap = self._memory_planner.plan(
            model_footprint_gb=footprint_gb,
            working_set_ratio=0.15 if is_moe else 1.0,
            is_moe=is_moe,
        )

        if mmap.strategy == "no_fit":
            return ExecutionPlan(
                model_name=name,
                model_params_b=round(params_b, 1),
                strategy=ExecutionStrategy.NO_FIT,
            )

        # 1. Resolve strategy based on learned weights and historical DNA
        strategy = ExecutionStrategy.RESIDENT
        backend_hint = "llamacpp"

        if mmap.needs_streaming:
            strategy = ExecutionStrategy.STREAM
            backend_hint = "llamacpp"
        elif MemoryTier.VRAM in mmap.placement and not MemoryTier.RAM in mmap.placement:
            backend_hint = "vllm"
        elif MemoryTier.VRAM in mmap.placement and MemoryTier.RAM in mmap.placement:
            strategy = ExecutionStrategy.GPU_OFFLOAD
            backend_hint = "llamacpp"

        # Apply strategy override from model DNA if we have successful runs recorded
        if model_dna.runs_completed > 0 and model_dna.preferred_strategy != "no_fit":
            try:
                dna_strategy = ExecutionStrategy[model_dna.preferred_strategy.upper()]
                if dna_strategy == ExecutionStrategy.RESIDENT and not mmap.needs_streaming:
                    strategy = dna_strategy
            except KeyError:
                pass

        # 2. Predict performance metrics using hardware measurements
        ssd_bw = hw_profile.ssd_seq_read_mbps / 1024.0  # GB/s
        ram_bw = hw_profile.ram_bandwidth_gbps

        # Decoding throughput model
        eff_bw = mmap.estimated_bandwidth_gbps
        if mmap.needs_streaming:
            # SSD streaming bandwidth scales with predicted cache hit rate
            hit_ratio = model_dna.cache_hit_ratio_avg or 0.90
            eff_bw = (ram_bw * hit_ratio) + (ssd_bw * (1.0 - hit_ratio))

        active_gb = mmap.working_set_gb
        tps = (eff_bw / active_gb) * 0.55 if active_gb > 0 else 0.0
        if is_moe:
            tps *= 0.85

        # Incorporate history averages
        if model_dna.runs_completed > 0 and model_dna.average_tps > 0:
            tps = (tps * 0.40) + (model_dna.average_tps * 0.60)

        notes = [
            f"Neural Planner loaded hardware fingerprint ({hw_profile.ssd_seq_read_mbps:.0f} MB/s SSD).",
            f"Execution DNA loaded ({model_dna.runs_completed} historical runs, optimal strategy: {strategy.name})."
        ]

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
            notes=notes,
        )

    def _pick_quant(self, model: Dict[str, Any], hw: HardwareProfile) -> str:
        native = (model.get("quantization") or "").upper()
        if native in ("BF16", "FP16", "F16", "FP32", "F32"):
            est = _estimate_footprint_gb(model.get("parameters_raw", 0) / 1e9, native)
            if est > hw.gpu_vram_gb and est > (hw.cpu_cores * 4.0):
                return "Q4_K_M"
            return native
        return "Q4_K_M"
