# core/cognitive/analogy.py
"""Spark Analogical Reasoning Engine.

Scans the Cognitive Graph to locate structural or semantic analogies to current
problems (similar bugs, optimization traces, or designs) to reuse engineering choices.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from .graph import UnifiedCognitiveGraph, GraphNode

logger = logging.getLogger("spark.cognitive.analogy")


@dataclass
class AnalogyMatch:
    """A match representing a similar engineering case in the graph."""
    source_node_id: str
    similarity_score: float         # 0.0 to 1.0
    shared_features: List[str]
    suggested_solution: str


class AnalogicalReasoningEngine:
    """Searches the graph for structural analogies to resolve current engineering tasks."""

    def __init__(self, graph: UnifiedCognitiveGraph):
        self._graph = graph

    def find_analogies(self, problem_description: str, kind: str = "experience") -> List[AnalogyMatch]:
        """Search the graph for similar problem scopes using Jaccard keyword overlaps."""
        logger.info("Analogical Reasoning: Searching for matching analogies for query: '%s'...", problem_description[:50])
        matches: List[AnalogyMatch] = []
        
        candidates = self._graph.get_nodes_by_kind(kind)
        if not candidates:
            return matches

        def clean_words(text: str) -> set[str]:
            cleaned = re.sub(r"[^\w\s]", " ", text.lower())
            return set(cleaned.split())

        prob_words = clean_words(problem_description)
        
        for cand in candidates:
            # Combine title, problem description, and lessons to get rich match surface
            title = cand.properties.get("title", "")
            problem = cand.properties.get("problem", "")
            combined_desc = f"{title} {problem}"
            
            cand_words = clean_words(combined_desc)
            
            # Compute Jaccard overlap
            intersection = prob_words.intersection(cand_words)
            union = prob_words.union(cand_words)
            
            score = len(intersection) / len(union) if union else 0.0
            
            if score > 0.05:  # Match threshold
                matches.append(AnalogyMatch(
                    source_node_id=cand.node_id,
                    similarity_score=round(score, 2),
                    shared_features=list(intersection),
                    suggested_solution=cand.properties.get("solution", "No solution recorded.")
                ))

        # Sort matches by similarity score (highest first)
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        logger.info("Analogical Reasoning: Found %d matching case analogies.", len(matches))
        return matches
