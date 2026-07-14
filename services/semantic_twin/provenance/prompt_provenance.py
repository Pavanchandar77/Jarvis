"""Inject prompt and requirement nodes into the graph."""

from __future__ import annotations

from ..ids import prompt_node_id, requirement_node_id
from ..models import SemanticNode, SourceLocation
from ..schema import EdgeKind, NodeKind
from ..pipeline.context import PipelineContext


def inject_prompt_provenance(ctx: PipelineContext) -> None:
    g = ctx.graph
    app_id = ctx.extras.get("app_node_id")
    prompt_ids = {}

    for p in ctx.manifest.prompts or []:
        nid = prompt_node_id(p.id)
        prompt_ids[p.id] = nid
        g.add_node(
            SemanticNode(
                id=nid,
                kind=NodeKind.PROMPT.value,
                name=f"Prompt #{p.ordinal}: {p.role}",
                description=(p.text_ref or "")[:500],
                purpose="Captures the generative prompt that shaped the application.",
                why_exists="Prompt provenance explains why code was generated.",
                created_by="ai",
                prompt_id=p.id,
                attributes={
                    "ordinal": p.ordinal,
                    "role": p.role,
                    "model": p.model,
                    "text_ref": p.text_ref,
                },
                difficulty_score=0.2,
            ),
            replace=True,
        )
        if app_id:
            g.add_edge(EdgeKind.CONTAINS.value, app_id, nid)

    for req in ctx.manifest.requirements or []:
        rid = req.get("id") or req.get("text", "")[:32]
        nid = requirement_node_id(str(rid))
        g.add_node(
            SemanticNode(
                id=nid,
                kind=NodeKind.REQUIREMENT.value,
                name=f"Requirement: {(req.get('text') or '')[:60]}",
                description=req.get("text") or "",
                purpose="A product requirement extracted from generation.",
                why_exists="Requirements bridge prompts and design decisions.",
                created_by="ai",
                prompt_id=req.get("prompt_id"),
                attributes={"text": req.get("text"), "raw_id": rid},
                difficulty_score=0.25,
            ),
            replace=True,
        )
        if app_id:
            g.add_edge(EdgeKind.CONTAINS.value, app_id, nid)
        pid = req.get("prompt_id")
        if pid and pid in prompt_ids:
            g.add_edge(EdgeKind.GENERATED_FROM.value, nid, prompt_ids[pid])

    # Link modules/code to prompts via file_prompt_map
    for path, pids in (ctx.manifest.file_prompt_map or {}).items():
        for node in g.nodes_for_file(path.replace("\\", "/")):
            for pid in pids:
                if pid in prompt_ids:
                    g.add_edge(EdgeKind.GENERATED_FROM.value, node.id, prompt_ids[pid])
                    if not node.prompt_id:
                        node.prompt_id = pid
