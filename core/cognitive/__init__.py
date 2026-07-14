# core/cognitive/__init__.py
"""Spark Cognitive Operating System.

Provides the knowledge representation and abstraction layers that support long-term
memory, analogical reasoning, autonomous research, and cross-project transfers.
"""

from .graph import UnifiedCognitiveGraph, GraphNode, GraphEdge
from .experience import EngineeringExperience, ArchitecturalDecision, ExperienceMemory
from .discovery import DiscoveredPattern, HighLevelConcept, PatternDiscoveryEngine, ConceptFormationEngine
from .analogy import AnalogyMatch, AnalogicalReasoningEngine
from .evolution import ResearchTopic, GraphQualityMetrics, KnowledgeEvolutionEngine
from .cross_project import TransferredKnowledge, CrossProjectIntelligence
from .dashboard import CognitiveDashboardData, CognitiveDashboardBackend
from .migration import SemanticTwinMigrator

__all__ = [
    "UnifiedCognitiveGraph",
    "GraphNode",
    "GraphEdge",
    "EngineeringExperience",
    "ArchitecturalDecision",
    "ExperienceMemory",
    "DiscoveredPattern",
    "HighLevelConcept",
    "PatternDiscoveryEngine",
    "ConceptFormationEngine",
    "AnalogyMatch",
    "AnalogicalReasoningEngine",
    "ResearchTopic",
    "GraphQualityMetrics",
    "KnowledgeEvolutionEngine",
    "TransferredKnowledge",
    "CrossProjectIntelligence",
    "CognitiveDashboardData",
    "CognitiveDashboardBackend",
    "SemanticTwinMigrator",
]
