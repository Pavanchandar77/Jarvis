# core/cognitive/cross_project.py
"""Spark Cross-Project Intelligence.

Facilitates knowledge transfer (architectural patterns, performance optimizations,
and deployment settings) between different workspace repositories.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .graph import UnifiedCognitiveGraph

logger = logging.getLogger("spark.cognitive.cross_project")


@dataclass
class TransferredKnowledge:
    """An object package exported for transfer across workspace repositories."""
    source_project_id: str
    target_project_id: str
    knowledge_type: str               # architectural_pattern | optimization | test_strategy
    data: Dict[str, Any]
    traceability_log: str


class CrossProjectIntelligence:
    """Manages secure and traceable sharing of graph knowledge across repositories."""

    def __init__(self, graph: UnifiedCognitiveGraph):
        self._graph = graph
        self._transfer_history: List[TransferredKnowledge] = []

    def export_pattern(self, project_id: str, knowledge_type: str, node_id: str) -> Optional[Dict[str, Any]]:
        """Export a validated pattern from a source project node."""
        node = self._graph.get_node(node_id)
        if not node:
            logger.warning("Cross-Project: Node '%s' not found for export.", node_id)
            return None

        logger.info("Cross-Project: Exporting %s from project '%s'", knowledge_type, project_id)
        return {
            "source_project": project_id,
            "type": knowledge_type,
            "properties": node.properties,
        }

    def import_pattern(self, target_project_id: str, payload: Dict[str, Any]) -> str:
        """Import a package of validated pattern knowledge into the local graph."""
        source = payload.get("source_project", "unknown_source")
        k_type = payload.get("type", "architectural_pattern")
        props = payload.get("properties", {})
        
        node_id = f"cp_{target_project_id}_{k_type[:5]}_{hash(json.dumps(props)) % 10000}"
        
        # Write to graph
        self._graph.add_node(
            node_id=node_id,
            kind="concept",
            properties={
                "origin_project": source,
                "import_target": target_project_id,
                "type": k_type,
                "data": props,
                "transferred_at": time.time() if hasattr(time, "time") else 0.0,
            }
        )

        log = f"Transferred {k_type} from project '{source}' to target '{target_project_id}'."
        self._transfer_history.append(TransferredKnowledge(
            source_project_id=source,
            target_project_id=target_project_id,
            knowledge_type=k_type,
            data=props,
            traceability_log=log
        ))

        logger.info("Cross-Project: Successfully imported package: %s", log)
        return node_id

    def get_transfer_logs(self) -> List[TransferredKnowledge]:
        return list(self._transfer_history)
