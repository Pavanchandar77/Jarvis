"""Phase A0/A harness layer tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from services.harness.base import CodingHarness
from services.harness.manager import HarnessManager
from services.harness.null_harness import NullHarness
from services.harness.registry import HarnessRegistry


@pytest.fixture
def registry():
    reg = HarnessRegistry()
    reg.register("null", NullHarness, display_name="Null")
    return reg


@pytest.mark.asyncio
async def test_null_harness_protocol(registry, tmp_path):
    mgr = HarnessManager(session_store_path=str(tmp_path / "sess.json"), registry=registry)
    assert any(h["harness_id"] == "null" for h in mgr.list_harnesses())

    handle = await mgr.start("null", "ws1", str(tmp_path / "repo"))
    assert handle.harness_id == "null"
    st = await mgr.status(handle.handle_id)
    assert st.state == "running"

    session = await mgr.create_session(handle.handle_id, model="m1")
    await mgr.send(session.session_id, "hello")
    events = []
    async for ev in mgr.stream(session.session_id):
        events.append(ev)
        if ev.type == "done":
            break
    assert any(e.type == "message.delta" for e in events)
    await mgr.cancel(session.session_id)
    await mgr.stop(handle.handle_id)


def test_registry_unknown():
    reg = HarnessRegistry()
    with pytest.raises(KeyError):
        reg.create("missing")


def test_null_is_coding_harness():
    h = NullHarness()
    assert isinstance(h, CodingHarness)
