# core/engine/__init__.py
"""Spark Universal Inference Engine.

A model-agnostic execution engine that treats storage as part of the
memory hierarchy.  Instead of routing models to fixed backends, Spark
produces an ExecutionPlan that orchestrates RAM, VRAM, SSD, caching,
and compute through a unified planner.

    ExecutionPlanner -> MemoryPlanner -> StreamingScheduler
         |                                     |
         v                                     v
    ExecutionPlan                         CacheManager
                                               |
                                               v
                                          TensorLoader
                                               |
                                               v
                                        InferenceRuntime
"""

from .memory import (
    MemoryTier,
    TierProfile,
    MemoryMap,
    MemoryPlanner,
    DEFAULT_BANDWIDTH,
    DEFAULT_LATENCY,
)
from .planner import (
    ExecutionStrategy,
    ExecutionPlan,
    ExecutionPlanner,
)
from .scheduler import StreamingScheduler, TensorBlock, SchedulerState
from .cache import CacheManager, CacheEntry, CacheStats
from .loader import TensorLoader, LoadRequest, LoadResult, StorageFormat, detect_format
from .prefetch import PredictivePrefetchEngine, PrefetchStats
from .telemetry import TelemetrySubsystem, SessionTelemetry
from .async_io import AsyncIOPipeline
from .cost_planner import CostBasedPlanner, CostEvaluation
from .fingerprint import HardwareFingerprinter, HardwareProfile
from .dna import ModelDNA, ExecutionDNADatabase
from .neural_planner import NeuralExecutionPlanner
from .graph_planner import GraphMemoryPlanner, ExecutionCluster
from .intent_cache import IntentBasedCacheManager, UserIntent, IntentPolicy
from .optimizer import AutonomousOptimizer, OptimizationReport
from .fabric import UniversalMemoryFabric, MemoryPage

__all__ = [
    # Memory
    "MemoryTier",
    "TierProfile",
    "MemoryMap",
    "MemoryPlanner",
    "DEFAULT_BANDWIDTH",
    "DEFAULT_LATENCY",
    # Planner
    "ExecutionStrategy",
    "ExecutionPlan",
    "ExecutionPlanner",
    # Scheduler
    "StreamingScheduler",
    "TensorBlock",
    "SchedulerState",
    # Cache
    "CacheManager",
    "CacheEntry",
    "CacheStats",
    # Loader
    "TensorLoader",
    "LoadRequest",
    "LoadResult",
    "StorageFormat",
    "detect_format",
    # Prefetch
    "PredictivePrefetchEngine",
    "PrefetchStats",
    # Telemetry
    "TelemetrySubsystem",
    "SessionTelemetry",
    # Async I/O
    "AsyncIOPipeline",
    # Cost Planner
    "CostBasedPlanner",
    "CostEvaluation",
    # Fingerprint
    "HardwareFingerprinter",
    "HardwareProfile",
    # DNA
    "ModelDNA",
    "ExecutionDNADatabase",
    # Neural Planner
    "NeuralExecutionPlanner",
    # Graph Planner
    "GraphMemoryPlanner",
    "ExecutionCluster",
    # Intent Cache
    "IntentBasedCacheManager",
    "UserIntent",
    "IntentPolicy",
    # Optimizer
    "AutonomousOptimizer",
    "OptimizationReport",
    # Fabric
    "UniversalMemoryFabric",
    "MemoryPage",
]
