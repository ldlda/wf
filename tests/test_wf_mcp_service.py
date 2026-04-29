from __future__ import annotations

import asyncio
import shutil

from wf_core import END, RunStatus
from wf_mcp import (
    AuthRecord,
    ConnectionConfig,
    FileStore,
    RawWorkflowPlan,
    WfMcpService,
)
from wf_mcp.error_info import error_payload

from test_wf_mcp_support import (
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
                "additionalProperties": True,
                "properties": {"text": {"title": "Text"}},
                "required": ["text"],
                "title": "demo.personal_echo_tool_Input",
                "type": "object",
            },
            "output_schema": {
                "additionalProperties": True,
                "properties": {"echoed": {"title": "Echoed"}},
                "required": ["echoed"],
                "title": "demo.personal_echo_tool_Output",
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
