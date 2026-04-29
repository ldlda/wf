from __future__ import annotations

from mcp.server.fastmcp import FastMCP


server = FastMCP("echo-fixture")


@server.tool()
async def echo_tool(text: str) -> dict[str, str]:
    return {"echoed": text}


@server.resource(
    "fixture://docs/welcome",
    name="resource.welcome",
    description="Welcome text resource for fixture tests.",
    mime_type="text/plain",
)
def welcome_resource() -> str:
    return "Welcome from the fixture MCP server."


@server.prompt(
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
