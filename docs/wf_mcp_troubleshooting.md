# wf_mcp Troubleshooting

This guide is organized by symptom. It assumes you already know the normal flow
from [`wf_mcp_end_to_end_runbook.md`](wf_mcp_end_to_end_runbook.md).

Use the smallest useful inspection first. Prefer compact discovery tools before
dumping full catalogs.

## Quick Triage Ladder

When something is missing or will not run, inspect in this order:

1. `wf.admin.list_connections`
2. `wf.admin.list_sources`
3. `wf.admin.inspect_source`
4. `wf.workflow.list_capabilities`
5. `wf.workflow.inspect_capability`
6. `wf.workflow.validate_deployment`

That sequence tells you whether the problem is:

- no configured connection
- no source
- no discovered capabilities
- no workflow-ready capability
- or a saved deployment dependency problem

## A Connection Exists But No Source Appears

Check:

```text
wf.admin.list_connections
wf.admin.list_sources
```

Expected model:

- configured upstream connections should appear as connection sources even
  before a catalog snapshot has been fetched
- a newly added source may have zero capabilities until refresh succeeds

If the connection exists but its source does not appear, that is a platform bug,
not a normal "refresh first" state.

## A Source Exists But Has No Capabilities

Check:

```text
wf.admin.inspect_source
wf.admin.refresh_connection_catalog
```

Likely causes:

- the source was never refreshed
- refresh failed
- the upstream server exposes no usable capabilities

Important distinction:

- `tools/list` is the important workflow-facing discovery family
- `resources/list` and `prompts/list` are optional MCP families

A tools-only server that returns MCP `Method not found` for prompts/resources is
still valid and should refresh successfully.

## I Refreshed But Still Cannot Find The Capability

Check both views:

```text
wf.admin.inspect_source
wf.workflow.list_capabilities
```

If the source inventory shows an upstream **tool** but
`wf.workflow.list_capabilities` does not show a corresponding planner-visible
node spec, the capability may not currently be projected as workflow-ready.

Remember:

```text
raw upstream tool != workflow capability
```

The raw tool can still be callable through the proxy while not being a pleasant
or allowed workflow node.

## The Tool Exists In The Server, But My LLM Client Cannot Call It

This can be a harness/tool-list refresh problem rather than a server problem.

Symptoms:

- the MCP server's `tools/list` changed
- inspector or logs show the new tool
- the current LLM turn still cannot call it

Some LLM harnesses do not reliably rebuild callable tool schemas after
`tools/list` changes mid-session. The platform therefore keeps stable tools such
as:

```text
wf.workflow.list_capabilities
wf.workflow.call_capability
wf.workflow.run_deployment
```

Use those stable control-plane tools instead of depending on a brand-new dynamic
MCP tool becoming callable immediately.

## A Config Change Says `requires_reload`

Connection config mutation tools stage file-backed changes. They do not
immediately remount the live proxy/provider set.

If a response says:

```text
requires_reload: true
```

then the next action is the server reload path, not repeated rediscovery against
the old mounted set.

After reload, inspect:

```text
wf.admin.list_connections
wf.admin.list_sources
```

## `validate_deployment` Says `binding_missing`

Meaning:

```text
the artifact requires a logical source alias, but the deployment does not bind it
```

Example:

```text
artifact requires: demo.echo_tool
deployment bindings: {}
```

Fix:

- add a binding such as `"demo": "demo.personal"`
- then validate again

Use:

```text
wf.workflow.inspect_artifact
wf.workflow.save_deployment
wf.workflow.validate_deployment
```

## `validate_deployment` Says `source_missing`

Meaning:

```text
the deployment binds a logical source to a concrete source id that is not
available now
```

Likely causes:

- the connection was removed
- the deployment points at the wrong account id
- this environment never had that source configured

Fix:

- reconnect/register the source
- or rebind the deployment to another compatible source

Use:

```text
wf.admin.list_sources
wf.workflow.inspect_artifact
wf.workflow.save_deployment
```

## `validate_deployment` Says `source_disabled`

Meaning:

```text
the bound source exists, but it is not enabled
```

Fix:

- enable the source/connection when that is the correct operational choice
- or bind to another compatible enabled source

Use:

```text
wf.admin.inspect_source
wf.admin.enable_connection
wf.workflow.validate_deployment
```

## `validate_deployment` Says `capability_missing`

Meaning:

```text
the concrete source exists, but it no longer exposes the required capability
```

Likely causes:

- upstream server changed
- catalog is stale
- deployment is bound to the wrong account/source

Fix path:

1. refresh the source catalog
2. inspect the source inventory
3. if the capability is genuinely gone, rebind or migrate the artifact

Use:

```text
wf.admin.refresh_connection_catalog
wf.admin.inspect_source
wf.workflow.inspect_artifact
wf.workflow.validate_deployment
```

## `validate_deployment` Says `schema_changed`

Meaning:

```text
the capability still exists, but its current schema hashes differ from the saved
artifact contract snapshot
```

The artifact is immutable. The environment changed around it.

Inspect:

```text
wf.workflow.inspect_artifact
wf.workflow.inspect_capability
wf.workflow.validate_deployment
```

Then decide:

- migrate/create a new artifact version
- rebind to a compatible source
- or adjust deployment drift policy when the change is known acceptable

Current drift policies:

| Policy | Behavior |
| --- | --- |
| `block` | treat drift as an error |
| `warn` | return a warning diagnostic |
| `allow` | suppress schema-drift diagnostics |

Prefer `block` unless a human has actually reviewed the changed contract.

## `run_deployment` Returns `unrunnable`

`run_deployment` validates dependencies before execution. If blocking
diagnostics exist, it returns an unrunnable result instead of trying to execute a
broken graph.

Inspect the returned diagnostics first. Then use the matching section above:

- `binding_missing`
- `source_missing`
- `source_disabled`
- `capability_missing`
- `schema_changed`

Do not debug runtime behavior before dependency validation is clean.

## `run_deployment` Refuses An Interrupting Artifact

Interrupting saved artifacts are not fully supported through the current saved
artifact execution path yet.

Expected diagnostic:

```text
interrupting_artifact_unsupported
```

That is a known platform limitation, not a missing deployment binding.

## A Raw MCP Tool Works But The Workflow Version Is Awkward

This is often not a bug.

Raw tools are provider-facing. Workflow nodes are graph-facing. A tool may need a
wrapper when it:

- encodes status inside output fields
- uses provider-specific envelopes
- has human-oriented inputs rather than stable graph-oriented inputs
- needs explicit workflow outcomes where the transport only exposes generic
  success/error behavior

See [`workflow_capabilities.md`](workflow_capabilities.md).

## MCP Resources Or Prompts Are Missing

First ask whether the upstream server actually supports them.

Check:

```text
wf.admin.inspect_source
```

If the source has tools but no prompts/resources, that may be completely valid.
MCP servers are not required to implement every capability family.

## What To Capture In A Bug Report

For a control-plane discovery bug:

```text
wf.admin.list_connections
wf.admin.list_sources
wf.admin.inspect_source(<id>)
wf.admin.get_connection_statuses
```

For a deployment bug:

```text
wf.workflow.inspect_artifact(<id>, <version>)
wf.workflow.list_deployments
wf.workflow.validate_deployment(<deployment_id>)
```

For a proxy visibility bug:

```text
whether tools/list changed
whether the MCP inspector sees it
whether the LLM harness can call it in the same session
```

## Read Next

- [`wf_mcp_operator_manual.md`](wf_mcp_operator_manual.md) for the mental model
- [`wf_mcp_end_to_end_runbook.md`](wf_mcp_end_to_end_runbook.md) for the happy
  path
- [`workflow_artifacts.md`](workflow_artifacts.md) for dependency diagnostics
  and drift policy
