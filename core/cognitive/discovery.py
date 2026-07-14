# core/cognitive/discovery.py
"""Spark Pattern Discovery & Concept Formation Engine.

Analyzes nodes, relationships, and code topologies in the Cognitive Graph to
extract recurring design patterns, anti-patterns, and build higher-level
conceptual abstractions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Set

from .graph import UnifiedCognitiveGraph, GraphNode

logger = logging.getLogger("spark.cognitive.discovery")


@dataclass
class DiscoveredPattern:
    """A recurring structure or sequence detected in the graph."""
    pattern_id: str
    kind: str                         # architectural | workflow | anti-pattern
    description: str
    frequency: int
    participating_node_ids: List[str] = field(default_factory=list)


@dataclass
class HighLevelConcept:
    """A synthesized conceptual abstraction based on observed instances."""
    concept_id: str
    name: str
    generalization: str
    common_failure_modes: List[str] = field(default_factory=list)
    exemplar_node_ids: List[str] = field(default_factory=list)


class PatternDiscoveryEngine:
    """Scans structural graphs to locate design layouts and form concepts."""

    def __init__(self, graph: UnifiedCognitiveGraph):
        self._graph = graph

    def discover_patterns(self) -> List[DiscoveredPattern]:
        """Perform topological analysis on edges to find recurring structures."""
        logger.info("Pattern Discovery: Analyzing Cognitive Graph topology...")
        
        patterns = []
        nodes = self._graph.get_edges()
        if not nodes:
            return patterns

        # Group edges by relationship type to check recurring layouts
        relationship_counts = {}
        for edge in nodes:
            relationship_counts[edge.relationship] = relationship_counts.get(edge.relationship, 0) + 1

        for rel, freq in relationship_counts.items():
            if freq >= 3:
                # We have a recurring pattern of relationships
                patterns.append(DiscoveredPattern(
                    pattern_id=f"pat_rel_{rel}",
                    kind="architectural",
                    description=f"Recurring '{rel}' relationship pattern detected across multiple nodes.",
                    frequency=freq,
                ))

        logger.info("Pattern Discovery: Found %d recurring structural patterns.", len(patterns))
        return patterns

    def form_concepts(self) -> List[HighLevelConcept]:
        """Synthesize high-level concepts from groups of related nodes."""
        logger.info("Concept Formation: Grouping similar instances into abstractions...")
        
        concepts = []
        # Group experiences by category keywords
        exps = self._graph.get_nodes_by_kind("experience")
        if not exps:
            return concepts

        categories: Dict[str, List[str]] = {}
        for e in exps:
            title = e.properties.get("title", "").lower()
            if "cache" in title or "pin" in title:
                categories.setdefault("CachingTemplate", []).append(e.node_id)
            elif "router" in title or "routing" in title:
                categories.setdefault("DynamicRouterDesign", []).append(e.node_id)

        for concept_name, instance_ids in categories.items():
            if len(instance_ids) >= 1:
                concept_id = f"con_{concept_name.lower()}"
                
                # Check if concept node exists in graph, if not add it
                concept_node = self._graph.get_node(concept_id)
                if not concept_node:
                    self._graph.add_node(
                        node_id=concept_id,
                        kind="concept",
                        properties={
                            "name": concept_name,
                            "generalization": f"Abstract concept of {concept_name} synthesized from historical runs.",
                            "exemplars": instance_ids
                        }
                    )
                    
                    # Add links from instances to the new concept
                    for inst_id in instance_ids:
                        self._graph.add_edge(inst_id, concept_id, "subclass_of", weight=1.0)
                
                concepts.append(HighLevelConcept(
                    concept_id=concept_id,
                    name=concept_name,
                    generalization=f"Abstract concept of {concept_name}.",
                    exemplar_node_ids=instance_ids
                ))

        logger.info("Concept Formation: Synthesized %d conceptual nodes.", len(concepts))
        return concepts
class ConceptFormationEngine(PatternDiscoveryEngine):
    """Alias for PatternDiscoveryEngine to support conceptual grouping API."""
    pass
