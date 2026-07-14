"""Concept Extractor — CS concepts, patterns, difficulty, learning resources."""

from __future__ import annotations

import time
from typing import Dict, List, Tuple

from ..ids import concept_id
from ..models import LearningResource, SemanticNode, SuggestedImprovement
from ..schema import EdgeKind, NodeKind
from .context import PipelineContext

# (slug, title, category, keywords, resource_url)
_CONCEPT_CATALOG: List[Tuple[str, str, str, List[str], str]] = [
    ("async-await", "Async / Await", "concurrency", ["async", "await", "asyncio"], "https://docs.python.org/3/library/asyncio.html"),
    ("rest-api", "REST API", "networking", ["api_endpoint", "route", "get", "post", "router"], "https://restfulapi.net/"),
    ("react-components", "React Components", "ui", ["component", "jsx", "tsx", "react"], "https://react.dev/learn"),
    ("hooks", "Hooks", "ui", ["hook", "usestate", "useeffect", "use_"], "https://react.dev/reference/react"),
    ("state-management", "State Management", "architecture", ["state", "store", "atom", "usestate"], "https://react.dev/learn/managing-state"),
    ("dependency-injection", "Dependency Injection", "architecture", ["inject", "depends", "provider"], ""),
    ("authentication", "Authentication", "security", ["auth", "login", "token", "jwt", "password"], "https://owasp.org/www-project-authentication-cheat-sheet/"),
    ("database", "Database Access", "data", ["table", "sql", "query", "orm", "migration"], ""),
    ("routing", "Routing", "networking", ["route", "path", "router", "navigate"], ""),
    ("testing", "Testing", "quality", ["test", "pytest", "jest", "assert"], "https://docs.pytest.org/"),
    ("error-handling", "Error Handling", "reliability", ["except", "try", "error", "raise", "catch"], ""),
    ("caching", "Caching", "performance", ["cache", "memo", "lru"], ""),
]


class ConceptExtractorStage:
    name = "concept_extractor"

    def run(self, ctx: PipelineContext) -> None:
        t0 = time.perf_counter()
        g = ctx.graph
        concept_nodes: Dict[str, str] = {}  # slug → id

        for slug, title, category, keywords, url in _CONCEPT_CATALOG:
            cid = concept_id(slug)
            resources = []
            if url:
                resources.append(
                    LearningResource(title=f"Learn {title}", url=url, kind="docs", difficulty=0.4)
                )
            node = SemanticNode(
                id=cid,
                kind=NodeKind.CONCEPT.value,
                name=title,
                description=f"Concept: {title}",
                purpose=f"Explains the idea of {title} as used in this application.",
                why_exists="Concepts orient learners and power findConcept / tutorials.",
                created_by="plugin:concept_extractor",
                difficulty_score=0.4,
                learning_resources=resources,
                attributes={"slug": slug, "category": category, "keywords": keywords},
            )
            # Only add concepts that actually match something
            matched = False
            for n in g.nodes():
                if self._matches(n, keywords):
                    matched = True
                    break
            if matched:
                g.add_node(node, replace=True)
                concept_nodes[slug] = cid

        # Link code nodes → concepts
        for n in g.nodes():
            if n.kind in (NodeKind.CONCEPT.value, NodeKind.PROMPT.value, NodeKind.APPLICATION.value):
                continue
            for slug, cid in concept_nodes.items():
                keywords = next(k for s, _, _, k, _ in _CONCEPT_CATALOG if s == slug)
                if self._matches(n, keywords):
                    if cid not in n.related_concepts:
                        n.related_concepts.append(cid)
                    g.add_edge(EdgeKind.RELATED_TO.value, n.id, cid)
                    g.add_edge(EdgeKind.ILLUSTRATES.value, cid, n.id)

        # Suggested improvements (lightweight heuristics)
        for n in g.nodes():
            if n.kind in (NodeKind.FUNCTION.value, NodeKind.METHOD.value, NodeKind.COMPONENT.value):
                fan_out = len(n.dependencies)
                if fan_out > 8:
                    n.suggested_improvements.append(
                        SuggestedImprovement(
                            summary="High fan-out — consider facade or decomposition",
                            rationale=f"{n.name} depends on {fan_out} symbols.",
                            impact="medium",
                            effort="medium",
                            category="maintainability",
                        )
                    )
                if (n.attributes or {}).get("async") and "timeout" not in (n.signature if hasattr(n, "signature") else ""):
                    sig = (n.attributes or {}).get("signature", "")
                    if "timeout" not in sig.lower():
                        n.suggested_improvements.append(
                            SuggestedImprovement(
                                summary="Add timeouts around async I/O",
                                rationale="Async functions without timeouts can hang under failure.",
                                impact="high",
                                effort="low",
                                category="reliability" if False else "performance",
                            )
                        )
                if n.kind == NodeKind.API_ENDPOINT.value or "auth" in n.name.lower():
                    n.suggested_improvements.append(
                        SuggestedImprovement(
                            summary="Review authorization on this surface",
                            rationale="Network-facing or auth-related symbols need explicit access control.",
                            impact="high",
                            effort="medium",
                            category="security",
                        )
                    )

        # Security / perf surface nodes for notable cases
        for n in g.nodes_by_kind(NodeKind.API_ENDPOINT.value):
            sid = concept_id(f"sec-{n.id}")  # stable-ish
            # Use stable_node_id style via concept_id is ok for surfaces
            from ..ids import stable_node_id
            sec_id = stable_node_id(NodeKind.SECURITY_SURFACE.value, n.source_file, n.name)
            g.add_node(
                SemanticNode(
                    id=sec_id,
                    kind=NodeKind.SECURITY_SURFACE.value,
                    name=f"Surface: {n.name}",
                    description="Attack surface derived from API endpoint.",
                    purpose="Tracks security considerations for this endpoint.",
                    why_exists="Security viewing mode and audits.",
                    created_by="plugin:concept_extractor",
                    source_file=n.source_file,
                    attributes={"severity": "medium", "related": n.id},
                    difficulty_score=0.55,
                ),
                replace=True,
            )
            g.add_edge(EdgeKind.RELATED_TO.value, n.id, sec_id)

        ctx.stage_metrics[self.name] = time.perf_counter() - t0

    def _matches(self, node: SemanticNode, keywords: List[str]) -> bool:
        blob = " ".join([
            node.name or "",
            node.kind or "",
            node.description or "",
            str((node.attributes or {}).get("signature", "")),
            str((node.attributes or {}).get("path_pattern", "")),
            str((node.attributes or {}).get("framework", "")),
        ]).lower()
        return any(k.lower() in blob for k in keywords)
