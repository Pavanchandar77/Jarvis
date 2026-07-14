"""Bidirectional sync between ArchitectureSpec and Semantic Twin."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.semantic_twin.models import GenerationManifest, SemanticNode, SemanticTwin, SourceLocation
from services.semantic_twin.ids import stable_node_id, new_edge_id
from services.semantic_twin.schema import EdgeKind, NodeKind

from ..models import ArchitectureEdge, ArchitectureNode, ArchitectureSpec


# Map architecture kinds → twin node kinds
_KIND_MAP = {
    "service": NodeKind.MODULE.value,
    "ui": NodeKind.COMPONENT.value,
    "api": NodeKind.API_ENDPOINT.value,
    "database": NodeKind.TABLE.value,
    "event": NodeKind.EVENT.value,
    "bounded_context": NodeKind.PACKAGE.value,
    "security_boundary": NodeKind.SECURITY_SURFACE.value,
    "dependency": NodeKind.MODULE.value,
    "queue": NodeKind.EVENT.value,
}


class ArchitectureTwinSync:
    """Keep architecture design nodes reflected on the twin graph."""

    def apply_spec_to_twin(
        self,
        twin: SemanticTwin,
        spec: ArchitectureSpec,
    ) -> SemanticTwin:
        """Inject/update architecture nodes as twin nodes without dropping code nodes."""
        node_map = twin.node_map()
        existing_arch = {
            n.id: n for n in twin.nodes
            if (n.attributes or {}).get("architecture_id") == spec.architecture_id
        }

        # Remove stale architecture-only nodes for this spec
        keep_ids = set()
        for an in spec.nodes:
            tid = self._twin_id(spec, an)
            keep_ids.add(tid)
            kind = _KIND_MAP.get(an.kind, NodeKind.MODULE.value)
            if tid in node_map:
                n = node_map[tid]
                n.name = an.name
                n.purpose = an.purpose or n.purpose
                n.description = an.description or n.description
                n.attributes = {
                    **(n.attributes or {}),
                    "architecture_id": spec.architecture_id,
                    "architecture_kind": an.kind,
                    "owner_agent": an.owner_agent,
                    **(an.attributes or {}),
                }
                if an.requirement_ids:
                    n.attributes["requirement_ids"] = list(an.requirement_ids)
            else:
                twin.nodes.append(
                    SemanticNode(
                        id=tid,
                        kind=kind,
                        name=an.name,
                        description=an.description or f"Architecture {an.kind}: {an.name}",
                        purpose=an.purpose or an.name,
                        why_exists="Defined in architecture-first design before/alongside code.",
                        created_by="plugin:architecture_designer",
                        attributes={
                            "architecture_id": spec.architecture_id,
                            "architecture_kind": an.kind,
                            "owner_agent": an.owner_agent,
                            "requirement_ids": list(an.requirement_ids or []),
                            **(an.attributes or {}),
                        },
                        difficulty_score=0.35,
                    )
                )

        # Drop removed arch nodes
        twin.nodes = [
            n for n in twin.nodes
            if (n.attributes or {}).get("architecture_id") != spec.architecture_id
            or n.id in keep_ids
        ]

        # Edges from architecture
        edge_ids = {e.id for e in twin.edges}
        for ae in spec.edges:
            src = self._map_edge_end(spec, ae.source)
            tgt = self._map_edge_end(spec, ae.target)
            if not src or not tgt:
                continue
            kind = self._edge_kind(ae.kind)
            eid = new_edge_id(kind, src, tgt, spec.architecture_id)
            if eid in edge_ids:
                continue
            from services.semantic_twin.models import SemanticEdge
            twin.edges.append(
                SemanticEdge(
                    id=eid,
                    kind=kind,
                    source=src,
                    target=tgt,
                    attributes={"architecture_id": spec.architecture_id, **(ae.attributes or {})},
                )
            )
            edge_ids.add(eid)

        twin.meta.node_count = len(twin.nodes)
        twin.meta.edge_count = len(twin.edges)
        twin.manifest.metadata = dict(twin.manifest.metadata or {})
        twin.manifest.metadata["architecture_id"] = spec.architecture_id
        twin.manifest.metadata["architecture_version"] = spec.version
        return twin

    def extract_spec_from_twin(
        self,
        twin: SemanticTwin,
        *,
        architecture_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> ArchitectureSpec:
        """Derive an ArchitectureSpec snapshot from twin (code → architecture)."""
        aid = architecture_id or f"extracted-{twin.twin_id[:12]}"
        nodes = []
        for n in twin.nodes:
            ak = (n.attributes or {}).get("architecture_kind")
            if ak:
                kind = ak
            elif n.kind == NodeKind.API_ENDPOINT.value:
                kind = "api"
            elif n.kind == NodeKind.COMPONENT.value:
                kind = "ui"
            elif n.kind == NodeKind.TABLE.value:
                kind = "database"
            elif n.kind == NodeKind.EVENT.value:
                kind = "event"
            elif n.kind in (NodeKind.MODULE.value, NodeKind.PACKAGE.value):
                kind = "service"
            else:
                continue
            nodes.append(
                ArchitectureNode(
                    id=n.id,
                    kind=kind,
                    name=n.name,
                    description=n.description,
                    purpose=n.purpose,
                    attributes=dict(n.attributes or {}),
                    owner_agent=(n.attributes or {}).get("owner_agent"),
                    requirement_ids=list((n.attributes or {}).get("requirement_ids") or []),
                )
            )
        id_set = {n.id for n in nodes}
        edges = []
        for e in twin.edges:
            if e.source in id_set and e.target in id_set:
                edges.append(
                    ArchitectureEdge(
                        id=e.id,
                        kind=e.kind,
                        source=e.source,
                        target=e.target,
                        attributes=dict(e.attributes or {}),
                    )
                )
        return ArchitectureSpec(
            architecture_id=aid,
            name=name or twin.meta.application_name or twin.application_id,
            description="Extracted from Semantic Twin",
            nodes=nodes,
            edges=edges,
            twin_id=twin.twin_id,
            project_id=twin.application_id,
            owner=twin.owner,
        )

    def _twin_id(self, spec: ArchitectureSpec, an: ArchitectureNode) -> str:
        return stable_node_id(
            _KIND_MAP.get(an.kind, "module"),
            f"arch:{spec.architecture_id}",
            an.id,
        )

    def _map_edge_end(self, spec: ArchitectureSpec, end_id: str) -> Optional[str]:
        for an in spec.nodes:
            if an.id == end_id:
                return self._twin_id(spec, an)
        return end_id if end_id.startswith("n_") else None

    def _edge_kind(self, kind: str) -> str:
        mapping = {
            "depends_on": EdgeKind.DEPENDS_ON.value,
            "calls": EdgeKind.CALLS.value,
            "publishes": EdgeKind.EMITS.value,
            "subscribes": EdgeKind.HANDLES.value,
            "secures": EdgeKind.RELATED_TO.value,
            "contains": EdgeKind.CONTAINS.value,
            "data_flows_to": EdgeKind.DATA_FLOWS_TO.value,
        }
        return mapping.get(kind, EdgeKind.DEPENDS_ON.value)
