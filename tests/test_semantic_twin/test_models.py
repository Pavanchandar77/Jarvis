"""Model serialization round-trips."""

from services.semantic_twin.models import (
    SEMANTIC_TWIN_SCHEMA_VERSION,
    GenerationManifest,
    SemanticEdge,
    SemanticNode,
    SemanticTwin,
    SourceLocation,
    ViewContent,
)


def test_node_roundtrip():
    n = SemanticNode(
        id="n1",
        kind="function",
        name="hello",
        description="d",
        purpose="p",
        why_exists="w",
        created_by="ai",
        prompt_id="pr1",
        source_file="a.py",
        source_location=SourceLocation(1, 10),
        difficulty_score=0.4,
        views={
            "beginner": ViewContent(mode="beginner", title="t", body="b"),
        },
    )
    back = SemanticNode.from_dict(n.to_dict())
    assert back.id == "n1"
    assert back.source_location.start_line == 1
    assert "beginner" in back.views


def test_twin_roundtrip():
    twin = SemanticTwin(
        twin_id="abc",
        application_id="app1",
        schema_version=SEMANTIC_TWIN_SCHEMA_VERSION,
        manifest=GenerationManifest.empty("g1"),
        nodes=[SemanticNode(id="n1", kind="function", name="f")],
        edges=[SemanticEdge(id="e1", kind="calls", source="n1", target="n1")],
    )
    twin.meta.application_id = "app1"
    twin.meta.application_name = "App"
    data = twin.to_dict()
    back = SemanticTwin.from_dict(data)
    assert back.twin_id == "abc"
    assert len(back.nodes) == 1
    assert back.schema_version == SEMANTIC_TWIN_SCHEMA_VERSION
