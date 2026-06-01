# wf_mcp Architecture Boundaries

`wf_mcp` is one distribution for now, but it is organized as separable concerns.
The goal is to keep future package extraction cheap without adding packaging
overhead before the APIs settle.

For the short operator-facing map of the current nouns and tool families, start
with [`wf_mcp_operator_manual.md`](wf_mcp_operator_manual.md).

## Packages

| Package | Responsibility |
| --- | --- |
| `wf_mcp.proxy` | Expose configured upstream MCP servers through mounted FastMCP proxy providers. Owns proxy runtime, admin tools, and proxy tool listing helpers. |
| `wf_mcp.broker` | Coordinate remembered connections, catalog snapshots, discovery, events, and workflow execution through broker services. |
| `wf_mcp.workflow` | Convert discovered MCP tools into `wf_authoring` / `wf_core` node specs. |
| `wf_mcp.sdk` | Speak to upstream MCP servers through the MCP Python SDK. Owns adapter protocols, SDK transport/session calls, and SDK object converters. |
| `wf_mcp.control` | Parse and mutate file-backed proxy/broker configuration. |
| `wf_mcp.storage` | Persist auth records and catalog snapshots. |
| `wf_mcp.shared` | Pure helpers used across concerns, such as names, pagination, and error payloads. |

The root `wf_mcp` package is a small public facade for common user entrypoints,
not a dump of every internal helper. If a caller needs broker internals, SDK
adapter protocols, proxy admin pieces, or shared name parsing, import the
relevant concern package directly.

## Dependency Rules

- `wf_api` is the process-local workflow application API. `wf_mcp` may import
  and adapt it; `wf_api` must not import `wf_mcp`.
- `wf_mcp.sdk` should not import `wf_core` or `wf_authoring`.
- `wf_mcp.proxy` should not import `wf_mcp.workflow`.
- `wf_mcp.workflow` is the only layer that converts MCP capabilities into node specs.
- `wf_mcp.broker` may coordinate `sdk`, `storage`, `control`, and `workflow`.
- `wf_mcp.control` should not know about live MCP clients or workflow execution.
- `wf_mcp.shared` should stay pure and should not import other `wf_mcp` concern packages.
- Root compatibility shims should stay thin: import and re-export only.

## Workflow API Boundary

Workflow lifecycle operations now have a protocol-neutral front door:

```text
wf_cli ─┐
        ├──> wf_api.WorkflowApi ───> WorkflowApiBackend
wf_mcp ─┘
```

The current backend is `wf_mcp.broker.service.WfMcpWorkflowApiBackend`, which
wraps the existing `wf_mcp.workflow_surface.WorkflowSurfaceHandlers`. That
handler class still contains most workflow-surface logic and still depends on
`WfMcpService`; it is kept for compatibility and incremental extraction.

New code should treat `wf_api.WorkflowApi` as the application-facing API. Do not
add new callers that import `WorkflowSurfaceHandlers` directly unless they are
inside the MCP backend adapter or compatibility tests.

This is a dependency-direction cleanup, not a full domain split. Most API
methods still mirror the old workflow-surface payloads and return
`dict[str, Any]`.

Protocol-neutral workflow helpers have moved to `wf_api`: constants, capability
refs, wrapper hints, next actions, raw workflow plans, runtime dependency
resolution, saved subgraph preparation, and durable run lifecycle helpers. The
old `wf_mcp.workflow_surface.*` helper modules are compatibility shims. MCP
tool schemas and registration still live in `wf_mcp.workflow_surface.models` and
`wf_mcp.workflow_surface.tools`.

The remaining extraction work is the large operation implementation:
`WorkflowSurfaceHandlers` still owns most capability, draft, artifact,
deployment, and run methods. Split that implementation by domain only after the
current helper shims are stable.

## Broker Catalogs

The broker keeps two related catalog views:

- `get_catalog()` is the backend MCP catalog. It only includes enabled upstream
  connection snapshots loaded from storage.
- `get_planner_catalog()` is the workflow-planning catalog. It includes backend
  connection snapshots plus broker-local system sources such as `wf.std`.

Broker-local sources are not fake MCP backend connections. They are registered
as service spec sources so raw workflow plans can address nodes like
`wf.std.runtime_error` without polluting connection status, auth, adapter lookup,
or persisted backend catalog snapshots.

The longer-term source model is described in
[`wf_mcp_capability_sources.md`](wf_mcp_capability_sources.md). In that model,
sources own tools, workflow node specs, prompts, and resources, while broker,
proxy, planner, and admin UI surfaces project different capability kinds.

## Hot Reload

Proxy reload is intentionally isolated in
`wf_mcp.proxy.runtime`. FastMCP does not currently expose a complete
provider/proxy unmount lifecycle that we can rely on for safe per-connection
teardown. Until that exists, reload should be treated as best-effort remounting,
not a fully safe session/subscription lifecycle.

Unified mode currently reuses `ProxyRuntime` as its proxy mounting engine. The
old `TransparentProxyRuntime` compatibility alias has been removed; use
`ProxyRuntime` directly.

`ProxyRuntime` now owns a small `ProxyMountRegistry`. Proxy/admin tools are
registered once on the top-level local provider; reload only clears the visible
mounted upstream provider list and rebuilds it from current config. Unchanged
enabled connections reuse their cached proxy mount instead of recreating a new
client/proxy pair every time. Disabled or removed connections are no longer
mounted after reload, but their cached mounts are only *retired* internally for
now; they are not safely closed or unmounted because FastMCP does not yet expose
the lifecycle hook we need.

The reused FastMCP proxies are not holding one forever-open upstream connection.
`create_proxy_mount()` gives `create_proxy(...)` a disconnected client, and
FastMCP creates fresh request clients from it. What persists across reload is the
proxy/provider object and its component-list caches. FastMCP refreshes those
caches on explicit `list_*` calls and otherwise expires them after its TTL.

After a successful reload, the runtime publishes local `tools_changed`,
`resources_changed`, `prompts_changed`, and `catalog_changed` events when an
event bus is supplied. The admin MCP tool projects the same event kinds into
MCP list-changed notifications for the current client session. Config mutation
tools still only stage changes and return `requires_reload`; they do not emit
list-changed notifications until reload remounts the visible capability set.
Internally, reload metadata uses `ProxyReloadResult`; MCP tools serialize that
typed result to a plain payload at the boundary.
Proxy tool listing similarly uses `ProxyToolPayload` / `ProxyToolsPage`
internally and serializes to admin MCP payloads at the boundary.

Do not add more lifecycle behavior outside `ProxyMountRegistry`. Cached clients
still need clear close/reconnect/error semantics, and the registry is the single
place where that future behavior should land. Prefer FastMCP's official
unmount/provider lifecycle when it becomes available.

Do not add notification proxying or long-lived subscription handling across
reloads without first introducing an explicit mount lifecycle boundary.

The current practical proxy roadmap, including which FastMCP gaps are worth
working around locally and which should stay upstream-dependent for now, lives
in [`wf_mcp_proxy_reality_and_roadmap.md`](wf_mcp_proxy_reality_and_roadmap.md).

The public MCP mode split has been retired. The execution plan is
[`superpowers/plans/2026-05-16-retire-legacy-mcp-modes.md`](superpowers/plans/2026-05-16-retire-legacy-mcp-modes.md):
`broker` and `proxy` were legacy public launch surfaces, while the ordinary
server now exposes both local capabilities and proxied upstream capabilities.
Internal concern packages remain useful even though the public mode choices are
gone.

## Future Extraction

If this becomes multiple distributions, likely split points are:

- `wf-mcp-proxy`: `proxy`, `control`, `shared`
- `wf-mcp-broker`: `broker`, `storage`, `workflow`, `shared`
- `wf-mcp-sdk`: `sdk`, `capabilities`, `models`, `shared`

For now, keep one distribution and use import discipline to preserve those
boundaries.
