"""Twin repository — CRUD with ownership checks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import SemanticTwin, TwinMeta
from . import format as fmt

logger = logging.getLogger(__name__)


class TwinRepository:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, twin: SemanticTwin) -> Path:
        path = fmt.write_twin_package(self.base, twin)
        logger.info(
            "Saved Semantic Twin %s (rev %s, %s nodes)",
            twin.twin_id,
            twin.content_revision,
            twin.meta.node_count,
        )
        return path

    def load(
        self,
        twin_id: str,
        *,
        owner: Optional[str] = None,
        include_graph: bool = True,
    ) -> SemanticTwin:
        twin = fmt.read_twin_package(self.base, twin_id, include_graph=include_graph)
        self._assert_owner(twin, owner)
        return twin

    def delete(self, twin_id: str, *, owner: Optional[str] = None) -> None:
        # Load header for ownership check
        twin = fmt.read_twin_package(self.base, twin_id, include_graph=False)
        self._assert_owner(twin, owner)
        fmt.delete_twin_package(self.base, twin_id)

    def list(self, *, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        for tid in fmt.list_twin_ids(self.base):
            try:
                twin = fmt.read_twin_package(self.base, tid, include_graph=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skip corrupt twin %s: %s", tid, exc)
                continue
            if owner is not None and twin.owner is not None and twin.owner != owner:
                continue
            results.append({
                "twin_id": twin.twin_id,
                "application_id": twin.application_id,
                "content_revision": twin.content_revision,
                "content_hash": twin.content_hash,
                "updated_at": twin.updated_at,
                "owner": twin.owner,
                "meta": twin.meta.to_dict(),
            })
        return results

    def exists(self, twin_id: str) -> bool:
        try:
            p = fmt.twin_dir(self.base, twin_id)
        except ValueError:
            return False
        return (p / "twin.json").is_file()

    def save_delta(self, twin_id: str, revision: int, patch: Dict[str, Any]) -> None:
        fmt.write_delta(self.base, twin_id, revision, patch)

    def _assert_owner(self, twin: SemanticTwin, owner: Optional[str]) -> None:
        if owner is None:
            return  # auth disabled / system
        if twin.owner is not None and twin.owner != owner:
            raise PermissionError("twin not found")  # 404-style opacity
