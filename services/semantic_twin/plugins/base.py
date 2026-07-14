"""Plugin protocols for Semantic Twin extensibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class SourceLocationDTO:
    start_line: int
    end_line: int
    start_col: Optional[int] = None
    end_col: Optional[int] = None


@dataclass
class Symbol:
    name: str
    kind: str  # function, class, method, component, hook, route, ...
    qualified_name: str
    source_file: str
    location: SourceLocationDTO
    signature: str = ""
    docstring: str = ""
    is_async: bool = False
    parent: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallSite:
    caller_qualified: str
    callee_name: str
    source_file: str
    line: int
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportRef:
    source_file: str
    module: str
    names: List[str] = field(default_factory=list)
    line: int = 1


@dataclass
class RouteDef:
    path_pattern: str
    method: str
    handler_name: str
    source_file: str
    line: int


@dataclass
class StateDef:
    name: str
    store_type: str
    source_file: str
    line: int


@dataclass
class ComponentDef:
    name: str
    framework: str
    source_file: str
    line: int
    end_line: int = 0


@dataclass
class AstForest:
    path: str
    language: str
    symbols: List[Symbol] = field(default_factory=list)
    calls: List[CallSite] = field(default_factory=list)
    imports: List[ImportRef] = field(default_factory=list)
    routes: List[RouteDef] = field(default_factory=list)
    state: List[StateDef] = field(default_factory=list)
    components: List[ComponentDef] = field(default_factory=list)
    raw: Any = None
    errors: List[str] = field(default_factory=list)


@runtime_checkable
class LanguagePlugin(Protocol):
    name: str
    languages: List[str]
    extensions: List[str]

    def can_parse(self, path: str, content: str) -> bool: ...

    def extract_ast(self, path: str, content: str) -> AstForest: ...


@runtime_checkable
class AnalyzerPlugin(Protocol):
    name: str

    def analyze(self, forests: List[AstForest], graph: Any) -> None: ...


@runtime_checkable
class ConceptPlugin(Protocol):
    name: str

    def extract_concepts(self, graph: Any) -> List[Dict[str, Any]]: ...
