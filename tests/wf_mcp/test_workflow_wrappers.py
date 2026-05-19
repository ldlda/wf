from __future__ import annotations

import asyncio
from typing import Any, cast

from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_mcp.capabilities import DiscoveredTool
from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.sdk import BackendAdapter, ToolCallResult
from wf_mcp.workflow import wrap_discovered_tool


class RecordingAdapter:
    """Tiny adapter fake that records exactly what MCP payload would be sent."""

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
        return ToolCallResult(outcome="ok", output={})


def test_discovered_tool_wrapper_omits_unset_optional_arguments() -> None:
    adapter = RecordingAdapter()
    spec = wrap_discovered_tool(
        connection=ConnectionConfig(
            id="playwright.default",
            server="playwright",
            account="default",
        ),
        auth=None,
        adapter=cast(BackendAdapter, adapter),
        tool=DiscoveredTool(
            name="browser_snapshot",
            title=None,
            description=None,
            input_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "depth": {"type": "integer"},
                },
            },
            output_schema={"type": "object", "properties": {}},
        ),
    )
    handler = build_async_registry(spec)[spec.name]

    async def run_calls() -> None:
        await handler({}, RuntimeContext(current_node_id="snapshot"))
        await handler(
            {"target": "main"},
            RuntimeContext(current_node_id="snapshot"),
        )

    asyncio.run(run_calls())

    assert adapter.payloads[0] == {}
    assert adapter.payloads[1] == {"target": "main"}
