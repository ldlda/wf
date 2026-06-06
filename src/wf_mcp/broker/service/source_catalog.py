from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from wf_authoring import NodeReturn, NodeSpec
from wf_mcp.capabilities import (
    CatalogNodeEntry,
    CatalogPromptEntry,
    CatalogResourceEntry,
)
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    DocumentationPrompt,
    DocumentationResource,
    SourcePermissions,
    SourceVisibility,
    page_items,
)

from ...auth import AuthRecord
from ...connections import ConnectionConfig, qualify_node_name
from ...events import McpEvent, make_event
from ...models import (
    CatalogSnapshot,
)
from ...runtime import ToolExecutor
from ...storage import CatalogStore
from ...workflow.wrappers import _model_from_schema
from ..catalog import CombinedCatalog, snapshot_from_specs
from .specs import get_qualified_spec, qualify_spec

ConnectionLookup = Callable[[str], ConnectionConfig]
ConnectionList = Callable[[], list[ConnectionConfig]]
ToolExecutorLookup = Callable[[ConnectionConfig], ToolExecutor]
AuthLoader = Callable[[ConnectionConfig], AuthRecord | None]
EventEmitter = Callable[[McpEvent], None]


@dataclass(slots=True)
class SourceCatalogService:
    """Own service-local capability sources and catalog projections.

    This is deliberately still MCP-broker-internal. It knows about stored MCP
    catalog snapshots because hydrated workflow NodeSpecs must call back through
    the broker's configured tool executor.
    """

    store: CatalogStore
    connection_lookup: ConnectionLookup
    connection_list_enabled: ConnectionList
    connection_list_all: ConnectionList
    tool_executor_for: ToolExecutorLookup
    load_auth: AuthLoader
    emit_event: EventEmitter
    default_catalog_max_age_seconds: int = 300
    capability_sources: dict[str, CapabilitySource] = field(default_factory=dict)

    def register_capability_source(self, source: CapabilitySource) -> None:
        """Register one source as canonical planner/runtime source state."""
        self.capability_sources[source.id] = source

    def get_catalog(self) -> CombinedCatalog:
        snapshots: dict[str, CatalogSnapshot] = {}
        for connection in self.connection_list_enabled():
            snapshot = self.store.load_catalog(connection.id)
            if snapshot is not None:
                snapshots[connection.id] = snapshot
        return CombinedCatalog(snapshots=snapshots)

    def get_planner_catalog(self) -> CombinedCatalog:
        """Return all planner-visible specs, including broker-local sources."""
        snapshots: dict[str, CatalogSnapshot] = {}
        fetched_at_epoch_ms = int(time.time() * 1000)
        for source in self.capability_sources.values():
            if not source.enabled or not source.visibility.planner:
                continue
            stored_snapshot = self.store.load_catalog(source.id)
            snapshots[source.id] = snapshot_from_specs(
                source.id,
                specs=source.capabilities.node_specs,
                tool_display_names={
                    entry.local_name: entry.title for entry in stored_snapshot.nodes
                }
                if stored_snapshot is not None
                else None,
                metadata={
                    "kind": source.kind,
                    "description": source.description,
                }
                if stored_snapshot is None
                else stored_snapshot.metadata,
                fetched_at_epoch_ms=(
                    stored_snapshot.fetched_at_epoch_ms
                    if stored_snapshot is not None
                    else fetched_at_epoch_ms
                ),
                max_age_seconds=(
                    stored_snapshot.max_age_seconds
                    if stored_snapshot is not None
                    else self.default_catalog_max_age_seconds
                ),
            )
            if stored_snapshot is not None:
                snapshots[source.id].resources = list(stored_snapshot.resources)
                snapshots[source.id].prompts = list(stored_snapshot.prompts)
        return CombinedCatalog(snapshots=snapshots)

    def list_sources(self) -> list[dict[str, Any]]:
        """Return every capability source with the names it currently owns."""
        return [
            source.as_inventory().model_dump(mode="json")
            for source in sorted(
                self.capability_sources.values(),
                key=lambda source: source.id,
            )
        ]

    def list_source_summaries(
        self,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return compact paged source summaries for progressive discovery."""
        summaries = [
            source.as_status().model_dump(mode="json")
            for source in sorted(
                self.capability_sources.values(),
                key=lambda source: source.id,
            )
        ]
        page = page_items(summaries, cursor=cursor, limit=limit)
        return {
            "sources": list(page.items),
            "next_cursor": page.next_cursor,
            "total": page.total,
        }

    def inspect_source(self, source_id: str) -> dict[str, Any]:
        """Return the full source inventory for one exact source id."""
        try:
            source = self.capability_sources[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source {source_id!r}") from exc
        return source.as_inventory().model_dump(mode="json")

    def list_available_specs(self) -> list[CatalogNodeEntry]:
        """Return planner-visible node catalog entries from every visible source."""
        return self.get_planner_catalog().entries()

    def get_connection_snapshot(self, connection_id: str) -> CatalogSnapshot | None:
        self.connection_lookup(connection_id)
        return self.store.load_catalog(connection_id)

    def connection_statuses(self) -> list[dict[str, Any]]:
        statuses: list[dict[str, Any]] = []
        for connection in self.connection_list_all():
            snapshot = self.store.load_catalog(connection.id)
            statuses.append(
                {
                    "connection_id": connection.id,
                    "server": connection.server,
                    "account": connection.account,
                    "enabled": connection.enabled,
                    "has_snapshot": snapshot is not None,
                    "fetched_at_epoch_ms": None
                    if snapshot is None
                    else snapshot.fetched_at_epoch_ms,
                    "max_age_seconds": None
                    if snapshot is None
                    else snapshot.max_age_seconds,
                    "node_count": 0 if snapshot is None else len(snapshot.nodes),
                    "resource_count": 0
                    if snapshot is None
                    else len(snapshot.resources),
                    "prompt_count": 0 if snapshot is None else len(snapshot.prompts),
                }
            )
        return statuses

    def list_resources(
        self,
        *,
        connection_id: str | None = None,
    ) -> list[CatalogResourceEntry]:
        if connection_id is None:
            return self.get_catalog().resource_entries()
        snapshot = self.get_connection_snapshot(connection_id)
        if snapshot is None:
            return []
        return sorted(snapshot.resources, key=lambda entry: entry.qualified_name)

    def list_prompts(
        self,
        *,
        connection_id: str | None = None,
    ) -> list[CatalogPromptEntry]:
        if connection_id is None:
            return self.get_catalog().prompt_entries()
        snapshot = self.get_connection_snapshot(connection_id)
        if snapshot is None:
            return []
        return sorted(snapshot.prompts, key=lambda entry: entry.qualified_name)

    def get_resource(self, qualified_name: str) -> CatalogResourceEntry:
        entry = self.get_catalog().find_resource(qualified_name)
        if entry is None:
            raise KeyError(f"unknown resource {qualified_name!r}")
        return entry

    def get_prompt(self, qualified_name: str) -> CatalogPromptEntry:
        entry = self.get_catalog().find_prompt(qualified_name)
        if entry is None:
            raise KeyError(f"unknown prompt {qualified_name!r}")
        return entry

    def hydrate_connection_source_from_snapshot(
        self,
        connection: ConnectionConfig,
    ) -> None:
        """Register one connection source, hydrating specs from snapshot if present."""
        if connection.id in self.capability_sources:
            return

        snapshot = self.store.load_catalog(connection.id)
        specs = {
            entry.qualified_name: self.spec_from_snapshot_entry(entry)
            for entry in (() if snapshot is None else snapshot.nodes)
        }
        description = (
            f"Specs restored from catalog for {connection.id}."
            if specs
            else f"No catalog loaded for {connection.id}."
        )
        self.register_capability_source(
            CapabilitySource(
                id=connection.id,
                kind="connection",
                enabled=connection.enabled,
                capabilities=CapabilityBuckets(node_specs=specs),
                visibility=SourceVisibility(
                    planner=True,
                    mcp_client=True,
                    admin_dashboard=True,
                ),
                permissions=SourcePermissions(calls_upstream=True),
                description=description,
            )
        )

    def spec_from_snapshot_entry(
        self,
        entry: CatalogNodeEntry,
    ) -> NodeSpec[Any, Any]:
        """Rebuild an executable tool wrapper from a stored catalog node entry.

        Snapshot entries store schema/name metadata, not Python functions. This
        helper reconstructs the same generated NodeSpec shape and routes calls
        through `tool_executor_for()`, so hydrated specs use the persistent MCP
        runtime when the service has one configured.
        """
        model_prefix = entry.qualified_name.replace(".", "_").replace("-", "_")
        input_model = _model_from_schema(f"{model_prefix}_Input", entry.input_schema)
        output_schema = entry.output_schema
        output_model = _model_from_schema(f"{model_prefix}_Output", output_schema)

        async def invoke_tool(payload: BaseModel) -> NodeReturn[BaseModel]:
            connection = self.connection_lookup(entry.connection_id)
            auth = self.load_auth(connection)
            result = await self.tool_executor_for(connection).call_tool(
                connection,
                auth,
                entry.local_name,
                payload.model_dump(exclude_unset=True),
            )
            return NodeReturn(
                outcome=result.outcome,
                output=output_model.model_validate(result.output),
            )

        return NodeSpec(
            name=entry.qualified_name,
            input_model=input_model,
            output_model=output_model,
            outcomes=entry.outcomes,
            fn=invoke_tool,
            description=entry.description,
            is_async=True,
            accepts_context=False,
            input_schema_contract=entry.input_schema,
            output_schema_contract=output_schema,
        )

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        return get_qualified_spec(self.capability_sources, qualified_name)

    def register_specs(
        self,
        connection_id: str,
        *specs: NodeSpec[Any, Any],
        max_age_seconds: int | None = None,
        emit_change_events: bool = True,
        record_catalog_change_events: Callable[
            [str, CatalogSnapshot, str],
            None,
        ]
        | None = None,
    ) -> CatalogSnapshot:
        self.connection_lookup(connection_id)
        qualified_specs = {
            qualify_node_name(connection_id, spec.name): qualify_spec(
                connection_id, spec
            )
            for spec in specs
        }
        existing_source = self.capability_sources.get(connection_id)
        if existing_source is not None:
            existing_source.capabilities.node_specs = qualified_specs
        else:
            self.register_capability_source(
                CapabilitySource(
                    id=connection_id,
                    kind="connection",
                    capabilities=CapabilityBuckets(node_specs=qualified_specs),
                    enabled=self.connection_lookup(connection_id).enabled,
                    visibility=SourceVisibility(
                        planner=True,
                        mcp_client=True,
                        admin_dashboard=True,
                    ),
                    permissions=SourcePermissions(calls_upstream=True),
                    description=(
                        f"Specs discovered or registered for {connection_id}."
                    ),
                )
            )
        snapshot = snapshot_from_specs(
            connection_id,
            specs=qualified_specs,
            fetched_at_epoch_ms=int(time.time() * 1000),
            max_age_seconds=max_age_seconds or self.default_catalog_max_age_seconds,
        )
        self.store.save_catalog(snapshot)
        self.emit_event(
            make_event(
                "specs_registered",
                connection_id=connection_id,
                payload={"node_count": len(qualified_specs)},
            )
        )
        if emit_change_events and record_catalog_change_events is not None:
            record_catalog_change_events(connection_id, snapshot, "specs_registered")
        return snapshot

    def local_documentation_resource(
        self,
        qualified_name: str,
    ) -> DocumentationResource | None:
        """Return a local docs resource from capability sources by qualified name."""
        for source in self.capability_sources.values():
            resource = source.capabilities.resources.get(qualified_name)
            if isinstance(resource, DocumentationResource):
                return resource
        return None

    def local_documentation_prompt(
        self,
        qualified_name: str,
    ) -> DocumentationPrompt | None:
        """Return a local docs prompt from capability sources by qualified name."""
        for source in self.capability_sources.values():
            prompt = source.capabilities.prompts.get(qualified_name)
            if isinstance(prompt, DocumentationPrompt):
                return prompt
        return None
