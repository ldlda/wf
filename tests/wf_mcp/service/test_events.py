from __future__ import annotations

from typing import Any, cast

from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_mcp.broker import WfMcpService
from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.runtime import ToolExecutor
from wf_mcp.sdk import ToolCallResult
from wf_mcp.shared.errors import error_payload
from wf_mcp.storage import FileStore

from ..test_support import (
    FailingDiscoveryAdapter,
    FakeAdapter,
    local_temp_root,
)


async def test_service_records_tool_call_events() -> None:
    from wf_core import END, RunStatus

    from ..test_support import input_binding, output_binding
    from .conftest import raw_plan

    service = WfMcpService(store=FileStore(local_temp_root() / "tool_event_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    await service.refresh_connection_catalog("demo.personal")

    plan = raw_plan(
        name="tool_event_plan",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        state_schema={"fields": {"echoed": {"type": "string"}}},
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
                "input": [input_binding("input.text", "text")],
                "output": [output_binding("echoed", "state.echoed")],
            }
        ],
        edges=[{"from": "echo", "outcome": "ok", "to": END}],
    )

    run = await service.run_workflow_from_plan(plan, {"text": "hello"})

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


async def test_service_rejects_text_binding_for_raw_mcp_content_contract() -> None:
    from wf_core import END

    from ..test_support import input_binding, output_binding
    from .conftest import ContentOnlyOutputAdapter, raw_plan

    service = WfMcpService(store=FileStore(local_temp_root() / "raw_content_contract"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", ContentOnlyOutputAdapter())
    await service.refresh_connection_catalog("demo.personal")
    plan = raw_plan(
        name="raw_content_contract",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        state_schema={"properties": {"outline": {"type": "string"}}},
        output_schema={
            "type": "object",
            "properties": {"outline": {"type": "string"}},
            "required": ["outline"],
        },
        output=[
            {
                "target": {"root": "local", "parts": ["outline"]},
                "path": {"root": "state", "parts": ["outline"]},
            }
        ],
        start="echo",
        nodes=[
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
                "input": [input_binding("input.text", "message")],
                "output": [output_binding("text", "state.outline")],
            }
        ],
        edges=[{"from": "echo", "outcome": "ok", "to": END}],
    )

    workflow = service.compile_plan(plan)
    report = workflow.validate_structure()

    assert not report.ok
    assert any(
        "source field 'text' is not declared in node output schema" in issue.message
        for issue in report.errors
    )


async def test_service_can_inspect_resources_and_prompts() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "inspect_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    await service.refresh_connection_catalog("demo.personal")

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


async def test_service_reports_connection_statuses() -> None:
    import shutil

    store = local_temp_root() / "status_store"
    shutil.rmtree(store, ignore_errors=True)
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

    await service.refresh_connection_catalog("demo.personal")
    after = service.connection_statuses()
    assert after[0]["has_snapshot"] is True
    assert after[0]["node_count"] == 1
    assert after[0]["resource_count"] == 1
    assert after[0]["prompt_count"] == 1


async def test_service_can_proxy_resource_reads_and_prompt_gets() -> None:
    import shutil

    store = local_temp_root() / "proxy_store"
    shutil.rmtree(store, ignore_errors=True)
    service = WfMcpService(store=FileStore(store))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    await service.refresh_connection_catalog("demo.personal")

    resource_result = await service.read_resource("demo.personal.resource.welcome")
    prompt_result = await service.render_prompt(
        "demo.personal.prompt.summarize",
        arguments={"text": "hello world"},
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


async def test_service_can_invoke_raw_method_and_notification() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "raw_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    result = await service.invoke_method(
        "demo.personal", "demo.echo", params={"text": "hello"}
    )
    await service.send_notification(
        "demo.personal",
        "notifications/progress",
        params={"progress": 1},
    )

    assert result == {"echoed": "hello"}
    event_kinds = [event.kind for event in service.list_events()]
    assert "raw_method_started" in event_kinds
    assert "raw_method_completed" in event_kinds
    assert "raw_notification_started" in event_kinds
    assert "raw_notification_completed" in event_kinds


async def test_generated_specs_use_injected_tool_executor() -> None:
    class RecordingExecutor:
        def __init__(self) -> None:
            self.payloads: list[dict[str, Any]] = []

        async def call_tool(
            self,
            connection: ConnectionConfig,
            auth: AuthRecord | None,
            tool_name: str,
            payload: dict[str, Any],
        ) -> ToolCallResult:
            self.payloads.append(payload)
            return ToolCallResult(outcome="ok", output={"echoed": payload["text"]})

    executor = RecordingExecutor()
    service = WfMcpService(
        store=FileStore(local_temp_root() / "injected_executor_store"),
        tool_executor=cast(ToolExecutor, executor),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    await service.refresh_connection_catalog("demo.personal")
    spec = service._get_qualified_spec("demo.personal.echo_tool")
    handler = build_async_registry(spec)[spec.name]

    result = await handler(
        {"text": "hello"}, RuntimeContext(current_node_id="echo")
    )

    assert result["outcome"] == "ok"
    assert result["output"]["echoed"] == "hello"
    assert executor.payloads == [{"text": "hello"}]


async def test_service_records_catalog_refresh_failures() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "refresh_fail_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FailingDiscoveryAdapter())

    try:
        await service.refresh_connection_catalog("demo.personal")
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
