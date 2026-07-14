# core/pipeline/capability.py
"""Spark Pipeline Capability Analyzer.

Inspects task descriptions to determine required AI capabilities (e.g. code generation,
long-context reasoning, tool execution) prior to model selection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger("spark.pipeline.capability")


@dataclass
class RequiredCapabilities:
    """The capability footprint required to complete a task."""
    code_generation: bool = False
    long_context: bool = False
    mathematics: bool = False
    tool_usage: bool = False
    planning: bool = False
    min_context_window: int = 2048


class CapabilityAnalyzer:
    """Analyzes task profiles to establish minimum execution requirements."""

    def analyze_task(self, description: str) -> RequiredCapabilities:
        desc_lower = description.lower()
        
        req = RequiredCapabilities(
            code_generation=any(w in desc_lower for w in ["code", "frontend", "backend", "api", "database", "script"]),
            long_context=any(w in desc_lower for w in ["summarize", "literature", "report", "extract", "pdf", "long"]),
            mathematics=any(w in desc_lower for w in ["math", "equation", "solve", "formula"]),
            tool_usage=any(w in desc_lower for w in ["search", "query", "run", "call", "web"]),
            planning=any(w in desc_lower for w in ["plan", "architecture", "design", "workflow"]),
        )
        
        # Determine context size requirements
        if req.long_context:
            req.min_context_window = 8192
        elif req.code_generation:
            req.min_context_window = 4096
            
        logger.info(
            "Pipeline Capability Analyzer: Task requires capabilities: code=%s, math=%s, context=%d",
            req.code_generation, req.mathematics, req.min_context_window
        )
        return req
