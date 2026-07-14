# core/engine/cost_planner.py
"""Spark Cost-Based Execution Planner.

Evolves Spark's execution planner from simple capacity-based heuristics into
a quantitative cost model. Estimates latency, bandwidth, and compute costs
across multiple strategies using hardware profiles and telemetry history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .memory import MemoryMap, MemoryPlanner, MemoryTier
from .planner import ExecutionPlan, ExecutionStrategy, _estimate_footprint_gb
from .telemetry import TelemetrySubsystem

logger = logging.getLogger("spark.engine.cost_planner")


@dataclass
class CostEvaluation:
    """Estimated costs for a candidate execution strategy."""
    strategy: ExecutionStrategy
    backend_hint: str
    estimated_latency_ms: float      # Time to process a prompt token (prefill)
    estimated_tps: float             # Generated tokens per second (decoding)
    estimated_stall_time_ms: float   # Expected I/O stalls per token
    compute_overhead_score: float    # Resource utilisation score (higher = heavier)
    total_score: float               # Lower is better (overall cost score)


class CostBasedPlanner:
    """Evaluates multiple execution strategies and selects the lowest-cost one.

    Uses hardware characteristics (bandwidth, latency) and historical telemetry
    data to calibrate cost coefficients over time.
    """

    def __init__(self, telemetry: Optional[TelemetrySubsystem] = None):
        self._telemetry = telemetry or TelemetrySubsystem()
        self._memory_planner = MemoryPlanner()

    def select_best_strategy(
        self,
        model: Dict[str, Any],
        system_info: Dict[str, Any],
        target_quant: Optional[str] = None,
        target_context: Optional[int] = None,
    ) -> ExecutionPlan:
        """Select the strategy with the lowest predicted cost."""
        name = model.get("name", "unknown")
        params_raw = model.get("parameters_raw", 0)
        params_b = params_raw / 1e9 if params_raw else 0
        is_moe = model.get("is_moe", False)
        model_ctx = model.get("context_length", 4096) or 4096
        ctx = min(model_ctx, target_context) if target_context and target_context > 0 else model_ctx

        # 1. Profile system
        self._memory_planner.profile_system(system_info)
        
        # 2. Compile list of candidates to evaluate
        quants = [target_quant] if target_quant else ["Q4_K_M", "Q8_0", "BF16"]
        candidates: List[CostEvaluation] = []

        for q in quants:
            if not q:
                continue
            footprint_gb = _estimate_footprint_gb(params_b, q)
            
            # Map memory layout for this quant
            mmap = self._memory_planner.plan(
                model_footprint_gb=footprint_gb,
                working_set_ratio=0.15 if is_moe else 1.0,
                is_moe=is_moe,
            )
            
            if mmap.strategy == "no_fit":
                continue

            # Evaluate strategy costs
            evals = self._evaluate_strategy(mmap, q, params_b, is_moe, system_info)
            candidates.extend(evals)

        if not candidates:
            # Fallback to no fit
            return ExecutionPlan(
                model_name=name,
                model_params_b=round(params_b, 1),
                strategy=ExecutionStrategy.NO_FIT,
            )

        # 3. Sort candidates by cost score (lowest first)
        candidates.sort(key=lambda c: c.total_score)
        best = candidates[0]

        # Re-plan memory placement for the winning strategy
        footprint_gb = _estimate_footprint_gb(params_b, best.quantisation if hasattr(best, 'quantisation') else "Q4_K_M")
        mmap = self._memory_planner.plan(
            model_footprint_gb=footprint_gb,
            working_set_ratio=0.15 if is_moe else 1.0,
            is_moe=is_moe,
        )

        notes = [
            f"Cost model evaluated {len(candidates)} strategies. Winner: {best.strategy.name} "
            f"({best.estimated_tps:.2f} TPS, score {best.total_score:.1f})"
        ]

        return ExecutionPlan(
            model_name=name,
            model_params_b=round(params_b, 1),
            is_moe=is_moe,
            strategy=best.strategy,
            quantisation=best.quantisation if hasattr(best, 'quantisation') else "Q4_K_M",
            memory_map=mmap,
            estimated_tps=best.estimated_tps,
            estimated_ttft_ms=best.estimated_latency_ms,
            context_length=ctx,
            backend_hint=best.backend_hint,
            streaming_enabled=mmap.needs_streaming,
            prefetch_enabled=mmap.needs_streaming,
            notes=notes,
        )

    # -- Cost Evaluation --

    def _evaluate_strategy(
        self,
        mmap: MemoryMap,
        quant: str,
        params_b: float,
        is_moe: bool,
        system_info: Dict[str, Any],
    ) -> List[CostEvaluation]:
        evals = []
        
        # We model latency as a function of size (GB) / bandwidth (GBps) + I/O latency
        bw = mmap.estimated_bandwidth_gbps
        if bw <= 0:
            return evals

        size_gb = mmap.total_model_gb
        active_gb = mmap.working_set_gb

        # Baseline compute coefficients
        compute_ms_per_gb = 2.0  # ms/GB for CPU compute
        if system_info.get("has_gpu"):
            compute_ms_per_gb = 0.1  # ms/GB for GPU compute

        # 1. Estimate Prefill Latency (TTFT)
        # Prefill processes all prompt tokens at once, so it reads the model weights once
        prefill_read_time = (size_gb / bw) * 1000.0
        prefill_compute = size_gb * compute_ms_per_gb
        ttft = prefill_read_time + prefill_compute

        # 2. Estimate Decoding TPS
        # Decoding processes one token at a time, reading the active weight set per step
        decoding_read_time_s = active_gb / bw
        decoding_compute_s = (active_gb * compute_ms_per_gb) / 1000.0
        
        # If streaming, add predicted I/O stall penalty based on prefetch failure rate (default 10%)
        stall_penalty_s = 0.0
        if mmap.needs_streaming:
            stall_penalty_s = (active_gb / mmap.estimated_bandwidth_gbps) * 0.10

        step_time_s = decoding_read_time_s + decoding_compute_s + stall_penalty_s
        tps = 1.0 / step_time_s if step_time_s > 0 else 0.0
        if is_moe:
            tps *= 0.85  # Routing overhead

        # 3. Calculate Overall Cost Score (lower is better)
        # Weights: 60% speed (TPS), 30% latency (TTFT), 10% compute/memory overhead
        speed_cost = 100.0 / (tps + 0.01)
        latency_cost = ttft * 0.1
        overhead = size_gb * (0.01 if system_info.get("has_gpu") else 0.05)
        
        total_score = speed_cost * 0.60 + latency_cost * 0.30 + overhead * 0.10

        # Adjust score using historical telemetry calibration
        history = self._telemetry.get_history(limit=5)
        for h in history:
            if h.get("strategy") == mmap.strategy and h.get("quantisation") == quant:
                actual_tps = h.get("average_tps", 0)
                if actual_tps > 0:
                    # Calibrate estimate closer to observed historical performance
                    tps = (tps + actual_tps) / 2.0
                    total_score = (total_score + (100.0 / (actual_tps + 0.01))) / 2.0

        # Map to appropriate runtime backend
        backend_hint = "llamacpp"
        exec_strategy = ExecutionStrategy.RESIDENT

        if mmap.needs_streaming:
            exec_strategy = ExecutionStrategy.STREAM
            backend_hint = "llamacpp"
        elif MemoryTier.VRAM in mmap.placement and not MemoryTier.RAM in mmap.placement:
            backend_hint = "vllm"
        elif MemoryTier.VRAM in mmap.placement and MemoryTier.RAM in mmap.placement:
            exec_strategy = ExecutionStrategy.GPU_OFFLOAD
            backend_hint = "llamacpp"

        candidate = CostEvaluation(
            strategy=exec_strategy,
            backend_hint=backend_hint,
            estimated_latency_ms=ttft,
            estimated_tps=tps,
            estimated_stall_time_ms=stall_penalty_s * 1000.0,
            compute_overhead_score=overhead,
            total_score=total_score,
        )
        # Hack to attach quant parameter dynamically
        candidate.quantisation = quant
        
        evals.append(candidate)
        return evals
