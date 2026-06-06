from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from wf_mcp.capabilities import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
)


@dataclass(slots=True)
class CatalogSnapshot:
    connection_id: str
    fetched_at_epoch_ms: int
    max_age_seconds: int
    nodes: list[CatalogNodeEntry] = field(default_factory=list)
    resources: list[CatalogResourceEntry] = field(default_factory=list)
    prompts: list[CatalogPromptEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_stale(self, now_epoch_ms: int) -> bool:
        age_ms = now_epoch_ms - self.fetched_at_epoch_ms
        return age_ms > self.max_age_seconds * 1000


def dump_catalog_snapshot(snapshot: CatalogSnapshot) -> dict[str, Any]:
    return {
        "connection_id": snapshot.connection_id,
        "fetched_at_epoch_ms": snapshot.fetched_at_epoch_ms,
        "max_age_seconds": snapshot.max_age_seconds,
        "nodes": [asdict(node) for node in snapshot.nodes],
        "resources": [asdict(resource) for resource in snapshot.resources],
        "prompts": [asdict(prompt) for prompt in snapshot.prompts],
        "metadata": snapshot.metadata,
    }


__all__ = [
    "CatalogSnapshot",
    "dump_catalog_snapshot",
]
