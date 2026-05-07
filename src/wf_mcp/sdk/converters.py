from __future__ import annotations

from mcp.types import CallToolResult as McpCallToolResult
from mcp.types import Prompt as McpPrompt
from mcp.types import Resource as McpResource
from mcp.types import Tool as McpTool

from ..capabilities import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from .base import ToolCallResult


def tool_to_discovered(tool: McpTool) -> DiscoveredTool:
    """Convert an MCP SDK tool into the broker discovery model."""
    output_schema = tool.outputSchema or {
        "type": "object",
        "properties": {"content": {"type": "array"}},
    }
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
        output = {
            "content": [item.model_dump(by_alias=True) for item in result.content]
        }
    return ToolCallResult(
        outcome="error" if result.isError else "ok",
        output=output,
        meta=result.meta or {},
    )
