"""Phase 2 Spark OS — all ten capabilities via Twin."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from services.semantic_twin.models import GenerationManifest
from services.semantic_twin.service import SemanticTwinService
from services.semantic_twin.integration.hooks import IntegrationService, set_integration_service
from services.spark_os import SparkOSService


@pytest.fixture
def os_stack(tmp_path, sample_app_root):
    twin_store = tmp_path / "twins"
    os_dir = tmp_path / "os"
    twin_svc = SemanticTwinService(twin_store)
    integ = IntegrationService(
        twin_svc,
        registry_path=str(tmp_path / "reg.json"),
        projects_dir=str(tmp_path / "projects"),
        timeline_base=str(twin_store),
    )
    set_integration_service(integ)
    os_svc = SparkOSService(twin_svc, os_dir=os_dir, integration=integ)

    app = tmp_path / "app"
    shutil.copytree(sample_app_root, app)
    twin = twin_svc.generate(
        app,
        GenerationManifest(
            generation_id="p2",
            user_prompt="Build catalog API",
            requirements=[{"id": "req-items", "text": "Expose GET /items", "prompt_id": "p1"}],
            tech_stack=["python"],
        ),
        application_id="p2-app",
        application_name="P2 App",
        owner="tester",
    )
    integ.timeline.record(twin, trigger="generate", label="initial")
    integ.registry.register(
        project_id="p2-app",
        name="P2 App",
        app_root=str(app),
        twin_id=twin.twin_id,
        owner="tester",
        revision=twin.content_revision,
    )
    return os_svc, twin_svc, twin, app


def test_architecture_first_compile(os_stack, tmp_path):
    os_svc, twin_svc, twin, app = os_stack
    spec = os_svc.designer.from_template(
        "Demo Arch",
        services=["api", "worker"],
        apis=[{"name": "Health", "method": "GET", "path": "/health"}],
        databases=["main_db"],
        owner="tester",
    )
    target = tmp_path / "compiled"
    result = os_svc.compile_architecture(
        spec.architecture_id,
        str(target),
        owner="tester",
        generate_twin=True,
        run_review=True,
    )
    assert (target / "ARCHITECTURE.md").is_file()
    assert result.get("twin_id")
    assert result.get("review")
    assert "overall" in result["review"]


def test_living_requirements_trace(os_stack):
    os_svc, twin_svc, twin, app = os_stack
    os_svc.link_requirement(
        twin.twin_id,
        {"id": "req-items", "text": "Expose GET /items", "artifact_ids": []},
        owner="tester",
    )
    listed = os_svc.list_requirements(twin.twin_id, owner="tester")
    assert listed["requirements"]
    rid = listed["requirements"][0]["id"]
    trace = os_svc.trace_requirement(twin.twin_id, rid, owner="tester")
    assert "chain" in trace
    assert "narrative" in trace


def test_design_review(os_stack):
    os_svc, twin_svc, twin, app = os_stack
    report = os_svc.review_architecture(twin.twin_id, owner="tester")
    assert "scores" in report
    assert "findings" in report
    assert 0 <= report["overall"] <= 1


def test_multi_agent_workspace(os_stack):
    os_svc, twin_svc, twin, app = os_stack
    boot = os_svc.agent_bootstrap(twin.twin_id, owner="tester")
    assert "ownership" in boot
    status = os_svc.agent_status(twin.application_id)
    assert "roles" in status
    msg = os_svc.agent_message(twin.application_id, {
        "from_agent": "backend",
        "to_agent": "architect",
        "type": "claim",
        "region_node_ids": list(boot["ownership"].keys())[:2],
        "requires_approval": True,
    })
    assert msg["message"]["id"]


def test_time_machine(os_stack):
    os_svc, twin_svc, twin, app = os_stack
    hist = os_svc.timeline_history(twin.twin_id, project_id=twin.application_id)
    assert "versions" in hist
    if hist["versions"]:
        scrub = os_svc.timeline_scrub(twin.twin_id, hist["versions"][0]["revision"])
        assert "why" in scrub
        assert "narrative" in scrub


def test_simulation_no_disk_write(os_stack):
    os_svc, twin_svc, twin, app = os_stack
    before = {p.name: p.stat().st_mtime for p in app.rglob("*") if p.is_file()}
    report = os_svc.simulate(
        twin.twin_id,
        "Delete the health endpoint and move database",
        owner="tester",
    )
    after = {p.name: p.stat().st_mtime for p in app.rglob("*") if p.is_file()}
    assert report["risk_level"] in ("low", "medium", "high")
    assert report["estimated_effort_days"] >= 0
    # source tree untouched
    assert before == after


def test_org_memory(os_stack):
    os_svc, twin_svc, twin, app = os_stack
    os_svc.review_architecture(twin.twin_id, owner="tester")
    learned = os_svc.memory_learn(twin.twin_id, owner="tester")
    assert learned["learned"]
    hits = os_svc.memory_retrieve("api testing security")
    assert "hits" in hits


def test_runtime_visualization(os_stack):
    os_svc, twin_svc, twin, app = os_stack
    viz = os_svc.runtime_visualization(twin.twin_id, owner="tester")
    assert len(viz["frames"]) >= 5
    assert viz["path_label"]


def test_marketplace(os_stack):
    os_svc, twin_svc, twin, app = os_stack
    listed = os_svc.marketplace_list()
    assert len(listed["architectures"]) >= 8
    item = os_svc.marketplace_get("saas")
    assert item["slug"] == "saas"
    used = os_svc.marketplace_use("event-driven", owner="tester")
    assert used["architecture"]["architecture_id"]


def test_refactor_pipeline(os_stack):
    os_svc, twin_svc, twin, app = os_stack
    cat = os_svc.refactor_catalog()
    assert cat["transformations"]
    result = os_svc.refactor_pipeline(
        twin.twin_id,
        "introduce_caching",
        owner="tester",
    )
    assert result["risk"]
    assert result["migration"]["files"]
    assert result["validation"]
