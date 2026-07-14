"""Organizational Knowledge Memory — learn across projects for future generations."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.semantic_twin.models import SemanticTwin

from ..models import KnowledgePattern
from ..storage.store import append_jsonl, ensure_dir, read_jsonl


class OrgKnowledgeMemory:
    """
    Continuous learning store:
    architectures, patterns, anti-patterns, refactors, bugs, incidents,
    security lessons, performance optimizations.
    """

    def __init__(self, store_dir: str | Path) -> None:
        self.store = ensure_dir(store_dir)
        self.patterns_path = self.store / "patterns.jsonl"
        self.anti_path = self.store / "anti_patterns.jsonl"
        self.incidents_path = self.store / "incidents.jsonl"

    def learn_from_twin(
        self,
        twin: SemanticTwin,
        *,
        review: Optional[Dict[str, Any]] = None,
    ) -> List[KnowledgePattern]:
        learned: List[KnowledgePattern] = []
        # Patterns from tech stack + structure
        if twin.meta.tech_stack:
            p = KnowledgePattern(
                id=self._id("arch", ",".join(twin.meta.tech_stack)),
                kind="architecture",
                title=f"Stack: {', '.join(twin.meta.tech_stack[:6])}",
                summary=f"Used in {twin.meta.application_name} with {twin.meta.node_count} nodes.",
                tags=list(twin.meta.tech_stack),
                evidence={"twin_id": twin.twin_id, "languages": twin.meta.languages},
                score=0.6,
                source_project=twin.application_id,
            )
            self._append(self.patterns_path, p)
            learned.append(p)

        # Successful structure: presence of tests + apis
        tests = sum(1 for n in twin.nodes if n.kind == "test")
        apis = sum(1 for n in twin.nodes if n.kind == "api_endpoint")
        if tests > 0 and apis > 0:
            p = KnowledgePattern(
                id=self._id("pattern", f"tested-api-{twin.application_id}"),
                kind="pattern",
                title="API surface with tests",
                summary="Project pairs HTTP endpoints with test nodes.",
                tags=["api", "testing"],
                evidence={"tests": tests, "apis": apis},
                score=0.7,
                source_project=twin.application_id,
            )
            self._append(self.patterns_path, p)
            learned.append(p)

        # Anti-patterns from review findings
        if review:
            for f in review.get("findings") or []:
                if f.get("severity") in ("critical", "high"):
                    p = KnowledgePattern(
                        id=self._id("anti", f.get("title", "")),
                        kind="anti_pattern",
                        title=f.get("title") or "Anti-pattern",
                        summary=f.get("explanation") or "",
                        tags=[f.get("category") or "architecture"],
                        evidence={"severity": f.get("severity"), "solution": f.get("proposed_solution")},
                        score=0.8,
                        source_project=twin.application_id,
                    )
                    self._append(self.anti_path, p)
                    learned.append(p)

        # Security lessons
        for n in twin.nodes:
            if n.kind == "security_surface":
                p = KnowledgePattern(
                    id=self._id("sec", n.name),
                    kind="security",
                    title=f"Security surface: {n.name}",
                    summary=n.purpose or n.description,
                    tags=["security"],
                    evidence={"node_id": n.id},
                    score=0.65,
                    source_project=twin.application_id,
                )
                self._append(self.patterns_path, p)
                learned.append(p)
                if len(learned) > 20:
                    break

        # Design decisions as reusable rationale
        for n in twin.nodes:
            if n.kind == "design_decision":
                p = KnowledgePattern(
                    id=self._id("dec", n.name),
                    kind="pattern",
                    title=n.name,
                    summary=n.description or n.purpose,
                    tags=["decision"],
                    evidence={"trade_offs": (n.attributes or {}).get("trade_offs")},
                    score=0.55,
                    source_project=twin.application_id,
                )
                self._append(self.patterns_path, p)
                learned.append(p)
                if len([x for x in learned if x.kind == "pattern"]) > 15:
                    break

        return learned

    def record_incident(
        self,
        title: str,
        summary: str,
        *,
        tags: Optional[List[str]] = None,
        project_id: Optional[str] = None,
    ) -> KnowledgePattern:
        p = KnowledgePattern(
            id=self._id("inc", title),
            kind="incident",
            title=title,
            summary=summary,
            tags=list(tags or ["incident"]),
            score=0.9,
            source_project=project_id,
        )
        self._append(self.incidents_path, p)
        return p

    def retrieve(
        self,
        query: str,
        *,
        kinds: Optional[List[str]] = None,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        q = (query or "").lower()
        tokens = [t for t in re.split(r"\W+", q) if t]
        kind_set = set(kinds or [])
        rows: List[KnowledgePattern] = []
        for path in (self.patterns_path, self.anti_path, self.incidents_path):
            for raw in read_jsonl(path, limit=5000):
                try:
                    p = KnowledgePattern.from_dict(raw)
                except Exception:
                    continue
                if kind_set and p.kind not in kind_set:
                    continue
                rows.append(p)

        scored = []
        for p in rows:
            blob = f"{p.title} {p.summary} {' '.join(p.tags)}".lower()
            score = p.score
            if tokens:
                score += sum(1.0 if t in blob else 0.0 for t in tokens)
            else:
                score += 0.1
            scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p.to_dict() for _, p in scored[:limit]]

    def inject_for_generation(self, query: str, limit: int = 8) -> Dict[str, Any]:
        """Retrieve knowledge to inject into GenerationManifest.metadata."""
        hits = self.retrieve(query, limit=limit)
        return {
            "org_memory_hits": hits,
            "guidance": [
                h.get("title") + ": " + (h.get("summary") or "")[:160]
                for h in hits
            ],
        }

    def _append(self, path: Path, p: KnowledgePattern) -> None:
        append_jsonl(path, p.to_dict())

    def _id(self, kind: str, text: str) -> str:
        return kind + "_" + hashlib.sha256(text.encode()).hexdigest()[:14]
