"""Stable ID generation for Semantic Twin nodes and edges."""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Optional


def new_twin_id() -> str:
    """Return a new twin identifier (UUID4 hex, 32 chars)."""
    return uuid.uuid4().hex


def new_edge_id(kind: str, source: str, target: str, disambiguator: str = "") -> str:
    raw = f"edge|{kind}|{source}|{target}|{disambiguator}"
    return "e_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def stable_node_id(
    kind: str,
    source_file: Optional[str],
    qualified_name: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """
    Deterministic node id from structural identity.

    Unchanged files regenerate the same ids (critical for incremental updates
    and compareVersions).
    """
    path = (source_file or "").replace("\\", "/").lstrip("./")
    span = f"{start_line or 0}:{end_line or 0}"
    raw = f"node|{kind}|{path}|{qualified_name}|{span}"
    return "n_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def concept_id(slug: str) -> str:
    clean = slugify(slug)
    return "c_" + hashlib.sha256(f"concept|{clean}".encode("utf-8")).hexdigest()[:20]


def prompt_node_id(prompt_id: str) -> str:
    return "p_" + hashlib.sha256(f"prompt|{prompt_id}".encode("utf-8")).hexdigest()[:20]


def decision_node_id(decision_id: str) -> str:
    return "d_" + hashlib.sha256(f"decision|{decision_id}".encode("utf-8")).hexdigest()[:20]


def requirement_node_id(req_id: str) -> str:
    return "r_" + hashlib.sha256(f"requirement|{req_id}".encode("utf-8")).hexdigest()[:20]


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unnamed"


def content_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
