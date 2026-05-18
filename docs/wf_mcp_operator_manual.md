# wf_mcp Operator Manual

This is the short practical map for using the current MCP-facing platform.

Use this document when you need to answer:

- what object am I looking at?
- which tool family manages it?
- what is the normal path from "I connected a server" to "a workflow runs"?

For deeper design notes, follow the links at the end.

## What This Server Is

The public MCP server exposes three kinds of things at once:

1. proxied upstream MCP capabilities such as `everything.default.echo`
2. local control-plane tools such as `wf.admin.list_sources`
3. local workflow authoring/runtime tools such as
   `wf.workflow.list_capabilities`

Those are different surfaces over one platform. They should not be confused
with each other just because MCP transports them all.

## The Nouns

| Noun | Meaning | Example |
| --- | --- | --- |
| Connection | A configured upstream MCP account/profile with auth and transport settings. | `everything.default` |
| Source | A named owner of capabilities. A source may be local or backed by a connection. | `wf.std`, `wf.mcp`, `everything.default` |
| Catalog | A discovered snapshot of backend MCP capabilities. | tools/resources/prompts loaded from `everything.default` |
| Workflow capability | A workflow-ready `NodeSpec` contract that graphs can consume. | `wf.std.runtime_error`, `everything.default.echo` |
| Artifact | An immutable saved workflow definition or saved wrapper workflow. | `codex_echo_probe` version `2` |
| Deployment | A runnable binding from an artifact version to concrete runtime sources. | `codex_echo_probe.prod` |

The most important split:

```text
connection != source
raw MCP tool != workflow capability
artifact != deployment
```

## The Surfaces

### `wf.admin`

Privileged control plane.

Use it for:

- registering and editing connections
- refreshing backend catalogs
- inspecting configured sources
- reading platform status and events
- mutating config

Typical tools:

- `wf.admin.list_connections`
- `wf.admin.add_connection`
- `wf.admin.refresh_connection_catalog`
- `wf.admin.list_sources`
- `wf.admin.inspect_source`
- `wf.admin.get_catalog`
- `wf.admin.get_planner_catalog`

`wf.admin` is not meant to be a normal workflow dependency.

### `wf.workflow`

Workflow authoring and execution surface.

Use it for:

- discovering workflow-ready capabilities
- inspecting and directly test-calling one capability
- creating saved artifacts
- listing and inspecting saved artifacts
- saving deployments
- validating and running deployments

Typical tools:

- `wf.workflow.list_capabilities`
- `wf.workflow.inspect_capability`
- `wf.workflow.call_capability`
- `wf.workflow.create_artifact_from_plan`
- `wf.workflow.list_artifacts`
- `wf.workflow.inspect_artifact`
- `wf.workflow.save_deployment`
- `wf.workflow.validate_deployment`
- `wf.workflow.run_deployment`

### Proxied Upstream Tools

These are the upstream MCP tools themselves, projected under connection/source
names such as:

```text
everything.default.echo
context7.default.query_docs
```

They are useful for direct interactive use and for capability discovery. They
are not automatically good workflow abstractions; a workflow may want a cleaner
wrapper with explicit outcomes and a smaller contract.

## Human Operator Workflow

### 1. Register Or Update A Connection

Use the config/admin surface:

```text
wf.admin.add_connection
wf.admin.update_connection
wf.admin.enable_connection
wf.admin.disable_connection
```

A connection can exist before any catalog has been fetched. In that state it
should still appear as a source with zero discovered capabilities.

### 2. Refresh Its Catalog

```text
wf.admin.refresh_connection_catalog
```

This asks the upstream MCP server for its current supported capability families.
`tools/list` is required for workflow-facing discovery. `resources/list` and
`prompts/list` are optional; a server that does not implement them can still be
a valid tools-only source.

### 3. Inspect The Platform View

Use:

```text
wf.admin.list_sources
wf.admin.inspect_source
wf.admin.get_catalog
wf.admin.get_planner_catalog
```

Prefer `list_sources` first. It is the compact inventory. Inspect one source
only when you need its full owned-capability list.

### 4. Manage Saved Workflows

Use `wf.workflow.*` for artifacts and deployments:

```text
create artifact -> inspect artifact -> save deployment -> validate deployment
```

Artifacts are immutable saved definitions. Deployments are where those saved
definitions bind to concrete runtime sources/accounts.

## LLM Client Workflow

An LLM author should usually avoid starting from giant raw catalogs.

### 1. Discover Sources

```text
wf.admin.list_sources
```

This tells the client what exists and which sources are planner-visible.

### 2. Discover Workflow-Ready Capabilities

```text
wf.workflow.list_capabilities
wf.workflow.inspect_capability
```

Use the compact list first, then inspect only the likely candidates.

### 3. Test One Capability Directly

```text
wf.workflow.call_capability
```

This is the workflow-facing REPL step. It is different from directly calling a
raw upstream MCP tool because it exercises the `NodeSpec` contract that the
graph would consume.

### 4. Build And Save

```text
wf.workflow.create_artifact_from_plan
wf.workflow.save_deployment
```

Artifacts should prefer logical source aliases in saved plans. Deployments bind
those logical aliases to concrete sources such as `context7.default`.

### 5. Validate And Run

```text
wf.workflow.validate_deployment
wf.workflow.run_deployment
```

Use `run_deployment` rather than expecting newly saved workflows to appear as
brand-new MCP tools. Many LLM harnesses do not reliably refresh callable tool
schemas mid-session.

## Which Tool Do I Use?

| I want to... | Use |
| --- | --- |
| See configured upstream accounts | `wf.admin.list_connections` |
| Add or edit an upstream account | `wf.admin.add_connection`, `wf.admin.update_connection` |
| Re-fetch what an upstream server exposes | `wf.admin.refresh_connection_catalog` |
| See all capability owners | `wf.admin.list_sources` |
| See everything one source owns | `wf.admin.inspect_source` |
| See raw backend MCP snapshots | `wf.admin.get_catalog` |
| See planner-visible workflow-ready nodes | `wf.admin.get_planner_catalog` or preferably `wf.workflow.list_capabilities` |
| Find one workflow-ready node | `wf.workflow.list_capabilities` |
| Read one node contract in full | `wf.workflow.inspect_capability` |
| Test one node directly | `wf.workflow.call_capability` |
| Save a workflow definition | `wf.workflow.create_artifact_from_plan` |
| List saved workflows/wrappers | `wf.workflow.list_artifacts` |
| Bind a saved workflow to concrete sources | `wf.workflow.save_deployment` |
| Check whether a deployment can run | `wf.workflow.validate_deployment` |
| Execute a saved workflow | `wf.workflow.run_deployment` |

## Common Confusions

### `get_catalog` Versus `get_planner_catalog`

`get_catalog` is the backend MCP snapshot view. It answers:

```text
what did upstream MCP connections expose?
```

`get_planner_catalog` is the workflow-planning view. It answers:

```text
what workflow-ready node specs can the planner use?
```

The second includes local workflow sources such as `wf.std` and `wf.mcp`; the
first does not.

### Source Versus Connection

Every upstream connection becomes a source, but not every source is a
connection.

Examples:

- `everything.default`: both a connection and a source
- `wf.std`: a local source, not a connection
- `wf.admin`: a privileged local source, not a connection

### Raw Tool Versus Workflow Capability

A raw MCP tool is shaped for the provider. A workflow capability is shaped for
graph composition.

A raw tool can be directly callable and still be an awkward workflow node if it
uses provider-specific result envelopes, status strings, or transport-level
errors where a graph wants explicit outcomes.

### Artifact Versus Deployment

An artifact is the immutable saved workflow definition.

A deployment is the runnable instance that binds it to concrete source choices.
Different deployments can point the same artifact version at different MCP
accounts.

## Read Next

- [`wf_mcp_end_to_end_runbook.md`](wf_mcp_end_to_end_runbook.md) for one full
  connection-to-deployment example
- [`wf_mcp_troubleshooting.md`](wf_mcp_troubleshooting.md) for missing-source,
  missing-capability, and unrunnable-deployment cases
- [`wf_mcp_architecture.md`](wf_mcp_architecture.md) for package boundaries and
  hot-reload behavior
- [`wf_mcp_capability_sources.md`](wf_mcp_capability_sources.md) for the source
  model
- [`workflow_capabilities.md`](workflow_capabilities.md) for raw versus
  workflow-facing capability design
- [`workflow_artifacts.md`](workflow_artifacts.md) for immutable artifacts,
  deployments, and saved workflows as future nodes
