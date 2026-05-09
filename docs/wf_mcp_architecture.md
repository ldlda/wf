# wf_mcp Architecture Boundaries

`wf_mcp` is one distribution for now, but it is organized as separable concerns.
The goal is to keep future package extraction cheap without adding packaging
overhead before the APIs settle.

## Packages

| Package | Responsibility |
| --- | --- |
| `wf_mcp.transparent_proxy` | Expose configured upstream MCP servers as a transparent MCP proxy. Owns proxy runtime, admin tools, and proxy tool listing helpers. |
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

- `wf_mcp.sdk` should not import `wf_core` or `wf_authoring`.
- `wf_mcp.transparent_proxy` should not import `wf_mcp.workflow`.
- `wf_mcp.workflow` is the only layer that converts MCP capabilities into node specs.
- `wf_mcp.broker` may coordinate `sdk`, `storage`, `control`, and `workflow`.
- `wf_mcp.control` should not know about live MCP clients or workflow execution.
- `wf_mcp.shared` should stay pure and should not import other `wf_mcp` concern packages.
- Root compatibility shims should stay thin: import and re-export only.

## Broker Catalogs

The broker keeps two related catalog views:

- `get_catalog()` is the backend MCP catalog. It only includes enabled upstream
  connection snapshots loaded from storage.
- `get_planner_catalog()` is the workflow-planning catalog. It includes backend
  connection snapshots plus broker-local system sources such as `wf.std` and
  `wf.mcp`.

Broker-local sources are not fake MCP backend connections. They are registered
as service spec sources so raw workflow plans can address nodes like
`wf.std.runtime_error` and `wf.mcp.call_tool` without polluting connection status,
auth, adapter lookup, or persisted backend catalog snapshots.

The longer-term source model is described in
[`wf_mcp_capability_sources.md`](wf_mcp_capability_sources.md). In that model,
sources own tools, workflow node specs, prompts, and resources, while broker,
proxy, planner, and admin UI surfaces project different capability kinds.

## Hot Reload

Transparent proxy reload is intentionally isolated in
`wf_mcp.transparent_proxy.runtime`. FastMCP does not currently expose a complete
provider/proxy unmount lifecycle that we can rely on for safe per-connection
teardown. Until that exists, reload should be treated as best-effort remounting,
not a fully safe session/subscription lifecycle.

Do not add notification proxying or long-lived subscription handling across
reloads without first introducing an explicit mount lifecycle boundary.

## Future Extraction

If this becomes multiple distributions, likely split points are:

- `wf-mcp-proxy`: `transparent_proxy`, `control`, `shared`
- `wf-mcp-broker`: `broker`, `storage`, `workflow`, `shared`
- `wf-mcp-sdk`: `sdk`, `capabilities`, `models`, `shared`

For now, keep one distribution and use import discipline to preserve those
boundaries.
