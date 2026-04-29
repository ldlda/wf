from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from wf_authoring import NodeSpec, build_async_registry
from wf_core import NodeUse, Workflow, execute_workflow_async

from .adapters import BackendAdapter
from .catalog import CombinedCatalog, snapshot_from_specs
from .connections import ConnectionRegistry, parse_connection_id, qualify_node_name
from .models import AuthRecord, CatalogSnapshot, ConnectionConfig, RawWorkflowPlan
from .store import Store
from .wrappers import wrap_discovered_tool


def _qualify_spec(connection_id: str, spec: NodeSpec[Any, Any]) -> NodeSpec[Any, Any]:
    return NodeSpec(
        name=qualify_node_name(connection_id, spec.name),
        input_model=spec.input_model,
        output_model=spec.output_model,
        outcomes=spec.outcomes,
        fn=spec.fn,
        description=spec.description,
        is_async=spec.is_async,
    )


@dataclass(slots=True)
class WfMcpService:
    store: Store
    default_catalog_max_age_seconds: int = 300
    connections: ConnectionRegistry = field(default_factory=ConnectionRegistry)
    adapters: dict[str, BackendAdapter] = field(default_factory=dict)
    specs_by_connection: dict[str, dict[str, NodeSpec[Any, Any]]] = field(
        default_factory=dict
    )

    def register_connection(self, connection: ConnectionConfig) -> None:
        parse_connection_id(connection.id)
        self.connections.register(connection)

    def register_adapter(self, server: str, adapter: BackendAdapter) -> None:
        self.adapters[server] = adapter

    def save_auth(self, record: AuthRecord) -> None:
        self.store.save_auth(record)

    def load_auth(self, connection_id: str) -> AuthRecord | None:
        return self.store.load_auth(connection_id)

    def register_specs(
        self,
        connection_id: str,
        *specs: NodeSpec[Any, Any],
        max_age_seconds: int | None = None,
    ) -> None:
        self.connections.get(connection_id)
        qualified_specs = {
            qualify_node_name(connection_id, spec.name): _qualify_spec(
                connection_id, spec
            )
            for spec in specs
        }
        self.specs_by_connection[connection_id] = qualified_specs
        snapshot = snapshot_from_specs(
            connection_id,
            specs=qualified_specs,
            fetched_at_epoch_ms=int(time.time() * 1000),
            max_age_seconds=max_age_seconds or self.default_catalog_max_age_seconds,
        )
        self.store.save_catalog(snapshot)

    def get_catalog(self) -> CombinedCatalog:
        snapshots: dict[str, CatalogSnapshot] = {}
        for connection in self.connections.list_enabled():
            snapshot = self.store.load_catalog(connection.id)
            if snapshot is not None:
                snapshots[connection.id] = snapshot
        return CombinedCatalog(snapshots=snapshots)

    async def refresh_connection_catalog(
        self,
        connection_id: str,
        *,
        max_age_seconds: int | None = None,
    ) -> None:
        connection = self.connections.get(connection_id)
        adapter = self.adapters.get(connection.server)
        if adapter is None:
            raise KeyError(f"no adapter registered for server {connection.server!r}")

        auth = self.load_auth(connection_id)
        tools = await adapter.list_tools(connection, auth)
        specs = [
            wrap_discovered_tool(
                connection=connection,
                auth=auth,
                adapter=adapter,
                tool=tool,
            )
            for tool in tools
        ]
        self.register_specs(
            connection_id,
            *specs,
            max_age_seconds=max_age_seconds,
        )

    def compile_plan(self, plan: RawWorkflowPlan) -> Workflow:
        node_defs: dict[str, Any] = {}
        for step in plan.nodes:
            if step.get("type") != "node":
                continue
            qualified_name = step["node"]
            spec = self._get_qualified_spec(qualified_name)
            node_defs[qualified_name] = spec.to_node_def()

        payload = {
            "name": plan.name,
            "input_schema": plan.input_schema,
            "state_schema": plan.state_schema,
            "output_schema": plan.output_schema,
            "start": plan.start,
            "node_defs": [node.model_dump() for node in node_defs.values()],
            "nodes": plan.nodes,
            "edges": plan.edges,
        }
        return Workflow.model_validate(payload)

    async def run_workflow_from_plan(
        self,
        plan: RawWorkflowPlan,
        workflow_input: dict[str, Any],
    ):
        workflow = self.compile_plan(plan)
        specs = [
            self._get_qualified_spec(node.node)
            for node in workflow.nodes
            if isinstance(node, NodeUse)
        ]
        registry = build_async_registry(*specs)
        return await execute_workflow_async(workflow, workflow_input, registry)

    def _get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        connection_id, _ = qualified_name.rsplit(".", 1)
        specs = self.specs_by_connection.get(connection_id)
        if specs is None or qualified_name not in specs:
            raise KeyError(f"unknown qualified node {qualified_name!r}")
        return specs[qualified_name]
