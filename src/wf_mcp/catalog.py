from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wf_authoring import NodeCatalog, NodeSpec

from .capabilities import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    DiscoveredPrompt,
    DiscoveredResource,
)
from .connections import qualify_node_name
from .models import CatalogSnapshot


def snapshot_from_specs(
    connection_id: str,
    *,
    specs: dict[str, NodeSpec[Any, Any]],
    resources: list[DiscoveredResource] | None = None,
    prompts: list[DiscoveredPrompt] | None = None,
    metadata: dict[str, Any] | None = None,
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
    resource_entries = [
        CatalogResourceEntry(
            qualified_name=qualify_node_name(connection_id, resource.name),
            connection_id=connection_id,
            local_name=resource.name,
            uri=resource.uri,
            description=resource.description,
            mime_type=resource.mime_type,
            metadata=resource.metadata,
        )
        for resource in resources or []
    ]
    prompt_entries = [
        CatalogPromptEntry(
            qualified_name=qualify_node_name(connection_id, prompt.name),
            connection_id=connection_id,
            local_name=prompt.name,
            description=prompt.description,
            arguments=prompt.arguments,
            metadata=prompt.metadata,
        )
        for prompt in prompts or []
    ]
    return CatalogSnapshot(
        connection_id=connection_id,
        fetched_at_epoch_ms=fetched_at_epoch_ms,
        max_age_seconds=max_age_seconds,
        nodes=nodes,
        resources=resource_entries,
        prompts=prompt_entries,
        metadata=metadata or {},
    )


@dataclass(slots=True)
class CombinedCatalog:
    snapshots: dict[str, CatalogSnapshot] = field(default_factory=dict)

    def entries(self) -> list[CatalogNodeEntry]:
        result: list[CatalogNodeEntry] = []
        for snapshot in self.snapshots.values():
            result.extend(snapshot.nodes)
        return sorted(result, key=lambda entry: entry.qualified_name)

    def resource_entries(self) -> list[CatalogResourceEntry]:
        result: list[CatalogResourceEntry] = []
        for snapshot in self.snapshots.values():
            result.extend(snapshot.resources)
        return sorted(result, key=lambda entry: entry.qualified_name)

    def prompt_entries(self) -> list[CatalogPromptEntry]:
        result: list[CatalogPromptEntry] = []
        for snapshot in self.snapshots.values():
            result.extend(snapshot.prompts)
        return sorted(result, key=lambda entry: entry.qualified_name)

    def find_resource(self, qualified_name: str) -> CatalogResourceEntry | None:
        for entry in self.resource_entries():
            if entry.qualified_name == qualified_name:
                return entry
        return None

    def find_prompt(self, qualified_name: str) -> CatalogPromptEntry | None:
        for entry in self.prompt_entries():
            if entry.qualified_name == qualified_name:
                return entry
        return None

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
            ],
            "resources": [
                {
                    "qualified_name": entry.qualified_name,
                    "connection_id": entry.connection_id,
                    "local_name": entry.local_name,
                    "uri": entry.uri,
                    "description": entry.description,
                    "mime_type": entry.mime_type,
                    "metadata": entry.metadata,
                }
                for entry in self.resource_entries()
            ],
            "prompts": [
                {
                    "qualified_name": entry.qualified_name,
                    "connection_id": entry.connection_id,
                    "local_name": entry.local_name,
                    "description": entry.description,
                    "arguments": entry.arguments,
                    "metadata": entry.metadata,
                }
                for entry in self.prompt_entries()
            ],
            "connections": [
                {
                    "connection_id": snapshot.connection_id,
                    "fetched_at_epoch_ms": snapshot.fetched_at_epoch_ms,
                    "max_age_seconds": snapshot.max_age_seconds,
                    "metadata": snapshot.metadata,
                }
                for snapshot in sorted(
                    self.snapshots.values(),
                    key=lambda snapshot: snapshot.connection_id,
                )
            ],
        }
