# Workflow Lifecycle Reference

Use this when an agent needs to go from available capabilities to a saved,
validated, runnable deployment.

## Primary Path

1. List sources.
   - MCP: `wf.admin.list_sources`
   - CLI: `wf cap list --format ids`
2. List workflow capabilities.
   - MCP: `wf.workflow.list_capabilities`
   - CLI: `wf cap list`
3. Inspect one capability.
   - MCP: `wf.workflow.inspect_capability`
   - CLI: `wf cap inspect <name>`
4. Bootstrap a draft workspace.
   - MCP: `wf.workflow.create_draft_workspace_from_capability`
   - CLI: `wf draft create-from-capability <workspace_id> <capability>`
5. Inspect/patch/validate the workspace until valid.
   - Prefer focused helpers when available.
   - Use JSON Patch only for general edits.
6. Save an artifact.
   - Full workflow: `create_artifact_from_workspace`
   - Reusable wrapper: `create_wrapper_from_workspace`
7. Save and validate a deployment.
8. Run the deployment.
9. Inspect the run summary first; read bounded traces only when needed.

## Object Model

- **Source**: owner of capabilities, such as `wf.std` or `everything.default`.
- **Workflow capability**: graph-ready `NodeSpec` or saved wrapper artifact.
- **Artifact**: immutable saved workflow or wrapper.
- **Deployment**: mutable binding from artifact version to concrete sources.
- **Run**: durable stopped execution record with status, output, and trace count.

## Result Handling

`run_deployment` returns compact status by default. Capture `run_id` even for
completed or failed runs. Use:

- `inspect_run` for compact stored result.
- `read_run_trace` for explicit debug slices, for example
  `{"start": 0, "limit": 25}`.
- `resume_run` only for interrupted runs.

Do not ask for unbounded traces.
