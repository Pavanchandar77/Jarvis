"""Shared data models for Spark OS capabilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class ArchitectureNode:
    """Architecture-first design node (pre-code)."""
    id: str
    kind: str  # service|api|database|event|bounded_context|security_boundary|dependency|ui|queue
    name: str
    description: str = ""
    purpose: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    owner_agent: Optional[str] = None
    requirement_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArchitectureNode":
        return cls(
            id=d["id"],
            kind=d["kind"],
            name=d["name"],
            description=d.get("description", ""),
            purpose=d.get("purpose", ""),
            attributes=dict(d.get("attributes") or {}),
            owner_agent=d.get("owner_agent"),
            requirement_ids=list(d.get("requirement_ids") or []),
        )


@dataclass
class ArchitectureEdge:
    id: str
    kind: str  # depends_on|calls|publishes|subscribes|secures|contains|data_flows_to
    source: str
    target: str
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArchitectureEdge":
        return cls(
            id=d["id"],
            kind=d["kind"],
            source=d["source"],
            target=d["target"],
            attributes=dict(d.get("attributes") or {}),
        )


@dataclass
class ArchitectureSpec:
    """Primary design artifact before code exists."""
    architecture_id: str
    name: str
    description: str = ""
    nodes: List[ArchitectureNode] = field(default_factory=list)
    edges: List[ArchitectureEdge] = field(default_factory=list)
    twin_id: Optional[str] = None
    project_id: Optional[str] = None
    owner: Optional[str] = None
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "architecture_id": self.architecture_id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "twin_id": self.twin_id,
            "project_id": self.project_id,
            "owner": self.owner,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ArchitectureSpec":
        return cls(
            architecture_id=d["architecture_id"],
            name=d.get("name", ""),
            description=d.get("description", ""),
            nodes=[ArchitectureNode.from_dict(n) for n in (d.get("nodes") or [])],
            edges=[ArchitectureEdge.from_dict(e) for e in (d.get("edges") or [])],
            twin_id=d.get("twin_id"),
            project_id=d.get("project_id"),
            owner=d.get("owner"),
            created_at=d.get("created_at") or _utcnow(),
            updated_at=d.get("updated_at") or _utcnow(),
            version=int(d.get("version") or 1),
            metadata=dict(d.get("metadata") or {}),
        )


@dataclass
class LivingRequirement:
    id: str
    text: str
    requested_by: str = "user"
    prompt_id: Optional[str] = None
    status: str = "active"  # active|satisfied|deprecated
    priority: str = "medium"
    artifact_ids: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LivingRequirement":
        return cls(
            id=d["id"],
            text=d["text"],
            requested_by=d.get("requested_by", "user"),
            prompt_id=d.get("prompt_id"),
            status=d.get("status", "active"),
            priority=d.get("priority", "medium"),
            artifact_ids=list(d.get("artifact_ids") or []),
            attributes=dict(d.get("attributes") or {}),
        )


@dataclass
class ReviewFinding:
    id: str
    category: str
    severity: str  # critical|high|medium|low|info
    title: str
    explanation: str
    evidence: List[str] = field(default_factory=list)
    proposed_solution: str = ""
    estimated_impact: str = "medium"
    node_ids: List[str] = field(default_factory=list)
    score_delta: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewReport:
    review_id: str
    twin_id: str
    scores: Dict[str, float] = field(default_factory=dict)
    overall: float = 0.0
    findings: List[ReviewFinding] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "twin_id": self.twin_id,
            "scores": dict(self.scores),
            "overall": self.overall,
            "findings": [f.to_dict() for f in self.findings],
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


AGENT_ROLES = (
    "architect", "planner", "frontend", "backend", "database",
    "security", "infrastructure", "performance", "documentation",
    "testing", "refactoring",
)


@dataclass
class AgentMessage:
    id: str
    from_agent: str
    to_agent: str  # role or "broadcast"
    type: str  # claim|delegate|negotiate|approve|reject|info
    region_node_ids: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    status: str = "open"  # open|approved|rejected|merged
    ts: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentMessage":
        return cls(
            id=d["id"],
            from_agent=d["from_agent"],
            to_agent=d.get("to_agent", "broadcast"),
            type=d.get("type", "info"),
            region_node_ids=list(d.get("region_node_ids") or []),
            payload=dict(d.get("payload") or {}),
            requires_approval=bool(d.get("requires_approval")),
            status=d.get("status", "open"),
            ts=d.get("ts") or _utcnow(),
        )


@dataclass
class SimulationReport:
    simulation_id: str
    twin_id: str
    proposal: str
    risk_level: str
    impacted_files: List[str] = field(default_factory=list)
    impacted_services: List[str] = field(default_factory=list)
    broken_apis: List[str] = field(default_factory=list)
    broken_tests: List[str] = field(default_factory=list)
    performance: Dict[str, Any] = field(default_factory=dict)
    security: List[str] = field(default_factory=list)
    migration_complexity: str = "medium"
    estimated_effort_days: float = 1.0
    narrative: str = ""
    affected_node_ids: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgePattern:
    id: str
    kind: str  # architecture|pattern|anti_pattern|refactor|bug|incident|security|performance
    title: str
    summary: str
    tags: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.5
    source_project: Optional[str] = None
    created_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgePattern":
        return cls(
            id=d["id"],
            kind=d.get("kind", "pattern"),
            title=d["title"],
            summary=d.get("summary", ""),
            tags=list(d.get("tags") or []),
            evidence=dict(d.get("evidence") or {}),
            score=float(d.get("score") or 0.5),
            source_project=d.get("source_project"),
            created_at=d.get("created_at") or _utcnow(),
        )


@dataclass
class MarketplaceArchitecture:
    slug: str
    name: str
    category: str
    description: str
    rationale: str
    trade_offs: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    architecture: Optional[Dict[str, Any]] = None  # ArchitectureSpec dict
    learning_resources: List[Dict[str, str]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RefactorPlan:
    plan_id: str
    twin_id: str
    transformation: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    simulation: Optional[Dict[str, Any]] = None
    review: Optional[Dict[str, Any]] = None
    risk_level: str = "medium"
    status: str = "proposed"  # proposed|approved|migrating|validated|applied|rejected
    created_at: str = field(default_factory=_utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeFrame:
    """One frame of live execution visualization over architecture."""
    order: int
    stage: str  # user|frontend|state|api|database|jobs|response|render
    node_ids: List[str] = field(default_factory=list)
    edge_ids: List[str] = field(default_factory=list)
    label: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    highlight: str = "normal"  # normal|bottleneck|failure|slow|retry

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
