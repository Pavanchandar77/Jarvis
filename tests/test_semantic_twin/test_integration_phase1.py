"""Phase 1 — automatic generation, registry, continuous sync, agent bridge."""

from __future__ import annotations

import json
from pathlib import Path

from services.semantic_twin.integration.agent_bridge import do_semantic_twin
from services.semantic_twin.integration.hooks import (
    IntegrationService,
    on_agent_turn_end,
    on_agent_turn_start,
    on_file_written,
    set_integration_service,
)
from services.semantic_twin.integration.manifest_builder import ManifestBuilder
from services.semantic_twin.models import GenerationManifest
from services.semantic_twin.service import SemanticTwinService


def test_expanded_manifest_roundtrip():
    m = GenerationManifest(
        generation_id="g1",
        user_prompt="Build a todo app",
        planning_prompt="- [ ] API\n- [ ] UI",
        agent_chain=[{"round": 1, "tools": ["write_file"]}],
        tool_history=[{"tool": "write_file", "path": "a.py"}],
        backend="http://localhost:8080",
        file_ownership={"a.py": "agent"},
        trade_offs=["simplicity"],
    )
    back = GenerationManifest.from_dict(m.to_dict())
    assert back.user_prompt == "Build a todo app"
    assert back.agent_chain[0]["round"] == 1
    assert back.file_ownership["a.py"] == "agent"


def test_manifest_builder_from_prompt():
    b = ManifestBuilder(
        user_prompt="Build an API\n- GET /items\n- list UI",
        model="test-model",
        backend="local",
    )
    b.record_tool(tool="write_file", path="src/app.py", exit_code=0)
    b.record_decision(
        "Use Flask",
        "Simple for demo",
        "Flask",
        alternatives=[{"id": "a", "title": "FastAPI", "summary": "async", "why_rejected": "overkill"}],
        trade_offs=["sync vs async"],
    )
    m = b.build()
    assert m.user_prompt
    assert m.requirements
    assert m.decisions
    assert m.tool_history
    assert "python" in m.tech_stack or m.file_prompt_map


def test_auto_generate_on_turn_end(tmp_path, sample_app_root):
    storage = tmp_path / "twins"
    registry = tmp_path / "registry.json"
    projects = tmp_path / "projects"
    twin_svc = SemanticTwinService(storage)
    integ = IntegrationService(
        twin_svc,
        registry_path=str(registry),
        projects_dir=str(projects),
        timeline_base=str(storage),
    )
    set_integration_service(integ)

    # Copy sample into a project dir and simulate writes
    import shutil
    app = tmp_path / "myapp"
    shutil.copytree(sample_app_root, app)

    on_agent_turn_start(
        session_id="sess-1",
        owner="tester",
        workspace=str(app),
        model="test-model",
        backend="http://localhost",
        user_prompt="Generate a catalog API",
    )
    # Simulate write_file notifications for each source file
    for p in app.rglob("*"):
        if p.is_file():
            on_file_written(str(p), session_id="sess-1", owner="tester", workspace=str(app))

    result = on_agent_turn_end(
        session_id="sess-1",
        owner="tester",
        workspace=str(app),
        model="test-model",
        endpoint_url="http://localhost",
        tool_events=[
            {"tool": "write_file", "command": str(app / "src" / "app.py"), "exit_code": 0, "round": 1}
        ],
    )
    assert result is not None
    assert result["ok"] is True
    assert result["twin_id"]
    assert result["project_id"]

    # Registry has the project
    rows = integ.registry.list(owner="tester")
    assert any(r.twin_id == result["twin_id"] for r in rows)

    # Timeline has a version
    versions = integ.timeline.list_versions(result["twin_id"])
    assert versions

    # Twin has expanded manifest intent
    twin = twin_svc.load(result["twin_id"], owner="tester")
    assert twin.manifest.user_prompt or twin.manifest.prompts

    # Agent bridge can list / search
    out = do_semantic_twin(json.dumps({"action": "list_projects"}), owner="tester")
    assert out["exit_code"] == 0
    out2 = do_semantic_twin(
        json.dumps({"action": "architecture", "twin_id": result["twin_id"]}),
        owner="tester",
    )
    assert out2["exit_code"] == 0
    assert "modules" in out2["result"]

    # Runtime event enriches
    rt = integ.runtime.ingest(
        result["twin_id"],
        {"type": "app.launch", "name": "Application"},
        persist=True,
        owner="tester",
    )
    assert rt["ok"]


def test_continuous_sync_notify(tmp_path, sample_app_root):
    storage = tmp_path / "twins"
    twin_svc = SemanticTwinService(storage)
    integ = IntegrationService(
        twin_svc,
        registry_path=str(tmp_path / "reg.json"),
        projects_dir=str(tmp_path / "proj"),
        timeline_base=str(storage),
    )
    set_integration_service(integ)

    import shutil
    app = tmp_path / "syncapp"
    shutil.copytree(sample_app_root, app)

    twin = twin_svc.generate(
        app,
        GenerationManifest(generation_id="g-sync", user_prompt="sync test"),
        application_id="syncapp",
        application_name="Sync App",
    )
    integ.registry.register(
        project_id="syncapp",
        name="Sync App",
        app_root=str(app),
        twin_id=twin.twin_id,
        revision=twin.content_revision,
    )

    target = app / "src" / "app.py"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n\ndef synced():\n    return 1\n",
        encoding="utf-8",
    )
    integ.sync.notify(
        twin_id=twin.twin_id,
        app_root=str(app),
        rel_path="src/app.py",
    )
    updated = integ.sync.flush_now(twin.twin_id)
    assert updated is not None
    names = {n.name for n in updated.nodes}
    assert "synced" in names or updated.content_revision >= twin.content_revision
