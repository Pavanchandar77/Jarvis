# core/cognitive/migration.py
"""Spark Semantic Twin Migration Engine.

Provides incremental migration pathways to port nodes, edges, and index metadata
from legacy Semantic Twin repositories into the Unified Cognitive Graph.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .graph import UnifiedCognitiveGraph
from services.semantic_twin.storage.repository import TwinRepository

logger = logging.getLogger("spark.cognitive.migration")


class SemanticTwinMigrator:
    """Migrates nodes/edges from legacy Semantic Twin packages into Cognitive Graphs."""

    def __init__(self, graph: UnifiedCognitiveGraph, repo_base: str | Path):
        self._graph = graph
        self._repo = TwinRepository(repo_base)

    def run_migration(self, owner: Optional[str] = None) -> Dict[str, Any]:
        """Iterate over all twin packages and merge nodes/edges incrementally."""
        logger.info("Migration Engine: Starting incremental migration from base: %s", self._repo.base)
        
        twins_metadata = self._repo.list(owner=owner)
        migrated_twins = 0
        total_nodes = 0
        total_edges = 0

        for meta in twins_metadata:
            twin_id = meta["twin_id"]
            try:
                # Load the full twin package including graph nodes
                twin = self._repo.load(twin_id, owner=owner, include_graph=True)
                
                # Check if this twin/revision is already in the graph
                node_id = f"twin_{twin_id}"
                existing_node = self._graph.get_node(node_id)
                if existing_node and existing_node.properties.get("revision", 0) >= twin.content_revision:
                    logger.info("Migration Engine: Twin %s already migrated at revision %d, skipping.", twin_id, twin.content_revision)
                    continue
                
                # Migrate Twin node itself
                self._graph.add_node(
                    node_id=node_id,
                    kind="project",
                    properties={
                        "application_id": twin.application_id,
                        "revision": twin.content_revision,
                        "updated_at": twin.updated_at,
                        "owner": twin.owner,
                    }
                )

                # Migrate all Semantic Nodes
                for node in twin.nodes:
                    source_file = getattr(node, "source_file", None)
                    self._graph.add_node(
                        node_id=node.id,
                        kind=node.kind.name if hasattr(node.kind, "name") else str(node.kind),
                        properties={
                            "name": node.name,
                            "source_file": source_file,
                            "description": getattr(node, "description", ""),
                        }
                    )
                    # Link node to the project/twin
                    self._graph.add_edge(node.id, node_id, "implements", weight=1.0)
                    total_nodes += 1

                # Migrate all Semantic Edges
                for edge in twin.edges:
                    self._graph.add_edge(
                        source_id=edge.source,
                        target_id=edge.target,
                        relationship=edge.kind.name if hasattr(edge.kind, "name") else str(edge.kind),
                        weight=edge.weight
                    )
                    total_edges += 1

                migrated_twins += 1
                logger.info("Migration Engine: Migrated twin '%s' (%d nodes, %d edges)", twin_id, len(twin.nodes), len(twin.edges))

            except Exception as e:
                logger.warning("Migration Engine: Failed to migrate twin %s: %s", twin_id, e)

        return {
            "migrated_twins": migrated_twins,
            "migrated_nodes": total_nodes,
            "migrated_edges": total_edges,
        }
