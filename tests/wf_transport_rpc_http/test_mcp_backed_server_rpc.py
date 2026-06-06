from __future__ import annotations

import httpx

from wf_api.models import RawWorkflowPlan
from wf_config import WorkflowConfigFile
from wf_mcp.broker.server import (
    build_workflow_server_from_config,
    build_workflow_server_from_workflow_config,
)
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
