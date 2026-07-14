# core/pipeline/intent.py
"""Spark Pipeline Intent Analyzer.

Analyzes user requests to determine intent classification, request complexity,
estimated compute budget, and target reasoning depth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("spark.pipeline.intent")


@dataclass
class IntentAnalysis:
    """Result of analyzing request intent and complexity."""
    intent: str                      # coding | research | math | reasoning | summarization | general
    complexity: float                # 0.0 to 1.0 (complexity score)
    confidence: float                # Confidence score of classification
    estimated_compute_budget: str    # low | medium | high
    estimated_reasoning_depth: int   # 1 to 5 (number of iterative passes)


class IntentAnalyzer:
    """Analyzes and classifies request queries to target pipeline routing."""

    def __init__(self):
        self._intents = {
            "coding": ["def ", "class ", "import ", "python", "javascript", "code", "bug", "rust", "compile", "html", "css", "function"],
            "math": ["solve", "equation", "theorem", "math", "calculus", "integral", "derivative", "matrix", "algebra"],
            "reasoning": ["why", "how to", "think step by step", "reason", "logic", "conclude", "analyze", "explain"],
            "summarization": ["summarize", "tldr", "abstract", "shorten", "outline", "digest", "condense"],
            "research": ["literature", "paper", "arxiv", "find details on", "citation", "document analysis"],
        }

    def analyze(self, query: str) -> IntentAnalysis:
        query_lower = query.lower()
        
        # Calculate intent matches
        scores = {intent: 0 for intent in self._intents}
        for intent, keywords in self._intents.items():
            for kw in keywords:
                if kw in query_lower:
                    scores[intent] += 1

        # Classify best intent
        best_intent = "general"
        max_score = 0
        for intent, score in scores.items():
            if score > max_score:
                max_score = score
                best_intent = intent

        # Complexity heuristics
        length_factor = min(len(query) / 1000.0, 0.5)  # Max 0.5 from length
        keyword_factor = min(max_score * 0.1, 0.5)      # Max 0.5 from keywords
        complexity = round(length_factor + keyword_factor, 2)
        
        # Budget and reasoning depth
        if complexity >= 0.7:
            budget = "high"
            depth = 4
        elif complexity >= 0.4:
            budget = "medium"
            depth = 2
        else:
            budget = "low"
            depth = 1

        analysis = IntentAnalysis(
            intent=best_intent,
            complexity=complexity,
            confidence=0.85 if max_score > 0 else 0.50,
            estimated_compute_budget=budget,
            estimated_reasoning_depth=depth,
        )
        logger.info("Pipeline Intent Analyzer: classified query as %s (complexity: %.2f)", best_intent, complexity)
        return analysis
