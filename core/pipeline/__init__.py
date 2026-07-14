# core/pipeline/__init__.py
"""Spark Adaptive Inference Pipeline.

An orchestrator layer that analyzes queries, decomposes tasks into dependent
DAG nodes, selects optimal models using hardware capability maps, routes subtasks
to specialize models, runs verification engines, and synthesizes final responses.
"""

from .intent import IntentAnalyzer, IntentAnalysis
from .planner import TaskPlanner, TaskNode
from .capability import CapabilityAnalyzer, RequiredCapabilities
from .router import ModelRouter
from .orchestrator import MultiModelOrchestrator, OrchestrationStep
from .reasoning import ReasoningController, ReasoningConfig
from .verifier import VerificationEngine, VerificationResult
from .synthesizer import ResponseSynthesizer
from .memory import PipelineMemory, PipelineRunRecord

__all__ = [
    "IntentAnalyzer",
    "IntentAnalysis",
    "TaskPlanner",
    "TaskNode",
    "CapabilityAnalyzer",
    "RequiredCapabilities",
    "ModelRouter",
    "MultiModelOrchestrator",
    "OrchestrationStep",
    "ReasoningController",
    "ReasoningConfig",
    "VerificationEngine",
    "VerificationResult",
    "ResponseSynthesizer",
    "PipelineMemory",
    "PipelineRunRecord",
]
