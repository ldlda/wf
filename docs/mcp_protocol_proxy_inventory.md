# MCP Protocol Proxy Inventory

This document records observed behavior of `wf-mcp` unified mode against real
upstream MCP servers. It is not a design spec. It is a fact log for deciding
which proxy features need explicit implementation.

## Live Everything Server Probe

Probe date: 2026-05-13

Server command in config:

```text
pnpx @modelcontextprotocol/server-everything
```

Connection id:

```text
everything.default
```

Proxy mode:

```text
wf-mcp serve --mode unified
```

### Working

- `tools/list` shows Everything tools through `wf-mcp`.
- `tools/call` works for normal tools such as `everything.default_echo`.
- Tool metadata is preserved for proxy inventory, including title, description,
  and JSON input schema.
- Annotated text content is preserved.
- Tiny image content returns through the proxy.
- Structured content returns structured JSON.
- `trigger-long-running-operation` completes through the proxy as a normal tool
  call.
- `toggle-simulated-logging` and `toggle-subscriber-updates` return success.
- Native listed resources are namespaced by FastMCP mount/proxy transforms.
- Native listed resource templates are namespaced by FastMCP mount/proxy
  transforms.
- Namespaced static and dynamic resources can be read through `wf-mcp`.

Example listed resource mapping:

```text
upstream: demo://resource/static/document/instructions.md
proxied:  demo://everything.default/resource/static/document/instructions.md
```

### Gaps

- Resource links embedded inside tool results are not rewritten by the proxy.
  For example, `get-resource-links` returns raw upstream URIs such as:

```text
demo://resource/dynamic/text/2
```

  `wf-mcp` cannot read that raw URI. The manually namespaced URI works for
  normal dynamic resources:

```text
demo://everything.default/resource/dynamic/text/2
```

- Session resource links from `gzip-file-as-resource` are not currently usable
  through `wf-mcp`. The tool returned:

```text
demo://resource/session/probe.txt
```

  Neither the raw URI nor the manually namespaced URI was readable through
  `wf-mcp` during the live probe. Direct `everything` read also failed in this
  Codex session, so this may be session-affinity, lifecycle, or returned-link
  behavior rather than only URI rewriting.

- `simulate-research-query` is discovered, but calling it fails cleanly:

```text
Tool simulate-research-query requires task augmentation (taskSupport: 'required')
```

  This is a task/protocol support gap, not an ordinary tool-call failure.

- Logging and subscriber update tools return success, but no separate logging
  or resource-update notification was visible in the Codex tool channel during
  this probe.

- Sampling was not visible as a direct listed tool in the current Everything
  server inventory.

### Current Classification

- Proxy tool projection: healthy for ordinary tools.
- Proxy resource list/read projection: healthy for listed resources and
  templates.
- Tool-result resource links: incomplete; embedded resource URIs need explicit
  rewrite or a documented limitation.
- Session resources: unresolved; needs a focused test because session affinity
  may matter.
- Tasks: unsupported; task-required tools should remain clearly diagnosed until
  MCP task support is implemented.
- Notifications/logging/subscriptions: unverified; current client did not show
  forwarded notifications.

## Next Test Targets

- Add automated tests for listed resource/template namespacing through unified
  mode.
- Add a fixture or Everything integration test showing tool-returned
  `resource_link` URIs are not rewritten today.
- Decide whether to rewrite embedded resource links in tool results or expose a
  helper that resolves upstream resource links into proxied resource URIs.
- Investigate session resource lifecycle separately from URI rewriting.
- Inventory current FastMCP/MCP SDK APIs for tasks, logging notifications, and
  resource update notifications before implementing protocol forwarding.

## Notification Inventory

Spec version checked: 2025-11-25

Official spec pages checked:

- <https://modelcontextprotocol.io/specification/2025-11-25/server/tools>
- <https://modelcontextprotocol.io/specification/2025-11-25/server/resources>
- <https://modelcontextprotocol.io/specification/2025-11-25/server/prompts>
- <https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/progress>

Installed local packages checked:

- `fastmcp==3.2.4`
- `mcp==1.27.0`

### Protocol Notifications

The MCP spec defines these relevant server-to-client notifications:

| Event | MCP notification | Notes |
| --- | --- | --- |
| Tool catalog changed | `notifications/tools/list_changed` | Requires server `tools.listChanged` capability. |
| Resource catalog changed | `notifications/resources/list_changed` | Requires server `resources.listChanged` capability. |
| Prompt catalog changed | `notifications/prompts/list_changed` | Requires server `prompts.listChanged` capability. |
| Specific resource updated | `notifications/resources/updated` | Requires resource subscription flow. Params include resource `uri`. |
| Request progress | `notifications/progress` | Requires an active request with `_meta.progressToken`. |
| Logging message | `notifications/message` | Uses MCP logging level and client logging preferences. |
| Task status | `notifications/tasks/status` | Used by MCP task-augmented execution. |

The spec also defines client-to-server requests that matter for notifications:

| Request | Purpose |
| --- | --- |
| `resources/subscribe` | Client subscribes to updates for a specific resource URI. |
| `resources/unsubscribe` | Client stops receiving updates for a specific resource URI. |
| request `_meta.progressToken` | Client asks for progress notifications for that request. |

### FastMCP / SDK Reality

MCP SDK has concrete notification types in `mcp.types`, including:

- `ToolListChangedNotification`
- `ResourceListChangedNotification`
- `PromptListChangedNotification`
- `ResourceUpdatedNotification`
- `ProgressNotification`
- `LoggingMessageNotification`
- `TaskStatusNotification`

FastMCP low-level server advertises notification support for all three list
changed capabilities by default:

```text
prompts_changed=True
resources_changed=True
tools_changed=True
```

FastMCP `Context` exposes request-scoped helpers:

- `ctx.send_notification(notification)`
- `ctx.report_progress(progress, total=None, message=None)`
- `ctx.log(...)`, plus convenience `ctx.info`, `ctx.warning`, `ctx.error`, etc.
- `ctx.enable_components(...)`, `ctx.disable_components(...)`, and
  `ctx.reset_visibility(...)`, which send list-changed notifications for the
  current session.

Important constraint: no global `FastMCP.notify_all(...)` style API was found.
The obvious notification path is request/session scoped through FastMCP
`Context` or lower-level server sessions. This matters because our internal
event bus can emit outside a currently executing MCP tool call, while MCP
notifications need a connected client session.

### Mapping From wf-mcp Events

Current internal events that can map to MCP notifications:

| Internal event | Candidate MCP notification | Caveat |
| --- | --- | --- |
| `tools_changed` | `notifications/tools/list_changed` | Needs a session-aware sink. |
| `resources_changed` | `notifications/resources/list_changed` | Needs a session-aware sink. |
| `prompts_changed` | `notifications/prompts/list_changed` | Needs a session-aware sink. |
| future `resource_updated` | `notifications/resources/updated` | Requires subscription ownership and namespaced URI mapping. |
| future `workflow_run_progress` | `notifications/progress` | Only valid when a caller supplied a progress token. |
| future broker log events | `notifications/message` | Needs client logging level behavior. |
| future workflow task events | `notifications/tasks/status` | Should wait for task execution support. |

### Implementation Guidance

Do not emit MCP notifications directly from `WfMcpService`.

Recommended shape:

```text
WfMcpService
  -> EventBus
    -> InMemoryEventSink
    -> later: McpSessionNotificationSink
```

Near-term implementation should add a notification mapping layer with a fake
sink first. Real MCP emission needs one of these session-aware entry points:

- a FastMCP tool/resource/prompt handler with injected `Context`
- middleware that can access the active `Context` or session
- explicit lower-level session management if FastMCP exposes enough stable API

Until we have a session-aware sink, list-changed events should remain internal
events exposed through `get_broker_events` / `wf-mcp://events`.

### Concrete Notification Plan

Implement notifications in this order.

1. Add a pure mapping layer from internal events to MCP notification objects.

```text
tools_changed     -> ToolListChangedNotification
resources_changed -> ResourceListChangedNotification
prompts_changed   -> PromptListChangedNotification
```

This layer should not know about FastMCP sessions. It should be easy to test
with plain `mcp.types` objects.

2. Add a fake/test notification sink.

The first sink should only record which MCP notification objects would be sent.
This proves the event-to-notification mapping without depending on Codex,
Inspector, stdio behavior, or Streamable HTTP behavior.

3. Add a FastMCP `Context` notification sink.

This sink can call:

```text
ctx.send_notification(...)
```

It is only valid while handling a request that has an active FastMCP context.
This should be treated as a session-scoped projection, not a global broadcast
system.

4. Wire local admin operations first.

Best first live target:

```text
wf.admin.reload_config
```

When reload changes mounted capabilities, it should:

- perform the reload
- emit internal catalog/tool/resource/prompt change events
- send list-changed MCP notifications to the current client session when a
  FastMCP context is available

This is intentionally local. It does not require solving upstream notification
forwarding.

5. Verify with Inspector/Codex.

Expected outcomes:

- clients that honor list-changed notifications refresh their tool/resource/
  prompt lists
- clients that ignore notifications can still manually call list/search tools
- no workflow or broker correctness depends on notification delivery

6. Only after local list-changed works, investigate upstream notification
forwarding.

Upstream forwarding is a separate problem because mounted proxies may or may
not already forward upstream notifications. It also needs namespaced resource
URIs for `notifications/resources/updated`.

### Deferred Notification Work

- `notifications/resources/updated`: requires explicit resource subscription
  ownership and URI rewriting.
- `notifications/progress`: requires an active request `_meta.progressToken`.
- `notifications/message`: should respect client logging level behavior.
- `notifications/tasks/status`: should wait for task-augmented execution.
- Upstream-to-downstream notification forwarding: needs a focused FastMCP proxy
  behavior test before implementation.

### Open Questions

- Can a mounted FastMCP proxy forward upstream notifications to the downstream
  client automatically, or only notifications generated by local handlers?
- Can we attach a durable notification sink to every active FastMCP session
  without relying on private APIs?
- Does Codex surface list-changed, resource-updated, logging, or progress
  notifications from an MCP server in this environment?
- For streamable HTTP, does FastMCP event-store support make notification
  replay possible for disconnected clients?
