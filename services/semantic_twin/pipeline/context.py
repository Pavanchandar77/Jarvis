"""Shared pipeline context mutated by each stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..graph.knowledge_graph import KnowledgeGraph
from ..models import GenerationManifest
from ..plugins.base import AstForest
from ..plugins.registry import PluginRegistry


@dataclass
class SourceFile:
    path: str  # relative posix path
    absolute: str
    content: str
    content_hash: str
    language: str = "unknown"


@dataclass
class PipelineContext:
    app_root: Path
    application_id: str
    application_name: str
    manifest: GenerationManifest
    owner: Optional[str] = None
    twin_id: Optional[str] = None
    registry: PluginRegistry = field(default_factory=PluginRegistry.with_builtins)
    sources: Dict[str, SourceFile] = field(default_factory=dict)
    forests: Dict[str, AstForest] = field(default_factory=dict)
    graph: KnowledgeGraph = field(default_factory=KnowledgeGraph)
    stage_metrics: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    dirty_files: Optional[List[str]] = None  # None = full scan
    symbol_table: Dict[str, str] = field(default_factory=dict)  # qualified → node_id
    extras: Dict[str, Any] = field(default_factory=dict)
