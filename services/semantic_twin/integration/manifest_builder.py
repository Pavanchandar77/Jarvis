"""Build expanded GenerationManifest from live agent turn evidence."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import (
    AlternativeImplementation,
    DesignDecision,
    GenerationManifest,
    PromptRecord,
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _short_id(prefix: str, text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{prefix}-{h}"


class ManifestBuilder:
    """
    Accumulates generation evidence during an agent turn and builds a
    complete GenerationManifest at finalize time.
    """

    def __init__(
        self,
        *,
        generation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        owner: Optional[str] = None,
        model: Optional[str] = None,
        backend: Optional[str] = None,
        user_prompt: str = "",
        planning_prompt: str = "",
        approved_plan: str = "",
    ) -> None:
        self.generation_id = generation_id or uuid.uuid4().hex
        self.session_id = session_id
        self.owner = owner
        self.model = model
        self.backend = backend or ""
        self.user_prompt = user_prompt or ""
        self.planning_prompt = planning_prompt or ""
        self.approved_plan = approved_plan or ""
        self.agent_chain: List[Dict[str, Any]] = []
        self.tool_history: List[Dict[str, Any]] = []
        self.files_written: Dict[str, str] = {}  # rel_or_abs → prompt_id
        self.file_ownership: Dict[str, str] = {}  # path → agent role
        self.component_ownership: Dict[str, str] = {}
        self.decisions: List[DesignDecision] = []
        self.requirements: List[Dict[str, Any]] = []
        self.dependency_reasoning: List[Dict[str, Any]] = []
        self.trade_offs: List[str] = []
        self.runtime_metadata: Dict[str, Any] = {}
        self.tech_stack: List[str] = []
        self._prompt_ordinal = 0
        self.prompts: List[PromptRecord] = []
        self._seed_prompts()

    def _seed_prompts(self) -> None:
        if self.user_prompt:
            self.prompts.append(
                PromptRecord(
                    id="prompt-user",
                    ordinal=self._prompt_ordinal,
                    role="user",
                    text_ref=self.user_prompt[:4000],
                    model=self.model,
                    created_at=_utcnow(),
                )
            )
            self._prompt_ordinal += 1
            self._extract_requirements(self.user_prompt, "prompt-user")
        if self.planning_prompt or self.approved_plan:
            text = self.planning_prompt or self.approved_plan
            self.prompts.append(
                PromptRecord(
                    id="prompt-plan",
                    ordinal=self._prompt_ordinal,
                    role="system",
                    text_ref=text[:4000],
                    model=self.model,
                    created_at=_utcnow(),
                )
            )
            self._prompt_ordinal += 1
            self._extract_plan_steps(text)

    def _extract_requirements(self, text: str, prompt_id: str) -> None:
        # Bullet / numbered lines as lightweight requirements
        for line in text.splitlines():
            m = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$", line)
            if m and len(m.group(1)) > 8:
                req_text = m.group(1).strip()
                self.requirements.append({
                    "id": _short_id("req", req_text),
                    "text": req_text[:500],
                    "prompt_id": prompt_id,
                })
        if not self.requirements and text.strip():
            self.requirements.append({
                "id": "req-root",
                "text": text.strip()[:500],
                "prompt_id": prompt_id,
            })

    def _extract_plan_steps(self, plan: str) -> None:
        for line in plan.splitlines():
            m = re.match(r"^\s*[-*]\s*\[[ xX]\]\s*(.+)$", line)
            if m:
                step = m.group(1).strip()
                self.agent_chain.append({
                    "step": step,
                    "done": bool(re.search(r"\[[xX]\]", line)),
                    "source": "plan",
                })

    def record_agent_round(self, round_num: int, summary: str = "", tools: Optional[List[str]] = None) -> None:
        self.agent_chain.append({
            "round": round_num,
            "summary": (summary or "")[:500],
            "tools": list(tools or []),
            "ts": _utcnow(),
        })

    def record_tool(
        self,
        *,
        tool: str,
        command: str = "",
        exit_code: Optional[int] = None,
        output: str = "",
        round_num: int = 0,
        path: Optional[str] = None,
    ) -> None:
        entry = {
            "tool": tool,
            "command": (command or "")[:1000],
            "exit_code": exit_code,
            "output_preview": (output or "")[:400],
            "round": round_num,
            "ts": _utcnow(),
        }
        if path:
            entry["path"] = path
        self.tool_history.append(entry)

        # Infer decisions from update_plan / ask_user / notable choices
        if tool == "update_plan" and command:
            self._ingest_plan_update(command)
        if tool in ("write_file", "edit_file") and path:
            pid = self.prompts[0].id if self.prompts else "prompt-user"
            self.files_written[path] = pid
            self.file_ownership[path] = "agent"

    def _ingest_plan_update(self, content: str) -> None:
        # content may be JSON {"plan": "..."}
        plan_text = content
        try:
            import json
            if content.strip().startswith("{"):
                data = json.loads(content)
                plan_text = data.get("plan") or content
        except Exception:
            pass
        self.planning_prompt = plan_text[:4000]
        self._extract_plan_steps(plan_text)

    def record_decision(
        self,
        title: str,
        rationale: str,
        chosen: str,
        *,
        alternatives: Optional[List[Dict[str, str]]] = None,
        trade_offs: Optional[List[str]] = None,
        prompt_id: Optional[str] = None,
    ) -> None:
        alts = []
        for i, a in enumerate(alternatives or []):
            alts.append(
                AlternativeImplementation(
                    id=a.get("id") or f"alt-{i}",
                    title=a.get("title") or f"Alternative {i+1}",
                    summary=a.get("summary") or "",
                    why_rejected=a.get("why_rejected") or "",
                    when_preferable=a.get("when_preferable"),
                )
            )
        self.decisions.append(
            DesignDecision(
                id=_short_id("dec", title),
                title=title,
                rationale=rationale,
                chosen=chosen,
                alternatives=alts,
                prompt_id=prompt_id or (self.prompts[0].id if self.prompts else None),
                trade_offs=list(trade_offs or []),
            )
        )
        for t in trade_offs or []:
            if t not in self.trade_offs:
                self.trade_offs.append(t)

    def record_dependency_reason(self, source: str, target: str, reason: str) -> None:
        self.dependency_reasoning.append({
            "source": source,
            "target": target,
            "reason": reason,
            "ts": _utcnow(),
        })

    def infer_tech_stack(self, paths: List[str]) -> None:
        exts = {p.rsplit(".", 1)[-1].lower() for p in paths if "." in p}
        mapping = {
            "py": "python",
            "ts": "typescript",
            "tsx": "react",
            "js": "javascript",
            "jsx": "react",
            "go": "go",
            "rs": "rust",
            "java": "java",
            "kt": "kotlin",
            "swift": "swift",
            "css": "css",
            "html": "html",
            "sql": "sql",
            "json": "json",
            "yml": "yaml",
            "yaml": "yaml",
            "toml": "toml",
            "md": "markdown",
        }
        for e in exts:
            stack = mapping.get(e)
            if stack and stack not in self.tech_stack:
                self.tech_stack.append(stack)

    def set_runtime_metadata(self, **kwargs: Any) -> None:
        self.runtime_metadata.update(kwargs)

    def build(self) -> GenerationManifest:
        paths = list(self.files_written.keys())
        self.infer_tech_stack(paths)

        # Relative-friendly file_prompt_map keys (basename + last 2 segments)
        file_prompt_map: Dict[str, List[str]] = {}
        for path, pid in self.files_written.items():
            key = path.replace("\\", "/")
            file_prompt_map.setdefault(key, []).append(pid)
            parts = key.split("/")
            if len(parts) >= 2:
                short = "/".join(parts[-2:])
                file_prompt_map.setdefault(short, []).append(pid)

        # Auto decision if none recorded but files written
        if not self.decisions and paths:
            self.record_decision(
                title="Generate application files via agent tools",
                rationale="Spark agent wrote project files using write_file/edit_file during generation.",
                chosen="Agent tool-based generation",
                alternatives=[{
                    "id": "alt-manual",
                    "title": "Manual scaffolding",
                    "summary": "Human writes files without agent",
                    "why_rejected": "User requested AI generation",
                }],
                trade_offs=["Speed and coverage vs human control"],
            )

        model_ids = [m for m in [self.model] if m]

        return GenerationManifest(
            generation_id=self.generation_id,
            model_ids=model_ids,
            prompts=list(self.prompts),
            requirements=list(self.requirements),
            decisions=list(self.decisions),
            file_prompt_map=file_prompt_map,
            tech_stack=list(self.tech_stack),
            created_at=_utcnow(),
            # Expanded Phase-1 fields
            user_prompt=self.user_prompt,
            planning_prompt=self.planning_prompt or self.approved_plan,
            agent_chain=list(self.agent_chain),
            tool_history=list(self.tool_history)[-200:],  # cap
            backend=self.backend,
            runtime_metadata={
                **self.runtime_metadata,
                "session_id": self.session_id,
                "owner": self.owner,
            },
            file_ownership=dict(self.file_ownership),
            component_ownership=dict(self.component_ownership),
            dependency_reasoning=list(self.dependency_reasoning),
            trade_offs=list(self.trade_offs),
            metadata={
                "source": "spark_agent",
                "files_written_count": len(paths),
                "tools_count": len(self.tool_history),
            },
        )
