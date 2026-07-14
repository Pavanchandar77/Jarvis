"""Knowledge graph invariants and traversal."""

from services.semantic_twin.graph.knowledge_graph import KnowledgeGraph
from services.semantic_twin.graph.query import GraphQuery
from services.semantic_twin.models import SemanticNode


def test_add_nodes_and_edges():
    g = KnowledgeGraph()
    g.add_node(SemanticNode(id="a", kind="function", name="a"))
    g.add_node(SemanticNode(id="b", kind="function", name="b"))
    e = g.add_edge("calls", "a", "b")
    assert e is not None
    assert len(g.edges()) == 1
    assert g.validate() == []


def test_contains_cycle_rejected():
    g = KnowledgeGraph()
    g.add_node(SemanticNode(id="a", kind="module", name="a"))
    g.add_node(SemanticNode(id="b", kind="module", name="b"))
    assert g.add_edge("contains", "a", "b") is not None
    # b → a would cycle
    assert g.add_edge("contains", "b", "a") is None


def test_calls_may_cycle():
    g = KnowledgeGraph()
    g.add_node(SemanticNode(id="a", kind="function", name="a"))
    g.add_node(SemanticNode(id="b", kind="function", name="b"))
    assert g.add_edge("calls", "a", "b") is not None
    assert g.add_edge("calls", "b", "a") is not None


def test_trace_execution_cycle_safe():
    g = KnowledgeGraph()
    for i, name in enumerate("abc"):
        g.add_node(SemanticNode(id=name, kind="function", name=name, execution_order=i))
    g.add_edge("calls", "a", "b")
    g.add_edge("calls", "b", "c")
    g.add_edge("calls", "c", "a")  # cycle
    q = GraphQuery.from_graph(g)
    steps, _ = q.trace_execution("a", max_depth=10)
    ids = [s[0] for s in steps]
    assert ids[0] == "a"
    assert len(ids) == len(set(ids))  # no duplicate visits
