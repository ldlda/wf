from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wf_artifacts import (
    FileWorkflowArtifactStore,
    RequiredCapability,
    WorkflowArtifact,
)
from wf_authoring import node, reducer
from wf_mcp.broker import WfMcpService
from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.sdk import ToolCallResult
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers
from wf_mcp.capabilities import DiscoveredTool

from ..test_support import input_binding, output_binding


class AmountInput(BaseModel):
    amount: int


class AmountOutput(BaseModel):
    amount: int


class ChangedEchoInput(BaseModel):
    message: str


class ChangedEchoOutput(BaseModel):
    echoed: str


@node()
async def amount_tool(payload: AmountInput) -> AmountOutput:
    return AmountOutput(amount=payload.amount)


@node(name="echo_tool")
def changed_echo_tool(payload: ChangedEchoInput) -> ChangedEchoOutput:
    return ChangedEchoOutput(echoed=payload.message)


@node(name="mcp_echo_tool", outcomes=("ok", "error"))
def mcp_echo_tool(payload: ChangedEchoInput) -> ChangedEchoOutput:
    """Test fixture that mirrors naive MCP wrappers with ok/error outcomes."""
    return ChangedEchoOutput(echoed=payload.message)


@node(name="failing_tool")
def failing_tool(payload: ChangedEchoInput) -> ChangedEchoOutput:
    raise RuntimeError("upstream exploded")


class ContentOnlyOutputAdapter:
    """MCP-like adapter whose tool exposes raw content blocks as output schema."""

    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        return [
            DiscoveredTool(
                name="echo",
                title="Echo",
                description="Echo a message as an MCP text content block.",
                input_schema={
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"content": {"type": "array"}},
                    "required": ["content"],
                },
            )
        ]

    async def list_resources(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[Any]:
        return []

    async def list_prompts(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[Any]:
        return []

    async def get_connection_metadata(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        return {"server": connection.server}

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        message = payload.get("message", "")
        return ToolCallResult(
            outcome="ok",
            output={"content": [{"type": "text", "text": f"Echo: {message}"}]},
        )

    async def read_resource(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        raise KeyError(uri)

    async def get_prompt(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        raise KeyError(prompt_name)

    async def invoke_method(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise KeyError(method)

    async def send_notification(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        raise KeyError(method)


@reducer(name="custom.default.multiply")
def multiply(current: int | None, incoming: int) -> int:
    return (current or 1) * incoming


def handlers(artifact_store: FileWorkflowArtifactStore) -> WorkflowSurfaceHandlers:
    service = WfMcpService(
        store=FileStore(artifact_store.root / "surface_mcp" / str(id(artifact_store))),
        artifact_store=artifact_store,
    )
    return WorkflowSurfaceHandlers(service)


def artifact() -> WorkflowArtifact:
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


def echo_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
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
                "input": [input_binding("input.text", "text")],
                "output": [output_binding("echoed", "state.echoed")],
            }
        ],
        "edges": [{"from": "echo", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="echo",
        version=1,
        title="Echo",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities={
            "demo.echo_tool": RequiredCapability(
                ref="demo.echo_tool",
                kind="node_spec",
            )
        },
    )


def echo_draft() -> dict[str, Any]:
    return {
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
        "steps": {
            "echo": {
                "use": "demo.personal.echo_tool",
                "input": [
                    {
                        "target": {"root": "local", "parts": ["text"]},
                        "path": {"root": "input", "parts": ["text"]},
                    }
                ],
                "output": [
                    {
                        "source": {"root": "local", "parts": ["echoed"]},
                        "target": {"root": "state", "parts": ["echoed"]},
                    }
                ],
            }
        },
        "routes": {"echo": {"ok": "__end__"}},
    }


def logical_echo_artifact() -> WorkflowArtifact:
    a = echo_artifact()
    plan = dict(a.plan)
    nodes = [dict(node) for node in plan["nodes"]]
    nodes[0]["node"] = "demo.echo_tool"
    plan["nodes"] = nodes
    return a.model_copy(
        update={
            "id": "logical_echo",
            "plan": plan,
        }
    )


def failing_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "fail",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": {
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
        },
        "start": "fail",
        "nodes": [
            {
                "id": "fail",
                "type": "node",
                "node": "demo.personal.failing_tool",
                "input": [input_binding("input.message", "message")],
                "output": [output_binding("echoed", "state.echoed")],
            }
        ],
        "edges": [{"from": "fail", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="fail",
        version=1,
        title="Fail",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities={
            "demo.failing_tool": RequiredCapability(
                ref="demo.failing_tool",
                kind="node_spec",
            )
        },
    )


def custom_reducer_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "multiply",
        "input_schema": {
            "type": "object",
            "properties": {
                "total": {"type": "integer"},
                "amount": {"type": "integer"},
            },
            "required": ["total", "amount"],
        },
        "state_schema": {
            "type": "object",
            "properties": {
                "total": {
                    "type": "integer",
                    "reducer": "custom.multiply",
                }
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {"total": {"type": "integer"}},
            "required": ["total"],
        },
        "start": "amount",
        "nodes": [
            {
                "id": "amount",
                "type": "node",
                "node": "demo.personal.amount_tool",
                "input": [input_binding("input.amount", "amount")],
                "output": [output_binding("amount", "state.total")],
            }
        ],
        "edges": [{"from": "amount", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="multiply",
        version=1,
        title="Multiply",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities={
            "demo.amount_tool": RequiredCapability(
                ref="demo.amount_tool",
                kind="node_spec",
            ),
            "custom.multiply": RequiredCapability(
                ref="custom.multiply",
                kind="reducer",
            ),
        },
    )
