from __future__ import annotations

import asyncio

from wf_core import END, RunStatus
from wf_mcp import (
    AuthRecord,
    ConnectionConfig,
    FileStore,
    RawWorkflowPlan,
    WfMcpService,
)

from test_wf_mcp_support import FakeAdapter, echo_tool, finalize_tool, local_temp_root


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
