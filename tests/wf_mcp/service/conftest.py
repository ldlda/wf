from __future__ import annotations

import asyncio
import shutil
from typing import Any, cast

from wf_artifacts import FileDraftWorkspaceStore, WorkflowDeployment
from wf_authoring import NodeSpec, build_async_registry, node
from wf_core import END, NodeUse, RunStatus, RuntimeContext
from wf_mcp.broker import WfMcpService
from wf_mcp.capabilities import DiscoveredTool
from wf_mcp.models import AuthRecord, ConnectionConfig, RawWorkflowPlan
from wf_mcp.runtime import ToolExecutor
from wf_mcp.sdk import ToolCallResult
from wf_mcp.shared.errors import error_payload
from wf_mcp.storage import FileStore
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourceVisibility,
)

from ..test_support import (
    EchoInput,
    EchoOutput,
    FailingDiscoveryAdapter,
    FakeAdapter,
    echo_tool,
    finalize_tool,
    input_binding,
    local_temp_root,
    output_binding,
)


@node(name="foo.bar")
def pro_dotted_echo_tool(payload: EchoInput) -> EchoOutput:
    return EchoOutput(echoed=f"pro:{payload.text}")


class ContentOnlyOutputAdapter(FakeAdapter):
    """Adapter fixture for MCP tools that expose the raw content envelope."""

    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        return [
            DiscoveredTool(
                name="echo_tool",
                title="Echo Tool",
                description="Echo text back",
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


def single_echo_plan(plan_name: str, node_name: str) -> RawWorkflowPlan:
    return raw_plan(
        name=plan_name,
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
                "node": node_name,
                "input": [input_binding("input.text", "text")],
                "output": [output_binding("echoed", "state.echoed")],
            }
        ],
        edges=[
            {"from": "echo", "outcome": "ok", "to": END},
        ],
    )


def raw_plan(**payload: object) -> RawWorkflowPlan:
    """Parse JSON-shaped workflow input through the public typed boundary."""
    return RawWorkflowPlan.model_validate(payload)
