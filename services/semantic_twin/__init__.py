"""Spark Semantic Twin — graph-native knowledge system for generated applications."""

from .models import (
    SEMANTIC_TWIN_SCHEMA_VERSION,
    SemanticNode,
    SemanticEdge,
    SemanticTwin,
    GenerationManifest,
    ViewingMode,
)
from .service import SemanticTwinService

# Phase-1 integration is imported lazily via services.semantic_twin.integration
# to avoid circular imports with app bootstrap.

__all__ = [
    "SEMANTIC_TWIN_SCHEMA_VERSION",
    "SemanticNode",
    "SemanticEdge",
    "SemanticTwin",
    "GenerationManifest",
    "ViewingMode",
    "SemanticTwinService",
]
