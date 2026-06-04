from __future__ import annotations

import httpx

from wf_config import WorkflowConfigFile
from wf_mcp.broker.server import build_workflow_server_from_config, build_workflow_server_from_workflow_config
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
)
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


async def _rpc(client: httpx.AsyncClient, method: str, params: dict) -> dict:
    response = await client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": "test", "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


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
        connections = await _rpc(
            http_client, "workflow.admin.connections.list", {}
        )
        events = await _rpc(http_client, "workflow.admin.events.list", {})

    assert connections["result"]["connections"][0]["id"] == "demo.default"
    assert any(
        event["kind"] == "connection_registered"
        for event in events["result"]["events"]
    )


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
        connections = await _rpc(
            http_client, "workflow.admin.connections.list", {}
        )

    assert connections["result"]["connections"][0]["id"] == "demo.default"
