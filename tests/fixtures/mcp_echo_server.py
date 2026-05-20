from __future__ import annotations

from typing import Annotated, Any, TypedDict

import mcp.types as mcp_types
from mcp.server.fastmcp import Context, FastMCP
from pydantic import AnyUrl
from pydantic import Field


server = FastMCP("echo-fixture")


class EchoToolResult(TypedDict):
    echoed: str


@server.tool(title="Echo tool")
async def echo_tool(
    text: Annotated[str, Field(description="Text to echo")],
) -> EchoToolResult:
    return {"echoed": text}


@server.tool(title="Resource link tool")
async def resource_link_tool() -> list[mcp_types.ResourceLink]:
    """Return a link to a fixture resource so proxy URI rewriting is testable."""
    return [
        mcp_types.ResourceLink.model_validate({
            "type": "resource_link",
            "name": "resource.welcome",
            "uri": "fixture://docs/welcome",
            "mimeType": "text/plain",
        })
    ]


@server.tool(title="Emit notifications tool")
async def emit_notifications_tool(ctx: Context[Any, Any, Any]) -> dict[str, bool]:
    """Emit protocol notifications so proxy relay behavior can be tested."""
    await ctx.request_context.session.send_tool_list_changed()
    await ctx.request_context.session.send_resource_list_changed()
    await ctx.request_context.session.send_prompt_list_changed()
    await ctx.request_context.session.send_resource_updated(
        AnyUrl("fixture://docs/welcome")
    )
    await ctx.info("fixture emitted notifications")
    return {"emitted": True}


@server.resource(
    "fixture://docs/welcome",
    name="resource.welcome",
    title="Resource Welcome",
    description="Welcome text resource for fixture tests.",
    mime_type="text/plain",
)
def welcome_resource() -> str:
    return "Welcome from the fixture MCP server."


@server.prompt(
    title="Prompt Summarize",
    name="prompt.summarize",
    description="Summarize an input text for fixture tests.",
)
def summarize_prompt(text: str) -> list[dict[str, object]]:
    return [
        {
            "role": "user",
            "content": f"Summarize this text:\n\n{text}",
        }
    ]


if __name__ == "__main__":
    server.run("stdio")
