# Workflow Troubleshooting Reference

Use this when a source, capability, artifact, deployment, or run is missing,
unrunnable, or surprising.

## Missing Capability

Check in this order:

1. `wf.admin.list_sources`
2. `wf.admin.inspect_source`
3. `wf.workflow.list_capabilities`
4. `wf.workflow.inspect_capability`

Remember: MCP control tools are not workflow capabilities. They appear in
MCP `tools/list`, not `wf.workflow.list_capabilities`.

## Unrunnable Deployment

Run `validate_deployment` before `run_deployment`.

Common diagnostics:

- `binding_missing`: deployment lacks a logical-to-concrete source binding.
- `source_missing`: bound concrete source does not exist or is disabled.
- `capability_missing`: required node/reducer is not available.
- `schema_changed`: saved snapshot no longer matches current source.
- `source_unreachable`: live check could not contact an upstream source.

Use `live_check=true` only when you intentionally want to contact upstream
sources. It may spawn stdio servers or perform network I/O.

## Run Debugging

If a run fails:

1. Read `status`, `error`, `diagnostics`, and `trace_count`.
2. Use `inspect_run` for stored summary.
3. Use `read_run_trace` with a bounded range.

Do not request full traces unless the user explicitly asks and the trace is
known to be small.

## Harness Problems

Some LLM harnesses do not refresh `tools/list` mid-session. Do not rely on new
saved workflows becoming new tools. Use `run_deployment` and `call_capability`
instead.
