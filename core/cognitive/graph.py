# core/cognitive/graph.py
"""Spark Unified Cognitive Graph.

Represents all software projects, conversations, code elements, policies, execution
traces, and user preferences as a unified, queryable entity-relationship graph.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("spark.cognitive.graph")


@dataclass
class GraphNode:
    """A node in the cognitive graph."""
    node_id: str
    kind: str                         # model | code | conversation | project | strategy | user | concept
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class GraphEdge:
    """A directed relationship between two nodes in the cognitive graph."""
    source_id: str
    target_id: str
    relationship: str                # uses | subclass_of | implements | refactors | verifies | similar_to
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)


class UnifiedCognitiveGraph:
    """Manages creation, query, and persistence of the cognitive graph."""

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir:
            self._persist_dir = Path(os.path.expanduser(persist_dir))
        else:
            self._persist_dir = Path.home() / ".spark"

        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._graph_path = self._persist_dir / "cognitive_graph.json"
        
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge] = []
        self._load_graph()

    def add_node(self, node_id: str, kind: str, properties: Dict[str, Any]) -> GraphNode:
        """Add or update a node in the graph."""
        node = GraphNode(node_id=node_id, kind=kind, properties=properties)
        self._nodes[node_id] = node
        self._save_graph()
        return node

    def add_edge(self, source_id: str, target_id: str, relationship: str, weight: float = 1.0) -> None:
        """Add a directed edge between two nodes."""
        if source_id not in self._nodes or target_id not in self._nodes:
            logger.warning("Cognitive Graph: Cannot link non-existent nodes %s -> %s", source_id, target_id)
            return

        # Check duplicates
        for edge in self._edges:
            if edge.source_id == source_id and edge.target_id == target_id and edge.relationship == relationship:
                edge.weight = weight
                self._save_graph()
                return

        self._edges.append(GraphEdge(source_id=source_id, target_id=target_id, relationship=relationship, weight=weight))
        self._save_graph()

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self._nodes.get(node_id)

    def get_nodes_by_kind(self, kind: str) -> List[GraphNode]:
        return [n for n in self._nodes.values() if n.kind == kind]

    def get_neighbors(self, node_id: str) -> List[tuple[GraphNode, str]]:
        """Retrieve neighboring nodes along with their relationship type."""
        neighbors = []
        for edge in self._edges:
            if edge.source_id == node_id and edge.target_id in self._nodes:
                neighbors.append((self._nodes[edge.target_id], edge.relationship))
            elif edge.target_id == node_id and edge.source_id in self._nodes:
                neighbors.append((self._nodes[edge.source_id], f"rev_{edge.relationship}"))
        return neighbors

    def get_edges(self) -> List[GraphEdge]:
        return list(self._edges)

    # -- Persistence --

    def _load_graph(self) -> None:
        if self._graph_path.is_file():
            try:
                data = json.loads(self._graph_path.read_text(encoding="utf-8"))
                for n in data.get("nodes", []):
                    self._nodes[n["node_id"]] = GraphNode(**n)
                for e in data.get("edges", []):
                    self._edges.append(GraphEdge(**e))
                logger.info("Cognitive Graph: Loaded %d nodes and %d edges.", len(self._nodes), len(self._edges))
            except Exception as e:
                logger.warning("Failed to load cognitive graph: %s", e)

    def _save_graph(self) -> None:
        try:
            raw = {
                "nodes": [asdict(n) for n in self._nodes.values()],
                "edges": [asdict(e) for e in self._edges],
            }
            self._graph_path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to save cognitive graph: %s", e)
