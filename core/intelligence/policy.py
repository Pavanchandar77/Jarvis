# core/intelligence/policy.py
"""Spark Policy Engine.

Defines, versions, and manages benchmarkable policies for task planning, model
routing, verifier thresholds, cache budgets, and prefetching.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("spark.intelligence.policy")


@dataclass
class ExecutionPolicy:
    """A versioned policy governing runtime or pipeline routing decisions."""
    policy_id: str
    version: int
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0


class PolicyEngine:
    """Manages active, candidate, and versioned policies."""

    def __init__(self, persist_dir: Optional[str] = None):
        if persist_dir:
            self._persist_dir = Path(os.path.expanduser(persist_dir))
        else:
            self._persist_dir = Path.home() / ".spark" / "policies"

        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._active_policies: Dict[str, ExecutionPolicy] = {}
        self._load_defaults()

    def get_policy(self, policy_id: str) -> ExecutionPolicy:
        """Fetch the active policy, falling back to defaults if not customized."""
        if policy_id in self._active_policies:
            return self._active_policies[policy_id]

        path = self._persist_dir / f"{policy_id}.policy.json"
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                policy = ExecutionPolicy(**data)
                self._active_policies[policy_id] = policy
                return policy
            except Exception:
                pass

        # Return default policy
        return self._active_policies.get(policy_id, ExecutionPolicy(policy_id=policy_id, version=1))

    def update_policy(self, policy: ExecutionPolicy) -> None:
        """Update and persist a policy version."""
        self._active_policies[policy.policy_id] = policy
        path = self._persist_dir / f"{policy.policy_id}.policy.json"
        try:
            path.write_text(json.dumps(asdict(policy), indent=1), encoding="utf-8")
            logger.info("Policy Engine: Updated policy '%s' (version: %d)", policy.policy_id, policy.version)
        except Exception as e:
            logger.warning("Failed to save policy: %s", e)

    # -- Default Policies --

    def _load_defaults(self) -> None:
        # Default Routing Policy
        self._active_policies["routing"] = ExecutionPolicy(
            policy_id="routing",
            version=1,
            settings={
                "prefer_small_models": True,
                "small_model_parameter_limit_b": 15.0,
                "complexity_threshold": 0.30,
            }
        )
        # Default Caching Policy
        self._active_policies["caching"] = ExecutionPolicy(
            policy_id="caching",
            version=1,
            settings={
                "auto_pin_threshold": 50,
                "hot_threshold": 10,
                "base_cache_budget_bytes": 2 * 1024**3,
            }
        )
