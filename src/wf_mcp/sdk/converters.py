from __future__ import annotations

from typing import Any

from mcp.types import CallToolResult as McpCallToolResult
from mcp.types import Prompt as McpPrompt
from mcp.types import Resource as McpResource
from mcp.types import Tool as McpTool

from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool

from .base import ToolCallResult


def tool_to_discovered(tool: McpTool) -> DiscoveredTool:
    """Convert an MCP SDK tool into the broker discovery model."""
    output_schema = workflow_output_schema_from_mcp_tool_schema(tool.outputSchema)
    display_name = (
        tool.annotations.title
        if tool.annotations is not None and tool.annotations.title
        else tool.title
    )
    return DiscoveredTool(
        name=tool.name,
        title=display_name,
        description=tool.description,
        input_schema=tool.inputSchema,
        output_schema=output_schema,
        outcomes=("ok", "error"),
        metadata=tool.model_dump(by_alias=True, mode="json"),
    )


def workflow_output_schema_from_mcp_tool_schema(
    schema: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the MCP tool output schema without inventing workflow fields.

    MCP tools without structured output expose raw content blocks. Those blocks
    can be text, images, resource links, or mixed results, so wf_mcp must not
    pretend there is a stable top-level ``text`` field. Workflow authors should
    add an explicit wrapper/extraction node for the block shape they expect.
    """
    return schema or {
        "type": "object",
        "properties": {"content": {"type": "array"}},
    }


def resource_to_discovered(resource: McpResource) -> DiscoveredResource:
    """Convert an MCP SDK resource into the broker discovery model."""
    local_name = resource.name or str(resource.uri)
    return DiscoveredResource(
        uri=str(resource.uri),
        name=local_name,
        title=resource.title,
        description=resource.description,
        mime_type=resource.mimeType,
        metadata=resource.model_dump(by_alias=True, mode="json"),
    )


def prompt_to_discovered(prompt: McpPrompt) -> DiscoveredPrompt:
    """Convert an MCP SDK prompt into the broker discovery model."""
    arguments = [
        argument.model_dump(by_alias=True, mode="json")
        for argument in prompt.arguments or []
    ]
    return DiscoveredPrompt(
        name=prompt.name,
        title=prompt.title,
        description=prompt.description,
        arguments=arguments,
        metadata=prompt.model_dump(by_alias=True, mode="json"),
    )


def tool_result_to_call_result(result: McpCallToolResult) -> ToolCallResult:
    """Convert an MCP SDK tool call result into the adapter result model."""
    if result.structuredContent is not None:
        output = result.structuredContent
    else:
        output: dict[str, Any] = {
            "content": [item.model_dump(by_alias=True) for item in result.content]
        }
    return ToolCallResult(
        outcome="error" if result.isError else "ok",
        output=output,
        meta=result.meta or {},
    )
