"""Multi-agent communication protocol over the Semantic Twin."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from ..models import AGENT_ROLES, AgentMessage


class AgentProtocol:
    """Validate and create agent bus messages."""

    VALID_TYPES = frozenset({"claim", "delegate", "negotiate", "approve", "reject", "info"})

    def create(
        self,
        *,
        from_agent: str,
        to_agent: str = "broadcast",
        type: str = "info",
        region_node_ids: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        requires_approval: bool = False,
    ) -> AgentMessage:
        if from_agent not in AGENT_ROLES and from_agent != "system":
            # allow custom but prefer known roles
            pass
        if type not in self.VALID_TYPES:
            raise ValueError(f"invalid message type: {type}")
        return AgentMessage(
            id=uuid.uuid4().hex,
            from_agent=from_agent,
            to_agent=to_agent,
            type=type,
            region_node_ids=list(region_node_ids or []),
            payload=dict(payload or {}),
            requires_approval=requires_approval,
        )

    def conflicts(self, messages: List[AgentMessage]) -> List[Dict[str, Any]]:
        """Detect competing claims on the same node region."""
        claims: Dict[str, List[AgentMessage]] = {}
        for m in messages:
            if m.type != "claim" or m.status == "rejected":
                continue
            for nid in m.region_node_ids:
                claims.setdefault(nid, []).append(m)
        out = []
        for nid, ms in claims.items():
            agents = {m.from_agent for m in ms}
            if len(agents) > 1:
                out.append({
                    "node_id": nid,
                    "agents": sorted(agents),
                    "message_ids": [m.id for m in ms],
                    "resolution": "architect_approval_required",
                })
        return out
