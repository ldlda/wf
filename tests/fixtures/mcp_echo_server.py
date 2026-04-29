from __future__ import annotations

from mcp.server.fastmcp import FastMCP


server = FastMCP("echo-fixture")


@server.tool()
async def echo_tool(text: str) -> dict[str, str]:
    return {"echoed": text}


if __name__ == "__main__":
    server.run("stdio")
