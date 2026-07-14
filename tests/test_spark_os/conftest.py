"""Fixtures for Spark OS tests — reuse sample app from Semantic Twin suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_APP = ROOT / "tests" / "test_semantic_twin" / "fixtures" / "sample_app"


@pytest.fixture
def sample_app_root() -> Path:
    return FIXTURE_APP
