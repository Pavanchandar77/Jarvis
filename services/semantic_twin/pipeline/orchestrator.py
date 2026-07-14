"""Pipeline orchestrator — runs stages in mandatory order."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Protocol

from ..models import GenerationManifest, SemanticTwin
from ..plugins.registry import PluginRegistry
from .ast_extraction import AstExtractionStage
from .concept_extractor import ConceptExtractorStage
from .context import PipelineContext
from .execution_analyzer import ExecutionAnalyzerStage
from .graph_builder import GraphBuilderStage
from .parser import ParserStage
from .relationship_engine import RelationshipEngineStage
from .semantic_analyzer import SemanticAnalyzerStage
from .twin_generator import TwinGeneratorStage

logger = logging.getLogger(__name__)


class Stage(Protocol):
    name: str

    def run(self, ctx: PipelineContext) -> None: ...


DEFAULT_STAGES: List[Stage] = [
    ParserStage(),
    AstExtractionStage(),
    SemanticAnalyzerStage(),
    GraphBuilderStage(),
    ExecutionAnalyzerStage(),
    ConceptExtractorStage(),
    RelationshipEngineStage(),
    TwinGeneratorStage(),
]


class PipelineOrchestrator:
    def __init__(
        self,
        stages: Optional[List[Stage]] = None,
        registry: Optional[PluginRegistry] = None,
    ) -> None:
        self.stages = list(stages or DEFAULT_STAGES)
        self.registry = registry or PluginRegistry.with_builtins()

    def run(
        self,
        app_root: str | Path,
        manifest: GenerationManifest,
        *,
        application_id: Optional[str] = None,
        application_name: Optional[str] = None,
        owner: Optional[str] = None,
        twin_id: Optional[str] = None,
        dirty_files: Optional[List[str]] = None,
        prior_revision: int = 0,
        created_at: Optional[str] = None,
        existing_graph=None,
    ) -> SemanticTwin:
        root = Path(app_root)
        app_id = application_id or root.name or "app"
        ctx = PipelineContext(
            app_root=root,
            application_id=app_id,
            application_name=application_name or app_id,
            manifest=manifest,
            owner=owner,
            twin_id=twin_id,
            registry=self.registry,
            dirty_files=dirty_files,
        )
        if prior_revision:
            ctx.extras["content_revision"] = prior_revision + 1
        if created_at:
            ctx.extras["created_at"] = created_at
        if existing_graph is not None:
            ctx.graph = existing_graph

        for stage in self.stages:
            logger.debug("Semantic Twin stage start: %s", stage.name)
            stage.run(ctx)
            logger.debug(
                "Semantic Twin stage done: %s (%.3fs)",
                stage.name,
                ctx.stage_metrics.get(stage.name, 0.0),
            )

        twin = ctx.extras.get("twin")
        if twin is None:
            raise RuntimeError("Twin generator did not produce a SemanticTwin")
        if ctx.errors:
            twin.meta.stage_metrics = twin.meta.stage_metrics or {}
            twin.manifest.metadata = dict(twin.manifest.metadata or {})
            twin.manifest.metadata["pipeline_errors"] = ctx.errors[:100]
        return twin
