from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wf_authoring import NodeReturn, node
from wf_core import END, RuntimeContext, RunStatus
from wf_mcp import (
    AuthRecord,
    ConnectionConfig,
    DiscoveredTool,
    FileStore,
    RawWorkflowPlan,
    ToolCallResult,
    WfMcpService,
)


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    echoed: str


class FinalizeInput(BaseModel):
    echoed: str


class FinalizeOutput(BaseModel):
    result: str


@node()
async def echo_tool(payload: EchoInput, ctx: RuntimeContext) -> EchoOutput:
    return EchoOutput(echoed=payload.text)


@node(outcomes=("done",))
def finalize_tool(
    payload: FinalizeInput, ctx: RuntimeContext
) -> NodeReturn[FinalizeOutput]:
    return NodeReturn(
        outcome="done",
        output=FinalizeOutput(result=f"final:{payload.echoed}"),
    )


def _local_temp_root() -> Path:
    root = Path("test-artifacts") / "wf_mcp_store"
    root.mkdir(parents=True, exist_ok=True)
    return root


class FakeAdapter:
    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        return [
            DiscoveredTool(
                name="echo_tool",
                description="Echo text back",
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
            )
        ]

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        if tool_name != "echo_tool":
            raise KeyError(tool_name)
        return ToolCallResult(
            outcome="ok",
            output={"echoed": str(payload["text"])},
        )


def test_file_store_round_trips_auth() -> None:
    store = FileStore(_local_temp_root() / "auth_store")
    record = AuthRecord(
        connection_id="demo.personal",
        scheme="oauth",
        payload={"token": "secret"},
    )

    store.save_auth(record)
    loaded = store.load_auth("demo.personal")

    assert loaded == record


def test_service_builds_namespaced_catalog() -> None:
    service = WfMcpService(store=FileStore(_local_temp_root() / "catalog_store"))
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
    service = WfMcpService(store=FileStore(_local_temp_root() / "run_store"))
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


def test_service_refreshes_catalog_from_adapter() -> None:
    service = WfMcpService(store=FileStore(_local_temp_root() / "adapter_store"))
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
