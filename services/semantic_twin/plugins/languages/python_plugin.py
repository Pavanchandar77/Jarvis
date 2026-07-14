"""Python language plugin using the stdlib ast module."""

from __future__ import annotations

import ast
import re
from typing import List, Optional

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


class PythonLanguagePlugin:
    name = "python"
    languages = ["python"]
    extensions = [".py", ".pyi"]

    def can_parse(self, path: str, content: str) -> bool:
        lower = path.lower().replace("\\", "/")
        return any(lower.endswith(ext) for ext in self.extensions)

    def extract_ast(self, path: str, content: str) -> AstForest:
        forest = AstForest(path=path.replace("\\", "/"), language="python")
        try:
            tree = ast.parse(content)
            forest.raw = tree
        except SyntaxError as exc:
            forest.errors.append(f"SyntaxError: {exc}")
            return forest

        self._walk_module(tree, forest, path.replace("\\", "/"))
        self._detect_routes(content, forest)
        self._detect_state(content, forest)
        return forest

    def _walk_module(self, tree: ast.AST, forest: AstForest, path: str) -> None:
        for node in tree.body if hasattr(tree, "body") else []:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                forest.symbols.append(self._fn_symbol(node, path, parent=None))
                forest.calls.extend(self._calls_in(node, node.name, path))
            elif isinstance(node, ast.ClassDef):
                forest.symbols.append(self._class_symbol(node, path))
                # Heuristic: React-like / UI class names
                if node.name.endswith(("Component", "View", "Page", "Widget")):
                    forest.components.append(
                        ComponentDef(
                            name=node.name,
                            framework="python",
                            source_file=path,
                            line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
                        )
                    )
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        qn = f"{node.name}.{item.name}"
                        forest.symbols.append(self._fn_symbol(item, path, parent=node.name, kind="method"))
                        forest.calls.extend(self._calls_in(item, qn, path))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                forest.imports.append(self._import_ref(node, path))

    def _fn_symbol(
        self,
        node: ast.AST,
        path: str,
        parent: Optional[str],
        kind: str = "function",
    ) -> Symbol:
        name = node.name  # type: ignore[attr-defined]
        is_async = isinstance(node, ast.AsyncFunctionDef)
        # Hooks heuristic
        if name.startswith("use_") or name.startswith("use"):
            kind = "hook"
        args = []
        if hasattr(node, "args"):
            for a in node.args.args:  # type: ignore[attr-defined]
                args.append(a.arg)
        sig = f"{'async ' if is_async else ''}def {name}({', '.join(args)})"
        doc = ast.get_docstring(node) or ""
        qn = f"{parent}.{name}" if parent else name
        return Symbol(
            name=name,
            kind=kind,
            qualified_name=qn,
            source_file=path,
            location=SourceLocationDTO(
                start_line=node.lineno,  # type: ignore[attr-defined]
                end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
            ),
            signature=sig,
            docstring=doc,
            is_async=is_async,
            parent=parent,
        )

    def _class_symbol(self, node: ast.ClassDef, path: str) -> Symbol:
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(b.attr)
        return Symbol(
            name=node.name,
            kind="class",
            qualified_name=node.name,
            source_file=path,
            location=SourceLocationDTO(
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
            ),
            signature=f"class {node.name}({', '.join(bases)})",
            docstring=ast.get_docstring(node) or "",
            attributes={"bases": bases},
        )

    def _calls_in(self, node: ast.AST, caller_qn: str, path: str) -> List[CallSite]:
        sites: List[CallSite] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = self._call_name(child.func)
                if name:
                    sites.append(
                        CallSite(
                            caller_qualified=caller_qn,
                            callee_name=name,
                            source_file=path,
                            line=getattr(child, "lineno", 1) or 1,
                        )
                    )
        return sites

    def _call_name(self, func: ast.AST) -> Optional[str]:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None

    def _import_ref(self, node: ast.AST, path: str) -> ImportRef:
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
            mod = names[0] if names else ""
            return ImportRef(source_file=path, module=mod, names=names, line=node.lineno)
        assert isinstance(node, ast.ImportFrom)
        mod = node.module or ""
        names = [a.name for a in node.names] if node.names else []
        return ImportRef(source_file=path, module=mod, names=names, line=node.lineno)

    def _detect_routes(self, content: str, forest: AstForest) -> None:
        # FastAPI / Flask style decorators
        patterns = [
            re.compile(
                r"@(?:app|router)\.(get|post|put|delete|patch|options|head)\(\s*['\"]([^'\"]+)['\"]",
                re.I,
            ),
            re.compile(
                r"@\w+\.route\(\s*['\"]([^'\"]+)['\"]",
                re.I,
            ),
        ]
        lines = content.splitlines()
        for i, line in enumerate(lines, start=1):
            for pi, pat in enumerate(patterns):
                m = pat.search(line)
                if not m:
                    continue
                if pi == 0:
                    method, path_pat = m.group(1).upper(), m.group(2)
                else:
                    method, path_pat = "GET", m.group(1)
                # next def
                handler = "handler"
                for j in range(i, min(i + 5, len(lines) + 1)):
                    dm = re.match(r"\s*(?:async\s+)?def\s+(\w+)", lines[j - 1])
                    if dm:
                        handler = dm.group(1)
                        break
                forest.routes.append(
                    RouteDef(
                        path_pattern=path_pat,
                        method=method,
                        handler_name=handler,
                        source_file=forest.path,
                        line=i,
                    )
                )

    def _detect_state(self, content: str, forest: AstForest) -> None:
        for i, line in enumerate(content.splitlines(), start=1):
            m = re.search(r"(\w+)\s*=\s*(?:useState|createStore|State\()", line)
            if m:
                forest.state.append(
                    StateDef(
                        name=m.group(1),
                        store_type="state",
                        source_file=forest.path,
                        line=i,
                    )
                )
