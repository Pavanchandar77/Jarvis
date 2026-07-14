"""Generic language plugin — last-resort regex heuristics for any text source."""

from __future__ import annotations

import re

from ..base import AstForest, SourceLocationDTO, Symbol

_FN_ANY = re.compile(
    r"(?:function|def|fn|func)\s+(\w+)\s*\(",
    re.I,
)

_SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".gz", ".tar", ".7z", ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".class", ".o", ".a",
    ".mp3", ".mp4", ".webm", ".wav",
    ".lock", ".map",
}


class GenericLanguagePlugin:
    name = "generic"
    languages = ["generic"]
    extensions: list[str] = []  # matches anything not claimed by earlier plugins

    def can_parse(self, path: str, content: str) -> bool:
        lower = path.lower().replace("\\", "/")
        for ext in _SKIP_EXT:
            if lower.endswith(ext):
                return False
        # Skip huge binaries / empty
        if not content or "\x00" in content[:1024]:
            return False
        return True

    def extract_ast(self, path: str, content: str) -> AstForest:
        path = path.replace("\\", "/")
        forest = AstForest(path=path, language="generic")
        for i, line in enumerate(content.splitlines(), start=1):
            m = _FN_ANY.search(line)
            if m:
                name = m.group(1)
                forest.symbols.append(
                    Symbol(
                        name=name,
                        kind="function",
                        qualified_name=name,
                        source_file=path,
                        location=SourceLocationDTO(start_line=i, end_line=i),
                        signature=line.strip()[:120],
                    )
                )
        return forest
