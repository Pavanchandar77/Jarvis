"""
Integration hooks called from Spark agent loop and tool execution.

These are the only entry points tool_execution / agent_loop should call.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

from .continuous_sync import ContinuousSync
from .extensions import EXTENSIONS
from .manifest_builder import ManifestBuilder
from .project_registry import ProjectRegistry
from .runtime_events import RuntimeEventIngestor
from .session_tracker import SessionTracker, _norm
from .version_timeline import VersionTimeline

logger = logging.getLogger(__name__)

_service_lock = threading.RLock()
_integration = None  # IntegrationService singleton


class IntegrationService:
    """Orchestrates automatic twin lifecycle inside Spark."""

    def __init__(
        self,
        twin_service,
        *,
        registry_path: str,
        projects_dir: str,
        timeline_base: Optional[str] = None,
    ) -> None:
        self.twin_service = twin_service
        self.registry = ProjectRegistry(registry_path)
        self.projects_dir = projects_dir
        os.makedirs(projects_dir, exist_ok=True)
        self.tracker = SessionTracker()
        self.timeline = VersionTimeline(timeline_base or os.path.dirname(registry_path))
        self.runtime = RuntimeEventIngestor(twin_service)
        self.sync = ContinuousSync(
            twin_service,
            on_updated=self._on_sync_updated,
        )
        self.extensions = EXTENSIONS

    def _on_sync_updated(self, twin, paths) -> None:
        try:
            # Load prior is hard; record timeline entry without full prior diff
            self.timeline.record(twin, prior=None, trigger="sync", label=f"sync {len(paths)} file(s)")
            rec = self.registry.by_twin(twin.twin_id)
            if rec:
                self.registry.bind_twin(rec.project_id, twin.twin_id, twin.content_revision)
        except Exception as exc:
            logger.debug("timeline after sync: %s", exc)

    # ── agent turn lifecycle ──────────────────────────────────────────

    def start_turn(
        self,
        *,
        session_id: Optional[str],
        owner: Optional[str],
        workspace: Optional[str],
        model: Optional[str] = None,
        backend: str = "",
        user_prompt: str = "",
        planning_prompt: str = "",
        approved_plan: str = "",
    ):
        ws = workspace or None
        if ws:
            ws = _norm(ws)
        return self.tracker.start(
            session_id=session_id,
            owner=owner,
            workspace=ws,
            model=model,
            backend=backend,
            user_prompt=user_prompt,
            planning_prompt=planning_prompt,
            approved_plan=approved_plan,
        )

    def note_file_write(
        self,
        abs_path: str,
        *,
        session_id: Optional[str] = None,
        owner: Optional[str] = None,
        workspace: Optional[str] = None,
        tool: str = "write_file",
        exit_code: int = 0,
    ) -> None:
        if exit_code not in (0, None):
            return
        if not abs_path or not os.path.isfile(abs_path):
            # write may have just happened — still track path
            if not abs_path:
                return

        gs = self.tracker.get(session_id=session_id, owner=owner, workspace=workspace)
        if gs is None:
            gs = self.tracker.get_for_path(abs_path)
        if gs is None:
            # Lazy-start a session so writes without explicit start still work
            gs = self.start_turn(
                session_id=session_id,
                owner=owner,
                workspace=workspace,
                user_prompt="",
            )
        gs.note_write(abs_path)
        gs.builder.record_tool(
            tool=tool,
            path=abs_path,
            exit_code=exit_code or 0,
        )

        # Continuous sync if project already has a twin
        rec = self.registry.find_root_for_path(abs_path)
        if rec and rec.twin_id and rec.app_root:
            try:
                rel = os.path.relpath(abs_path, rec.app_root).replace("\\", "/")
                if not rel.startswith(".."):
                    self.sync.notify(
                        twin_id=rec.twin_id,
                        app_root=rec.app_root,
                        rel_path=rel,
                        owner=owner or rec.owner,
                    )
            except ValueError:
                pass

    def note_tool_event(
        self,
        *,
        session_id: Optional[str],
        owner: Optional[str],
        workspace: Optional[str],
        tool: str,
        command: str = "",
        exit_code: Optional[int] = None,
        output: str = "",
        round_num: int = 0,
    ) -> None:
        gs = self.tracker.get(session_id=session_id, owner=owner, workspace=workspace)
        if not gs:
            return
        gs.builder.record_tool(
            tool=tool,
            command=command,
            exit_code=exit_code,
            output=output,
            round_num=round_num,
        )
        if tool == "update_plan":
            gs.builder._ingest_plan_update(command)

    def finalize_turn(
        self,
        *,
        session_id: Optional[str],
        owner: Optional[str],
        workspace: Optional[str],
        model: Optional[str] = None,
        endpoint_url: str = "",
        tool_events: Optional[List[Dict[str, Any]]] = None,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        After agent turn ends: if files were written, generate/update twin
        and register the project automatically.
        """
        gs = self.tracker.get(session_id=session_id, owner=owner, workspace=workspace)
        if not gs:
            return None
        if gs.finalized and not force:
            return None

        # Merge tool_events from agent loop for completeness
        for ev in tool_events or []:
            gs.builder.record_tool(
                tool=ev.get("tool") or "",
                command=ev.get("command") or "",
                exit_code=ev.get("exit_code"),
                output=str(ev.get("output") or "")[:400],
                round_num=int(ev.get("round") or 0),
            )
            if (ev.get("tool") in ("write_file", "edit_file")) and ev.get("command"):
                # command often starts with path
                raw = (ev.get("command") or "").split("\n", 1)[0].strip()
                if raw and os.path.isabs(raw):
                    gs.note_write(raw)

        if not gs.written_paths and not force:
            return None

        app_root = gs.infer_app_root()
        if not app_root or not os.path.isdir(app_root):
            logger.info("Semantic Twin finalize: no valid app_root (files=%d)", len(gs.written_paths))
            return None

        # Recompute relative dirty paths against inferred root
        dirty = []
        for p in gs.written_paths:
            try:
                rel = os.path.relpath(p, app_root).replace("\\", "/")
                if not rel.startswith(".."):
                    dirty.append(rel)
                    gs.builder.files_written.setdefault(rel, gs.builder.prompts[0].id if gs.builder.prompts else "prompt-user")
                    gs.builder.file_ownership.setdefault(rel, "agent")
            except ValueError:
                continue

        if model:
            gs.builder.model = model
        if endpoint_url:
            gs.builder.backend = endpoint_url
            gs.builder.set_runtime_metadata(endpoint_url=endpoint_url)

        manifest = gs.builder.build()
        project_id = gs.project_id or self.tracker.project_id_for_root(app_root)
        name = os.path.basename(app_root.rstrip("\\/")) or project_id

        existing = self.registry.by_root(app_root)
        twin_id = (existing.twin_id if existing else None) or gs.twin_id

        ctx = {
            "app_root": app_root,
            "project_id": project_id,
            "session_id": session_id,
            "owner": owner,
            "manifest": manifest,
        }
        prior = None
        try:
            if twin_id and self.twin_service.repo.exists(twin_id):
                try:
                    prior = self.twin_service.load(twin_id, owner=owner, include_graph=True)
                except Exception:
                    prior = None
                self.extensions.fire_before_update(twin_id, ctx)
                twin = self.twin_service.update(
                    twin_id,
                    app_root,
                    changed_files=dirty or None,
                    manifest_delta={
                        "prompts": [p.to_dict() for p in manifest.prompts],
                        "decisions": [d.to_dict() for d in manifest.decisions],
                        "requirements": manifest.requirements,
                        "file_prompt_map": manifest.file_prompt_map,
                        "tech_stack": manifest.tech_stack,
                    },
                    owner=owner,
                    force_full=not dirty,
                    persist=True,
                )
                # Overlay expanded manifest fields
                twin.manifest = manifest
                twin.manifest.generation_id = manifest.generation_id
                self.twin_service.repo.save(twin)
                self.extensions.fire_after_update(twin, ctx)
                trigger = "update"
            else:
                self.extensions.fire_before_generate(ctx)
                twin = self.twin_service.generate(
                    app_root,
                    manifest,
                    application_id=project_id,
                    application_name=name,
                    owner=owner,
                    twin_id=twin_id,
                    persist=True,
                )
                self.extensions.fire_after_generate(twin, ctx)
                trigger = "generate"
        except Exception as exc:
            logger.exception("Semantic Twin auto-generation failed: %s", exc)
            return {"ok": False, "error": str(exc), "app_root": app_root}

        self.timeline.record(twin, prior=prior, trigger=trigger, label=f"{trigger} {name}")
        self.registry.register(
            project_id=project_id,
            name=name,
            app_root=app_root,
            twin_id=twin.twin_id,
            owner=owner,
            session_id=session_id,
            revision=twin.content_revision,
            metadata={
                "model": model,
                "generation_id": manifest.generation_id,
            },
        )
        gs.twin_id = twin.twin_id
        gs.project_id = project_id
        gs.finalized = True

        logger.info(
            "Semantic Twin auto-%s project=%s twin=%s rev=%s nodes=%s",
            trigger,
            project_id,
            twin.twin_id,
            twin.content_revision,
            twin.meta.node_count,
        )
        return {
            "ok": True,
            "trigger": trigger,
            "project_id": project_id,
            "twin_id": twin.twin_id,
            "content_revision": twin.content_revision,
            "app_root": app_root,
            "node_count": twin.meta.node_count,
            "edge_count": twin.meta.edge_count,
            "name": name,
        }


def set_integration_service(svc: IntegrationService) -> None:
    global _integration
    with _service_lock:
        _integration = svc


def get_integration_service() -> Optional[IntegrationService]:
    return _integration


def on_agent_turn_start(**kwargs) -> None:
    svc = get_integration_service()
    if not svc:
        return
    try:
        svc.start_turn(**kwargs)
    except Exception as exc:
        logger.debug("on_agent_turn_start: %s", exc)


def on_file_written(
    abs_path: str,
    *,
    session_id: Optional[str] = None,
    owner: Optional[str] = None,
    workspace: Optional[str] = None,
    tool: str = "write_file",
    exit_code: int = 0,
) -> None:
    svc = get_integration_service()
    if not svc:
        return
    try:
        svc.note_file_write(
            abs_path,
            session_id=session_id,
            owner=owner,
            workspace=workspace,
            tool=tool,
            exit_code=exit_code,
        )
    except Exception as exc:
        logger.debug("on_file_written: %s", exc)


def on_agent_turn_end(**kwargs) -> Optional[Dict[str, Any]]:
    svc = get_integration_service()
    if not svc:
        return None
    try:
        return svc.finalize_turn(**kwargs)
    except Exception as exc:
        logger.warning("on_agent_turn_end: %s", exc)
        return None


def on_runtime_event(twin_id: str, event: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    svc = get_integration_service()
    if not svc:
        return {"ok": False, "error": "integration not initialized"}
    return svc.runtime.ingest(twin_id, event, **kwargs)
