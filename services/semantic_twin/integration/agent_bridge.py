"""Agent tool bridge — reason over the Semantic Twin instead of re-parsing repos."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def do_semantic_twin(content: str, owner: Optional[str] = None) -> Dict[str, Any]:
    """
    Agent tool: semantic_twin

    Args (JSON):
      {
        "action": "search|explain|trace_execution|trace_dependency|find_concept|
                   simulate|architecture|status|list_projects|quiz|tutorial|timeline",
        "twin_id": "...",          # optional if project_id or path provided
        "project_id": "...",
        "q": "query",
        "node_id": "...",
        "mode": "beginner|...",
        "direction": "downstream|upstream|both",
        "proposal": "...",
        "limit": 20
      }
    """
    from .hooks import get_integration_service

    svc = get_integration_service()
    if not svc:
        return {"error": "Semantic Twin integration is not initialized", "exit_code": 1}

    try:
        args = json.loads(content) if content.strip().startswith("{") else {"action": "status", "q": content}
    except json.JSONDecodeError:
        args = {"action": "search", "q": content}

    action = (args.get("action") or "search").strip().lower()
    twin_id = args.get("twin_id")
    project_id = args.get("project_id")

    # Resolve twin_id from project registry
    if not twin_id and project_id:
        rec = svc.registry.get(project_id)
        if rec:
            twin_id = rec.twin_id
    if not twin_id and args.get("path"):
        rec = svc.registry.find_root_for_path(args["path"])
        if rec:
            twin_id = rec.twin_id
            project_id = rec.project_id

    if action == "list_projects":
        rows = svc.registry.list(owner=owner)
        return {
            "output": json.dumps([
                {
                    "project_id": r.project_id,
                    "name": r.name,
                    "twin_id": r.twin_id,
                    "app_root": r.app_root,
                    "revision": r.last_revision,
                }
                for r in rows[:50]
            ], indent=2),
            "exit_code": 0,
            "projects": [r.to_dict() for r in rows[:50]],
        }

    if action == "status":
        rows = svc.registry.list(owner=owner)
        return {
            "output": f"{len(rows)} registered project(s) with Semantic Twins.",
            "exit_code": 0,
            "count": len(rows),
            "projects": [
                {"project_id": r.project_id, "name": r.name, "twin_id": r.twin_id}
                for r in rows[:20]
            ],
        }

    if not twin_id:
        # Fall back to most recent project for this owner
        rows = svc.registry.list(owner=owner)
        if rows and rows[0].twin_id:
            twin_id = rows[0].twin_id
            project_id = rows[0].project_id
        else:
            return {
                "error": (
                    "No twin_id/project_id provided and no registered projects. "
                    "Generate an app (write files in agent mode) first, or pass twin_id."
                ),
                "exit_code": 1,
            }

    try:
        twin = svc.twin_service.load(twin_id, owner=owner, include_graph=True)
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        return {"error": f"Twin not available: {exc}", "exit_code": 1}

    api = svc.twin_service.api(twin)
    limit = int(args.get("limit") or 20)

    try:
        if action == "search":
            result = api.search(args.get("q") or "", kinds=args.get("kinds"), limit=limit)
        elif action == "explain":
            node_id = args.get("node_id")
            if not node_id:
                hits = api.search(args.get("q") or "", limit=1)
                if not hits["hits"]:
                    return {"error": "No node matched query", "exit_code": 1}
                node_id = hits["hits"][0]["node_id"]
            result = api.explain(node_id, mode=args.get("mode") or "senior")
        elif action == "trace_execution":
            node_id = args.get("node_id") or args.get("entry_id")
            if not node_id:
                return {"error": "node_id required", "exit_code": 1}
            result = api.trace_execution(node_id, max_depth=int(args.get("max_depth") or 20))
        elif action == "trace_dependency":
            node_id = args.get("node_id")
            if not node_id:
                return {"error": "node_id required", "exit_code": 1}
            result = api.trace_dependency(
                node_id,
                direction=args.get("direction") or "downstream",
                max_depth=int(args.get("max_depth") or 10),
            )
        elif action in ("find_concept", "concept"):
            result = api.find_concept(args.get("q") or "", limit=limit)
        elif action == "simulate":
            result = api.simulate_modification(
                args.get("proposal") or args.get("q") or "",
                focus_node_id=args.get("node_id"),
            )
        elif action == "architecture":
            apps = [n for n in twin.nodes if n.kind == "application"]
            modules = [n for n in twin.nodes if n.kind == "module"]
            apis = [n for n in twin.nodes if n.kind == "api_endpoint"]
            components = [n for n in twin.nodes if n.kind == "component"]
            decisions = [n for n in twin.nodes if n.kind == "design_decision"]
            result = {
                "twin_id": twin.twin_id,
                "application": apps[0].to_dict() if apps else None,
                "summary": twin.meta.to_dict(),
                "modules": [{"id": n.id, "name": n.name, "file": n.source_file} for n in modules[:40]],
                "api_endpoints": [{"id": n.id, "name": n.name} for n in apis[:40]],
                "components": [{"id": n.id, "name": n.name} for n in components[:40]],
                "decisions": [{"id": n.id, "name": n.name, "purpose": n.purpose} for n in decisions[:20]],
                "tech_stack": twin.meta.tech_stack,
                "entrypoints": twin.meta.entrypoints,
            }
        elif action == "quiz":
            result = api.generate_quiz(count=int(args.get("count") or 5))
        elif action == "tutorial":
            result = api.generate_tutorial(
                focus_node_id=args.get("node_id"),
                max_steps=int(args.get("max_steps") or 8),
            )
        elif action == "timeline":
            result = {
                "twin_id": twin_id,
                "versions": svc.timeline.list_versions(twin_id),
            }
        else:
            return {
                "error": f"Unknown action '{action}'. Use search|explain|trace_execution|"
                         "trace_dependency|find_concept|simulate|architecture|status|"
                         "list_projects|quiz|tutorial|timeline",
                "exit_code": 1,
            }
    except KeyError as exc:
        return {"error": f"Node not found: {exc}", "exit_code": 1}
    except Exception as exc:
        logger.exception("semantic_twin tool failed")
        return {"error": str(exc), "exit_code": 1}

    text = json.dumps(result, indent=2, ensure_ascii=False)
    if len(text) > 12000:
        text = text[:12000] + "\n... [truncated]"
    return {
        "output": text,
        "exit_code": 0,
        "twin_id": twin_id,
        "project_id": project_id,
        "action": action,
        "result": result,
    }
