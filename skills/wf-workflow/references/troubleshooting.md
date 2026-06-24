# Workflow Troubleshooting Reference

Use this when a source, capability, artifact, deployment, or run is missing,
unrunnable, or surprising.

## Missing Capability

Check in this order:

1. `wf status`
2. `wf cap list --format ids`
3. `wf cap inspect <capability>`

Remember: MCP control tools are not workflow capabilities. They appear in
MCP `tools/list`, not `wf cap list`.

## Unrunnable Deployment

Run `wf deploy validate <deployment_id>` before `wf run start`.

Common diagnostics:

- `binding_missing`: deployment lacks a logical-to-concrete source binding.
- `source_missing`: bound concrete source does not exist or is disabled.
- `capability_missing`: required node/reducer is not available.
- `schema_changed`: saved snapshot no longer matches current source.
- `source_unreachable`: live check could not contact an upstream source.

Use `wf explain <diagnostic-code>` after validation failures to get
human-readable explanations.

## Run Debugging

If a run fails:

1. Read `status`, `error`, `diagnostics`, and `trace_count`.
2. Use `wf run inspect <run_id>` for stored summary.
3. Use `wf run trace <run_id> --from <n> --limit <n>` with a bounded range.

Do not request full traces unless the user explicitly asks and the trace is
known to be small.

## Harness Problems

Some LLM harnesses do not refresh `tools/list` mid-session. Do not rely on new
saved workflows becoming new tools. Use `wf run start` and `wf cap call`
instead.
