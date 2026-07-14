# core/intelligence/__init__.py
"""Spark Autonomous Intelligence Engine.

Maintains unified performance databases, manages versioned execution policies,
conducts automated A/B tests, runs offline benchmark suites, and runs background
evolution workers to promote optimizations to production.
"""

from .warehouse import PerformanceWarehouse, TransactionRecord
from .policy import ExecutionPolicy, PolicyEngine
from .experiment import ABExperiment, ExperimentEngine
from .evaluator import BenchmarkTask, OfflineEvaluator
from .meta_router import MetaRouter
from .evolution import PromotionLog, KnowledgeEvolutionEngine

__all__ = [
    "PerformanceWarehouse",
    "TransactionRecord",
    "ExecutionPolicy",
    "PolicyEngine",
    "ABExperiment",
    "ExperimentEngine",
    "BenchmarkTask",
    "OfflineEvaluator",
    "MetaRouter",
    "PromotionLog",
    "KnowledgeEvolutionEngine",
]
