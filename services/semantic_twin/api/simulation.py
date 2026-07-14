"""simulateModification — heuristic impact analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..graph.query import GraphQuery
from ..models import SemanticTwin


def simulate_modification(
    twin: SemanticTwin,
    proposal: str,
    focus_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    q = GraphQuery.from_twin(twin)
    node_map = twin.node_map()

    root = focus_node_id
    if not root or root not in node_map:
        # Keyword hint from proposal
        prop_l = (proposal or "").lower()
        for n in twin.nodes:
            if n.name.lower() in prop_l:
                root = n.id
                break
        if not root and twin.meta.entrypoints:
            root = twin.meta.entrypoints[0]
        if not root and twin.nodes:
            root = twin.nodes[0].id

    if not root or root not in node_map:
        return {
            "proposal": proposal,
            "affected_node_ids": [],
            "risk_level": "low",
            "predicted_breaks": [],
            "suggested_tests": [],
            "narrative": "No nodes available to simulate against.",
        }

    nodes, edges = q.trace_dependency(root, direction="upstream", max_depth=4)
    # upstream dependents = who breaks if we change root
    # also include root
    affected = list(dict.fromkeys([root] + nodes))
    root_node = node_map[root]
    breaks: List[str] = []
    tests: List[str] = []

    for nid in affected[1:8]:
        n = node_map.get(nid)
        if not n:
            continue
        breaks.append(f"{n.kind} `{n.name}` may observe changed behavior from `{root_node.name}`.")
        tests.append(f"Add/adjust test covering `{n.name}` interaction with `{root_node.name}`.")

    if root_node.kind in ("api_endpoint", "route"):
        breaks.append("Contract changes may break external clients.")
        tests.append("Contract / integration test for the HTTP surface.")
        risk = "high"
    elif len(affected) > 12:
        risk = "high"
    elif len(affected) > 4:
        risk = "medium"
    else:
        risk = "low"

    if "security" in (proposal or "").lower() or "auth" in (proposal or "").lower():
        risk = "high"
        breaks.append("Security-sensitive change — review authorization paths.")

    narrative = (
        f"Proposal: {proposal}\n"
        f"Focus: `{root_node.name}` ({root_node.kind}). "
        f"Estimated impact fan-in walk found {len(affected)} node(s). "
        f"Risk: {risk}."
    )

    return {
        "proposal": proposal,
        "affected_node_ids": affected,
        "risk_level": risk,
        "predicted_breaks": breaks[:20],
        "suggested_tests": tests[:20],
        "narrative": narrative,
    }
