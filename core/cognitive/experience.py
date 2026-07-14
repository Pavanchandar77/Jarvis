# core/cognitive/experience.py
"""Spark Experience & Decision Memory.

Structures complete engineering experiences (successful refactors, architectural
decisions, rationale, trade-offs, and outcomes) as reusable knowledge nodes.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .graph import UnifiedCognitiveGraph

logger = logging.getLogger("spark.cognitive.experience")


@dataclass
class EngineeringExperience:
    """A documented engineering session containing problem, solution, and outcome details."""
    title: str
    problem_description: str
    solution_applied: str
    outcome: str                      # success | partial | failure
    lessons_learned: List[str] = field(default_factory=list)


@dataclass
class ArchitecturalDecision:
    """A documented system architecture design decision (ADR)."""
    decision_id: str
    title: str
    rationale: str
    alternatives_considered: List[str] = field(default_factory=list)
    trade_offs: Dict[str, str] = field(default_factory=dict)
    status: str = "approved"         # proposed | approved | superseded | rejected


class ExperienceMemory:
    """Logs and links experiences and design choices to the cognitive graph."""

    def __init__(self, graph: UnifiedCognitiveGraph):
        self._graph = graph

    def record_experience(self, exp: EngineeringExperience) -> str:
        """Create an experience node and link it to relevant system/project nodes."""
        node_id = f"exp_{uuid.uuid4().hex[:8]}"
        
        self._graph.add_node(
            node_id=node_id,
            kind="experience",
            properties={
                "title": exp.title,
                "problem": exp.problem_description,
                "solution": exp.solution_applied,
                "outcome": exp.outcome,
                "lessons": exp.lessons_learned,
            }
        )
        logger.info("Experience Memory: Recorded engineering experience '%s' as node %s", exp.title, node_id)
        return node_id

    def record_adr(self, adr: ArchitecturalDecision) -> str:
        """Create an Architectural Decision Record (ADR) node in the graph."""
        node_id = f"adr_{adr.decision_id}"
        
        self._graph.add_node(
            node_id=node_id,
            kind="adr",
            properties={
                "title": adr.title,
                "rationale": adr.rationale,
                "alternatives": adr.alternatives_considered,
                "trade_offs": adr.trade_offs,
                "status": adr.status,
            }
        )
        logger.info("Decision Memory: Recorded ADR '%s' as node %s", adr.title, node_id)
        return node_id
