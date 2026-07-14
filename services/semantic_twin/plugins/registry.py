"""Plugin discovery and lifecycle."""

from __future__ import annotations

from typing import Dict, List, Optional

from .base import LanguagePlugin
from .languages.python_plugin import PythonLanguagePlugin
from .languages.typescript_plugin import TypeScriptLanguagePlugin
from .languages.generic_plugin import GenericLanguagePlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._language: Dict[str, LanguagePlugin] = {}
        self._ordered: List[LanguagePlugin] = []

    def register_language(self, plugin: LanguagePlugin) -> None:
        self._language[plugin.name] = plugin
        # Keep order: specific before generic
        self._ordered = [p for p in self._ordered if p.name != plugin.name]
        if plugin.name == "generic":
            self._ordered.append(plugin)
        else:
            self._ordered.insert(0, plugin)

    def language_plugins(self) -> List[LanguagePlugin]:
        return list(self._ordered)

    def resolve(self, path: str, content: str) -> Optional[LanguagePlugin]:
        for plugin in self._ordered:
            if plugin.can_parse(path, content):
                return plugin
        return None

    @classmethod
    def with_builtins(cls) -> "PluginRegistry":
        reg = cls()
        reg.register_language(PythonLanguagePlugin())
        reg.register_language(TypeScriptLanguagePlugin())
        reg.register_language(GenericLanguagePlugin())
        return reg
