import asyncio
from typing import Dict, Any

pending_approvals: Dict[str, Dict[str, Any]] = {}

def register_approval(approval_id: str) -> asyncio.Event:
    event = asyncio.Event()
    pending_approvals[approval_id] = {
        "event": event,
        "approved": False,
        "response_sent": False
    }
    return event

def resolve_approval(approval_id: str, approved: bool):
    if approval_id in pending_approvals:
        pending_approvals[approval_id]["approved"] = approved
        pending_approvals[approval_id]["response_sent"] = True
        pending_approvals[approval_id]["event"].set()

def get_approval_status(approval_id: str) -> bool:
    if approval_id in pending_approvals:
        return pending_approvals[approval_id]["approved"]
    return False
