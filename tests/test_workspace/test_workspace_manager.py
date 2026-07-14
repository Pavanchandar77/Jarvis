"""Workspace Manager + manifest tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.harness.manager import HarnessManager
from services.harness.null_harness import NullHarness
from services.harness.registry import HarnessRegistry
from services.workspace.manifest import WorkspaceManifest
from services.workspace.manager import WorkspaceManager
from services.workspace.registry import WorkspaceRegistry


@pytest.fixture
def wm(tmp_path):
    reg = HarnessRegistry()
    reg.register("null", NullHarness)
    hm = HarnessManager(str(tmp_path / "sess.json"), registry=reg)
    wr = WorkspaceRegistry(tmp_path / "index.json", tmp_path / "manifests")
    return WorkspaceManager(wr, hm)


def test_create_and_manifest_fields(wm, tmp_path):
    root = tmp_path / "proj"
    m = wm.create("Demo", str(root), owner="u1", active_harness="null", active_model="gpt")
    assert m.workspace_id
    assert Path(m.repo_root).is_dir()
    assert m.active_harness == "null"
    assert m.active_model == "gpt"
    loaded = wm.get(m.workspace_id)
    assert loaded.name == "Demo"
    assert wm.registry.by_root(str(root)).workspace_id == m.workspace_id


def test_bind_runtime_and_agents(wm, tmp_path):
    m = wm.create("R", str(tmp_path / "r2"))
    m = wm.bind_runtime(m.workspace_id, active_model="local-7b", endpoint_url="http://x")
    assert m.active_model == "local-7b"
    m = wm.set_agents(m.workspace_id, ["architect", "backend"])
    assert "architect" in m.active_agents


@pytest.mark.asyncio
async def test_start_harness_updates_manifest(wm, tmp_path):
    m = wm.create("H", str(tmp_path / "r3"), active_harness="null")
    result = await wm.start_harness(m.workspace_id)
    assert result["handle"]["harness_id"] == "null"
    m2 = wm.get(m.workspace_id)
    assert m2.harness_handle_id
    assert m2.active_harness == "null"
    sess = await wm.create_coding_session(m.workspace_id)
    assert sess["session"]["session_id"]
    await wm.stop_harness(m.workspace_id)


def test_manifest_roundtrip():
    m = WorkspaceManifest.create("n", "/tmp/x", twin_id="t1", knowledge_memory_id="org")
    back = WorkspaceManifest.from_dict(m.to_dict())
    assert back.twin_id == "t1"
    assert back.knowledge_memory_id == "org"
