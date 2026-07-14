"""Multi-agent workspace — ownership, negotiation, delegation via Twin regions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from services.semantic_twin.models import SemanticTwin

from ..models import AGENT_ROLES, AgentMessage
from ..storage.store import ensure_dir, read_json, write_json
from .protocol import AgentProtocol
from .roles import default_ownership_map, region_for_role


class AgentWorkspace:
    def __init__(self, store_dir: str | Path) -> None:
        self.store = ensure_dir(store_dir)
        self.protocol = AgentProtocol()

    def _path(self, project_id: str) -> Path:
        safe = "".join(c for c in project_id if c.isalnum() or c in "-_") or "default"
        return self.store / f"{safe}.json"

    def load(self, project_id: str) -> Dict[str, Any]:
        data = read_json(self._path(project_id))
        return data or {
            "project_id": project_id,
            "ownership": {},
            "messages": [],
            "approvals": [],
        }

    def save(self, project_id: str, state: Dict[str, Any]) -> None:
        write_json(self._path(project_id), state)

    def bootstrap(self, project_id: str, twin: SemanticTwin) -> Dict[str, Any]:
        state = self.load(project_id)
        ownership = default_ownership_map(twin)
        # Persist owner_agent on twin nodes (caller may save twin)
        for n in twin.nodes:
            if n.id in ownership:
                n.attributes = {**(n.attributes or {}), "owner_agent": ownership[n.id]}
        state["ownership"] = ownership
        state["regions"] = {role: region_for_role(twin, role) for role in AGENT_ROLES}
        self.save(project_id, state)
        return state

    def post_message(self, project_id: str, message: AgentMessage) -> Dict[str, Any]:
        state = self.load(project_id)
        msgs = [AgentMessage.from_dict(m) if isinstance(m, dict) else m for m in state.get("messages") or []]
        msgs.append(message)
        # Cap history
        state["messages"] = [m.to_dict() for m in msgs[-500:]]
        state["conflicts"] = self.protocol.conflicts(msgs)
        self.save(project_id, state)
        return {"message": message.to_dict(), "conflicts": state["conflicts"]}

    def approve(self, project_id: str, message_id: str, by_agent: str = "architect") -> Dict[str, Any]:
        state = self.load(project_id)
        found = None
        for m in state.get("messages") or []:
            if m.get("id") == message_id:
                m["status"] = "approved"
                found = m
                break
        if not found:
            return {"error": "message not found"}
        state.setdefault("approvals", []).append({
            "message_id": message_id,
            "by": by_agent,
        })
        # Apply ownership claims
        if found.get("type") == "claim":
            for nid in found.get("region_node_ids") or []:
                state.setdefault("ownership", {})[nid] = found.get("from_agent")
        self.save(project_id, state)
        return {"ok": True, "message": found}

    def reject(self, project_id: str, message_id: str, by_agent: str = "architect") -> Dict[str, Any]:
        state = self.load(project_id)
        for m in state.get("messages") or []:
            if m.get("id") == message_id:
                m["status"] = "rejected"
                self.save(project_id, state)
                return {"ok": True, "message": m}
        return {"error": "message not found"}

    def delegate(
        self,
        project_id: str,
        from_agent: str,
        to_agent: str,
        node_ids: List[str],
        task: str,
    ) -> Dict[str, Any]:
        msg = self.protocol.create(
            from_agent=from_agent,
            to_agent=to_agent,
            type="delegate",
            region_node_ids=node_ids,
            payload={"task": task},
            requires_approval=False,
        )
        return self.post_message(project_id, msg)

    def claim(
        self,
        project_id: str,
        agent: str,
        node_ids: List[str],
        reason: str = "",
    ) -> Dict[str, Any]:
        msg = self.protocol.create(
            from_agent=agent,
            to_agent="architect",
            type="claim",
            region_node_ids=node_ids,
            payload={"reason": reason},
            requires_approval=True,
        )
        return self.post_message(project_id, msg)

    def status(self, project_id: str) -> Dict[str, Any]:
        state = self.load(project_id)
        msgs = state.get("messages") or []
        return {
            "project_id": project_id,
            "roles": list(AGENT_ROLES),
            "ownership_count": len(state.get("ownership") or {}),
            "open_messages": sum(1 for m in msgs if m.get("status") == "open"),
            "conflicts": state.get("conflicts") or [],
            "recent": msgs[-20:],
        }
