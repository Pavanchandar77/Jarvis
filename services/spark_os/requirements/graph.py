"""Living Requirements Graph — requirements never disappear after generation."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from services.semantic_twin.ids import requirement_node_id, new_edge_id
from services.semantic_twin.models import SemanticEdge, SemanticNode, SemanticTwin
from services.semantic_twin.schema import EdgeKind, NodeKind

from ..models import LivingRequirement

# Trace order for living requirements narrative
TRACE_ORDER = (
    "requirement",
    "prompt",
    "design_decision",
    "component",
    "function",
    "api_endpoint",
    "route",
    "table",
    "test",
    "event",
)


class RequirementGraph:
    """Maintain requirement nodes and satisfaction edges on the Twin."""

    def upsert_requirements(
        self,
        twin: SemanticTwin,
        requirements: List[LivingRequirement],
    ) -> SemanticTwin:
        existing = {n.id: n for n in twin.nodes if n.kind == NodeKind.REQUIREMENT.value}
        for req in requirements:
            rid = requirement_node_id(req.id)
            if rid in existing:
                n = existing[rid]
                n.description = req.text
                n.purpose = req.text
                n.attributes = {
                    **(n.attributes or {}),
                    "requested_by": req.requested_by,
                    "status": req.status,
                    "priority": req.priority,
                    "artifact_ids": list(req.artifact_ids),
                    **(req.attributes or {}),
                }
                n.prompt_id = req.prompt_id or n.prompt_id
            else:
                twin.nodes.append(
                    SemanticNode(
                        id=rid,
                        kind=NodeKind.REQUIREMENT.value,
                        name=f"Requirement: {req.text[:60]}",
                        description=req.text,
                        purpose=req.text,
                        why_exists="Living requirement — retained for full lifecycle traceability.",
                        created_by="plugin:living_requirements",
                        prompt_id=req.prompt_id,
                        attributes={
                            "requested_by": req.requested_by,
                            "status": req.status,
                            "priority": req.priority,
                            "raw_id": req.id,
                            "artifact_ids": list(req.artifact_ids),
                            **(req.attributes or {}),
                        },
                        difficulty_score=0.25,
                    )
                )
            # Link to artifacts
            for aid in req.artifact_ids:
                if any(n.id == aid for n in twin.nodes):
                    eid = new_edge_id(EdgeKind.GENERATED_FROM.value, aid, rid)
                    if not any(e.id == eid for e in twin.edges):
                        twin.edges.append(
                            SemanticEdge(
                                id=eid,
                                kind=EdgeKind.RELATED_TO.value,
                                source=aid,
                                target=rid,
                                attributes={"relation": "satisfies"},
                            )
                        )
        twin.meta.node_count = len(twin.nodes)
        twin.meta.edge_count = len(twin.edges)
        return twin

    def extract_from_twin(self, twin: SemanticTwin) -> List[LivingRequirement]:
        out = []
        for n in twin.nodes:
            if n.kind != NodeKind.REQUIREMENT.value:
                continue
            attrs = n.attributes or {}
            # artifacts that point at this requirement
            arts = list(attrs.get("artifact_ids") or [])
            for e in twin.edges:
                if e.target == n.id and e.source not in arts:
                    arts.append(e.source)
            out.append(
                LivingRequirement(
                    id=str(attrs.get("raw_id") or n.id),
                    text=n.description or n.purpose or n.name,
                    requested_by=str(attrs.get("requested_by") or "user"),
                    prompt_id=n.prompt_id,
                    status=str(attrs.get("status") or "active"),
                    priority=str(attrs.get("priority") or "medium"),
                    artifact_ids=arts,
                    attributes=dict(attrs),
                )
            )
        return out

    def link_artifact(
        self,
        twin: SemanticTwin,
        requirement_id: str,
        artifact_id: str,
    ) -> SemanticTwin:
        rid = requirement_node_id(requirement_id) if not requirement_id.startswith("r_") else requirement_id
        # ensure requirement exists lightly
        if not any(n.id == rid for n in twin.nodes):
            twin.nodes.append(
                SemanticNode(
                    id=rid,
                    kind=NodeKind.REQUIREMENT.value,
                    name=f"Requirement {requirement_id}",
                    description=requirement_id,
                    purpose=requirement_id,
                    why_exists="Linked requirement",
                    created_by="plugin:living_requirements",
                    attributes={"raw_id": requirement_id, "status": "active"},
                )
            )
        eid = new_edge_id("satisfies", artifact_id, rid)
        if not any(e.id == eid for e in twin.edges):
            twin.edges.append(
                SemanticEdge(
                    id=eid,
                    kind=EdgeKind.RELATED_TO.value,
                    source=artifact_id,
                    target=rid,
                    attributes={"relation": "satisfies"},
                )
            )
        for n in twin.nodes:
            if n.id == rid:
                arts = list((n.attributes or {}).get("artifact_ids") or [])
                if artifact_id not in arts:
                    arts.append(artifact_id)
                n.attributes = {**(n.attributes or {}), "artifact_ids": arts}
        return twin

    def from_manifest(self, twin: SemanticTwin) -> SemanticTwin:
        """Seed living requirements from twin.manifest.requirements."""
        reqs = []
        for r in twin.manifest.requirements or []:
            reqs.append(
                LivingRequirement(
                    id=str(r.get("id") or hashlib.sha256(str(r).encode()).hexdigest()[:10]),
                    text=str(r.get("text") or ""),
                    prompt_id=r.get("prompt_id"),
                    requested_by="user",
                )
            )
        # Best-effort: attach code nodes sharing prompt_id
        for req in reqs:
            if not req.prompt_id:
                continue
            for n in twin.nodes:
                if n.prompt_id == req.prompt_id and n.kind not in (
                    NodeKind.REQUIREMENT.value,
                    NodeKind.PROMPT.value,
                ):
                    req.artifact_ids.append(n.id)
        return self.upsert_requirements(twin, reqs)
