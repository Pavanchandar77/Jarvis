"""Specialized agent roles and default semantic region selectors."""

from __future__ import annotations

from typing import Callable, Dict, List

from services.semantic_twin.models import SemanticTwin
from services.semantic_twin.schema import NodeKind

from ..models import AGENT_ROLES


def region_for_role(twin: SemanticTwin, role: str) -> List[str]:
    """Return node ids that constitute this agent's semantic region."""
    role = role.lower()
    nodes = twin.nodes
    if role == "architect":
        return [n.id for n in nodes if n.kind in (
            NodeKind.APPLICATION.value, NodeKind.PACKAGE.value, NodeKind.DESIGN_DECISION.value,
            NodeKind.PATTERN.value,
        )][:100]
    if role == "planner":
        return [n.id for n in nodes if n.kind in (
            NodeKind.REQUIREMENT.value, NodeKind.PROMPT.value, NodeKind.DESIGN_DECISION.value,
        )][:100]
    if role == "frontend":
        return [n.id for n in nodes if n.kind in (
            NodeKind.COMPONENT.value, NodeKind.HOOK.value, NodeKind.PAGE.value, NodeKind.ROUTE.value,
            NodeKind.STATE_ATOM.value, NodeKind.STATE_STORE.value,
        )][:150]
    if role == "backend":
        return [n.id for n in nodes if n.kind in (
            NodeKind.FUNCTION.value, NodeKind.METHOD.value, NodeKind.CLASS.value,
            NodeKind.API_ENDPOINT.value, NodeKind.MIDDLEWARE.value,
        )][:150]
    if role == "database":
        return [n.id for n in nodes if n.kind in (
            NodeKind.TABLE.value, NodeKind.COLUMN.value, NodeKind.MIGRATION.value, NodeKind.RELATION.value,
        )][:100]
    if role == "security":
        return [n.id for n in nodes if n.kind in (
            NodeKind.SECURITY_SURFACE.value, NodeKind.API_ENDPOINT.value, NodeKind.MIDDLEWARE.value,
        ) or "auth" in n.name.lower()][:100]
    if role == "infrastructure":
        return [n.id for n in nodes if n.kind in (NodeKind.MODULE.value, NodeKind.PACKAGE.value)][:80]
    if role == "performance":
        return [n.id for n in nodes if n.kind == NodeKind.PERF_HOTSPOT.value or n.difficulty_score >= 0.6][:80]
    if role == "documentation":
        return [n.id for n in nodes if n.kind in (NodeKind.CONCEPT.value, NodeKind.RESOURCE.value)][:80]
    if role == "testing":
        return [n.id for n in nodes if n.kind in (NodeKind.TEST.value, NodeKind.COVERAGE_GAP.value)][:100]
    if role == "refactoring":
        return [n.id for n in nodes if (n.suggested_improvements or [])][:100]
    return []


def default_ownership_map(twin: SemanticTwin) -> Dict[str, str]:
    """Assign each node to a primary owner agent."""
    owned: Dict[str, str] = {}
    for role in AGENT_ROLES:
        for nid in region_for_role(twin, role):
            owned.setdefault(nid, role)
    return owned
