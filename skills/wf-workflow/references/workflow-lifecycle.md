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
   - Use focused CLI commands (`set-name`, `set-route`, `set-input`, `set-output`)
     for common edits.
   - Use JSON Patch only for general structural edits.
6. Save an artifact.
   - Full workflow: `create_artifact_from_workspace`
   - Reusable wrapper: `create_wrapper_from_workspace`
7. Save and validate a deployment.
   - `wf deploy save` (or `wf deploy create` alias)
8. Run the deployment.
9. Inspect the run summary first; read bounded traces only when needed.

## Raw Plan Escape Hatch

Draft workspaces are the normal interactive authoring path. If a compiler,
fixture, or advanced client already has a complete raw JSON/YAML workflow plan,
use the CLI escape hatch instead of writing a helper script around the Python
API:

```bash
wf artifact create-from-plan workflow.plan.json \
  --artifact <artifact_id> \
  --version 1 \
  --title "Workflow Title" \
  --outcome ok \
  --binding <logical_source>=<concrete_source>
```

Do not pass draft JSON to `artifact create-from-plan`. Drafts use `steps`,
`routes`, and step field `use`. Raw plans use `nodes`, `edges`, and node field
`node`.

Then continue with the normal deployment and run steps:

```bash
wf deploy save <deployment_id> --artifact <artifact_id> --version 1
wf deploy validate <deployment_id>
wf run start <deployment_id> --input-file input.json
```

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
