import asyncio

import mcp.types as mcp_types
from fastmcp import Client
from fastmcp.client.transports import FastMCPTransport
from fastmcp.server import create_proxy
from mcp.server.fastmcp import Context, FastMCP
from pydantic import AnyUrl

server = FastMCP("notification-fixture")


@server.tool()
async def emit_notifications_tool(ctx: Context) -> dict[str, bool]:
    await ctx.request_context.session.send_tool_list_changed()
    await ctx.request_context.session.send_resource_list_changed()
    await ctx.request_context.session.send_prompt_list_changed()
    await ctx.request_context.session.send_resource_updated(
        AnyUrl("fixture://docs/welcome")
    )
    await ctx.info("fixture emitted notifications")
    return {"emitted": True}


upstream_seen: list[str] = []
downstream_seen: list[str] = []


async def upstream_message_handler(message: object) -> None:
    if isinstance(message, mcp_types.ServerNotification):
        upstream_seen.append(message.root.method)


async def downstream_message_handler(message: object) -> None:
    if isinstance(message, mcp_types.ServerNotification):
        downstream_seen.append(message.root.method)


upstream_transport = FastMCPTransport(server) # any transport will do, tried python stdio, and fastmcp, both reproduce.


async def prog() -> None:
    upstream_client = Client(
        upstream_transport,
        message_handler=upstream_message_handler,
    )
    proxy = create_proxy(upstream_client)
    downstream_client = Client(
        proxy,
        message_handler=downstream_message_handler,
    )

    async with downstream_client:
        await downstream_client.call_tool("emit_notifications_tool")
    seen = [
        "notifications/tools/list_changed",
        "notifications/resources/list_changed",
        "notifications/prompts/list_changed",
        "notifications/resources/updated",
        "notifications/message",
    ]
    assert upstream_seen == seen
    assert downstream_seen == seen, "bug here: notifications should be forwarded by the proxy"


asyncio.run(prog())
