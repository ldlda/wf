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
- if the missing logical source is local, add a self-binding such as
  `"wf.std": "wf.std"` or `"wf.mcp": "wf.mcp"`
- then validate again

System-source self-bindings look redundant, but they mean "use the local
standard source with the same id." Current deployments bind local and external
sources through the same field.

If the artifact was created from a draft, inspect the
`create_artifact_from_draft` response for suggested local bindings.

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

## `validate_deployment(live_check=true)` Says `source_unreachable`

Meaning: static deployment validation found a matching saved source/catalog, but
the live upstream source could not answer when contacted.

Common causes:

- stdio MCP server command is missing or exits during startup
- network MCP server is offline
- auth/config changed outside the broker
- source process starts too slowly and hits the live-check timeout

What to do:

1. Check the connection with `wf.admin.get_connection_statuses`.
2. Refresh or reload the config if the source was recently enabled.
3. Fix the source command/auth/network outside the workflow artifact.
4. Run `wf.workflow.validate_deployment` again with `live_check=true`.

Do not fix this by editing the workflow artifact unless the source capability
itself changed. This is an environment problem, not workflow business logic.

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

## `run_deployment` Returns `interrupted`

The deployment paused at an interrupt node. The response should include:

```text
status: interrupted
outcome: null
run_id: <durable id>
resume_readiness: ready
interrupt: <request payload and metadata>
```

Send the requested resume payload to:

```text
wf.workflow.resume_run
```

The `run_id` identifies a stored stopped-state checkpoint and survives handler
or server recreation. Before applying the resume payload, the platform
revalidates the pinned deployment/source environment. If it returns
`resume_readiness: blocked`, inspect the diagnostics, restore the missing or
disabled source, and call `resume_run` again; the blocked attempt has not
advanced workflow state. After resume completes, `status` is `completed` and
`outcome` reports the workflow terminal outcome such as `ok` or `error`.

For debugging a completed, failed, or interrupted run, call
`wf.workflow.inspect_run` first. Only call `wf.workflow.read_run_trace` with a
small explicit range when node-level detail is necessary.

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

## A Draft Is Invalid Or Almost Correct

Use the draft tools before saving:

```text
wf.workflow.validate_draft
wf.workflow.patch_draft
wf.workflow.compile_draft
```

`validate_draft` checks the authored draft and the compiled raw workflow plan.
`patch_draft` applies RFC 6902 JSON Patch and validates the patched result.

Prefer patching a draft over patching a raw plan. The draft is the authoring
surface; the raw plan is the execution boundary.

If a draft compiles but the deployment later fails with `binding_missing`, add
the reported source binding to the deployment. Local system-source bindings can
be explicit, for example:

```json
{
  "wf.std": "wf.std",
  "wf.mcp": "wf.mcp"
}
```

For node inputs:

- `in` is path mapping only, in source-to-destination order such as
  `"input.url": "url"`.
- `with` is for static node-local values such as
  `"value": "CLICKED"`.
- Do not put literal objects inside `in`. Invalid `use` step payloads should be
  rejected, not silently treated as joins.

For strict MCP servers such as Playwright, unmapped optional tool arguments
should be omitted. If a trace shows optional keys being sent as `null`, capture
the capability name, the node trace `resolved_input`, and the upstream error;
that points at the workflow capability wrapper boundary rather than the raw MCP
tool.

## MCP Resources Or Prompts Are Missing

First ask whether the upstream server actually supports them.

Check:

```text
wf.admin.inspect_source
```

If the source has tools but no prompts/resources, that may be completely valid.
MCP servers are not required to implement every capability family.

## Test Deployment Clutter

Symptom: `wf.workflow.list_deployments` shows temporary deployments from earlier
tests or LLM attempts.

Use:

```yaml
tool: wf.workflow.delete_deployment
arguments:
  deployment_id: "test_alias_check"
```

This deletes only the mutable deployment binding. Saved artifacts and durable run
records remain.

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
- [`workflow_drafts.md`](workflow_drafts.md) for draft validation and patching
