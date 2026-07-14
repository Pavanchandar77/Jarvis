"""End-to-end pipeline on the sample fixture app."""

from services.semantic_twin.service import SemanticTwinService


def test_generate_sample_app(sample_app_root, twin_storage, sample_manifest):
    svc = SemanticTwinService(twin_storage)
    twin = svc.generate(
        sample_app_root,
        sample_manifest,
        application_id="sample-app",
        application_name="Sample App",
        owner="tester",
    )
    assert twin.twin_id
    assert twin.meta.node_count > 5
    assert twin.meta.edge_count > 0
    kinds = {n.kind for n in twin.nodes}
    assert "application" in kinds
    assert "function" in kinds or "method" in kinds
    assert "module" in kinds
    # Views present on code-ish nodes
    code_nodes = [n for n in twin.nodes if n.kind in ("function", "component", "class", "method")]
    assert code_nodes
    for n in code_nodes[:3]:
        for mode in (
            "beginner", "intermediate", "senior", "runtime",
            "ai_reasoning", "performance", "security",
        ):
            assert mode in n.views, f"missing view {mode} on {n.name}"
    # Required node fields
    n = code_nodes[0]
    for field in (
        "id", "name", "description", "purpose", "why_exists", "created_by",
        "dependencies", "dependents", "related_concepts",
        "suggested_improvements", "learning_resources", "difficulty_score",
    ):
        assert hasattr(n, field)
    # Provenance
    assert any(n.kind == "prompt" for n in twin.nodes)
    assert any(n.kind == "design_decision" for n in twin.nodes)
    # Persist load
    loaded = svc.load(twin.twin_id, owner="tester")
    assert loaded.content_hash == twin.content_hash
