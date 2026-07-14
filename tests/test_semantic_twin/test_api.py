"""Twin API facade methods."""

from services.semantic_twin.service import SemanticTwinService


def test_facade_methods(sample_app_root, twin_storage, sample_manifest):
    svc = SemanticTwinService(twin_storage)
    twin = svc.generate(sample_app_root, sample_manifest, application_id="api-app")
    api = svc.api(twin)

    search = api.search("health")
    assert "hits" in search

    # Pick a function node
    node = next(n for n in twin.nodes if n.kind in ("function", "method", "component", "class"))
    explained = api.explain(node.id, mode="beginner")
    assert explained["content"]["mode"] == "beginner"
    assert explained["content"]["body"]

    for mode in (
        "intermediate", "senior", "runtime", "ai_reasoning", "performance", "security"
    ):
        e = api.explain(node.id, mode=mode)
        assert e["content"]["body"]

    exec_trace = api.trace_execution(node.id, max_depth=5)
    assert exec_trace["entry_id"] == node.id
    assert isinstance(exec_trace["steps"], list)

    dep = api.trace_dependency(node.id, direction="downstream", max_depth=3)
    assert node.id in dep["nodes"]

    concepts = api.find_concept("api")
    assert "hits" in concepts

    quiz = api.generate_quiz(count=3)
    assert len(quiz["questions"]) <= 3
    assert quiz["questions"]

    tutorial = api.generate_tutorial(focus_node_id=node.id, max_steps=5)
    assert tutorial["steps"]

    sim = api.simulate_modification("rename function and change auth", focus_node_id=node.id)
    assert sim["risk_level"] in ("low", "medium", "high")
    assert node.id in sim["affected_node_ids"]

    diff = api.compare_versions(0)
    assert "summary" in diff

    story = api.story_for_node(node.id)
    kinds = [s["kind"] for s in story]
    assert kinds[0] == "prompt"
    assert "generated_code" in kinds
    assert "related_concepts" in kinds
