# core/pipeline/synthesizer.py
"""Spark Pipeline Response Synthesizer.

Merges multi-step task outputs, maintains clear traceability logs, and packages
reasoning history into the final user-facing response.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .planner import TaskNode

logger = logging.getLogger("spark.pipeline.synthesizer")


class ResponseSynthesizer:
    """Merges execution trace results into a single output document."""

    def synthesize(self, dag: List[TaskNode], trace_history: List[Dict[str, Any]]) -> str:
        logger.info("Response Synthesizer: merging outputs from %d task nodes...", len(dag))
        parts = []

        # 1. Add final synthesis header
        parts.append("# Spark Orchestrated Response\n")
        
        # 2. Append trace lineage details for transparency (explainability)
        parts.append("### Execution Trace & Lineage")
        parts.append("| Task ID | Description | Status | Model Used |")
        parts.append("|---|---|---|---|")
        
        for step in trace_history:
            parts.append(
                f"| {step.get('step_id')} | {step.get('description', '')} | "
                f"{step.get('status', 'completed')} | {step.get('model')} |"
            )
        parts.append("\n---\n")

        # 3. Append actual results
        for node in dag:
            if node.output:
                parts.append(f"## Step: {node.task_id.replace('_', ' ').title()}")
                parts.append(node.output)
                parts.append("\n")

        return "\n".join(parts)
