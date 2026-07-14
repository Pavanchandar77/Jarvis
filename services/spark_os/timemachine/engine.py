"""Project Time Machine — scrub architecture, code, requirements, graph, runtime history."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.semantic_twin.models import SemanticTwin


class ProjectTimeMachine:
    """
    Enriches Phase-1 VersionTimeline with multi-dimension evolution narratives.
    Does not replace timeline storage — composes it.
    """

    def __init__(self, timeline, event_log=None) -> None:
        self.timeline = timeline
        self.event_log = event_log

    def history(self, twin_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        versions = self.timeline.list_versions(twin_id)
        events = []
        if self.event_log and project_id:
            events = self.event_log.list(project_id, limit=100)
        return {
            "twin_id": twin_id,
            "project_id": project_id,
            "versions": versions,
            "events": events,
            "dimensions": [
                "architecture", "code", "requirements", "semantic_graph",
                "dependencies", "runtime",
            ],
        }

    def scrub(
        self,
        twin_id: str,
        revision: int,
        *,
        prior_revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Explain a point in history: why, who, what changed, impact."""
        entry = self.timeline.get_version(twin_id, revision) or {}
        diff = None
        if prior_revision is not None:
            diff = self.timeline.get_diff(twin_id, prior_revision, revision)
        elif entry:
            # try previous
            versions = self.timeline.list_versions(twin_id)
            prevs = [v for v in versions if v.get("revision", 0) < revision]
            if prevs:
                prior_revision = prevs[-1]["revision"]
                diff = self.timeline.get_diff(twin_id, prior_revision, revision)

        why = entry.get("label") or entry.get("trigger") or "unknown"
        who = "spark_agent" if (entry.get("trigger") in ("generate", "update", "sync")) else entry.get("trigger", "system")
        what = {
            "node_count": entry.get("node_count"),
            "edge_count": entry.get("edge_count"),
            "languages": entry.get("languages"),
            "tech_stack": entry.get("tech_stack"),
            "kinds": entry.get("kinds"),
        }
        impact = {}
        if diff:
            impact = {
                "added_nodes": len(diff.get("added_nodes") or []),
                "removed_nodes": len(diff.get("removed_nodes") or []),
                "modified_nodes": len(diff.get("modified_nodes") or []),
                "added_edges": len(diff.get("added_edges") or []),
                "removed_edges": len(diff.get("removed_edges") or []),
                "concept_diff": diff.get("concept_diff"),
                "dependency_diff": diff.get("dependency_diff"),
                "summary": diff.get("summary"),
            }

        return {
            "twin_id": twin_id,
            "revision": revision,
            "prior_revision": prior_revision,
            "why": why,
            "who": who,
            "what_changed": what,
            "impact": impact,
            "entry": entry,
            "diff": diff,
            "narrative": self._narrative(revision, who, why, impact),
        }

    def compare_dimensions(
        self,
        twin_a: SemanticTwin,
        twin_b: SemanticTwin,
    ) -> Dict[str, Any]:
        """Multi-dimension diff between two twin snapshots in memory."""
        from services.semantic_twin.api.compare import compare_twins
        base = compare_twins(twin_a, twin_b)
        req_a = {n.id for n in twin_a.nodes if n.kind == "requirement"}
        req_b = {n.id for n in twin_b.nodes if n.kind == "requirement"}
        dep_a = {(e.source, e.target) for e in twin_a.edges if e.kind in ("depends_on", "imports", "calls")}
        dep_b = {(e.source, e.target) for e in twin_b.edges if e.kind in ("depends_on", "imports", "calls")}
        return {
            **base,
            "requirement_evolution": {
                "added": sorted(req_b - req_a),
                "removed": sorted(req_a - req_b),
            },
            "dependency_evolution": {
                "added": len(dep_b - dep_a),
                "removed": len(dep_a - dep_b),
            },
            "architecture_evolution": {
                "a_nodes": twin_a.meta.node_count,
                "b_nodes": twin_b.meta.node_count,
            },
        }

    def _narrative(self, rev: int, who: str, why: str, impact: Dict) -> str:
        if not impact:
            return f"Revision r{rev} by {who}: {why}."
        return (
            f"Revision r{rev} by {who}: {why}. "
            f"Impact: +{impact.get('added_nodes', 0)}/-{impact.get('removed_nodes', 0)} nodes, "
            f"+{impact.get('added_edges', 0)}/-{impact.get('removed_edges', 0)} edges. "
            f"{impact.get('summary') or ''}"
        )
