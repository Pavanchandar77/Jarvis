"""
Workspace Manager — owns project lifecycle.

The harness edits code; the Workspace Manager owns the project:
repo, worktrees, twin, runtime, memory, active harness, agents.
"""

from .manifest import WorkspaceManifest
from .manager import WorkspaceManager
from .registry import WorkspaceRegistry

__all__ = [
    "WorkspaceManifest",
    "WorkspaceManager",
    "WorkspaceRegistry",
]
