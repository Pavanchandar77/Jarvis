"""Shared fixtures for Semantic Twin tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_APP = Path(__file__).parent / "fixtures" / "sample_app"


@pytest.fixture
def sample_app_root() -> Path:
    return FIXTURE_APP


@pytest.fixture
def twin_storage(tmp_path: Path) -> Path:
    d = tmp_path / "semantic_twins"
    d.mkdir()
    return d


@pytest.fixture
def sample_manifest():
    from services.semantic_twin.models import (
        AlternativeImplementation,
        DesignDecision,
        GenerationManifest,
        PromptRecord,
    )

    return GenerationManifest(
        generation_id="gen-test-001",
        model_ids=["test-model"],
        prompts=[
            PromptRecord(
                id="prompt-1",
                ordinal=0,
                role="user",
                text_ref="Build a small catalog API with a list UI.",
                model="test-model",
            )
        ],
        requirements=[
            {"id": "req-1", "text": "Expose GET /items", "prompt_id": "prompt-1"},
            {"id": "req-2", "text": "Render item list component", "prompt_id": "prompt-1"},
        ],
        decisions=[
            DesignDecision(
                id="dec-1",
                title="Use Flask for the HTTP layer",
                rationale="Simple surface for a sample app.",
                chosen="Flask",
                alternatives=[
                    AlternativeImplementation(
                        id="alt-1",
                        title="FastAPI",
                        summary="Async-native API framework",
                        why_rejected="Overkill for fixture",
                        when_preferable="When OpenAPI-first is required",
                    )
                ],
                prompt_id="prompt-1",
                trade_offs=["Sync simplicity vs async throughput"],
            )
        ],
        file_prompt_map={
            "src/app.py": ["prompt-1"],
            "src/components.py": ["prompt-1"],
            "api/client.ts": ["prompt-1"],
        },
        tech_stack=["python", "flask", "typescript"],
    )
