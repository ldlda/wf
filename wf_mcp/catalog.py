from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wf_authoring import NodeCatalog, NodeSpec

from .connections import qualify_node_name
from .models import CatalogNodeEntry, CatalogSnapshot


def snapshot_from_specs(
    connection_id: str,
    *,
    specs: dict[str, NodeSpec[Any, Any]],
    fetched_at_epoch_ms: int,
    max_age_seconds: int,
) -> CatalogSnapshot:
    catalog = NodeCatalog.from_specs(*specs.values())
    nodes = [
        CatalogNodeEntry(
            qualified_name=entry.name
            if entry.name.startswith(f"{connection_id}.")
            else qualify_node_name(connection_id, entry.name),
            connection_id=connection_id,
            local_name=entry.name.removeprefix(f"{connection_id}."),
            description=entry.description,
            outcomes=entry.outcomes,
            input_schema=entry.input_schema,
            output_schema=entry.output_schema,
        )
        for entry in catalog.entries()
    ]
    return CatalogSnapshot(
        connection_id=connection_id,
        fetched_at_epoch_ms=fetched_at_epoch_ms,
        max_age_seconds=max_age_seconds,
        nodes=nodes,
    )


@dataclass(slots=True)
class CombinedCatalog:
    snapshots: dict[str, CatalogSnapshot] = field(default_factory=dict)

    def entries(self) -> list[CatalogNodeEntry]:
        result: list[CatalogNodeEntry] = []
        for snapshot in self.snapshots.values():
            result.extend(snapshot.nodes)
        return sorted(result, key=lambda entry: entry.qualified_name)

    def as_payload(self) -> dict[str, Any]:
        return {
            "nodes": [
                {
                    "qualified_name": entry.qualified_name,
                    "connection_id": entry.connection_id,
                    "local_name": entry.local_name,
                    "description": entry.description,
                    "outcomes": list(entry.outcomes),
                    "input_schema": entry.input_schema,
                    "output_schema": entry.output_schema,
                }
                for entry in self.entries()
            ]
        }
