---
title: Should proxies forward upstream list/resource notifications downstream?
---

## summary

An upstream client used by a FastMCP proxy receives ordinary server
notifications correctly.
However, the downstream client connected to the proxy does not receive those
notifications.

I am not sure whether this is intended or just not implemented yet. The proxy
docs mention automatic forwarding for roots, sampling, elicitation, logging,
and progress, but I could not tell whether list/resource notifications are
meant to be forwarded too.

Tested on FastMCP `3.3.0`.

## minimal example

The upstream fixture emits ordinary MCP server notifications from one tool call:

```python
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
```

When called directly, a client can observe all of them.

With a proxy in the middle:

```python
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
```

the upstream-side handler still observes the notifications, but the downstream
handler observes none.

## observed behavior

```text
upstream_seen == [
  "notifications/tools/list_changed",
  "notifications/resources/list_changed",
  "notifications/prompts/list_changed",
  "notifications/resources/updated",
  "notifications/message",
]

downstream_seen == []
```

## question

Should a FastMCP proxy forward these upstream notifications to the downstream
client, or is the current behavior intentional?

## why i expected forwarding

From the downstream client's point of view, the upstream server's visible
surface can change while it is behind the proxy:

- tool list changes
- resource list changes
- prompt list changes
- a subscribed resource updates

If those notifications are not forwarded, a downstream client connected through
the proxy cannot react the same way it could when connected to the upstream
server directly.

## possible expected behavior

Server notifications received by the upstream side of a FastMCP proxy should be
forwarded to the downstream client, or there should be a supported proxy hook
for forwarding them.

## scope of this issue

This is specifically about upstream server notifications that already reach the
proxy's upstream client but do not reach the downstream client connected to the
proxy.

The minimal repro covers:

- `notifications/tools/list_changed`
- `notifications/resources/list_changed`
- `notifications/prompts/list_changed`
- `notifications/resources/updated`
- `notifications/message`
