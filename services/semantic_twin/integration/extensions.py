"""
Extension points for future Semantic Twin capabilities.

These interfaces are intentionally not fully implemented — they define
stable hooks for:
  - editable Semantic Twins
  - architecture-first development
  - AI architectural reviews
  - automated refactoring
  - repository ingestion
  - multi-agent collaboration
  - cross-project semantic search
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class TwinLifecycleHook(Protocol):
    """Called around twin generate/update lifecycle events."""

    name: str

    def on_before_generate(self, ctx: Dict[str, Any]) -> None: ...
    def on_after_generate(self, twin: Any, ctx: Dict[str, Any]) -> None: ...
    def on_before_update(self, twin_id: str, ctx: Dict[str, Any]) -> None: ...
    def on_after_update(self, twin: Any, ctx: Dict[str, Any]) -> None: ...


@runtime_checkable
class ArchitectureReviewExtension(Protocol):
    """Future: automated architectural review over a twin."""

    name: str

    def review(self, twin: Any, focus_node_ids: Optional[List[str]] = None) -> Dict[str, Any]: ...


@runtime_checkable
class RefactorExtension(Protocol):
    """Future: propose/apply refactors driven by twin graph."""

    name: str

    def propose(self, twin: Any, proposal: str) -> Dict[str, Any]: ...


@runtime_checkable
class RepositoryIngestExtension(Protocol):
    """Future: ingest an existing non-Spark repository into a twin."""

    name: str

    def ingest(self, repo_root: str, owner: Optional[str] = None) -> Any: ...


@runtime_checkable
class CrossProjectSearchExtension(Protocol):
    """Future: search concepts/architecture across many twins."""

    name: str

    def search(self, query: str, owner: Optional[str] = None, limit: int = 20) -> Dict[str, Any]: ...


@runtime_checkable
class EditableTwinExtension(Protocol):
    """Future: human edits to the twin graph that co-evolve code."""

    name: str

    def apply_edit(self, twin_id: str, edit: Dict[str, Any]) -> Any: ...


@runtime_checkable
class MultiAgentCollabExtension(Protocol):
    """Future: multi-agent coordination via shared twin state."""

    name: str

    def publish_intent(self, twin_id: str, agent_id: str, intent: Dict[str, Any]) -> None: ...
    def read_intents(self, twin_id: str) -> List[Dict[str, Any]]: ...


class TwinExtensionRegistry:
    """Central registry for Phase-2+ extensions. Safe no-ops when empty."""

    def __init__(self) -> None:
        self.lifecycle: List[TwinLifecycleHook] = []
        self.reviews: List[ArchitectureReviewExtension] = []
        self.refactors: List[RefactorExtension] = []
        self.ingestors: List[RepositoryIngestExtension] = []
        self.cross_search: List[CrossProjectSearchExtension] = []
        self.editable: List[EditableTwinExtension] = []
        self.collab: List[MultiAgentCollabExtension] = []

    def register_lifecycle(self, hook: TwinLifecycleHook) -> None:
        self.lifecycle.append(hook)

    def fire_before_generate(self, ctx: Dict[str, Any]) -> None:
        for h in self.lifecycle:
            try:
                h.on_before_generate(ctx)
            except Exception:
                pass

    def fire_after_generate(self, twin: Any, ctx: Dict[str, Any]) -> None:
        for h in self.lifecycle:
            try:
                h.on_after_generate(twin, ctx)
            except Exception:
                pass

    def fire_before_update(self, twin_id: str, ctx: Dict[str, Any]) -> None:
        for h in self.lifecycle:
            try:
                h.on_before_update(twin_id, ctx)
            except Exception:
                pass

    def fire_after_update(self, twin: Any, ctx: Dict[str, Any]) -> None:
        for h in self.lifecycle:
            try:
                h.on_after_update(twin, ctx)
            except Exception:
                pass


# Process-wide extension registry
EXTENSIONS = TwinExtensionRegistry()
