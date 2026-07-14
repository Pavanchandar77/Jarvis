"""
Phase 1 integration — automatic twin generation, continuous sync, agent bridge.

Public entry points used by tool_execution, agent_loop, routes, and agent tools.
"""

from .hooks import (
    on_agent_turn_start,
    on_file_written,
    on_agent_turn_end,
    on_runtime_event,
    get_integration_service,
    set_integration_service,
)
from .project_registry import ProjectRecord, ProjectRegistry
from .extensions import TwinExtensionRegistry

__all__ = [
    "on_agent_turn_start",
    "on_file_written",
    "on_agent_turn_end",
    "on_runtime_event",
    "get_integration_service",
    "set_integration_service",
    "ProjectRecord",
    "ProjectRegistry",
    "TwinExtensionRegistry",
]
