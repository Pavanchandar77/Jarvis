"""Semantic Twin data models — JSON-serializable dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from .schema import NodeKind, EdgeKind, ViewingMode, ALL_VIEWING_MODES

SEMANTIC_TWIN_SCHEMA_VERSION = "1.0.0"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _enum_val(v: Any) -> Any:
    if isinstance(v, Enum):
        return v.value
    return v


@dataclass
class SourceLocation:
    start_line: int
    end_line: int
    start_col: Optional[int] = None
    end_col: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"start_line": self.start_line, "end_line": self.end_line}
        if self.start_col is not None:
            d["start_col"] = self.start_col
        if self.end_col is not None:
            d["end_col"] = self.end_col
        return d

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["SourceLocation"]:
        if not data:
            return None
        return cls(
            start_line=int(data["start_line"]),
            end_line=int(data["end_line"]),
            start_col=data.get("start_col"),
            end_col=data.get("end_col"),
        )


@dataclass
class LearningResource:
    title: str
    kind: str = "docs"
    url: Optional[str] = None
    difficulty: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"title": self.title, "kind": self.kind}
        if self.url:
            d["url"] = self.url
        if self.difficulty is not None:
            d["difficulty"] = self.difficulty
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LearningResource":
        return cls(
            title=data["title"],
            kind=data.get("kind", "docs"),
            url=data.get("url"),
            difficulty=data.get("difficulty"),
        )


@dataclass
class SuggestedImprovement:
    summary: str
    rationale: str
    impact: str = "medium"
    effort: str = "medium"
    category: str = "maintainability"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SuggestedImprovement":
        return cls(
            summary=data["summary"],
            rationale=data.get("rationale", ""),
            impact=data.get("impact", "medium"),
            effort=data.get("effort", "medium"),
            category=data.get("category", "maintainability"),
        )


@dataclass
class ViewContent:
    mode: str
    title: str
    body: str
    bullets: List[str] = field(default_factory=list)
    code_refs: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metrics: Dict[str, Union[str, int, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "mode": _enum_val(self.mode),
            "title": self.title,
            "body": self.body,
        }
        if self.bullets:
            d["bullets"] = list(self.bullets)
        if self.code_refs:
            d["code_refs"] = list(self.code_refs)
        if self.warnings:
            d["warnings"] = list(self.warnings)
        if self.metrics:
            d["metrics"] = dict(self.metrics)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ViewContent":
        return cls(
            mode=data["mode"],
            title=data.get("title", ""),
            body=data.get("body", ""),
            bullets=list(data.get("bullets") or []),
            code_refs=list(data.get("code_refs") or []),
            warnings=list(data.get("warnings") or []),
            metrics=dict(data.get("metrics") or {}),
        )


@dataclass
class SemanticNode:
    id: str
    kind: str
    name: str
    description: str = ""
    purpose: str = ""
    why_exists: str = ""
    created_by: str = "ai"
    prompt_id: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    source_file: Optional[str] = None
    source_location: Optional[SourceLocation] = None
    execution_order: Optional[int] = None
    related_concepts: List[str] = field(default_factory=list)
    suggested_improvements: List[SuggestedImprovement] = field(default_factory=list)
    learning_resources: List[LearningResource] = field(default_factory=list)
    difficulty_score: float = 0.3
    views: Dict[str, ViewContent] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": _enum_val(self.kind),
            "name": self.name,
            "description": self.description,
            "purpose": self.purpose,
            "why_exists": self.why_exists,
            "created_by": self.created_by,
            "prompt_id": self.prompt_id,
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "source_file": self.source_file,
            "source_location": self.source_location.to_dict() if self.source_location else None,
            "execution_order": self.execution_order,
            "related_concepts": list(self.related_concepts),
            "suggested_improvements": [s.to_dict() for s in self.suggested_improvements],
            "learning_resources": [r.to_dict() for r in self.learning_resources],
            "difficulty_score": self.difficulty_score,
            "views": {k: v.to_dict() for k, v in self.views.items()},
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticNode":
        views_raw = data.get("views") or {}
        return cls(
            id=data["id"],
            kind=data["kind"],
            name=data["name"],
            description=data.get("description", ""),
            purpose=data.get("purpose", ""),
            why_exists=data.get("why_exists", ""),
            created_by=data.get("created_by", "ai"),
            prompt_id=data.get("prompt_id"),
            dependencies=list(data.get("dependencies") or []),
            dependents=list(data.get("dependents") or []),
            source_file=data.get("source_file"),
            source_location=SourceLocation.from_dict(data.get("source_location")),
            execution_order=data.get("execution_order"),
            related_concepts=list(data.get("related_concepts") or []),
            suggested_improvements=[
                SuggestedImprovement.from_dict(s)
                for s in (data.get("suggested_improvements") or [])
            ],
            learning_resources=[
                LearningResource.from_dict(r)
                for r in (data.get("learning_resources") or [])
            ],
            difficulty_score=float(data.get("difficulty_score", 0.3)),
            views={k: ViewContent.from_dict(v) for k, v in views_raw.items()},
            attributes=dict(data.get("attributes") or {}),
        )


@dataclass
class SemanticEdge:
    id: str
    kind: str
    source: str
    target: str
    weight: float = 1.0
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": _enum_val(self.kind),
            "source": self.source,
            "target": self.target,
            "weight": self.weight,
            "attributes": dict(self.attributes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticEdge":
        return cls(
            id=data["id"],
            kind=data["kind"],
            source=data["source"],
            target=data["target"],
            weight=float(data.get("weight", 1.0)),
            attributes=dict(data.get("attributes") or {}),
        )


@dataclass
class AlternativeImplementation:
    id: str
    title: str
    summary: str
    why_rejected: str
    when_preferable: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("when_preferable") is None:
            d.pop("when_preferable", None)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlternativeImplementation":
        return cls(
            id=data["id"],
            title=data["title"],
            summary=data.get("summary", ""),
            why_rejected=data.get("why_rejected", ""),
            when_preferable=data.get("when_preferable"),
        )


@dataclass
class DesignDecision:
    id: str
    title: str
    rationale: str
    chosen: str
    alternatives: List[AlternativeImplementation] = field(default_factory=list)
    prompt_id: Optional[str] = None
    related_node_ids: List[str] = field(default_factory=list)
    trade_offs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "rationale": self.rationale,
            "chosen": self.chosen,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "prompt_id": self.prompt_id,
            "related_node_ids": list(self.related_node_ids),
            "trade_offs": list(self.trade_offs),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DesignDecision":
        return cls(
            id=data["id"],
            title=data["title"],
            rationale=data.get("rationale", ""),
            chosen=data.get("chosen", ""),
            alternatives=[
                AlternativeImplementation.from_dict(a)
                for a in (data.get("alternatives") or [])
            ],
            prompt_id=data.get("prompt_id"),
            related_node_ids=list(data.get("related_node_ids") or []),
            trade_offs=list(data.get("trade_offs") or []),
        )


@dataclass
class PromptRecord:
    id: str
    ordinal: int
    role: str
    text_ref: str
    model: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "ordinal": self.ordinal,
            "role": self.role,
            "text_ref": self.text_ref,
        }
        if self.model:
            d["model"] = self.model
        if self.created_at:
            d["created_at"] = self.created_at
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptRecord":
        return cls(
            id=data["id"],
            ordinal=int(data.get("ordinal", 0)),
            role=data.get("role", "user"),
            text_ref=data.get("text_ref", ""),
            model=data.get("model"),
            created_at=data.get("created_at"),
        )


@dataclass
class GenerationManifest:
    """
    Captures AI intent for a generation session.

    Phase 0 fields remain stable. Phase 1 adds intent-preserving fields
    (user_prompt, agent_chain, tool_history, ownership maps, etc.).
    Older packages without those keys still load via from_dict defaults.
    """
    generation_id: str
    model_ids: List[str] = field(default_factory=list)
    prompts: List[PromptRecord] = field(default_factory=list)
    requirements: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[DesignDecision] = field(default_factory=list)
    file_prompt_map: Dict[str, List[str]] = field(default_factory=dict)
    tech_stack: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # ── Phase 1 expanded intent fields ────────────────────────────────
    user_prompt: str = ""
    planning_prompt: str = ""
    agent_chain: List[Dict[str, Any]] = field(default_factory=list)
    tool_history: List[Dict[str, Any]] = field(default_factory=list)
    backend: str = ""
    runtime_metadata: Dict[str, Any] = field(default_factory=dict)
    file_ownership: Dict[str, str] = field(default_factory=dict)
    component_ownership: Dict[str, str] = field(default_factory=dict)
    dependency_reasoning: List[Dict[str, Any]] = field(default_factory=list)
    trade_offs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generation_id": self.generation_id,
            "model_ids": list(self.model_ids),
            "prompts": [p.to_dict() for p in self.prompts],
            "requirements": list(self.requirements),
            "decisions": [d.to_dict() for d in self.decisions],
            "file_prompt_map": {k: list(v) for k, v in self.file_prompt_map.items()},
            "tech_stack": list(self.tech_stack),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
            "user_prompt": self.user_prompt,
            "planning_prompt": self.planning_prompt,
            "agent_chain": list(self.agent_chain),
            "tool_history": list(self.tool_history),
            "backend": self.backend,
            "runtime_metadata": dict(self.runtime_metadata),
            "file_ownership": dict(self.file_ownership),
            "component_ownership": dict(self.component_ownership),
            "dependency_reasoning": list(self.dependency_reasoning),
            "trade_offs": list(self.trade_offs),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationManifest":
        return cls(
            generation_id=data.get("generation_id") or data.get("id") or "unknown",
            model_ids=list(data.get("model_ids") or []),
            prompts=[PromptRecord.from_dict(p) for p in (data.get("prompts") or [])],
            requirements=list(data.get("requirements") or []),
            decisions=[DesignDecision.from_dict(d) for d in (data.get("decisions") or [])],
            file_prompt_map={
                k: list(v) for k, v in (data.get("file_prompt_map") or {}).items()
            },
            tech_stack=list(data.get("tech_stack") or []),
            created_at=data.get("created_at") or _utcnow_iso(),
            metadata=dict(data.get("metadata") or {}),
            user_prompt=data.get("user_prompt") or "",
            planning_prompt=data.get("planning_prompt") or "",
            agent_chain=list(data.get("agent_chain") or []),
            tool_history=list(data.get("tool_history") or []),
            backend=data.get("backend") or "",
            runtime_metadata=dict(data.get("runtime_metadata") or {}),
            file_ownership=dict(data.get("file_ownership") or {}),
            component_ownership=dict(data.get("component_ownership") or {}),
            dependency_reasoning=list(data.get("dependency_reasoning") or []),
            trade_offs=list(data.get("trade_offs") or []),
        )

    @classmethod
    def empty(
        cls,
        generation_id: Optional[str] = None,
        tech_stack: Optional[List[str]] = None,
    ) -> "GenerationManifest":
        import uuid
        return cls(
            generation_id=generation_id or uuid.uuid4().hex,
            tech_stack=list(tech_stack or []),
        )


@dataclass
class TwinMeta:
    application_id: str
    application_name: str
    entrypoints: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    languages: List[str] = field(default_factory=list)
    coverage_summary: Optional[Dict[str, Any]] = None
    stage_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "application_id": self.application_id,
            "application_name": self.application_name,
            "entrypoints": list(self.entrypoints),
            "tech_stack": list(self.tech_stack),
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "languages": list(self.languages),
        }
        if self.coverage_summary:
            d["coverage_summary"] = dict(self.coverage_summary)
        if self.stage_metrics:
            d["stage_metrics"] = dict(self.stage_metrics)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TwinMeta":
        return cls(
            application_id=data.get("application_id", ""),
            application_name=data.get("application_name", ""),
            entrypoints=list(data.get("entrypoints") or []),
            tech_stack=list(data.get("tech_stack") or []),
            node_count=int(data.get("node_count", 0)),
            edge_count=int(data.get("edge_count", 0)),
            languages=list(data.get("languages") or []),
            coverage_summary=data.get("coverage_summary"),
            stage_metrics=dict(data.get("stage_metrics") or {}),
        )


@dataclass
class TwinIndexes:
    by_file: Dict[str, List[str]] = field(default_factory=dict)
    by_kind: Dict[str, List[str]] = field(default_factory=dict)
    by_name: Dict[str, List[str]] = field(default_factory=dict)
    adjacency_out: Dict[str, List[str]] = field(default_factory=dict)
    adjacency_in: Dict[str, List[str]] = field(default_factory=dict)
    concepts: Dict[str, str] = field(default_factory=dict)
    file_hashes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "by_file": {k: list(v) for k, v in self.by_file.items()},
            "by_kind": {k: list(v) for k, v in self.by_kind.items()},
            "by_name": {k: list(v) for k, v in self.by_name.items()},
            "adjacency_out": {k: list(v) for k, v in self.adjacency_out.items()},
            "adjacency_in": {k: list(v) for k, v in self.adjacency_in.items()},
            "concepts": dict(self.concepts),
            "file_hashes": dict(self.file_hashes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TwinIndexes":
        return cls(
            by_file={k: list(v) for k, v in (data.get("by_file") or {}).items()},
            by_kind={k: list(v) for k, v in (data.get("by_kind") or {}).items()},
            by_name={k: list(v) for k, v in (data.get("by_name") or {}).items()},
            adjacency_out={k: list(v) for k, v in (data.get("adjacency_out") or {}).items()},
            adjacency_in={k: list(v) for k, v in (data.get("adjacency_in") or {}).items()},
            concepts=dict(data.get("concepts") or {}),
            file_hashes=dict(data.get("file_hashes") or {}),
        )


@dataclass
class SemanticTwin:
    twin_id: str
    application_id: str
    schema_version: str = SEMANTIC_TWIN_SCHEMA_VERSION
    content_revision: int = 1
    content_hash: str = ""
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    owner: Optional[str] = None
    manifest: GenerationManifest = field(default_factory=GenerationManifest.empty)
    nodes: List[SemanticNode] = field(default_factory=list)
    edges: List[SemanticEdge] = field(default_factory=list)
    indexes: TwinIndexes = field(default_factory=TwinIndexes)
    meta: TwinMeta = field(default_factory=lambda: TwinMeta(application_id="", application_name=""))

    def to_dict(self, include_graph: bool = True) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "twin_id": self.twin_id,
            "application_id": self.application_id,
            "schema_version": self.schema_version,
            "content_revision": self.content_revision,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "owner": self.owner,
            "manifest": self.manifest.to_dict(),
            "indexes": self.indexes.to_dict(),
            "meta": self.meta.to_dict(),
        }
        if include_graph:
            d["nodes"] = [n.to_dict() for n in self.nodes]
            d["edges"] = [e.to_dict() for e in self.edges]
        else:
            d["nodes"] = []
            d["edges"] = []
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticTwin":
        return cls(
            twin_id=data["twin_id"],
            application_id=data.get("application_id", ""),
            schema_version=data.get("schema_version", SEMANTIC_TWIN_SCHEMA_VERSION),
            content_revision=int(data.get("content_revision", 1)),
            content_hash=data.get("content_hash", ""),
            created_at=data.get("created_at") or _utcnow_iso(),
            updated_at=data.get("updated_at") or _utcnow_iso(),
            owner=data.get("owner"),
            manifest=GenerationManifest.from_dict(data.get("manifest") or {}),
            nodes=[SemanticNode.from_dict(n) for n in (data.get("nodes") or [])],
            edges=[SemanticEdge.from_dict(e) for e in (data.get("edges") or [])],
            indexes=TwinIndexes.from_dict(data.get("indexes") or {}),
            meta=TwinMeta.from_dict(data.get("meta") or {
                "application_id": data.get("application_id", ""),
                "application_name": "",
            }),
        )

    def node_map(self) -> Dict[str, SemanticNode]:
        return {n.id: n for n in self.nodes}

    def edge_map(self) -> Dict[str, SemanticEdge]:
        return {e.id: e for e in self.edges}


# Re-export viewing modes for convenience
__all__ = [
    "SEMANTIC_TWIN_SCHEMA_VERSION",
    "SourceLocation",
    "LearningResource",
    "SuggestedImprovement",
    "ViewContent",
    "SemanticNode",
    "SemanticEdge",
    "AlternativeImplementation",
    "DesignDecision",
    "PromptRecord",
    "GenerationManifest",
    "TwinMeta",
    "TwinIndexes",
    "SemanticTwin",
    "ViewingMode",
    "NodeKind",
    "EdgeKind",
    "ALL_VIEWING_MODES",
]
