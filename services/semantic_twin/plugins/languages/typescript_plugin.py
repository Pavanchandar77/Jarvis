"""TypeScript/TSX language plugin — Phase 0 regex/heuristic extractor."""

from __future__ import annotations

import re
from typing import List

from ..base import (
    AstForest,
    CallSite,
    ComponentDef,
    ImportRef,
    RouteDef,
    SourceLocationDTO,
    StateDef,
    Symbol,
)

_FN_RE = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
)
_ARROW_RE = re.compile(
    r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
)
_CLASS_RE = re.compile(r"(?:export\s+)?class\s+(\w+)")
_COMPONENT_RE = re.compile(
    r"(?:export\s+)?(?:default\s+)?(?:function|const)\s+([A-Z]\w*)\s*[=(]",
)
_IMPORT_RE = re.compile(
    r"""import\s+(?:type\s+)?(?:(\w+)|\{([^}]+)\}|\*\s+as\s+(\w+))\s+from\s+['"]([^'"]+)['"]"""
)
_HOOK_RE = re.compile(r"\b(use[A-Z]\w*)\s*\(")
_USESTATE_RE = re.compile(r"const\s+\[(\w+),\s*set\w+\]\s*=\s*useState")
_ROUTE_RE = re.compile(
    r"""(?:path|route)\s*[:=]\s*['"]([^'"]+)['"]""",
    re.I,
)
_CALL_RE = re.compile(r"\b([A-Za-z_][\w]*)\s*\(")


class TypeScriptLanguagePlugin:
    name = "typescript"
    languages = ["typescript", "javascript", "tsx", "jsx"]
    extensions = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]

    def can_parse(self, path: str, content: str) -> bool:
        lower = path.lower().replace("\\", "/")
        return any(lower.endswith(ext) for ext in self.extensions)

    def extract_ast(self, path: str, content: str) -> AstForest:
        path = path.replace("\\", "/")
        forest = AstForest(path=path, language=self._lang_for(path))
        lines = content.splitlines()

        for i, line in enumerate(lines, start=1):
            for m in _IMPORT_RE.finditer(line):
                names: List[str] = []
                if m.group(1):
                    names.append(m.group(1))
                if m.group(2):
                    names.extend(n.strip().split(" as ")[0].strip() for n in m.group(2).split(","))
                if m.group(3):
                    names.append(m.group(3))
                forest.imports.append(
                    ImportRef(source_file=path, module=m.group(4), names=names, line=i)
                )

            for m in _FN_RE.finditer(line):
                name, args = m.group(1), m.group(2)
                kind = "hook" if name.startswith("use") else "function"
                forest.symbols.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        qualified_name=name,
                        source_file=path,
                        location=SourceLocationDTO(start_line=i, end_line=i),
                        signature=f"function {name}({args})",
                        is_async="async" in line,
                    )
                )
            for m in _ARROW_RE.finditer(line):
                name, args = m.group(1), m.group(2)
                kind = "hook" if name.startswith("use") else "function"
                if name[0:1].isupper():
                    kind = "component"
                    forest.components.append(
                        ComponentDef(
                            name=name,
                            framework="react",
                            source_file=path,
                            line=i,
                            end_line=i,
                        )
                    )
                forest.symbols.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        qualified_name=name,
                        source_file=path,
                        location=SourceLocationDTO(start_line=i, end_line=i),
                        signature=f"const {name} = ({args}) =>",
                    )
                )
            for m in _CLASS_RE.finditer(line):
                name = m.group(1)
                forest.symbols.append(
                    Symbol(
                        name=name,
                        kind="class",
                        qualified_name=name,
                        source_file=path,
                        location=SourceLocationDTO(start_line=i, end_line=i),
                        signature=f"class {name}",
                    )
                )
            for m in _COMPONENT_RE.finditer(line):
                name = m.group(1)
                if not any(c.name == name for c in forest.components):
                    forest.components.append(
                        ComponentDef(
                            name=name,
                            framework="react",
                            source_file=path,
                            line=i,
                            end_line=i,
                        )
                    )
            for m in _USESTATE_RE.finditer(line):
                forest.state.append(
                    StateDef(name=m.group(1), store_type="useState", source_file=path, line=i)
                )
            for m in _ROUTE_RE.finditer(line):
                forest.routes.append(
                    RouteDef(
                        path_pattern=m.group(1),
                        method="GET",
                        handler_name="page",
                        source_file=path,
                        line=i,
                    )
                )

        # Call sites (coarse): associate with nearest preceding function name
        current_fn = "<module>"
        for i, line in enumerate(lines, start=1):
            fm = _FN_RE.search(line) or _ARROW_RE.search(line)
            if fm:
                current_fn = fm.group(1)
            for m in _CALL_RE.finditer(line):
                callee = m.group(1)
                if callee in (
                    "if", "for", "while", "switch", "catch", "function",
                    "return", "await", "typeof", "new", "const", "let", "var",
                ):
                    continue
                forest.calls.append(
                    CallSite(
                        caller_qualified=current_fn,
                        callee_name=callee,
                        source_file=path,
                        line=i,
                    )
                )
            for m in _HOOK_RE.finditer(line):
                forest.calls.append(
                    CallSite(
                        caller_qualified=current_fn,
                        callee_name=m.group(1),
                        source_file=path,
                        line=i,
                        attributes={"hook": True},
                    )
                )
        return forest

    def _lang_for(self, path: str) -> str:
        if path.endswith((".tsx", ".jsx")):
            return "tsx"
        if path.endswith((".ts",)):
            return "typescript"
        return "javascript"
