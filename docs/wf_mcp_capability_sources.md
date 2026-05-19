# wf_mcp Capability Sources

`wf_mcp` should model capabilities before it models MCP server tool lists.
Tools, workflow node specs, prompts, resources, and admin controls all belong to
a source. The MCP server, workflow planning, and future UI surfaces are
projections of those sources.

If you need the practical "which thing do I call?" view before the domain model,
start with [`wf_mcp_operator_manual.md`](wf_mcp_operator_manual.md).

This avoids the current trap where broker admin tools, transparent proxy admin
tools, workflow node specs, and upstream MCP tools all look like unrelated
systems.

## Core Model

A capability source is a named provider of one or more capability kinds.
The domain model lives in `wf_platform.sources`; `wf_mcp` projects MCP-backed
connections into that model rather than owning the model itself.

```text
CapabilitySource
  id: "wf.std" | "wf.docs" | "wf.admin" | "<server>.<account>"
  kind: "system" | "connection"
  enabled: bool
  visibility:
    planner: bool
    mcp_client: bool
    admin_dashboard: bool
  permissions:
    safe_for_workflow: bool
    calls_upstream: bool
    mutates_config: bool
    mutates_auth: bool
  capabilities:
    tools
    node_specs
    reducers
    prompts
    resources
```

Important rule: a source is not "an MCP tool source." A source owns
capabilities. Each surface decides which capability kinds it projects.

For the distinction between raw capabilities, workflow-facing `NodeSpec`s, and
future saved wrapper artifacts, see
[`workflow_capabilities.md`](workflow_capabilities.md).

## Canonical Sources

### `wf.docs`

Local platform documentation.

- Planner-visible: no.
- MCP-client-visible: yes.
- Admin-dashboard-visible: yes.
- MCP tools: none.
- Workflow safety: not applicable; it owns docs, not workflow nodes.

Current capabilities:

- `prompts`: `wf.docs.operator_guide`, `wf.docs.workflow_authoring_guide`,
  `wf.docs.troubleshooting_guide`.
- `resources`: `wf://docs/operator-manual`,
  `wf://docs/end-to-end-runbook`, `wf://docs/troubleshooting`.

The documentation resource model lives in `wf_platform`, not in the MCP
projection layer. That lets the same manuals feed MCP resources now and other
surfaces such as a future CLI or UI later.

### `wf.std`

Workflow standard library.

- Planner-visible: yes, for reusable workflow node specs.
- MCP-client-visible: yes, for prompts/resources/manuals.
- Admin-dashboard-visible: yes, for inspection and source toggling.
- MCP tools: normally none.
- Workflow safety: yes.

Expected capabilities:

- `node_specs`: `wf.std.runtime_error`, `wf.std.coalesce`,
  `wf.std.default_if_none`, `wf.std.constant`, `wf.std.pick_key`,
  `wf.std.truthy`, `wf.std.first_item`, `wf.std.first_item_maybe`,
  `wf.std.first_item_or_none`, `wf.std.last_item`, `wf.std.last_item_or_none`,
  `wf.std.length`, `wf.std.is_empty`.
- `reducers`: `wf.std.replace`, `wf.std.append`, `wf.std.max`,
  `wf.std.merge_object`, `wf.std.set_union`.
- `prompts`: workflow authoring guide, error-handling guide, mapping guide.
- `resources`: reference docs for stdlib node behavior.

### `wf.mcp`

Reserved for future workflow-safe MCP helpers.

`wf.mcp` currently owns no public NodeSpecs. The previous raw
`wf.mcp.call_tool` helper was deleted because it duplicated the proxy tool
surface and used the wrong abstraction for stateful servers. Workflow authors
should use generated connection NodeSpecs, saved wrappers, or
`wf.workflow.call_capability` when they need to test a workflow-facing
capability.

### `wf.admin`

Human/control-plane administration source.

- Planner-visible: no by default.
- MCP-client-visible: no by default.
- Admin-dashboard-visible: yes.
- MCP tools: only when explicitly launched with admin exposure enabled.
- Workflow safety: no.

Expected capabilities:

- `tools`: list sources, enable source, disable source, refresh catalog, list
  connections, add/update/remove connections, view config, reload config, inspect
  events, and inspect proxy tools.
- `prompts/resources`: admin documentation may be useful later.

This source is privileged. A normal client LLM should not automatically see
tools that can mutate config, auth, or its own available capability set.

### Connection Sources

Each upstream MCP connection is a source, for example `everything.default` or
`fixture.personal`.

- Planner-visible: yes when enabled and allowed.
- MCP-client-visible: yes when enabled and allowed.
- Admin-dashboard-visible: yes.
- MCP tools/resources/prompts: discovered from upstream.
- Workflow node specs: generated wrappers around upstream tools.

Connection sources are the only sources that represent upstream MCP server
snapshots. System sources are local broker capabilities.

A configured connection should still appear as a connection source even when no
catalog snapshot has been loaded yet. In that state the source can have zero
owned capabilities and a description such as `No catalog loaded for ...`; the
absence of discovered capabilities must not make the configured connection
disappear from source inventory.

Connection discovery treats `tools/list` as the required workflow-facing family.
Optional MCP families such as `resources/list` and `prompts/list` may be absent;
servers that return MCP `Method not found` for those methods still refresh as
tool-only sources instead of failing the whole catalog refresh.

## Projections

### Planner Catalog

The planner catalog shows `node_specs` where:

```text
source.enabled
and source.visibility.planner
and capability is safe or explicitly allowed for workflow
```

Examples:

- include `wf.std.runtime_error`
- include `everything.default.echo`
- exclude `wf.admin.disable_source`

### MCP Client Tools

The MCP `tools/list` projection shows `tools` where:

```text
source.enabled
and source.visibility.mcp_client
and capability kind == tool
```

Normal mode should not expose `wf.admin` tools. Admin mode may expose them with
clear names such as `wf.admin.list_sources`.

### MCP Client Prompts And Resources

The MCP `prompts/list` and `resources/list` projections may show documentation
from system sources.

Examples:

- `wf.std.workflow_manual`
- `wf.std.error_handling_guide`
- MCP workflow guides under `wf.docs`

These are MCP-visible without implying the source exposes MCP tools.

### Admin Dashboard

The admin dashboard projection shows sources, visibility, health, auth status,
and privileged operations.

This is the preferred place for source toggling:

- disable an entire source
- enable an entire source
- refresh a source catalog
- update connection config
- log out / replace auth

Dashboard operations should use `wf.admin` capability definitions or Python
control APIs, not ad hoc tool functions copied across broker and proxy modes.

## Implemented Shape

The code now has the first capability-source layer in place.

- `wf_platform.CapabilitySource` owns source metadata, visibility, permissions, and
  capability buckets.
- `CapabilitySource` is the mutable runtime registry object; typed
  `SourceStatus` and `SourceInventory` snapshots are the serializable domain
  projections used at boundaries such as `list_sources()`.
- Executable `NodeSpec` objects stay inside runtime buckets because they hold
  Python callables. Inventory exposes `NodeSpecInventory` contracts instead:
  names, descriptions, outcomes, schemas, and execution flags, but never the
  wrapped function object itself.
- Reducer inventory follows the same rule: executable reducer definitions stay
  private, while `ReducerInventory` exposes only reducer names, descriptions,
  and config schemas.
- `WfMcpService.capability_sources` is the canonical in-memory registry.
- Planner node lookup reads `CapabilitySource.capabilities.node_specs`
  directly; the old `SpecSource` compatibility layer has been removed.
- `wf.std` owns current `wf_authoring.ops` workflow node specs under
  `wf.std.*`.
- `wf.mcp` is reserved for future workflow-safe MCP helpers and currently owns
  no public NodeSpecs.
- `wf.admin` owns privileged admin capability metadata and is not planner-visible
  by default.
- Transparent proxy admin tools now use dotted `wf.admin.*` names through
  `LdaNamespace`.
- `wf.admin` and `wf.mcp` are reserved connection ids.
- Planner catalog, `list_available_specs()`, and workflow spec resolution respect
  source `enabled` and `visibility.planner`.

Legacy broker MCP tools still expose compatibility names such as
`list_connections` and `get_planner_catalog` on the compatibility-only broker
server constructor. They now reuse the same service-admin registrar as the
public server, with only the visible names changed. The public server projects
service-backed admin tools such as `wf.admin.list_sources` alongside
proxy-backed admin tools under the same `wf.admin.*` namespace.

## Current Code Mapping

Current code has several useful pieces but the boundaries are blurred.

| Current location | Current role | Target source |
| --- | --- | --- |
| `wf_authoring.ops` | reusable workflow node specs | `wf.std.node_specs` |
| `wf_core` built-in reducers | reusable workflow state reducers | `wf.std.reducers` |
| `wf_mcp.broker.service.builtins` | local workflow specs | `wf.std` |
| `wf_mcp.broker.tools` | compatibility wrapper over shared service-admin registration | `wf.admin.tools` |
| `wf_mcp.admin_surface.tools` | shared service-backed admin tool registration | `wf.admin.tools` |
| `wf_mcp.transparent_proxy.admin` | proxy-backed public admin tools | `wf.admin.tools` |
| discovered MCP tools | upstream tools and workflow wrappers | connection source |
| broker resources/prompts | catalog/status/planning context | likely `wf.admin` or docs sources |

New source behavior should be added to `CapabilitySource`.

## Naming Rules

Use source ids consistently:

- `wf.std.*` for workflow standard library capabilities.
- `wf.mcp.*` for workflow MCP runtime helpers.
- `wf.admin.*` for privileged control/admin capabilities.
- `<connection_id>.*` for upstream connection capabilities.

Avoid using `wf.mcp_*` for admin tools. `wf.mcp` is reserved for workflow MCP
runtime helpers. Transparent proxy admin tools now use dotted `wf.admin.*`
names.

## Migration Path

1. Keep explicit admin MCP exposure controls on the server surface.
2. Project admin tools from `wf.admin` only when admin MCP exposure is
   enabled.
3. Add source-level enable/disable operations backed by `wf.admin`.
4. Add persisted source policy so source visibility survives process restart.
5. Add system prompts/resources for `wf.std` and `wf.mcp` manuals.

The implementation should avoid having separate backend layers define copies of
the same admin/control capabilities.

## Current Inventory Surface

`list_sources()` is the compact source-discovery surface:

- returns paged source summaries with visibility, permissions, and counts
- includes small sorted preview name lists per capability kind
- includes `has_more` flags when a preview omits additional owned names
- is intentionally compact enough for progressive discovery
- pairs with `inspect_source(source_id)` for the full owned-capability inventory

Humans and LLM authoring clients should list sources first, then inspect only the
sources they need. Planner projection remains a different **use** of source
metadata, not a second source model.

The summary payload intentionally does not include schemas or executable
contracts:

```json
{
  "id": "wf.std",
  "node_spec_count": 12,
  "reducer_count": 6,
  "preview": {
    "node_specs": ["wf.std.coalesce", "wf.std.constant", "wf.std.default_if_none"],
    "reducers": ["wf.std.add", "wf.std.append", "wf.std.max"]
  },
  "has_more": {
    "node_specs": true,
    "reducers": true
  }
}
```

Call `inspect_source("wf.std")` only when those previews indicate the source is
relevant. That keeps large source inventories usable for MCP clients with tight
context windows.
