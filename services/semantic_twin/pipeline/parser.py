"""Parser Layer — discover source files and assign language plugins."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Iterable, Set

from ..ids import file_content_hash
from .context import PipelineContext, SourceFile

_SKIP_DIRS: Set[str] = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".next", ".turbo", "coverage", ".tox", ".mypy_cache", ".pytest_cache",
    "vendor", "target", "bin", "obj",
}

_MAX_FILE_BYTES = 1_500_000


class ParserStage:
    name = "parser"

    def run(self, ctx: PipelineContext) -> None:
        t0 = time.perf_counter()
        root = ctx.app_root.resolve()
        if not root.is_dir():
            ctx.errors.append(f"app_root is not a directory: {root}")
            ctx.stage_metrics[self.name] = time.perf_counter() - t0
            return

        dirty = None
        if ctx.dirty_files is not None:
            dirty = {self._rel(root, f) for f in ctx.dirty_files}

        for abs_path in self._walk(root):
            rel = self._rel(root, abs_path)
            if dirty is not None and rel not in dirty:
                continue
            try:
                data = Path(abs_path).read_bytes()
            except OSError as exc:
                ctx.errors.append(f"read failed {rel}: {exc}")
                continue
            if len(data) > _MAX_FILE_BYTES:
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = data.decode("utf-8", errors="replace")
                except Exception:
                    continue
            h = file_content_hash(data)
            ctx.sources[rel] = SourceFile(
                path=rel,
                absolute=str(abs_path),
                content=text,
                content_hash=h,
            )
            ctx.graph.file_hashes[rel] = h

        ctx.stage_metrics[self.name] = time.perf_counter() - t0

    def _walk(self, root: Path) -> Iterable[str]:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                if name.startswith("."):
                    continue
                yield str(Path(dirpath) / name)

    def _rel(self, root: Path, path) -> str:
        p = Path(path)
        try:
            return p.resolve().relative_to(root).as_posix()
        except ValueError:
            return Path(path).as_posix().replace("\\", "/")
