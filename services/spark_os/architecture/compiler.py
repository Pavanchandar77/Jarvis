"""Compile ArchitectureSpec → project scaffold + GenerationManifest intent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.semantic_twin.models import (
    DesignDecision,
    GenerationManifest,
    PromptRecord,
)

from ..models import ArchitectureSpec


class ArchitectureCompiler:
    """
    Architecture is primary; code is a compiled representation.

    Emits a file map (relative path → content) suitable for write_file
    and a GenerationManifest that preserves architectural intent.
    """

    def compile(
        self,
        spec: ArchitectureSpec,
        *,
        target_root: str | Path,
        write: bool = True,
    ) -> Dict[str, Any]:
        root = Path(target_root)
        files: Dict[str, str] = {}
        files["ARCHITECTURE.md"] = self._arch_doc(spec)
        files["README.md"] = f"# {spec.name}\n\nGenerated from architecture `{spec.architecture_id}`.\n"

        services = [n for n in spec.nodes if n.kind in ("service", "ui")]
        apis = [n for n in spec.nodes if n.kind == "api"]
        dbs = [n for n in spec.nodes if n.kind == "database"]
        events = [n for n in spec.nodes if n.kind == "event"]

        for svc in services:
            slug = _slug(svc.name)
            if svc.kind == "ui":
                files[f"frontend/src/{slug}.tsx"] = self._frontend_stub(svc)
            else:
                files[f"services/{slug}/__init__.py"] = f'"""Service: {svc.name}"""\n'
                files[f"services/{slug}/service.py"] = self._service_stub(svc, apis, dbs)

        for api in apis:
            slug = _slug(api.name)
            method = (api.attributes or {}).get("method", "GET")
            path = (api.attributes or {}).get("path", f"/{slug}")
            files[f"api/routes/{slug}.py"] = self._api_stub(api, method, path)

        for db in dbs:
            slug = _slug(db.name)
            engine = (db.attributes or {}).get("engine", "postgres")
            files[f"db/{slug}/schema.sql"] = f"-- {db.name} ({engine})\nCREATE TABLE IF NOT EXISTS {_slug(db.name)}_items (\n  id SERIAL PRIMARY KEY,\n  data JSONB\n);\n"

        for ev in events:
            slug = _slug(ev.name)
            files[f"events/{slug}.py"] = f'"""Event: {ev.name}"""\n\nEVENT_NAME = "{ev.name}"\n'

        files["main.py"] = self._main_stub(services, apis)

        written = []
        if write:
            root.mkdir(parents=True, exist_ok=True)
            for rel, content in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                written.append(rel.replace("\\", "/"))

        manifest = self._manifest(spec, written)
        return {
            "architecture_id": spec.architecture_id,
            "target_root": str(root),
            "files": written or list(files.keys()),
            "file_contents": files if not write else None,
            "manifest": manifest.to_dict(),
        }

    def _manifest(self, spec: ArchitectureSpec, files: List[str]) -> GenerationManifest:
        prompt = (
            f"Architecture-first generation for {spec.name}: "
            f"{len(spec.nodes)} nodes, {len(spec.edges)} edges. {spec.description}"
        )
        file_map = {f: ["prompt-arch"] for f in files}
        return GenerationManifest(
            generation_id=f"arch-{spec.architecture_id[:12]}",
            model_ids=["architecture-compiler"],
            prompts=[
                PromptRecord(
                    id="prompt-arch",
                    ordinal=0,
                    role="system",
                    text_ref=prompt[:4000],
                    model="architecture-compiler",
                )
            ],
            requirements=[
                {"id": f"req-{n.id}", "text": n.purpose or n.name, "prompt_id": "prompt-arch"}
                for n in spec.nodes[:50]
            ],
            decisions=[
                DesignDecision(
                    id=f"dec-arch-{spec.architecture_id[:8]}",
                    title="Architecture-first compilation",
                    rationale="Implementation compiled from architecture spec as primary artifact.",
                    chosen="Generate scaffold from ArchitectureSpec",
                    trade_offs=["Consistency with design vs hand-tuned code"],
                    prompt_id="prompt-arch",
                )
            ],
            file_prompt_map=file_map,
            tech_stack=_infer_stack(spec),
            user_prompt=prompt,
            planning_prompt=spec.description,
            backend="architecture-compiler",
            file_ownership={f: "architect" for f in files},
            trade_offs=["Architecture-first enforces structure; may need refinement"],
            metadata={
                "source": "architecture_compiler",
                "architecture_id": spec.architecture_id,
                "architecture_version": spec.version,
            },
        )

    def _arch_doc(self, spec: ArchitectureSpec) -> str:
        lines = [f"# Architecture: {spec.name}", "", spec.description or "", "", "## Nodes", ""]
        for n in spec.nodes:
            lines.append(f"- **{n.name}** (`{n.kind}`): {n.purpose or n.description}")
        lines += ["", "## Edges", ""]
        for e in spec.edges:
            lines.append(f"- {e.source} —{e.kind}→ {e.target}")
        return "\n".join(lines) + "\n"

    def _service_stub(self, svc, apis, dbs) -> str:
        return f'''"""Service: {svc.name}

Purpose: {svc.purpose or svc.description}
Compiled from architecture node {svc.id}.
"""

from typing import Any, Dict


class { _class(svc.name) }Service:
    """{svc.purpose or svc.name}"""

    def health(self) -> Dict[str, Any]:
        return {{"service": "{svc.name}", "ok": True}}

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {{"service": "{svc.name}", "echo": payload}}
'''

    def _api_stub(self, api, method: str, path: str) -> str:
        return f'''"""API: {api.name} — {method} {path}

Architecture node: {api.id}
"""

def handle_request(request=None):
    """Handler for {method} {path}."""
    return {{"api": "{api.name}", "method": "{method}", "path": "{path}", "ok": True}}
'''

    def _frontend_stub(self, svc) -> str:
        cname = _class(svc.name)
        return (
            f"// UI: {svc.name}\n"
            f"// Architecture node: {svc.id}\n\n"
            f"export function {cname}() {{\n"
            f"  return <div className=\"service-ui\">{{/* {svc.name} */}}</div>;\n"
            f"}}\n"
        )

    def _main_stub(self, services, apis) -> str:
        return f'''"""Application entry — compiled from architecture."""

def main():
    print("Spark architecture-compiled app")
    print("Services: {", ".join(s.name for s in services)}")
    print("APIs: {", ".join(a.name for a in apis)}")


if __name__ == "__main__":
    main()
'''


def _slug(name: str) -> str:
    s = "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s or "item"


def _class(name: str) -> str:
    parts = _slug(name).split("_")
    return "".join(p.capitalize() for p in parts if p) or "Component"


def _infer_stack(spec: ArchitectureSpec) -> List[str]:
    stack = ["python"]
    if any(n.kind == "ui" for n in spec.nodes):
        stack.append("typescript")
        stack.append("react")
    if any(n.kind == "database" for n in spec.nodes):
        stack.append("sql")
    if any(n.kind == "event" for n in spec.nodes):
        stack.append("events")
    return stack
