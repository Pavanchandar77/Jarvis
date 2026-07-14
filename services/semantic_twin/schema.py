"""Graph schema: node kinds, edge kinds, and invariants."""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, Set


class NodeKind(str, Enum):
    APPLICATION = "application"
    MODULE = "module"
    PACKAGE = "package"
    COMPONENT = "component"
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    HOOK = "hook"
    API_ENDPOINT = "api_endpoint"
    API_CLIENT = "api_client"
    MIDDLEWARE = "middleware"
    STATE_STORE = "state_store"
    STATE_ATOM = "state_atom"
    STATE_SELECTOR = "state_selector"
    ROUTE = "route"
    PAGE = "page"
    LAYOUT = "layout"
    TABLE = "table"
    COLUMN = "column"
    RELATION = "relation"
    MIGRATION = "migration"
    EVENT = "event"
    EVENT_HANDLER = "event_handler"
    SUBSCRIPTION = "subscription"
    DATA_FLOW = "data_flow"
    TRANSFORM = "transform"
    PROMPT = "prompt"
    REQUIREMENT = "requirement"
    DESIGN_DECISION = "design_decision"
    ALTERNATIVE = "alternative"
    CONCEPT = "concept"
    PATTERN = "pattern"
    RESOURCE = "resource"
    TEST = "test"
    COVERAGE_GAP = "coverage_gap"
    SECURITY_SURFACE = "security_surface"
    PERF_HOTSPOT = "perf_hotspot"
    ERROR = "error"


class EdgeKind(str, Enum):
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    IMPORTS = "imports"
    CALLS = "calls"
    RENDERS = "renders"
    READS_STATE = "reads_state"
    WRITES_STATE = "writes_state"
    ROUTES_TO = "routes_to"
    DATA_FLOWS_TO = "data_flows_to"
    FK_TO = "fk_to"
    EMITS = "emits"
    HANDLES = "handles"
    GENERATED_FROM = "generated_from"
    DECIDED_BY = "decided_by"
    ALTERNATIVE_TO = "alternative_to"
    RELATED_TO = "related_to"
    ILLUSTRATES = "illustrates"


class ViewingMode(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    SENIOR = "senior"
    RUNTIME = "runtime"
    AI_REASONING = "ai_reasoning"
    PERFORMANCE = "performance"
    SECURITY = "security"


ALL_VIEWING_MODES: tuple[ViewingMode, ...] = tuple(ViewingMode)

# Edge kinds that must not form cycles in structural hierarchy
ACYCLIC_EDGE_KINDS: FrozenSet[EdgeKind] = frozenset({
    EdgeKind.CONTAINS,
    EdgeKind.DEPENDS_ON,
    EdgeKind.FK_TO,
    EdgeKind.GENERATED_FROM,
    EdgeKind.DECIDED_BY,
    EdgeKind.ALTERNATIVE_TO,
})

# Edge kinds allowed to cycle (e.g. recursion)
CYCLIC_OK_EDGE_KINDS: FrozenSet[EdgeKind] = frozenset({
    EdgeKind.CALLS,
    EdgeKind.RENDERS,
    EdgeKind.DATA_FLOWS_TO,
    EdgeKind.RELATED_TO,
    EdgeKind.IMPORTS,
})

CODE_NODE_KINDS: FrozenSet[NodeKind] = frozenset({
    NodeKind.COMPONENT,
    NodeKind.FUNCTION,
    NodeKind.CLASS,
    NodeKind.METHOD,
    NodeKind.HOOK,
    NodeKind.API_ENDPOINT,
    NodeKind.MIDDLEWARE,
    NodeKind.ROUTE,
    NodeKind.PAGE,
    NodeKind.TEST,
})

EXECUTION_EDGE_KINDS: FrozenSet[EdgeKind] = frozenset({
    EdgeKind.CALLS,
    EdgeKind.RENDERS,
    EdgeKind.ROUTES_TO,
    EdgeKind.EMITS,
    EdgeKind.HANDLES,
    EdgeKind.DATA_FLOWS_TO,
})

DEPENDENCY_EDGE_KINDS: FrozenSet[EdgeKind] = frozenset({
    EdgeKind.DEPENDS_ON,
    EdgeKind.IMPORTS,
    EdgeKind.CALLS,
    EdgeKind.READS_STATE,
    EdgeKind.WRITES_STATE,
})


def validate_edge_kind(kind: str) -> EdgeKind:
    return EdgeKind(kind)


def validate_node_kind(kind: str) -> NodeKind:
    return NodeKind(kind)


def is_valid_node_kind(kind: str) -> bool:
    try:
        NodeKind(kind)
        return True
    except ValueError:
        return False


def is_valid_edge_kind(kind: str) -> bool:
    try:
        EdgeKind(kind)
        return True
    except ValueError:
        return False
