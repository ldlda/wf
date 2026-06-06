from __future__ import annotations

from mcp.types import CallToolResult, TextContent, Tool

from wf_sources_mcp.sdk.converters import tool_result_to_call_result, tool_to_discovered


def test_tool_without_output_schema_exposes_raw_content_schema() -> None:
    tool = Tool(
        name="echo",
        inputSchema={"type": "object", "properties": {}},
    )

    discovered = tool_to_discovered(tool)

    properties = discovered.output_schema["properties"]
    assert properties["content"]["type"] == "array"
    assert "text" not in properties


def test_tool_with_content_only_output_schema_stays_raw() -> None:
    tool = Tool(
        name="echo",
        inputSchema={"type": "object", "properties": {}},
        outputSchema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "array",
                    "description": "Raw MCP content blocks.",
                }
            },
            "required": ["content"],
        },
    )

    discovered = tool_to_discovered(tool)

    properties = discovered.output_schema["properties"]
    assert properties["content"]["type"] == "array"
    assert "text" not in properties
    assert discovered.output_schema["required"] == ["content"]


def test_tool_result_single_text_content_block_stays_in_content() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="Echo: hello")],
    )

    converted = tool_result_to_call_result(result)

    assert converted.outcome == "ok"
    assert "text" not in converted.output
    assert converted.output["content"][0]["type"] == "text"
    assert converted.output["content"][0]["text"] == "Echo: hello"


def test_tool_result_structured_content_is_not_rewritten() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="ignored")],
        structuredContent={"value": "structured"},
    )

    converted = tool_result_to_call_result(result)

    assert converted.output["value"] == "structured"
    assert "text" not in converted.output
