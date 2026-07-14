"""Quiz and tutorial generation from the twin graph."""

from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Optional

from ..models import SemanticTwin
from ..schema import NodeKind, ViewingMode


def generate_quiz(
    twin: SemanticTwin,
    *,
    node_ids: Optional[List[str]] = None,
    difficulty: Optional[float] = None,
    count: int = 5,
) -> Dict[str, Any]:
    nodes = twin.nodes
    if node_ids:
        idset = set(node_ids)
        nodes = [n for n in nodes if n.id in idset]
    # Prefer code + concept nodes
    pool = [
        n for n in nodes
        if n.kind in (
            NodeKind.FUNCTION.value,
            NodeKind.COMPONENT.value,
            NodeKind.API_ENDPOINT.value,
            NodeKind.CONCEPT.value,
            NodeKind.ROUTE.value,
            NodeKind.CLASS.value,
        )
    ]
    if difficulty is not None:
        pool = [n for n in pool if abs(n.difficulty_score - difficulty) < 0.35] or pool
    if not pool:
        pool = list(twin.nodes)[:10]

    rng = random.Random(twin.content_hash or twin.twin_id)
    sample = pool[:] if len(pool) <= count else rng.sample(pool, count)
    questions = []
    for i, n in enumerate(sample):
        wrong = [m.name for m in pool if m.id != n.id]
        rng.shuffle(wrong)
        choices = [n.purpose or n.description or n.name] + [
            (m.purpose or m.description or m.name)
            for m in pool
            if m.id != n.id
        ][:3]
        # Rebuild choices with names for clarity
        choices = [f"It { (n.purpose or n.description or 'does work').lower() }"]
        distractors = [
            f"It {(m.purpose or m.description or m.name).lower()}"
            for m in pool
            if m.id != n.id
        ][:3]
        while len(distractors) < 3:
            distractors.append(f"It is unrelated infrastructure ({len(distractors)})")
        choices = [choices[0]] + distractors
        rng.shuffle(choices)
        correct = choices.index(
            f"It { (n.purpose or n.description or 'does work').lower() }"
        )
        qid = hashlib.sha256(f"{twin.twin_id}:{n.id}:{i}".encode()).hexdigest()[:12]
        questions.append({
            "id": qid,
            "prompt": f"What is the purpose of `{n.name}`?",
            "choices": choices,
            "correct_index": correct,
            "explanation": n.purpose or n.description or n.why_exists,
            "node_ids": [n.id],
            "difficulty": n.difficulty_score,
        })

    return {
        "id": hashlib.sha256(f"quiz:{twin.twin_id}:{twin.content_revision}".encode()).hexdigest()[:16],
        "title": f"Quiz: {twin.meta.application_name}",
        "questions": questions,
    }


def generate_tutorial(
    twin: SemanticTwin,
    *,
    focus_node_id: Optional[str] = None,
    max_steps: int = 8,
) -> Dict[str, Any]:
    node_map = twin.node_map()
    steps: List[Dict[str, Any]] = []

    # Start from application or focus
    start = None
    if focus_node_id and focus_node_id in node_map:
        start = node_map[focus_node_id]
    else:
        apps = [n for n in twin.nodes if n.kind == NodeKind.APPLICATION.value]
        start = apps[0] if apps else (twin.nodes[0] if twin.nodes else None)

    if not start:
        return {
            "id": "empty",
            "title": "Empty tutorial",
            "steps": [],
        }

    ordered = [start]
    # Walk related concepts and dependencies
    seen = {start.id}
    queue = list(start.dependencies) + list(start.related_concepts)
    for nid in list(twin.indexes.adjacency_out.get(start.id, [])):
        e = twin.edge_map().get(nid)
        if e and e.target not in seen:
            queue.append(e.target)

    for nid in queue:
        if len(ordered) >= max_steps:
            break
        n = node_map.get(nid)
        if n and n.id not in seen:
            seen.add(n.id)
            ordered.append(n)

    # Pad with interesting kinds
    if len(ordered) < max_steps:
        for n in twin.nodes:
            if n.id in seen:
                continue
            if n.kind in (
                NodeKind.COMPONENT.value,
                NodeKind.API_ENDPOINT.value,
                NodeKind.CONCEPT.value,
                NodeKind.DESIGN_DECISION.value,
            ):
                ordered.append(n)
                seen.add(n.id)
            if len(ordered) >= max_steps:
                break

    modes = [
        ViewingMode.BEGINNER.value,
        ViewingMode.INTERMEDIATE.value,
        ViewingMode.AI_REASONING.value,
        ViewingMode.RUNTIME.value,
        ViewingMode.SENIOR.value,
    ]
    for i, n in enumerate(ordered[:max_steps]):
        mode = modes[i % len(modes)]
        view = (n.views or {}).get(mode)
        body = view.body if view else (n.purpose or n.description)
        steps.append({
            "id": f"step-{i}-{n.id[:8]}",
            "title": n.name,
            "body": body,
            "node_ids": [n.id],
            "mode": mode,
        })

    return {
        "id": hashlib.sha256(f"tutorial:{twin.twin_id}:{start.id}".encode()).hexdigest()[:16],
        "title": f"Tour: {start.name}",
        "steps": steps,
    }
