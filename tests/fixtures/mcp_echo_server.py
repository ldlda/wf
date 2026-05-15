from __future__ import annotations

from typing import Annotated, TypedDict

import mcp.types as mcp_types
from mcp.server.fastmcp import FastMCP
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
        mcp_types.ResourceLink.model_validate(
            {
                "type": "resource_link",
                "name": "resource.welcome",
                "uri": "fixture://docs/welcome",
                "mimeType": "text/plain",
            }
        )
    ]


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
