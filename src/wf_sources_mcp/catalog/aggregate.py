from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wf_authoring import NodeCatalog, NodeSpec
from wf_sources_mcp.ids import parse_connection_id

from .entries import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
    DiscoveredPrompt,
    DiscoveredResource,
)
from .models import CatalogSnapshot


def _qualify_local_name(connection_id: str, local_name: str) -> str:
    """Qualify a source-local catalog name without depending on wf_mcp shims."""
    parse_connection_id(connection_id)
    if not local_name:
        raise ValueError("local catalog name must not be empty")
    return f"{connection_id}.{local_name}"


def snapshot_from_specs(
    connection_id: str,
    *,
    specs: dict[str, NodeSpec[Any, Any]],
    tool_display_names: dict[str, str | None] | None = None,
    resources: list[DiscoveredResource] | None = None,
    prompts: list[DiscoveredPrompt] | None = None,
    metadata: dict[str, Any] | None = None,
    fetched_at_epoch_ms: int,
    max_age_seconds: int,
) -> CatalogSnapshot:
    from wf_sources_mcp.sdk.converters import (
        workflow_output_schema_from_mcp_tool_schema,
    )

    catalog = NodeCatalog.from_specs(*specs.values())
    nodes = [
        CatalogNodeEntry(
            qualified_name=entry.name
            if entry.name.startswith(f"{connection_id}.")
            else _qualify_local_name(connection_id, entry.name),
            connection_id=connection_id,
            local_name=entry.name.removeprefix(f"{connection_id}."),
            title=(tool_display_names or {}).get(
                entry.name.removeprefix(f"{connection_id}."),
                entry.display_name,
            ),
            description=entry.description,
            outcomes=entry.outcomes,
            input_schema=entry.input_schema,
            output_schema=workflow_output_schema_from_mcp_tool_schema(
                entry.output_schema
            ),
        )
        for entry in catalog.entries()
    ]
    resource_entries = [
        CatalogResourceEntry(
            qualified_name=_qualify_local_name(connection_id, resource.name),
            connection_id=connection_id,
            local_name=resource.name,
            title=resource.title,
            uri=resource.uri,
            description=resource.description,
            mime_type=resource.mime_type,
            metadata=resource.metadata,
        )
        for resource in resources or []
    ]
    prompt_entries = [
        CatalogPromptEntry(
            qualified_name=_qualify_local_name(connection_id, prompt.name),
            connection_id=connection_id,
            local_name=prompt.name,
            title=prompt.title,
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
                    "title": entry.title,
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
                    "title": entry.title,
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
                    "title": entry.title,
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


__all__ = ["CombinedCatalog", "snapshot_from_specs"]
