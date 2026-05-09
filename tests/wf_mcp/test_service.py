from __future__ import annotations

import asyncio
import shutil

from wf_core import END, RunStatus
from wf_mcp.broker import WfMcpService
from wf_mcp.models import AuthRecord, ConnectionConfig, RawWorkflowPlan
from wf_mcp.shared.errors import error_payload
from wf_mcp.storage import FileStore

from .test_support import (
    FailingDiscoveryAdapter,
    FakeAdapter,
    echo_tool,
    finalize_tool,
    local_temp_root,
)


def test_service_builds_namespaced_catalog() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "catalog_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool, finalize_tool)

    payload = service.get_catalog().as_payload()
    names = [node["qualified_name"] for node in payload["nodes"]]

    assert names == [
        "demo.personal.echo_tool",
        "demo.personal.finalize_tool",
    ]


def test_service_installs_builtin_stdlib_specs_by_default() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "builtin_store"))

    assert "wf.std" in service.spec_sources
    assert "wf.std.runtime_error" in service.spec_sources["wf.std"].specs
    assert "wf.mcp" in service.spec_sources
    assert "wf.mcp.call_tool" in service.spec_sources["wf.mcp"].specs

    sources = service.list_spec_sources()
    assert {source["id"] for source in sources} == {"wf.mcp", "wf.std"}
    assert all(source["kind"] == "system" for source in sources)


def test_service_can_disable_builtin_stdlib_specs() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "no_builtin_store"),
        include_builtin_specs=False,
    )

    assert "wf.std" not in service.spec_sources
    assert "wf.mcp" not in service.spec_sources
    assert service.list_spec_sources() == []


def test_service_catalog_split_keeps_system_specs_out_of_backend_catalog() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "planner_store"))

    backend_payload = service.get_catalog().as_payload()
    planner_payload = service.get_planner_catalog().as_payload()

    assert backend_payload["nodes"] == []
    assert [node["qualified_name"] for node in planner_payload["nodes"]] == [
        "wf.mcp.call_tool",
        "wf.std.runtime_error",
    ]
    assert [entry.qualified_name for entry in service.list_available_specs()] == [
        "wf.mcp.call_tool",
        "wf.std.runtime_error",
    ]


def test_service_compiles_and_runs_raw_plan() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "run_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool, finalize_tool)

    plan = RawWorkflowPlan(
        name="demo_plan",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        state_schema={
            "fields": {
                "echoed": {"type": "string"},
                "result": {"type": "string"},
            }
        },
        output_schema={
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        },
        start="echo",
        nodes=[
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
                "in_map": {"input.text": "text"},
                "out_map": {"echoed": "state.echoed"},
            },
            {
                "id": "finalize",
                "type": "node",
                "node": "demo.personal.finalize_tool",
                "in_map": {"state.echoed": "echoed"},
                "out_map": {"result": "state.result"},
            },
        ],
        edges=[
            {"from": "echo", "outcome": "ok", "to": "finalize"},
            {"from": "finalize", "outcome": "done", "to": END},
        ],
    )

    run = asyncio.run(service.run_workflow_from_plan(plan, {"text": "hello"}))

    assert run.status == RunStatus.COMPLETED
    assert run.output == {"result": "final:hello"}
    event_kinds = [event.kind for event in service.list_events()]
    assert "workflow_run_started" in event_kinds
    assert "workflow_run_completed" in event_kinds


def test_service_refreshes_catalog_from_adapter() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "adapter_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.save_auth(
        AuthRecord(
            connection_id="demo.personal",
            scheme="token",
            payload={"token": "abc"},
        )
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    payload = service.get_catalog().as_payload()
    assert payload["nodes"] == [
        {
            "qualified_name": "demo.personal.echo_tool",
            "connection_id": "demo.personal",
            "local_name": "echo_tool",
            "title": "Echo Tool",
            "description": "Echo text back",
            "outcomes": ["ok"],
            "input_schema": {
                "properties": {
                    "text": {
                        "description": "Text to echo",
                        "type": "string",
                    }
                },
                "required": ["text"],
                "type": "object",
            },
            "output_schema": {
                "properties": {
                    "echoed": {
                        "description": "Echoed text",
                        "type": "string",
                    }
                },
                "required": ["echoed"],
                "type": "object",
            },
        }
    ]
    assert payload["resources"] == [
        {
            "qualified_name": "demo.personal.resource.welcome",
            "connection_id": "demo.personal",
            "local_name": "resource.welcome",
            "title": "Welcome Resource",
            "uri": "demo://docs/welcome",
            "description": "Welcome resource",
            "mime_type": "text/plain",
            "metadata": {"kind": "static"},
        }
    ]
    assert payload["prompts"] == [
        {
            "qualified_name": "demo.personal.prompt.summarize",
            "connection_id": "demo.personal",
            "local_name": "prompt.summarize",
            "title": "Summarize Prompt",
            "description": "Summarize text",
            "arguments": [
                {
                    "name": "text",
                    "required": True,
                    "description": "Text to summarize",
                }
            ],
            "metadata": {"kind": "template"},
        }
    ]
    assert payload["connections"] == [
        {
            "connection_id": "demo.personal",
            "fetched_at_epoch_ms": payload["connections"][0]["fetched_at_epoch_ms"],
            "max_age_seconds": 300,
            "metadata": {
                "server": "demo",
                "account": "personal",
                "auth_scheme": "token",
            },
        }
    ]
    event_kinds = [event.kind for event in service.list_events()]
    assert "catalog_refresh_started" in event_kinds
    assert "catalog_refresh_completed" in event_kinds


def test_service_catalog_preserves_json_schema_description_metadata() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "schema_doc_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    node = service.get_catalog().as_payload()["nodes"][0]
    assert node["input_schema"]["type"] == "object"
    assert isinstance(node["input_schema"]["properties"], dict)
    assert node["input_schema"]["properties"]["text"]["description"] == "Text to echo"
    assert node["output_schema"]["type"] == "object"
    assert isinstance(node["output_schema"]["properties"], dict)


def test_service_wrapped_tool_adapter_model_validates_simple_schema_types() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "schema_model_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))
    spec = service.spec_sources["demo.personal"].specs["demo.personal.echo_tool"]

    parsed = spec.input_model.model_validate({"text": "hello"})
    assert parsed.model_dump() == {"text": "hello"}
    assert (
        spec.input_model.model_json_schema()["properties"]["text"]["description"]
        == "Text to echo"
    )

    try:
        spec.input_model.model_validate({"text": 123})
    except ValueError as exc:
        assert "text" in str(exc)
    else:
        raise AssertionError(
            "expected generated adapter model to reject non-string text"
        )


def test_service_records_tool_call_events() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "event_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    plan = RawWorkflowPlan(
        name="tool_only_plan",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        state_schema={
            "fields": {
                "echoed": {"type": "string"},
            }
        },
        output_schema={
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        start="echo",
        nodes=[
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
                "in_map": {"input.text": "text"},
                "out_map": {"echoed": "state.echoed"},
            }
        ],
        edges=[
            {"from": "echo", "outcome": "ok", "to": END},
        ],
    )

    run = asyncio.run(service.run_workflow_from_plan(plan, {"text": "hello"}))

    assert run.status == RunStatus.COMPLETED
    tool_events = [
        event for event in service.list_events() if "tool_call" in event.kind
    ]
    assert [event.kind for event in tool_events] == [
        "tool_call_started",
        "tool_call_completed",
    ]
    assert tool_events[0].capability_id == "demo.personal.echo_tool"
    assert tool_events[1].payload["outcome"] == "ok"


def test_service_can_call_upstream_tool_through_wf_mcp_system_node() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "system_tool_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    plan = RawWorkflowPlan(
        name="system_tool_plan",
        input_schema={
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
                "tool_name": {"type": "string"},
                "arguments": {"type": "object"},
            },
            "required": ["connection_id", "tool_name", "arguments"],
        },
        state_schema={
            "fields": {
                "tool_result": {"type": "object"},
            }
        },
        output_schema={
            "type": "object",
            "properties": {"tool_result": {"type": "object"}},
            "required": ["tool_result"],
        },
        start="call_tool",
        nodes=[
            {
                "id": "call_tool",
                "type": "node",
                "node": "wf.mcp.call_tool",
                "in_map": {
                    "input.connection_id": "connection_id",
                    "input.tool_name": "tool_name",
                    "input.arguments": "arguments",
                },
                "out_map": {"output": "state.tool_result"},
            }
        ],
        edges=[
            {"from": "call_tool", "outcome": "ok", "to": END},
            {"from": "call_tool", "outcome": "error", "to": END},
        ],
    )

    run = asyncio.run(
        service.run_workflow_from_plan(
            plan,
            {
                "connection_id": "demo.personal",
                "tool_name": "echo_tool",
                "arguments": {"text": "hello"},
            },
        )
    )

    assert run.status == RunStatus.COMPLETED
    assert run.output["tool_result"]["echoed"] == "hello"


def test_service_can_inspect_resources_and_prompts() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "inspect_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    resources = service.list_resources(connection_id="demo.personal")
    prompts = service.list_prompts(connection_id="demo.personal")

    assert [resource.qualified_name for resource in resources] == [
        "demo.personal.resource.welcome"
    ]
    assert [prompt.qualified_name for prompt in prompts] == [
        "demo.personal.prompt.summarize"
    ]

    resource = service.get_resource("demo.personal.resource.welcome")
    prompt = service.get_prompt("demo.personal.prompt.summarize")

    assert resource.uri == "demo://docs/welcome"
    assert prompt.arguments[0]["name"] == "text"


def test_service_reports_connection_statuses() -> None:
    store = local_temp_root() / "status_store"
    # clear store before test
    shutil.rmtree(store)
    service = WfMcpService(store=FileStore(store))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    before = service.connection_statuses()
    assert before == [
        {
            "connection_id": "demo.personal",
            "server": "demo",
            "account": "personal",
            "enabled": True,
            "has_snapshot": False,
            "fetched_at_epoch_ms": None,
            "max_age_seconds": None,
            "node_count": 0,
            "resource_count": 0,
            "prompt_count": 0,
        }
    ]

    asyncio.run(service.refresh_connection_catalog("demo.personal"))
    after = service.connection_statuses()
    assert after[0]["has_snapshot"] is True
    assert after[0]["node_count"] == 1
    assert after[0]["resource_count"] == 1
    assert after[0]["prompt_count"] == 1


def test_service_can_proxy_resource_reads_and_prompt_gets() -> None:
    store = local_temp_root() / "proxy_store"
    # new store
    shutil.rmtree(store)
    service = WfMcpService(store=FileStore(store))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    resource_result = asyncio.run(
        service.read_resource("demo.personal.resource.welcome")
    )
    prompt_result = asyncio.run(
        service.render_prompt(
            "demo.personal.prompt.summarize",
            arguments={"text": "hello world"},
        )
    )

    assert (
        resource_result["contents"][0]["text"]
        == "Welcome from the fake adapter resource."
    )
    assert (
        prompt_result["messages"][0]["content"]["text"]
        == "Summarize this text:\n\nhello world"
    )

    event_kinds = [event.kind for event in service.list_events()]
    assert "resource_read_started" in event_kinds
    assert "resource_read_completed" in event_kinds
    assert "prompt_get_started" in event_kinds
    assert "prompt_get_completed" in event_kinds


def test_service_can_invoke_raw_method_and_notification() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "raw_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    result = asyncio.run(
        service.invoke_method("demo.personal", "demo.echo", params={"text": "hello"})
    )
    asyncio.run(
        service.send_notification(
            "demo.personal",
            "notifications/progress",
            params={"progress": 1},
        )
    )

    assert result == {"echoed": "hello"}
    event_kinds = [event.kind for event in service.list_events()]
    assert "raw_method_started" in event_kinds
    assert "raw_method_completed" in event_kinds
    assert "raw_notification_started" in event_kinds
    assert "raw_notification_completed" in event_kinds


def test_service_can_call_upstream_tool_directly() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "direct_tool_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    result = asyncio.run(
        service.call_tool(
            "demo.personal",
            "echo_tool",
            arguments={"text": "hello"},
        )
    )

    assert result == {
        "outcome": "ok",
        "output": {"echoed": "hello"},
        "meta": {},
    }
    event_kinds = [event.kind for event in service.list_events()]
    assert "tool_call_started" in event_kinds
    assert "tool_call_completed" in event_kinds


def test_service_records_catalog_refresh_failures() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "refresh_fail_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FailingDiscoveryAdapter())

    try:
        asyncio.run(service.refresh_connection_catalog("demo.personal"))
    except PermissionError as exc:
        assert str(exc) == "Access is denied"
    else:
        raise AssertionError("expected refresh to fail")

    failure_events = [
        event
        for event in service.list_events()
        if event.kind == "catalog_refresh_failed"
    ]
    assert len(failure_events) == 1
    assert failure_events[0].payload == {
        "error_type": "PermissionError",
        "error": "Access is denied",
    }


def test_error_payload_unwraps_exception_group() -> None:
    exc = ExceptionGroup("outer", [PermissionError("Access is denied")])
    assert error_payload(exc) == {
        "error_type": "PermissionError",
        "error": "Access is denied",
    }
