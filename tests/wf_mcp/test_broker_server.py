from __future__ import annotations

import asyncio
import json
from typing import Any, cast

from wf_artifacts import (
    FileWorkflowArtifactStore,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_mcp.broker import (
    WfMcpService,
    build_service_from_config,
    create_broker_server,
    load_broker_config,
)
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.storage import FileStore

from .test_support import (
    FailingDiscoveryAdapter,
    FakeAdapter,
    echo_tool,
    local_temp_root,
)


def test_load_broker_config_resolves_relative_store_root() -> None:
    tmp_path = local_temp_root() / "broker_config_test"
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "wf_mcp.config.json"
    config_path.write_text(
        json.dumps({
            "store_root": ".broker-store",
            "connections": [
                {
                    "id": "demo.personal",
                    "server": "demo",
                    "account": "personal",
                }
            ],
        }),
        encoding="utf-8",
    )

    config = load_broker_config(config_path)

    assert config.store_root == (tmp_path / ".broker-store").resolve()
    assert [connection.id for connection in config.connections] == ["demo.personal"]


def test_create_broker_server_exposes_tools_resources_and_prompts() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "broker_server_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())
    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    server = create_broker_server(service)

    tools = asyncio.run(server.list_tools())
    resources = asyncio.run(server.list_resources())
    prompts = asyncio.run(server.list_prompts())

    tool_names = {tool.name for tool in tools}
    resource_names = {resource.name for resource in resources}
    prompt_names = {prompt.name for prompt in prompts}

    assert "get_connection_statuses" in tool_names
    assert "refresh_connection_catalog" in tool_names
    assert "get_planner_catalog" in tool_names
    assert "list_sources" in tool_names
    assert "invoke_broker_method" in tool_names
    assert "catalog.all" in resource_names
    assert "events.all" in resource_names
    assert "status.all" in resource_names
    assert "workflow_authoring_guide" in prompt_names
    assert "plan_with_catalog" not in prompt_names

    _content, planner_catalog_raw = asyncio.run(
        server.call_tool("get_planner_catalog", {})
    )
    planner_catalog = cast(dict[str, Any], cast(object, planner_catalog_raw))
    planner_names = [node["qualified_name"] for node in planner_catalog["nodes"]]
    assert "demo.personal.echo_tool" in planner_names
    assert "wf.std.runtime_error" in planner_names

    _content, all_sources_payload_raw = asyncio.run(
        server.call_tool("list_sources", {})
    )
    all_sources_payload = cast(dict[str, Any], cast(object, all_sources_payload_raw))
    all_sources = all_sources_payload["sources"]
    all_source_ids = {source["id"] for source in all_sources}
    assert "wf.admin" in all_source_ids
    assert "demo.personal" in all_source_ids


def test_broker_admin_tools_are_backed_by_wf_admin_source() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "broker_admin_source"))
    server = create_broker_server(service)

    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "get_planner_catalog" in tool_names
    assert (
        "wf.admin.list_sources"
        in service.capability_sources["wf.admin"].capabilities.tools
    )


def test_build_service_from_config_registers_connections() -> None:
    config = BrokerConfig(
        store_root=local_temp_root() / "broker_config_store",
        connections=[
            ConnectionConfig(id="demo.personal", server="demo", account="personal"),
            ConnectionConfig(id="demo.work", server="demo", account="work"),
        ],
    )

    service = build_service_from_config(config)

    ids = [connection.id for connection in service.connections.list_all()]
    assert ids == ["demo.personal", "demo.work"]


def test_broker_refresh_tool_returns_structured_error() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "broker_fail_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FailingDiscoveryAdapter())

    server = create_broker_server(service)

    _content, structured = asyncio.run(
        server.call_tool(
            "refresh_connection_catalog", {"connection_id": "demo.personal"}
        )
    )
    assert structured == {
        "connection_id": "demo.personal",
        "refreshed": False,
        "error_type": "PermissionError",
        "error": "Access is denied",
    }


def test_broker_lists_workflow_artifacts_from_artifact_store() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "broker_artifacts")
    artifact_store.save_artifact(_artifact())
    service = WfMcpService(
        store=FileStore(local_temp_root() / "broker_artifacts_mcp_store"),
        artifact_store=artifact_store,
    )
    server = create_broker_server(service)

    _content, structured = asyncio.run(server.call_tool("list_workflow_artifacts", {}))
    payload = cast(dict[str, Any], cast(object, structured))

    nodes = payload["nodes"]
    assert len(nodes) == 1
    assert nodes[0]["name"] == "workflow.summarize_docs.v1"
    assert nodes[0]["required_sources"] == ["context7"]
    assert "plan" not in nodes[0]


def test_broker_inspects_workflow_artifact_from_artifact_store() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "broker_inspect_artifacts"
    )
    artifact_store.save_artifact(_artifact())
    service = WfMcpService(
        store=FileStore(local_temp_root() / "broker_inspect_mcp_store"),
        artifact_store=artifact_store,
    )
    server = create_broker_server(service)

    _content, structured = asyncio.run(
        server.call_tool(
            "inspect_workflow_artifact",
            {"artifact_id": "summarize_docs", "version": 1},
        )
    )
    artifact = cast(dict[str, Any], cast(object, structured))

    assert artifact["id"] == "summarize_docs"
    assert artifact["version"] == 1
    assert artifact["plan"]["name"] == "summarize_docs"


def test_broker_validates_workflow_deployment_from_artifact_store() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "broker_validate_artifacts"
    )
    artifact_store.save_artifact(_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings=[
                {"logical_source": "context7", "concrete_source": "context7.personal"}
            ],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "broker_validate_mcp_store"),
        artifact_store=artifact_store,
    )
    server = create_broker_server(service)

    _content, structured = asyncio.run(
        server.call_tool(
            "validate_workflow_deployment",
            {"deployment_id": "summarize_docs.personal"},
        )
    )
    payload = cast(dict[str, Any], cast(object, structured))

    assert payload["deployment_id"] == "summarize_docs.personal"
    assert payload["artifact_id"] == "summarize_docs"
    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "source_missing"


def test_broker_saves_workflow_artifact() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "broker_save_artifacts"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "broker_save_mcp_store"),
        artifact_store=artifact_store,
    )
    server = create_broker_server(service)

    _content, structured = asyncio.run(
        server.call_tool(
            "save_workflow_artifact",
            {"artifact": _artifact().model_dump(mode="json")},
        )
    )
    payload = cast(dict[str, Any], cast(object, structured))
    loaded = artifact_store.get_artifact("summarize_docs", 1)

    assert payload["artifact_id"] == "summarize_docs"
    assert payload["version"] == 1
    assert loaded.title == "Summarize Docs"


def test_broker_creates_workflow_artifact_from_plan() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "broker_create_artifact_from_plan"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "broker_create_artifact_mcp_store"),
        artifact_store=artifact_store,
    )
    server = create_broker_server(service)

    _content, structured = asyncio.run(
        server.call_tool(
            "create_workflow_artifact_from_plan",
            {
                "artifact_id": "echo",
                "version": 1,
                "title": "Echo",
                "description": "Echo through a saved plan.",
                "plan": _echo_artifact().plan,
                "outcomes": ["done"],
                "required_capabilities": {
                    "demo.echo_tool": {
                        "logical_source": "demo",
                        "capability_name": "echo_tool",
                        "kind": "node_spec",
                    }
                },
                "created_from_catalog_version": "catalog-1",
            },
        )
    )
    payload = cast(dict[str, Any], cast(object, structured))
    loaded = artifact_store.get_artifact("echo", 1)

    assert payload["artifact_id"] == "echo"
    assert payload["version"] == 1
    assert payload["saved"] is True
    assert loaded.input_schema["properties"]["text"]["type"] == "string"
    assert loaded.output_schema["properties"]["echoed"]["type"] == "string"
    assert loaded.required_capability_map()["demo.echo_tool"].logical_source == "demo"


def test_broker_saves_and_lists_workflow_deployments() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "broker_save_deployments"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "broker_save_deployments_mcp_store"),
        artifact_store=artifact_store,
    )
    server = create_broker_server(service)

    _content, save_structured = asyncio.run(
        server.call_tool(
            "save_workflow_deployment",
            {
                "deployment": WorkflowDeployment(
                    id="summarize_docs.personal",
                    artifact_id="summarize_docs",
                    artifact_version=1,
                    bindings=[
                        {
                            "logical_source": "context7",
                            "concrete_source": "context7.personal",
                        }
                    ],
                ).model_dump(mode="json")
            },
        )
    )
    save_payload = cast(dict[str, Any], cast(object, save_structured))
    _content, list_structured = asyncio.run(
        server.call_tool("list_workflow_deployments", {})
    )
    list_payload = cast(dict[str, Any], cast(object, list_structured))

    assert save_payload["deployment_id"] == "summarize_docs.personal"
    assert list_payload["deployments"][0]["id"] == "summarize_docs.personal"
    binding = list_payload["deployments"][0]["bindings"][0]
    assert binding["logical_source"] == "context7"
    assert binding["concrete_source"] == "context7.personal"


def test_broker_runs_non_interrupting_workflow_deployment() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "broker_run_artifacts"
    )
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "broker_run_mcp_store"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    server = create_broker_server(service)

    _content, structured = asyncio.run(
        server.call_tool(
            "run_workflow_deployment",
            {
                "deployment_id": "echo.personal",
                "workflow_input": {"text": "hello"},
            },
        )
    )
    payload = cast(dict[str, Any], cast(object, structured))

    assert payload["deployment_id"] == "echo.personal"
    assert payload["artifact_id"] == "echo"
    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert payload["diagnostics"] == []
    assert payload["trace_count"] > 0


def test_broker_run_deployment_returns_unrunnable_for_dependency_errors() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "broker_run_unrunnable_artifacts"
    )
    artifact_store.save_artifact(_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings=[
                {"logical_source": "context7", "concrete_source": "context7.personal"}
            ],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "broker_run_unrunnable_mcp_store"),
        artifact_store=artifact_store,
    )
    server = create_broker_server(service)

    _content, structured = asyncio.run(
        server.call_tool(
            "run_workflow_deployment",
            {
                "deployment_id": "summarize_docs.personal",
                "workflow_input": {},
            },
        )
    )
    payload = cast(dict[str, Any], cast(object, structured))

    assert payload["status"] == "unrunnable"
    assert payload["output"] is None
    assert payload["diagnostics"][0]["code"] == "source_missing"


def test_broker_run_deployment_rejects_interrupting_artifacts() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "broker_run_interrupt_artifacts"
    )
    artifact_store.save_artifact(_interrupt_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="approval.personal",
            artifact_id="approval",
            artifact_version=1,
            bindings=[],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "broker_run_interrupt_mcp_store"),
        artifact_store=artifact_store,
    )
    server = create_broker_server(service)

    _content, structured = asyncio.run(
        server.call_tool(
            "run_workflow_deployment",
            {
                "deployment_id": "approval.personal",
                "workflow_input": {"message": "send?"},
            },
        )
    )
    payload = cast(dict[str, Any], cast(object, structured))

    assert payload["status"] == "unsupported"
    assert payload["output"] is None
    assert payload["diagnostics"][0]["code"] == "interrupting_artifact_unsupported"


def test_build_service_from_config_uses_store_root_for_artifacts() -> None:
    store_root = local_temp_root() / "broker_config_artifact_store"
    service = build_service_from_config(
        BrokerConfig(
            store_root=store_root,
            connections=[],
        )
    )

    assert isinstance(service.artifact_store, FileWorkflowArtifactStore)
    assert service.artifact_store.root == store_root


def _artifact() -> WorkflowArtifact:
    return WorkflowArtifact(
        id="summarize_docs",
        version=1,
        title="Summarize Docs",
        description="Summarize retrieved documentation.",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("done",),
        plan={"name": "summarize_docs", "nodes": [], "edges": []},
        required_capabilities={
            "context7.query-docs": RequiredCapability(
                ref="context7.query-docs",
                kind="tool",
                input_schema_hash="sha256:input",
                output_schema_hash="sha256:output",
            )
        },
    )


def _echo_artifact() -> WorkflowArtifact:
    return WorkflowArtifact(
        id="echo",
        version=1,
        title="Echo",
        description="Echo text through a demo capability.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        output_schema={
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        outcomes=("completed",),
        plan={
            "name": "echo",
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            "state_schema": {"fields": {"echoed": {"type": "string"}}},
            "output_schema": {
                "type": "object",
                "properties": {"echoed": {"type": "string"}},
                "required": ["echoed"],
            },
            "start": "echo",
            "nodes": [
                {
                    "id": "echo",
                    "type": "node",
                    "node": "demo.personal.echo_tool",
                    "in_map": {"input.text": "text"},
                    "out_map": {"echoed": "state.echoed"},
                }
            ],
            "edges": [{"from": "echo", "outcome": "ok", "to": "__end__"}],
        },
        required_capabilities={
            "demo.echo_tool": RequiredCapability(
                ref="demo.echo_tool",
                kind="node_spec",
            )
        },
    )


def _interrupt_artifact() -> WorkflowArtifact:
    return WorkflowArtifact(
        id="approval",
        version=1,
        title="Approval",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        output_schema={"type": "object", "properties": {}},
        outcomes=("submitted",),
        plan={
            "name": "approval",
            "input_schema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            "state_schema": {"fields": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "approval",
            "nodes": [
                {
                    "id": "approval",
                    "type": "interrupt",
                    "kind": "approval",
                    "request_map": {"input.message": "message"},
                    "out_map": {},
                    "outcomes": ["submitted"],
                }
            ],
            "edges": [{"from": "approval", "outcome": "submitted", "to": "__end__"}],
        },
    )
