# wf_mcp Capability Sources

`wf_mcp` should model capabilities before it models MCP server tool lists.
Tools, workflow node specs, prompts, resources, and admin controls all belong to
a source. Broker mode, transparent proxy mode, workflow planning, and future UI
surfaces are projections of those sources.

This avoids the current trap where broker admin tools, transparent proxy admin
tools, workflow node specs, and upstream MCP tools all look like unrelated
systems.

## Core Model

A capability source is a named provider of one or more capability kinds.

```text
CapabilitySource
  id: "wf.std" | "wf.mcp" | "wf.admin" | "<server>.<account>"
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
    prompts
    resources
```

Important rule: a source is not "an MCP tool source." A source owns
capabilities. Each surface decides which capability kinds it projects.

## Canonical Sources

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
- `prompts`: workflow authoring guide, error-handling guide, mapping guide.
- `resources`: reference docs for stdlib node behavior.

### `wf.mcp`

Workflow runtime helpers for interacting with MCP backends.

- Planner-visible: yes, for workflow node specs.
- MCP-client-visible: maybe, for docs/prompts/resources, not admin mutation.
- Admin-dashboard-visible: yes, for inspection and source toggling.
- MCP tools: normally none.
- Workflow safety: mixed. Individual capabilities must be marked.

Expected capabilities:

- `node_specs`: `wf.mcp.call_tool`, `wf.mcp.read_resource`,
  `wf.mcp.get_prompt`.
- Advanced/escape-hatch node specs may exist later:
  `wf.mcp.invoke_method`, `wf.mcp.send_notification`.
- `prompts/resources`: docs for building MCP-backed workflows.

`wf.mcp` is not the admin namespace. It should mean "workflow can interact with
MCP capabilities."

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
  events, inspect proxy tools, call/debug upstream capabilities.
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
- include `wf.mcp.call_tool`
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
- `wf.mcp.mcp_workflow_guide`

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

## Current Code Mapping

Current code has several useful pieces but the boundaries are blurred.

| Current location | Current role | Target source |
| --- | --- | --- |
| `wf_authoring.ops` | reusable workflow node specs | `wf.std.node_specs` |
| `wf_mcp.broker.service.builtins` | local workflow specs | `wf.std`, `wf.mcp` |
| `wf_mcp.broker.tools` | broker MCP admin/control tools | `wf.admin.tools` |
| `wf_mcp.transparent_proxy.admin` | proxy MCP admin/control tools | `wf.admin.tools` |
| discovered MCP tools | upstream tools and workflow wrappers | connection source |
| broker resources/prompts | catalog/status/planning context | likely `wf.admin` or docs sources |

The current `SpecSource` is a first step, but it only models workflow node specs.
It should evolve into `CapabilitySource`, or be replaced by it, so tools,
prompts, resources, and node specs share one source registry.

## Naming Rules

Use source ids consistently:

- `wf.std.*` for workflow standard library capabilities.
- `wf.mcp.*` for workflow MCP runtime helpers.
- `wf.admin.*` for privileged control/admin capabilities.
- `<connection_id>.*` for upstream connection capabilities.

Avoid using `wf.mcp_*` for admin tools. That name currently comes from
FastMCP's `Namespace` transform using underscores, but semantically it makes
admin look like MCP workflow runtime. If a custom namespace transform can
preserve dotted names, prefer `wf.admin.list_sources` over
`wf.mcp_list_sources`.

## Migration Path

1. Keep the current tests green while making `SpecSource` canonical for node
   specs.
2. Add a `CapabilitySource` shape that can hold `tools`, `node_specs`,
   `prompts`, and `resources`.
3. Move all `wf_authoring.ops` registrations into the `wf.std` source.
4. Move broker and transparent-proxy admin operations into one `wf.admin`
   source definition.
5. Make broker and proxy servers project admin tools from `wf.admin` only when
   admin MCP exposure is explicitly enabled.
6. Add source-level enable/disable behavior and make every projection respect it.
7. Add system prompts/resources for `wf.std` and `wf.mcp` manuals.

The implementation should avoid having broker mode and transparent proxy mode
define separate copies of the same admin/control capabilities.
