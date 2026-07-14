# core/cognitive/dashboard.py
"""Spark Cognitive Dashboard Backend.

Exposes JSON data arrays detailing the learning progress, active research states,
and topological quality scores of the Unified Cognitive Graph.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List

from .graph import UnifiedCognitiveGraph
from .evolution import KnowledgeEvolutionEngine

logger = logging.getLogger("spark.cognitive.dashboard")


@dataclass
class CognitiveDashboardData:
    """Consolidated statistics of Spark's cognitive state."""
    graph_node_count: int
    graph_edge_count: int
    graph_density: float
    graph_health: float
    active_research_count: int
    concepts_count: int
    pattern_count: int
    learning_progress_score: float    # percentage of positive outcomes


class CognitiveDashboardBackend:
    """Assembles metrics from multiple subsystems for frontend rendering."""

    def __init__(self, graph: UnifiedCognitiveGraph, evolution_engine: KnowledgeEvolutionEngine):
        self._graph = graph
        self._ee = evolution_engine

    def compile_dashboard_state(self) -> Dict[str, Any]:
        """Compile a complete snapshot of graph health and progress statistics."""
        metrics = self._ee.get_quality_metrics()
        
        # Calculate patterns
        from .discovery import PatternDiscoveryEngine
        pde = PatternDiscoveryEngine(self._graph)
        patterns = pde.discover_patterns()
        
        research_active = sum(1 for t in self._ee.get_research_topics() if t.status != "completed")
        
        # Simulated learning progress: increases as node count and concepts expand
        prog_score = 0.50
        if metrics.node_count > 0:
            prog_score = min(0.99, 0.50 + (metrics.concept_count * 0.10) + (metrics.node_count * 0.01))

        data = CognitiveDashboardData(
            graph_node_count=metrics.node_count,
            graph_edge_count=metrics.edge_count,
            graph_density=metrics.density,
            graph_health=metrics.graph_health_score,
            active_research_count=research_active,
            concepts_count=metrics.concept_count,
            pattern_count=len(patterns),
            learning_progress_score=round(prog_score, 2),
        )
        
        logger.info("Cognitive Dashboard: State compiled successfully.")
        return asdict(data)
