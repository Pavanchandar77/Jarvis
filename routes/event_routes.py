import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

class DummyEventBroadcaster:
    def broadcast(self, event_type: str, data: dict):
        logger.debug(f"[event-broadcast] {event_type}: {data}")

global_event_broadcaster = DummyEventBroadcaster()

def setup_event_routes():
    return APIRouter()
