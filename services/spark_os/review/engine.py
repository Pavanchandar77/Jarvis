"""Autonomous Architecture Review Engine — findings become Twin nodes."""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from services.semantic_twin.ids import new_edge_id, stable_node_id
from services.semantic_twin.models import SemanticEdge, SemanticNode, SemanticTwin
from services.semantic_twin.schema import EdgeKind, NodeKind

from ..models import ReviewFinding, ReviewReport


class ArchitectureReviewEngine:
    """
    Deterministic graph metrics review (Phase 2.0).
    Emits findings with severity, evidence, solution, impact.
    Optionally materializes findings onto the Twin.
    """

    CATEGORIES = (
        "architecture_quality", "coupling", "cohesion", "layering",
        "circular_dependencies", "scalability", "security", "maintainability",
        "testability", "performance", "cost", "complexity", "technical_debt",
    )

    def review(
        self,
        twin: SemanticTwin,
        *,
        focus_node_ids: Optional[List[str]] = None,
        attach_to_twin: bool = True,
    ) -> ReviewReport:
        findings: List[ReviewFinding] = []
        scores: Dict[str, float] = {c: 0.75 for c in self.CATEGORIES}

        node_map = twin.node_map()
        focus = set(focus_node_ids or [])

        # Coupling / fan-out
        high_fanout = []
        for n in twin.nodes:
            if focus and n.id not in focus:
                continue
            if len(n.dependencies) > 10:
                high_fanout.append(n)
        if high_fanout:
            scores["coupling"] = max(0.2, 0.75 - 0.05 * len(high_fanout))
            for n in high_fanout[:8]:
                findings.append(self._finding(
                    "coupling", "high",
                    f"High fan-out: {n.name}",
                    f"`{n.name}` depends on {len(n.dependencies)} symbols, reducing cohesion of change.",
                    [f"fan_out={len(n.dependencies)}", f"kind={n.kind}"],
                    "Introduce a facade or split responsibilities.",
                    "medium",
                    [n.id],
                    -0.05,
                ))

        # Circular dependencies via depends_on/imports/calls
        cycles = self._find_cycles(twin, kinds={"depends_on", "imports"})
        if cycles:
            scores["circular_dependencies"] = 0.35
            scores["architecture_quality"] = min(scores["architecture_quality"], 0.5)
            for cyc in cycles[:5]:
                findings.append(self._finding(
                    "circular_dependencies", "critical",
                    "Circular dependency detected",
                    "Cycle: " + " → ".join(cyc[:8]),
                    [f"cycle_length={len(cyc)}"],
                    "Break cycle with dependency inversion or extract shared kernel.",
                    "high",
                    [nid for nid in cyc if nid in node_map][:10],
                    -0.15,
                ))

        # Layering: API calling UI? DB called by everything?
        apis = [n for n in twin.nodes if n.kind == NodeKind.API_ENDPOINT.value]
        components = [n for n in twin.nodes if n.kind == NodeKind.COMPONENT.value]
        tables = [n for n in twin.nodes if n.kind == NodeKind.TABLE.value]
        if apis and components:
            for e in twin.edges:
                if e.kind == "calls":
                    src, tgt = node_map.get(e.source), node_map.get(e.target)
                    if src and tgt and src.kind == NodeKind.API_ENDPOINT.value and tgt.kind == NodeKind.COMPONENT.value:
                        scores["layering"] = 0.4
                        findings.append(self._finding(
                            "layering", "high",
                            "API depends on UI component",
                            f"{src.name} → {tgt.name} inverts layering.",
                            [e.id],
                            "UI should call APIs, not the reverse.",
                            "high",
                            [src.id, tgt.id],
                            -0.1,
                        ))

        # Security surfaces
        sec_nodes = [n for n in twin.nodes if n.kind == NodeKind.SECURITY_SURFACE.value]
        unsecured_apis = [a for a in apis if "auth" not in a.name.lower()]
        if apis and len(sec_nodes) < max(1, len(apis) // 3):
            scores["security"] = 0.45
            findings.append(self._finding(
                "security", "high",
                "Sparse security surface coverage",
                f"{len(apis)} API endpoints vs {len(sec_nodes)} security surfaces.",
                [f"apis={len(apis)}", f"surfaces={len(sec_nodes)}"],
                "Add authz checks and mark security_surface nodes per endpoint.",
                "high",
                [a.id for a in unsecured_apis[:5]],
                -0.1,
            ))

        # Testability
        tests = [n for n in twin.nodes if n.kind == NodeKind.TEST.value]
        code = [n for n in twin.nodes if n.kind in (
            NodeKind.FUNCTION.value, NodeKind.METHOD.value, NodeKind.COMPONENT.value
        )]
        ratio = len(tests) / max(1, len(code))
        scores["testability"] = min(1.0, 0.3 + ratio)
        if ratio < 0.15 and code:
            findings.append(self._finding(
                "testability", "medium",
                "Low test graph coverage",
                f"Only {len(tests)} test nodes for {len(code)} code units (ratio {ratio:.2f}).",
                [f"tests={len(tests)}", f"code={len(code)}"],
                "Add unit/integration tests for critical paths.",
                "medium",
                [c.id for c in code[:5]],
                -0.08,
            ))

        # Complexity / debt from difficulty scores
        hard = [n for n in twin.nodes if n.difficulty_score >= 0.7]
        if hard:
            scores["complexity"] = max(0.25, 0.8 - 0.03 * len(hard))
            scores["technical_debt"] = scores["complexity"]
            findings.append(self._finding(
                "complexity", "medium",
                f"{len(hard)} high-difficulty nodes",
                "Elevated difficulty scores suggest cognitive load / debt.",
                [f"{n.name}:{n.difficulty_score:.2f}" for n in hard[:5]],
                "Refactor or document complex units; reduce fan-out.",
                "medium",
                [n.id for n in hard[:8]],
                -0.05,
            ))

        # Performance: async without structure
        async_nodes = [n for n in twin.nodes if (n.attributes or {}).get("async")]
        if len(async_nodes) > 15:
            scores["performance"] = 0.55
            findings.append(self._finding(
                "performance", "medium",
                "Large async surface",
                f"{len(async_nodes)} async symbols — risk of unbounded concurrency.",
                [n.name for n in async_nodes[:5]],
                "Add timeouts, bulkheads, and backpressure.",
                "medium",
                [n.id for n in async_nodes[:5]],
                -0.05,
            ))

        # Scalability: single module concentration
        by_file = twin.indexes.by_file or {}
        if by_file:
            largest = max(by_file.items(), key=lambda kv: len(kv[1]))
            if len(largest[1]) > 40:
                scores["scalability"] = 0.5
                findings.append(self._finding(
                    "scalability", "medium",
                    f"God file: {largest[0]}",
                    f"{len(largest[1])} nodes in one file hinder scaling teams.",
                    [largest[0]],
                    "Split modules by bounded context.",
                    "high",
                    largest[1][:5],
                    -0.07,
                ))

        # Maintainability: missing why_exists / docs
        undocumented = [
            n for n in code
            if not (n.why_exists or "").strip() or len(n.why_exists) < 10
        ]
        if len(undocumented) > 10:
            scores["maintainability"] = 0.55
            findings.append(self._finding(
                "maintainability", "low",
                "Many nodes lack rationale",
                f"{len(undocumented)} code nodes have weak why_exists text.",
                [],
                "Backfill living requirements and design decisions.",
                "low",
                [n.id for n in undocumented[:5]],
                -0.03,
            ))

        # Cost proxy: too many services/endpoints
        if len(apis) > 50:
            scores["cost"] = 0.5
            findings.append(self._finding(
                "cost", "medium",
                "Large API surface",
                f"{len(apis)} endpoints increase ops and review cost.",
                [f"apis={len(apis)}"],
                "Consolidate endpoints; prefer BFF or gateway aggregation.",
                "medium",
                [a.id for a in apis[:5]],
                -0.04,
            ))

        # Cohesion: packages with mixed unrelated kinds — light heuristic
        scores["cohesion"] = 0.7 if not high_fanout else 0.5
        scores["architecture_quality"] = sum(scores.values()) / len(scores)
        overall = round(sum(scores.values()) / len(scores), 3)

        report = ReviewReport(
            review_id=uuid.uuid4().hex,
            twin_id=twin.twin_id,
            scores={k: round(v, 3) for k, v in scores.items()},
            overall=overall,
            findings=findings,
            metadata={"focus_count": len(focus)},
        )

        if attach_to_twin:
            self._attach(twin, report)
        return report

    def _attach(self, twin: SemanticTwin, report: ReviewReport) -> None:
        rid = stable_node_id("pattern", None, f"review:{report.review_id}")
        twin.nodes.append(
            SemanticNode(
                id=rid,
                kind=NodeKind.PATTERN.value,
                name=f"Architecture Review {report.overall:.2f}",
                description=f"Automated review overall={report.overall}",
                purpose="Holds architecture review results on the Twin.",
                why_exists="Autonomous design review before/after generation.",
                created_by="plugin:architecture_review",
                attributes={
                    "review_id": report.review_id,
                    "scores": report.scores,
                    "overall": report.overall,
                    "finding_count": len(report.findings),
                },
                difficulty_score=0.4,
            )
        )
        for f in report.findings:
            fid = stable_node_id("security_surface" if f.category == "security" else "pattern", None, f.id)
            kind = NodeKind.SECURITY_SURFACE.value if f.category == "security" else NodeKind.PATTERN.value
            twin.nodes.append(
                SemanticNode(
                    id=fid,
                    kind=kind,
                    name=f.severity.upper() + ": " + f.title,
                    description=f.explanation,
                    purpose=f.proposed_solution,
                    why_exists="Review finding attached to Semantic Twin.",
                    created_by="plugin:architecture_review",
                    attributes={
                        "review_id": report.review_id,
                        "category": f.category,
                        "severity": f.severity,
                        "evidence": f.evidence,
                        "estimated_impact": f.estimated_impact,
                    },
                    difficulty_score={"critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.3}.get(f.severity, 0.4),
                )
            )
            twin.edges.append(
                SemanticEdge(
                    id=new_edge_id("related_to", rid, fid),
                    kind=EdgeKind.RELATED_TO.value,
                    source=rid,
                    target=fid,
                )
            )
            for nid in f.node_ids:
                if any(n.id == nid for n in twin.nodes):
                    twin.edges.append(
                        SemanticEdge(
                            id=new_edge_id("related_to", fid, nid, f.id),
                            kind=EdgeKind.RELATED_TO.value,
                            source=fid,
                            target=nid,
                            attributes={"finding": f.id},
                        )
                    )
        twin.meta.node_count = len(twin.nodes)
        twin.meta.edge_count = len(twin.edges)
        twin.manifest.metadata = dict(twin.manifest.metadata or {})
        twin.manifest.metadata["last_review_id"] = report.review_id
        twin.manifest.metadata["last_review_overall"] = report.overall

    def _finding(self, category, severity, title, explanation, evidence, solution, impact, node_ids, score_delta) -> ReviewFinding:
        raw = f"{category}:{title}:{','.join(node_ids)}"
        fid = "f_" + hashlib.sha256(raw.encode()).hexdigest()[:14]
        return ReviewFinding(
            id=fid,
            category=category,
            severity=severity,
            title=title,
            explanation=explanation,
            evidence=list(evidence),
            proposed_solution=solution,
            estimated_impact=impact,
            node_ids=list(node_ids),
            score_delta=score_delta,
        )

    def _find_cycles(self, twin: SemanticTwin, kinds: Set[str]) -> List[List[str]]:
        graph: Dict[str, List[str]] = defaultdict(list)
        for e in twin.edges:
            if e.kind in kinds:
                graph[e.source].append(e.target)
        cycles = []
        visited: Set[str] = set()
        stack: Set[str] = set()
        path: List[str] = []

        def dfs(u: str) -> None:
            if len(cycles) >= 10:
                return
            visited.add(u)
            stack.add(u)
            path.append(u)
            for v in graph.get(u, []):
                if v not in visited:
                    dfs(v)
                elif v in stack:
                    if v in path:
                        i = path.index(v)
                        cycles.append(path[i:] + [v])
            path.pop()
            stack.discard(u)

        for n in list(graph.keys())[:200]:
            if n not in visited:
                dfs(n)
        return cycles
