from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from mcp.client.session import ClientSession
from mcp.types import (
    CallToolResult,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    TextContent,
    Tool,
)

from tests.wf_mcp.test_support import fixture_server_path
from wf_api import TraceRange, file_workflow_stores
from wf_api.models import RawWorkflowPlan
from wf_config import WorkflowConfigFile
from wf_mcp.broker.config import build_service_from_config
from wf_mcp.broker.server import (
    build_workflow_server_from_config,
    build_workflow_server_from_workflow_config,
    workflow_server_from_service,
)
from wf_mcp.broker.service import WfMcpService
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
)
from wf_server.context import WorkflowServer
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.runtime import McpRuntimePool
from wf_sources_mcp.runtime.factory import PersistentSessionFactory
from wf_sources_mcp.runtime.session import PersistentMcpSession
from wf_sources_mcp.storage import FileAuthStore, FileCatalogStore, FileStore
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app


def _registry_entry(source_id: str, *, enabled: bool = True) -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry.model_validate(
        {
            "id": source_id,
            "kind": "mcp",
            "enabled": enabled,
            "provider": "demo",
            "account": "registry",
            "transport": {"kind": "stdio", "command": "demo-server"},
        }
    )


def _interrupt_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "rpc_restart_approval",
            "input_schema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            "state_schema": {"fields": {}},
            "output_schema": {"type": "object", "properties": {}},
            "outcomes": ["submitted"],
            "start": "approval",
            "nodes": [
                {
                    "id": "approval",
                    "type": "interrupt",
                    "kind": "approval",
                    "request": [
                        {
                            "path": {"root": "input", "parts": ["message"]},
                            "target": {"root": "local", "parts": ["message"]},
                        }
                    ],
                    "resume": [],
                    "outcomes": ["submitted"],
                },
                {"id": "end_submitted", "type": "end", "outcome": "submitted"},
            ],
            "edges": [
                {"from": "approval", "outcome": "submitted", "to": "end_submitted"}
            ],
        }
    )


async def _rpc(client: httpx.AsyncClient, method: str, params: dict) -> dict:
    response = await client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": "test", "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


# ---------------------------------------------------------------------------
# Recording runtime fakes for session-reuse proof
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _CountingMcpClient:
    count: int = 0
    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name="counter",
                    title="Counter",
                    description="Increment a session-local counter.",
                    inputSchema={"type": "object", "properties": {}},
                    outputSchema={
                        "type": "object",
                        "properties": {"count": {"type": "integer"}},
                    },
                )
            ]
        )

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
    ) -> CallToolResult:
        self.tool_calls.append((tool_name, payload))
        if tool_name != "counter":
            raise KeyError(tool_name)
        self.count += 1
        return CallToolResult(
            content=[TextContent(type="text", text=str(self.count))],
            structuredContent={"count": self.count},
        )

    async def list_resources(self) -> ListResourcesResult:
        return ListResourcesResult(resources=[])

    async def list_prompts(self) -> ListPromptsResult:
        return ListPromptsResult(prompts=[])


class _RecordingSessionFactory(PersistentSessionFactory):
    def __init__(self) -> None:
        self.clients: list[_CountingMcpClient] = []
        self.created_connections: list[McpSourceConnection] = []

    async def create(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        self.created_connections.append(connection)
        client = _CountingMcpClient()
        self.clients.append(client)

        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            client=cast(ClientSession, client),
        )


def _runtime_reuse_server(
    tmp_path: Path,
) -> tuple[WorkflowServer, WfMcpService, _RecordingSessionFactory]:
    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[
            ConnectionConfig(
                id="fixture.default",
                server="fixture",
                account="default",
                metadata={
                    "transport": "stdio",
                    "command": "fake-mcp-server",
                },
            )
        ],
    )
    store_roots = config.store_roots
    workflow_stores = file_workflow_stores(store_roots.workflow_root)
    auth_store = FileAuthStore(store_roots.auth_root)
    catalog_store = FileCatalogStore(store_roots.catalog_cache_root)
    factory = _RecordingSessionFactory()
    runtime_pool = McpRuntimePool(factory.create)

    service = WfMcpService(
        store=FileStore(store_roots.auth_root),
        auth_store=auth_store,
        catalog_store=catalog_store,
        artifact_store=workflow_stores.artifact_store,
        draft_workspace_store=workflow_stores.draft_workspace_store,
        run_store=workflow_stores.run_store,
        tool_executor=runtime_pool,
        stateful_runtime=runtime_pool,
    )
    service.register_connection(config.connections[0])
    source_registry_store = FileSourceRegistryStore(store_roots.source_registry_root)
    server = workflow_server_from_service(
        service,
        config=config,
        source_registry_store=source_registry_store,
    )
    return server, service, factory


async def test_mcp_backed_rpc_lists_and_mutates_source_registry(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    FileSourceRegistryStore(config.store_root).save_registry(
        SourceRegistryFile(sources=[_registry_entry("demo.registry")])
    )
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc",
            http_client=http_client,
        )

        listed = await client.list_registry_entries(limit=10)
        disabled = await client.disable_registry_entry(source_id="demo.registry")
        inspected = await client.inspect_registry_entry(source_id="demo.registry")

    assert listed["entries"][0]["id"] == "demo.registry"
    assert disabled["entry"]["enabled"] is False
    assert inspected["entry"]["enabled"] is False


async def test_mcp_backed_rpc_capability_list_filters_by_source(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc",
            http_client=http_client,
        )
        listed = await client.list_capabilities(source_id="wf.std", limit=100)

    assert listed["capabilities"]
    assert {capability["source_id"] for capability in listed["capabilities"]} == {
        "wf.std"
    }


async def test_mcp_backed_rpc_reports_connections_and_events(tmp_path) -> None:
    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[
            ConnectionConfig(
                id="demo.default",
                server="demo",
                account="default",
            )
        ],
    )
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        connections = await _rpc(http_client, "workflow.admin.connections.list", {})

    assert connections["result"]["connections"][0]["id"] == "demo.default"


async def test_mcp_backed_rpc_applies_source_registry_changes(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await _rpc(
            client,
            "workflow.admin.source_registry.add",
            {
                "entry": {
                    "kind": "mcp",
                    "id": "dynamic.default",
                    "enabled": True,
                    "provider": "dynamic",
                    "account": "default",
                    "transport": {
                        "kind": "stdio",
                        "command": "dynamic-server",
                        "args": [],
                        "env": {},
                    },
                }
            },
        )
        before = await _rpc(
            client,
            "workflow.sources.list",
            {"limit": 50},
        )
        applied = await _rpc(
            client,
            "workflow.admin.source_registry.apply",
            {},
        )
        after = await _rpc(
            client,
            "workflow.sources.list",
            {"limit": 50},
        )

    before_ids = {source["id"] for source in before["result"]["sources"]}
    after_ids = {source["id"] for source in after["result"]["sources"]}
    assert "dynamic.default" not in before_ids
    assert applied["result"]["registered"] == ["dynamic.default"]
    assert "dynamic.default" in after_ids


async def test_mcp_backed_rpc_can_be_built_from_neutral_workflow_config(
    tmp_path,
) -> None:
    workflow_config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "mcp",
                        "id": "demo.default",
                        "provider": "demo",
                        "account": "default",
                        "transport": {"kind": "stdio", "command": "demo-server"},
                    }
                ],
            },
        }
    )
    server = build_workflow_server_from_workflow_config(workflow_config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        connections = await _rpc(http_client, "workflow.admin.connections.list", {})

    assert connections["result"]["connections"][0]["id"] == "demo.default"


async def test_mcp_backed_rpc_resumes_interrupted_run_after_server_rebuild(
    tmp_path,
) -> None:
    workflow_config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [],
            },
        }
    )
    first_server = build_workflow_server_from_workflow_config(workflow_config)
    await first_server.api.create_artifact_from_plan(
        artifact_id="rpc_restart_approval",
        version=1,
        title="RPC Restart Approval",
        plan=_interrupt_plan(),
        outcomes=["submitted"],
    )
    await first_server.api.save_deployment(
        {
            "id": "rpc_restart_approval.default",
            "artifact_id": "rpc_restart_approval",
            "artifact_version": 1,
            "bindings": [],
        }
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_rpc_app(first_server)),
        base_url="http://test",
    ) as http_client:
        first_client = RpcWorkflowApiClient(
            url="http://test/rpc",
            http_client=http_client,
        )
        started = await first_client.run_deployment(
            deployment_id="rpc_restart_approval.default",
            workflow_input={"message": "approve after restart?"},
        )

    assert started["status"] == "interrupted"
    assert started["interrupt"]["payload"]["message"] == "approve after restart?"

    rebuilt_server = build_workflow_server_from_workflow_config(workflow_config)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_rpc_app(rebuilt_server)),
        base_url="http://test",
    ) as http_client:
        rebuilt_client = RpcWorkflowApiClient(
            url="http://test/rpc",
            http_client=http_client,
        )
        inspected = await rebuilt_client.inspect_run(run_id=started["run_id"])
        resumed = await rebuilt_client.resume_run(
            run_id=started["run_id"],
            resume_payload={},
        )

    assert inspected["status"] == "interrupted"
    assert inspected["run_id"] == started["run_id"]
    assert resumed["run_id"] == started["run_id"]
    assert resumed["status"] == "completed"
    assert resumed["outcome"] == "submitted"


async def test_mcp_backed_rpc_workflow_reuses_runtime_session_across_runs(
    tmp_path,
) -> None:
    server, service, factory = _runtime_reuse_server(tmp_path)
    await service.refresh_connection_catalog("fixture.default")

    assert len(factory.clients) == 1
    assert factory.created_connections[0].id == "fixture.default"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_rpc_app(server)),
        base_url="http://test",
    ) as http_client:
        client = RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)

        created = await client.create_draft_workspace_from_capability(
            workspace_id="counter_ws",
            capability_name="fixture.default.counter",
            name="counter_workflow",
            title="Counter Workflow",
        )
        assert created["workspace_id"] == "counter_ws"

        artifact = await client.create_artifact_from_workspace(
            workspace_id="counter_ws",
            artifact_id="counter_workflow",
            version=1,
            title="Counter Workflow",
            outcomes=["ok", "error"],
            kind="workflow",
        )
        assert artifact.get("saved", True) is not False

        await client.save_deployment(
            {
                "id": "counter_workflow.default",
                "artifact_id": "counter_workflow",
                "artifact_version": 1,
                "bindings": [
                    {
                        "logical_source": "fixture.default",
                        "concrete_source": "fixture.default",
                    },
                    {"logical_source": "wf.std", "concrete_source": "wf.std"},
                ],
            }
        )

        first = await client.run_deployment(
            deployment_id="counter_workflow.default",
            workflow_input={},
        )
        second = await client.run_deployment(
            deployment_id="counter_workflow.default",
            workflow_input={},
        )

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert first["output"]["count"] == 1
    assert second["output"]["count"] == 2
    assert len(factory.clients) == 1
    assert len(factory.created_connections) == 1
    assert factory.clients[0].tool_calls == [
        ("counter", {}),
        ("counter", {}),
    ]


async def test_mcp_backed_rpc_workflow_reuses_runtime_session_direct_setup(
    tmp_path,
) -> None:
    server, service, factory = _runtime_reuse_server(tmp_path)
    await service.refresh_connection_catalog("fixture.default")

    assert len(factory.clients) == 1

    await server.api.create_artifact_from_plan(
        artifact_id="counter_workflow",
        version=1,
        title="Counter Workflow",
        plan=RawWorkflowPlan.model_validate(
            {
                "name": "counter_workflow",
                "input_schema": {"type": "object", "properties": {}},
                "state_schema": {
                    "fields": {
                        "count": {"type": "integer", "reducer": "wf.std.replace"}
                    }
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"count": {"type": "integer"}},
                },
                "outcomes": ["ok", "error"],
                "output": [
                    {
                        "path": {"root": "state", "parts": ["count"]},
                        "target": {"root": "local", "parts": ["count"]},
                    }
                ],
                "start": "run_counter",
                "nodes": [
                    {
                        "id": "run_counter",
                        "type": "node",
                        "node": "fixture.default.counter",
                        "input": [],
                        "output": [
                            {
                                "source": {"root": "local", "parts": ["count"]},
                                "target": {"root": "state", "parts": ["count"]},
                            }
                        ],
                    },
                    {"id": "end_ok", "type": "end", "outcome": "ok"},
                    {"id": "end_error", "type": "end", "outcome": "error"},
                ],
                "edges": [
                    {"from": "run_counter", "outcome": "ok", "to": "end_ok"},
                    {"from": "run_counter", "outcome": "error", "to": "end_error"},
                ],
            }
        ),
        outcomes=["ok", "error"],
    )
    await server.api.save_deployment(
        {
            "id": "counter_workflow.default",
            "artifact_id": "counter_workflow",
            "artifact_version": 1,
            "bindings": [
                {
                    "logical_source": "fixture.default",
                    "concrete_source": "fixture.default",
                },
                {"logical_source": "wf.std", "concrete_source": "wf.std"},
            ],
        }
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_rpc_app(server)),
        base_url="http://test",
    ) as http_client:
        client = RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)

        first = await client.run_deployment(
            deployment_id="counter_workflow.default",
            workflow_input={},
        )
        second = await client.run_deployment(
            deployment_id="counter_workflow.default",
            workflow_input={},
        )

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert first["output"]["count"] == 1
    assert second["output"]["count"] == 2
    assert len(factory.clients) == 1
    assert len(factory.created_connections) == 1
    assert factory.clients[0].tool_calls == [
        ("counter", {}),
        ("counter", {}),
    ]


async def test_mcp_backed_rpc_deployment_becomes_unrunnable_after_source_removed(
    tmp_path,
) -> None:
    server, service, _factory = _runtime_reuse_server(tmp_path)
    await service.refresh_connection_catalog("fixture.default")
    await server.api.create_artifact_from_plan(
        artifact_id="counter_removed_source",
        version=1,
        title="Counter Removed Source",
        plan=RawWorkflowPlan.model_validate(
            {
                "name": "counter_removed_source",
                "input_schema": {"type": "object", "properties": {}},
                "state_schema": {
                    "fields": {
                        "count": {"type": "integer", "reducer": "wf.std.replace"}
                    }
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"count": {"type": "integer"}},
                },
                "outcomes": ["ok", "error"],
                "output": [
                    {
                        "path": {"root": "state", "parts": ["count"]},
                        "target": {"root": "local", "parts": ["count"]},
                    }
                ],
                "start": "run_counter",
                "nodes": [
                    {
                        "id": "run_counter",
                        "type": "node",
                        "node": "fixture.default.counter",
                        "input": [],
                        "output": [
                            {
                                "source": {"root": "local", "parts": ["count"]},
                                "target": {"root": "state", "parts": ["count"]},
                            }
                        ],
                    },
                    {"id": "end_ok", "type": "end", "outcome": "ok"},
                    {"id": "end_error", "type": "end", "outcome": "error"},
                ],
                "edges": [
                    {"from": "run_counter", "outcome": "ok", "to": "end_ok"},
                    {"from": "run_counter", "outcome": "error", "to": "end_error"},
                ],
            }
        ),
        outcomes=["ok", "error"],
    )
    await server.api.save_deployment(
        {
            "id": "counter_removed_source.default",
            "artifact_id": "counter_removed_source",
            "artifact_version": 1,
            "bindings": [
                {
                    "logical_source": "fixture.default",
                    "concrete_source": "fixture.default",
                },
                {"logical_source": "wf.std", "concrete_source": "wf.std"},
            ],
        }
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_rpc_app(server)),
        base_url="http://test",
    ) as http_client:
        client = RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)

        before = await client.validate_deployment(
            deployment_id="counter_removed_source.default"
        )
        service.connection_service.sync_connections_from_config(
            BrokerConfig(store_root=tmp_path / "store", connections=[])
        )
        after = await client.validate_deployment(
            deployment_id="counter_removed_source.default"
        )

    assert before["status"] == "runnable"
    assert after["status"] == "unrunnable"
    assert after["diagnostics"]


async def test_mcp_backed_rpc_workflow_reuses_real_stdio_fixture_session(
    tmp_path,
) -> None:
    """The real stdio MCP fixture must keep server-local state across RPC runs."""

    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            )
        ],
    )
    service = build_service_from_config(config)
    try:
        await service.refresh_connection_catalog("fixture.personal")
    except PermissionError as exc:
        pytest.skip(f"stdio MCP transport is not permitted in this environment: {exc}")
    server = workflow_server_from_service(
        service,
        config=config,
        source_registry_store=FileSourceRegistryStore(config.store_root),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_rpc_app(server)),
        base_url="http://test",
    ) as http_client:
        client = RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)

        await client.create_draft_workspace_from_capability(
            workspace_id="remember_ws",
            capability_name="fixture.personal.remember_value_tool",
            name="remember_workflow",
            title="Remember Workflow",
        )
        await client.create_artifact_from_workspace(
            workspace_id="remember_ws",
            artifact_id="remember_workflow",
            version=1,
            title="Remember Workflow",
            outcomes=["ok", "error"],
            kind="workflow",
        )
        await client.save_deployment(
            {
                "id": "remember_workflow.default",
                "artifact_id": "remember_workflow",
                "artifact_version": 1,
                "bindings": [
                    {
                        "logical_source": "fixture.personal",
                        "concrete_source": "fixture.personal",
                    },
                    {"logical_source": "wf.std", "concrete_source": "wf.std"},
                ],
            }
        )

        await client.create_draft_workspace_from_capability(
            workspace_id="recall_ws",
            capability_name="fixture.personal.recall_value_tool",
            name="recall_workflow",
            title="Recall Workflow",
        )
        await client.create_artifact_from_workspace(
            workspace_id="recall_ws",
            artifact_id="recall_workflow",
            version=1,
            title="Recall Workflow",
            outcomes=["ok", "error"],
            kind="workflow",
        )
        await client.save_deployment(
            {
                "id": "recall_workflow.default",
                "artifact_id": "recall_workflow",
                "artifact_version": 1,
                "bindings": [
                    {
                        "logical_source": "fixture.personal",
                        "concrete_source": "fixture.personal",
                    },
                    {"logical_source": "wf.std", "concrete_source": "wf.std"},
                ],
            }
        )

        remembered = await client.run_deployment(
            deployment_id="remember_workflow.default",
            workflow_input={"value": "held-through-rpc"},
        )
        recalled = await client.run_deployment(
            deployment_id="recall_workflow.default",
            workflow_input={},
        )
        recall_trace = await client.read_run_trace(
            run_id=recalled["run_id"],
            trace_range=TraceRange(start=0, limit=5),
        )

    assert remembered["status"] == "completed"
    assert recalled["status"] == "completed"
    assert recall_trace["trace"][0]["output"]["remembered"] == "held-through-rpc"
