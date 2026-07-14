# core/engine/memory.py
"""Spark Hierarchical Memory Abstraction.

Models the storage hierarchy (VRAM -> RAM -> SSD -> HDD -> Remote) and
plans how model tensors are distributed across tiers based on capacity,
bandwidth, and latency.
"""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict, Optional


class MemoryTier(IntEnum):
    """Memory hierarchy tiers, ordered fastest to slowest."""
    VRAM   = 0   # GPU video memory (HBM / GDDR)
    RAM    = 1   # System DDR memory
    SSD    = 2   # NVMe / SATA solid-state
    HDD    = 3   # Spinning disk
    REMOTE = 4   # Network-attached storage (future)


# Default bandwidth estimates in GB/s per tier.
DEFAULT_BANDWIDTH: Dict[MemoryTier, float] = {
    MemoryTier.VRAM:   900.0,
    MemoryTier.RAM:     50.0,
    MemoryTier.SSD:      3.5,
    MemoryTier.HDD:      0.15,
    MemoryTier.REMOTE:   0.5,
}

# Default latency estimates in microseconds.
DEFAULT_LATENCY: Dict[MemoryTier, float] = {
    MemoryTier.VRAM:      0.1,
    MemoryTier.RAM:     100.0,
    MemoryTier.SSD:      10.0,
    MemoryTier.HDD:    5000.0,
    MemoryTier.REMOTE: 50000.0,
}


@dataclass
class TierProfile:
    """Measured or estimated characteristics of a single memory tier."""
    tier: MemoryTier
    capacity_gb: float = 0.0
    available_gb: float = 0.0
    bandwidth_gbps: float = 0.0
    latency_us: float = 0.0
    present: bool = False

    @property
    def usable(self) -> bool:
        return self.present and self.available_gb > 0


@dataclass
class MemoryMap:
    """How a model's data is distributed across memory tiers."""
    resident_gb: float = 0.0         # Always in fast memory (VRAM + RAM)
    streaming_gb: float = 0.0        # Streamed from slower storage on demand
    total_model_gb: float = 0.0
    working_set_gb: float = 0.0      # Active memory per forward pass
    kv_overhead_gb: float = 2.0      # KV cache + runtime overhead
    placement: Dict[MemoryTier, float] = field(default_factory=dict)
    strategy: str = "resident"       # resident | stream | hybrid | no_fit
    estimated_bandwidth_gbps: float = 0.0

    @property
    def fits(self) -> bool:
        return self.strategy != "no_fit"

    @property
    def needs_streaming(self) -> bool:
        return self.strategy in ("stream", "hybrid")


class MemoryPlanner:
    """Plans model placement across the memory hierarchy.

    Given a system's memory tier profiles and a model's footprint, decides
    the optimal data distribution and streaming strategy.
    """

    def __init__(self):
        self._tiers: Dict[MemoryTier, TierProfile] = {}

    def profile_system(self, system_info: dict) -> Dict[MemoryTier, TierProfile]:
        """Build tier profiles from a hwfit system_info dict."""
        tiers: Dict[MemoryTier, TierProfile] = {}

        # -- VRAM --
        vram = system_info.get("gpu_vram_gb") or 0
        if vram > 0:
            tiers[MemoryTier.VRAM] = TierProfile(
                tier=MemoryTier.VRAM,
                capacity_gb=vram,
                available_gb=vram * 0.90,
                bandwidth_gbps=DEFAULT_BANDWIDTH[MemoryTier.VRAM],
                latency_us=DEFAULT_LATENCY[MemoryTier.VRAM],
                present=True,
            )

        # -- RAM --
        ram = system_info.get("total_ram_gb") or 0
        avail = system_info.get("available_ram_gb") or (ram * 0.70)
        if ram > 0:
            tiers[MemoryTier.RAM] = TierProfile(
                tier=MemoryTier.RAM,
                capacity_gb=ram,
                available_gb=avail,
                bandwidth_gbps=DEFAULT_BANDWIDTH[MemoryTier.RAM],
                latency_us=DEFAULT_LATENCY[MemoryTier.RAM],
                present=True,
            )

        # -- SSD / HDD --
        disk_type = (system_info.get("disk_type") or "").lower()
        disk_free = system_info.get("disk_free_gb") or 0
        disk_bw = (system_info.get("disk_speed_mbps") or 0) / 1000.0

        if disk_free > 0:
            tier = MemoryTier.SSD if "ssd" in disk_type else MemoryTier.HDD
            tiers[tier] = TierProfile(
                tier=tier,
                capacity_gb=disk_free,
                available_gb=disk_free * 0.90,
                bandwidth_gbps=disk_bw or DEFAULT_BANDWIDTH[tier],
                latency_us=DEFAULT_LATENCY[tier],
                present=True,
            )

        self._tiers = tiers
        return tiers

    @property
    def tiers(self) -> Dict[MemoryTier, TierProfile]:
        return dict(self._tiers)

    def plan(
        self,
        model_footprint_gb: float,
        working_set_ratio: float = 1.0,
        is_moe: bool = False,
    ) -> MemoryMap:
        """Decide where model data should live.

        Args:
            model_footprint_gb: Total size of quantised model weights.
            working_set_ratio: Fraction of model active per forward pass.
                Dense: 1.0 (all weights read), MoE: 0.10-0.20 (active experts).
            is_moe: Whether the model uses Mixture-of-Experts routing.
        """
        if is_moe:
            working_set_ratio = min(working_set_ratio, 0.20)
        else:
            working_set_ratio = 1.0

        ws_gb = model_footprint_gb * working_set_ratio
        kv_overhead = 2.0

        vram = self._tiers.get(MemoryTier.VRAM)
        ram  = self._tiers.get(MemoryTier.RAM)
        ssd  = self._tiers.get(MemoryTier.SSD) or self._tiers.get(MemoryTier.HDD)

        # -- Strategy 1: Fully resident in VRAM --
        if vram and vram.usable and model_footprint_gb + kv_overhead <= vram.available_gb:
            return MemoryMap(
                resident_gb=model_footprint_gb,
                total_model_gb=model_footprint_gb,
                working_set_gb=ws_gb,
                kv_overhead_gb=kv_overhead,
                placement={MemoryTier.VRAM: model_footprint_gb},
                strategy="resident",
                estimated_bandwidth_gbps=vram.bandwidth_gbps,
            )

        # -- Strategy 2: Fully resident in RAM (+ optional VRAM acceleration) --
        if ram and ram.usable and model_footprint_gb + kv_overhead <= ram.available_gb:
            placement: Dict[MemoryTier, float] = {}
            if vram and vram.usable:
                in_vram = min(model_footprint_gb, vram.available_gb)
                placement[MemoryTier.VRAM] = in_vram
                placement[MemoryTier.RAM] = model_footprint_gb - in_vram + kv_overhead
            else:
                placement[MemoryTier.RAM] = model_footprint_gb + kv_overhead
            return MemoryMap(
                resident_gb=model_footprint_gb,
                total_model_gb=model_footprint_gb,
                working_set_gb=ws_gb,
                kv_overhead_gb=kv_overhead,
                placement=placement,
                strategy="resident",
                estimated_bandwidth_gbps=(
                    vram.bandwidth_gbps if vram and vram.usable
                    else ram.bandwidth_gbps
                ),
            )

        # -- Strategy 3: Stream from SSD, working set pinned in RAM/VRAM --
        if ram and ram.usable and ssd and ssd.usable:
            if model_footprint_gb <= ssd.available_gb:
                ram_budget = max(0.0, ram.available_gb - kv_overhead)
                in_ram = min(ws_gb, ram_budget)
                in_ssd = model_footprint_gb - in_ram

                placement = {}
                if vram and vram.usable:
                    in_vram = min(in_ram, vram.available_gb)
                    placement[MemoryTier.VRAM] = in_vram
                    placement[MemoryTier.RAM] = (in_ram - in_vram) + kv_overhead
                else:
                    placement[MemoryTier.RAM] = in_ram + kv_overhead

                placement[ssd.tier] = in_ssd

                # Effective bandwidth: harmonic blend of fast + slow paths
                fast_bw = (
                    vram.bandwidth_gbps if vram and vram.usable
                    else ram.bandwidth_gbps
                )
                fast_frac = in_ram / model_footprint_gb if model_footprint_gb > 0 else 0
                slow_frac = 1.0 - fast_frac
                if fast_frac + slow_frac > 0 and fast_bw > 0 and ssd.bandwidth_gbps > 0:
                    eff_bw = 1.0 / (
                        fast_frac / fast_bw + slow_frac / ssd.bandwidth_gbps
                    )
                else:
                    eff_bw = ssd.bandwidth_gbps

                return MemoryMap(
                    resident_gb=in_ram + kv_overhead,
                    streaming_gb=in_ssd,
                    total_model_gb=model_footprint_gb,
                    working_set_gb=ws_gb,
                    kv_overhead_gb=kv_overhead,
                    placement=placement,
                    strategy="stream",
                    estimated_bandwidth_gbps=eff_bw,
                )

        # -- No viable placement --
        return MemoryMap(
            total_model_gb=model_footprint_gb,
            working_set_gb=ws_gb,
            strategy="no_fit",
        )
