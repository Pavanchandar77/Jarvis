"""
Harness Layer — engine-agnostic coding engine interface.

Spark never talks to OpenCode (or any engine) directly.
All engines implement CodingHarness and are selected via HarnessManager.
"""

from .base import CodingHarness, EngineHandle, HarnessSession, HarnessEvent, HarnessStatus
from .manager import HarnessManager
from .registry import HarnessRegistry
from .session_manager import HarnessSessionManager

__all__ = [
    "CodingHarness",
    "EngineHandle",
    "HarnessSession",
    "HarnessEvent",
    "HarnessStatus",
    "HarnessManager",
    "HarnessRegistry",
    "HarnessSessionManager",
]
