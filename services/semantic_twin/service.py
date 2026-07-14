"""SemanticTwinService — public orchestrator for generate / update / query."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .api.facade import TwinApiFacade
from .graph.knowledge_graph import KnowledgeGraph
from .models import GenerationManifest, SemanticTwin
from .pipeline.orchestrator import PipelineOrchestrator
from .storage.incremental import build_delta_patch, compute_file_hashes, dirty_set
from .storage.repository import TwinRepository

logger = logging.getLogger(__name__)


class SemanticTwinService:
    def __init__(
        self,
        storage_dir: str | Path,
        orchestrator: Optional[PipelineOrchestrator] = None,
    ) -> None:
        self.repo = TwinRepository(storage_dir)
        self.orchestrator = orchestrator or PipelineOrchestrator()

    def generate(
        self,
        app_root: str | Path,
        manifest: Optional[GenerationManifest] = None,
        *,
        application_id: Optional[str] = None,
        application_name: Optional[str] = None,
        owner: Optional[str] = None,
        twin_id: Optional[str] = None,
        persist: bool = True,
    ) -> SemanticTwin:
        root = Path(app_root).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"app_root not found: {root}")

        man = manifest or GenerationManifest.empty(
            generation_id=uuid.uuid4().hex,
        )
        twin = self.orchestrator.run(
            root,
            man,
            application_id=application_id or root.name,
            application_name=application_name or root.name,
            owner=owner,
            twin_id=twin_id,
        )
        if persist:
            self.repo.save(twin)
        return twin

    def update(
        self,
        twin_id: str,
        app_root: str | Path,
        *,
        changed_files: Optional[List[str]] = None,
        manifest_delta: Optional[Dict[str, Any]] = None,
        owner: Optional[str] = None,
        force_full: bool = False,
        persist: bool = True,
    ) -> SemanticTwin:
        existing = self.repo.load(twin_id, owner=owner, include_graph=True)
        root = Path(app_root).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"app_root not found: {root}")

        # Merge manifest delta
        manifest = existing.manifest
        if manifest_delta:
            if "prompts" in manifest_delta:
                from .models import PromptRecord
                for p in manifest_delta["prompts"]:
                    manifest.prompts.append(PromptRecord.from_dict(p))
            if "decisions" in manifest_delta:
                from .models import DesignDecision
                for d in manifest_delta["decisions"]:
                    manifest.decisions.append(DesignDecision.from_dict(d))
            if "requirements" in manifest_delta:
                manifest.requirements.extend(manifest_delta["requirements"])
            if "file_prompt_map" in manifest_delta:
                for k, v in manifest_delta["file_prompt_map"].items():
                    manifest.file_prompt_map.setdefault(k, []).extend(v)
            if "tech_stack" in manifest_delta:
                for t in manifest_delta["tech_stack"]:
                    if t not in manifest.tech_stack:
                        manifest.tech_stack.append(t)

        if force_full:
            twin = self.orchestrator.run(
                root,
                manifest,
                application_id=existing.application_id,
                application_name=existing.meta.application_name,
                owner=owner if owner is not None else existing.owner,
                twin_id=existing.twin_id,
                prior_revision=existing.content_revision,
                created_at=existing.created_at,
            )
        else:
            current_hashes = compute_file_hashes(root)
            dirty, deleted = dirty_set(existing, current_hashes, explicit_changed=changed_files)
            # Seed graph with non-dirty nodes
            graph = KnowledgeGraph()
            dirty_all = set(dirty) | set(deleted)
            for n in existing.nodes:
                if n.source_file and n.source_file.replace("\\", "/") in dirty_all:
                    continue
                # Drop provenance on full re-inject; keep code nodes from clean files
                if n.kind in (
                    "prompt", "requirement", "design_decision", "alternative",
                    "concept", "security_surface", "application",
                ):
                    # concepts/prompts re-injected by pipeline; skip stale
                    continue
                graph.add_node(n, replace=True)
            for e in existing.edges:
                if graph.has_node(e.source) and graph.has_node(e.target):
                    try:
                        graph.add_edge(
                            e.kind, e.source, e.target,
                            weight=e.weight,
                            attributes=e.attributes,
                            edge_id=e.id,
                            allow_missing=True,
                        )
                    except Exception:
                        pass
            graph.file_hashes = {
                k: v for k, v in (existing.indexes.file_hashes or {}).items()
                if k not in dirty_all
            }

            twin = self.orchestrator.run(
                root,
                manifest,
                application_id=existing.application_id,
                application_name=existing.meta.application_name,
                owner=owner if owner is not None else existing.owner,
                twin_id=existing.twin_id,
                dirty_files=sorted(dirty) if dirty else [],
                prior_revision=existing.content_revision,
                created_at=existing.created_at,
                existing_graph=graph,
            )
            # If dirty empty and no deletes, still re-run concepts via empty dirty
            # (orchestrator with dirty=[] only parses nothing — ensure hashes update)
            if not dirty and not deleted:
                twin.indexes.file_hashes = current_hashes

        patch = build_delta_patch(existing, twin)
        if persist:
            self.repo.save(twin)
            self.repo.save_delta(twin.twin_id, twin.content_revision, patch)
        return twin

    def load(
        self,
        twin_id: str,
        *,
        owner: Optional[str] = None,
        include_graph: bool = True,
    ) -> SemanticTwin:
        return self.repo.load(twin_id, owner=owner, include_graph=include_graph)

    def list(self, *, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.repo.list(owner=owner)

    def delete(self, twin_id: str, *, owner: Optional[str] = None) -> None:
        self.repo.delete(twin_id, owner=owner)

    def api(self, twin: SemanticTwin, prior: Optional[SemanticTwin] = None) -> TwinApiFacade:
        return TwinApiFacade(twin, prior=prior)

    def api_for(self, twin_id: str, *, owner: Optional[str] = None) -> TwinApiFacade:
        return TwinApiFacade(self.load(twin_id, owner=owner, include_graph=True))
