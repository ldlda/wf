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
| Source | A named owner of capabilities. A source may be local or backed by a connection. | `wf.std`, `wf.docs`, `wf.mcp`, `everything.default` |
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
- validating, patching, and compiling workflow drafts
- creating saved artifacts from drafts or raw plans
- listing and inspecting saved artifacts
- saving deployments
- validating and running deployments

Typical tools:

- `wf.workflow.list_capabilities`
- `wf.workflow.inspect_capability`
- `wf.workflow.call_capability`
- `wf.workflow.validate_draft`
- `wf.workflow.compile_draft`
- `wf.workflow.patch_draft`
- `wf.workflow.create_artifact_from_draft`
- `wf.workflow.create_artifact_from_plan`
- `wf.workflow.list_artifacts`
- `wf.workflow.inspect_artifact`
- `wf.workflow.save_deployment`
- `wf.workflow.validate_deployment`
- `wf.workflow.run_deployment`

### `wf.docs`

Local documentation source.

It owns stable documentation resources such as:

- `wf://docs/operator-manual`
- `wf://docs/end-to-end-runbook`
- `wf://docs/troubleshooting`

It also owns short guide prompts such as:

- `wf.docs.operator_guide`
- `wf.docs.workflow_authoring_guide`
- `wf.docs.troubleshooting_guide`

This source exists so manuals are discoverable through the same capability model
as everything else. The docs themselves are provider-neutral platform
resources; MCP is only one projection of them.

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
only when you need its full owned-capability list. The compact response includes
counts plus small preview lists and `has_more` flags, so clients can usually
choose the next source to inspect without loading every schema.

Use `wf.workflow.list_capabilities` after that when you need workflow-ready
nodes rather than source ownership. Its rows include `source_id`, outcomes, and
top-level input/output field names, while full JSON schemas stay behind
`wf.workflow.inspect_capability`.

`wf.workflow.call_capability` is the REPL-style test step. Its result is
self-describing: `kind` is either `node_spec` or `wrapper_artifact`,
`source_id` identifies the owner when applicable, and `diagnostics` is empty for
successful calls.

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
wf.workflow.validate_draft
wf.workflow.create_artifact_from_draft
wf.workflow.save_deployment
```

Drafts are the preferred interactive authoring format. They compile into raw
workflow plans before saving. Use `create_artifact_from_plan` only when a caller
already has a compiled raw plan or intentionally wants the low-level escape
hatch.

Artifacts should prefer logical source aliases in saved workflows. Deployments
bind those logical aliases to concrete sources such as `context7.default`.

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
| Validate an authored workflow draft | `wf.workflow.validate_draft` |
| Apply a targeted fix to a draft | `wf.workflow.patch_draft` |
| Compile a draft without saving | `wf.workflow.compile_draft` |
| Save a workflow definition from a draft | `wf.workflow.create_artifact_from_draft` |
| Save a compiled raw workflow definition | `wf.workflow.create_artifact_from_plan` |
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
- `wf.docs`: a local documentation source, not a connection
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
- [`workflow_drafts.md`](workflow_drafts.md) for the preferred authoring format
- [`workflow_artifacts.md`](workflow_artifacts.md) for immutable artifacts,
  deployments, and saved workflows as future nodes

## Draft Workspace Authoring

Use draft workspaces when a client should iteratively edit one workflow without
resending the full draft each turn.

| Need | Tool |
| --- | --- |
| Start a patchable authoring session | `wf.workflow.create_minimal_draft_workspace` |
| List existing draft sessions | `wf.workflow.list_draft_workspaces` |
| Fetch current draft workspace | `wf.workflow.get_draft_workspace` |
| Patch current draft workspace | `wf.workflow.patch_draft_workspace` |
| Refresh validation without changing revision | `wf.workflow.validate_draft_workspace` |
| Change common draft fields without JSON Patch | `wf.workflow.set_draft_name`, `wf.workflow.set_draft_route`, `wf.workflow.set_step_input_map`, `wf.workflow.set_step_output_map` |
| Save final workspace as artifact | `wf.workflow.create_artifact_from_workspace` |
| Clean up a draft workspace | `wf.workflow.delete_draft_workspace` |

Workspace patches are optimistic-concurrency guarded. Pass the current
`revision` from `get_draft_workspace`; a stale revision returns
`revision_conflict` and leaves the stored draft unchanged.

Workspace mutation tools use a single `request` object in MCP Inspector. That
keeps the form grouped and lets the schema describe fields like
`input_schema`, `output_map`, and `error_message_source`.

Minimal example:

```json
{
  "request": {
    "workspace_id": "echo_draft",
    "name": "echo",
    "capability_name": "demo.personal.echo_tool",
    "input_schema": {
      "type": "object",
      "properties": {
        "text": {
          "type": "string"
        }
      },
      "required": ["text"]
    },
    "state_schema": {
      "fields": {
        "echoed": {
          "type": "string"
        }
      }
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "echoed": {
          "type": "string"
        }
      },
      "required": ["echoed"]
    },
    "input_map": {
      "input.text": "text"
    },
    "output_map": {
      "echoed": "state.echoed"
    }
  }
}
```

Patch example:

```json
{
  "request": {
    "workspace_id": "echo_draft",
    "revision": 1,
    "patch": [
      {
        "op": "replace",
        "path": "/name",
        "value": "echo_v2"
      }
    ]
  }
}
```

If you do not want to write JSON Patch by hand, use the focused helpers:

```json
{
  "request": {
    "workspace_id": "echo_draft",
    "revision": 1,
    "name": "echo_v2"
  }
}
```
