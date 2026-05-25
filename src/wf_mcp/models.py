from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from wf_core import Edge
from wf_core.models.steps import InputBinding, Step

from .capabilities import CatalogNodeEntry, CatalogPromptEntry, CatalogResourceEntry


@dataclass(slots=True)
class ConnectionConfig:
    id: str
    server: str
    account: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AuthRecord:
    connection_id: str
    scheme: str
    payload: dict[str, Any] = field(default_factory=dict)


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


class RawWorkflowPlan(BaseModel):
    """Raw authoring plan using the same graph step and edge models as core."""

    name: str
    input_schema: dict[str, Any]
    state_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: list[str] = Field(
        default_factory=lambda: ["ok"],
        description=(
            "Declared public workflow outcomes. Legacy plans without this field "
            "default to ok."
        ),
    )
    output: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Optional root workflow output bindings. Sources read graph paths "
            "such as state.result and targets write the public output payload."
        ),
    )
    start: str
    nodes: list[Step]
    edges: list[Edge]


@dataclass(slots=True)
class BrokerConfig:
    store_root: Path
    connections: list[ConnectionConfig] = field(default_factory=list)


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
