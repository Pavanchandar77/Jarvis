"""Architecture-first designer — architecture is the primary artifact."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import ArchitectureEdge, ArchitectureNode, ArchitectureSpec
from ..storage.store import ensure_dir, read_json, write_json


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _id(prefix: str, name: str) -> str:
    h = hashlib.sha256(f"{prefix}:{name}".encode()).hexdigest()[:12]
    return f"{prefix}_{h}"


class ArchitectureDesigner:
    """Create and mutate ArchitectureSpec before/without code."""

    def __init__(self, store_dir: str | Path) -> None:
        self.store = ensure_dir(store_dir)

    def create(
        self,
        name: str,
        *,
        description: str = "",
        owner: Optional[str] = None,
        project_id: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
    ) -> ArchitectureSpec:
        aid = uuid.uuid4().hex
        spec = ArchitectureSpec(
            architecture_id=aid,
            name=name,
            description=description,
            owner=owner,
            project_id=project_id,
        )
        for n in nodes or []:
            node = ArchitectureNode.from_dict({
                **n,
                "id": n.get("id") or _id(n.get("kind", "node"), n.get("name", "x")),
            })
            spec.nodes.append(node)
        for e in edges or []:
            edge = ArchitectureEdge.from_dict({
                **e,
                "id": e.get("id") or _id("edge", f"{e.get('source')}-{e.get('target')}"),
            })
            spec.edges.append(edge)
        self.save(spec)
        return spec

    def add_service(self, spec: ArchitectureSpec, name: str, **attrs) -> ArchitectureNode:
        node = ArchitectureNode(
            id=_id("svc", name),
            kind="service",
            name=name,
            purpose=attrs.pop("purpose", f"Service {name}"),
            description=attrs.pop("description", ""),
            attributes=attrs,
        )
        spec.nodes.append(node)
        spec.updated_at = _utcnow()
        spec.version += 1
        self.save(spec)
        return node

    def add_api(
        self,
        spec: ArchitectureSpec,
        name: str,
        method: str = "GET",
        path: str = "/",
        service_id: Optional[str] = None,
    ) -> ArchitectureNode:
        node = ArchitectureNode(
            id=_id("api", f"{method}:{path}:{name}"),
            kind="api",
            name=name,
            purpose=f"{method} {path}",
            attributes={"method": method, "path": path},
        )
        spec.nodes.append(node)
        if service_id:
            spec.edges.append(
                ArchitectureEdge(
                    id=_id("edge", f"{service_id}->{node.id}"),
                    kind="contains",
                    source=service_id,
                    target=node.id,
                )
            )
        spec.updated_at = _utcnow()
        spec.version += 1
        self.save(spec)
        return node

    def add_database(self, spec: ArchitectureSpec, name: str, engine: str = "postgres") -> ArchitectureNode:
        node = ArchitectureNode(
            id=_id("db", name),
            kind="database",
            name=name,
            purpose=f"{engine} datastore",
            attributes={"engine": engine},
        )
        spec.nodes.append(node)
        spec.updated_at = _utcnow()
        spec.version += 1
        self.save(spec)
        return node

    def add_event_flow(
        self,
        spec: ArchitectureSpec,
        name: str,
        publisher_id: str,
        subscriber_id: str,
    ) -> ArchitectureNode:
        node = ArchitectureNode(
            id=_id("evt", name),
            kind="event",
            name=name,
            purpose=f"Event {name}",
        )
        spec.nodes.append(node)
        spec.edges.append(
            ArchitectureEdge(id=_id("edge", f"{publisher_id}-pub-{node.id}"), kind="publishes", source=publisher_id, target=node.id)
        )
        spec.edges.append(
            ArchitectureEdge(id=_id("edge", f"{subscriber_id}-sub-{node.id}"), kind="subscribes", source=subscriber_id, target=node.id)
        )
        spec.updated_at = _utcnow()
        spec.version += 1
        self.save(spec)
        return node

    def add_bounded_context(self, spec: ArchitectureSpec, name: str, member_ids: Optional[List[str]] = None) -> ArchitectureNode:
        node = ArchitectureNode(
            id=_id("bc", name),
            kind="bounded_context",
            name=name,
            purpose=f"Bounded context {name}",
        )
        spec.nodes.append(node)
        for mid in member_ids or []:
            spec.edges.append(
                ArchitectureEdge(id=_id("edge", f"{node.id}-c-{mid}"), kind="contains", source=node.id, target=mid)
            )
        spec.updated_at = _utcnow()
        spec.version += 1
        self.save(spec)
        return node

    def add_security_boundary(
        self,
        spec: ArchitectureSpec,
        name: str,
        protected_ids: Optional[List[str]] = None,
    ) -> ArchitectureNode:
        node = ArchitectureNode(
            id=_id("sec", name),
            kind="security_boundary",
            name=name,
            purpose=f"Security boundary {name}",
            attributes={"severity": "high"},
        )
        spec.nodes.append(node)
        for pid in protected_ids or []:
            spec.edges.append(
                ArchitectureEdge(id=_id("edge", f"{node.id}-s-{pid}"), kind="secures", source=node.id, target=pid)
            )
        spec.updated_at = _utcnow()
        spec.version += 1
        self.save(spec)
        return node

    def link_dependency(self, spec: ArchitectureSpec, source_id: str, target_id: str, kind: str = "depends_on") -> ArchitectureEdge:
        edge = ArchitectureEdge(
            id=_id("edge", f"{source_id}-{kind}-{target_id}"),
            kind=kind,
            source=source_id,
            target=target_id,
        )
        spec.edges.append(edge)
        spec.updated_at = _utcnow()
        spec.version += 1
        self.save(spec)
        return edge

    def save(self, spec: ArchitectureSpec) -> None:
        write_json(self.store / f"{spec.architecture_id}.json", spec.to_dict())

    def load(self, architecture_id: str) -> Optional[ArchitectureSpec]:
        data = read_json(self.store / f"{architecture_id}.json")
        return ArchitectureSpec.from_dict(data) if data else None

    def list(self, owner: Optional[str] = None) -> List[ArchitectureSpec]:
        out = []
        for p in self.store.glob("*.json"):
            data = read_json(p)
            if not data:
                continue
            spec = ArchitectureSpec.from_dict(data)
            if owner is not None and spec.owner is not None and spec.owner != owner:
                continue
            out.append(spec)
        return out

    def from_template(
        self,
        name: str,
        services: List[str],
        apis: Optional[List[Dict[str, str]]] = None,
        databases: Optional[List[str]] = None,
        owner: Optional[str] = None,
    ) -> ArchitectureSpec:
        """Quick scaffold of a classic multi-service design."""
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        svc_ids = {}
        for s in services:
            sid = _id("svc", s)
            svc_ids[s] = sid
            nodes.append({"id": sid, "kind": "service", "name": s, "purpose": f"Service {s}"})
        for db in databases or []:
            did = _id("db", db)
            nodes.append({"id": did, "kind": "database", "name": db, "purpose": f"Database {db}"})
            if services:
                edges.append({
                    "id": _id("edge", f"{svc_ids[services[0]]}-{did}"),
                    "kind": "depends_on",
                    "source": svc_ids[services[0]],
                    "target": did,
                })
        for api in apis or []:
            aid = _id("api", api.get("name") or api.get("path", "api"))
            nodes.append({
                "id": aid,
                "kind": "api",
                "name": api.get("name") or api.get("path", "API"),
                "purpose": f"{api.get('method', 'GET')} {api.get('path', '/')}",
                "attributes": {"method": api.get("method", "GET"), "path": api.get("path", "/")},
            })
            if services:
                edges.append({
                    "id": _id("edge", f"{svc_ids[services[0]]}-{aid}"),
                    "kind": "contains",
                    "source": svc_ids[services[0]],
                    "target": aid,
                })
        # Frontend shell
        if services:
            fid = _id("svc", "frontend")
            nodes.append({"id": fid, "kind": "ui", "name": "Frontend", "purpose": "User interface"})
            edges.append({
                "id": _id("edge", f"{fid}-calls-{svc_ids[services[0]]}"),
                "kind": "calls",
                "source": fid,
                "target": svc_ids[services[0]],
            })
        return self.create(name, description="Architecture-first design", owner=owner, nodes=nodes, edges=edges)
