---
name: wf-cli
description: Use when authoring, validating, deploying, running, or debugging workflows through the repo-local `wf` CLI.
---

# wf CLI

Use the `wf` CLI when an agent needs a shell-friendly workflow lifecycle:

1. Discover capabilities.
2. Create or patch a draft workspace.
3. Validate the draft.
4. Save an artifact.
5. Save and validate a deployment.
6. Run the deployment.
7. Read bounded trace slices only when debugging.

Canonical docs:

- `docs/wf_cli.md`
- `docs/workflow_capabilities.md`
- `docs/workflow_drafts.md`
- `docs/workflow_artifacts.md`
- `docs/durable_run_operations.md`

If the workflow object model is unclear, read
`skills/wf-workflow/references/system-model.md` before choosing commands.

## Core Commands

```bash
wf --config wf.config.json status
wf cap list --format ids
wf cap inspect <capability>
wf cap call <capability> --input '{"field":"value"}'

wf draft create <workspace_id> --name <name>
wf draft create <workspace_id> --capability <capability>
wf draft inspect <workspace_id> --include-draft
wf draft patch <workspace_id> --revision <n> --input-file patch.json
wf draft set-name <workspace_id> --revision <n> --name <name>
wf draft set-start <workspace_id> --revision <n> --step <step_id>
wf draft set-contract <workspace_id> --revision <n> --state-schema-file state.schema.json --outcome ok --outcome error
wf draft set-route <workspace_id> --revision <n> --step <step_id> --outcome <outcome> --to <target>
wf draft set-input <workspace_id> --revision <n> --step <step_id> --map input.title=report.title
wf draft set-input <workspace_id> --revision <n> --step <step_id> --value request.format='"markdown"'
wf draft set-input <workspace_id> --revision <n> --step <step_id> --bindings-file bindings.json
wf draft set-input <workspace_id> --revision <n> --step <step_id> --clear
wf draft set-input <workspace_id> --revision <n> --step <step_id> --merge --map input.other=other
wf draft set-output <workspace_id> --revision <n> --step <step_id> --map text=state.text
wf draft set-output <workspace_id> --revision <n> --step <step_id> --bindings-file bindings.json
wf draft set-output <workspace_id> --revision <n> --step <step_id> --clear
wf draft set-output <workspace_id> --revision <n> --step <step_id> --merge --map other=state.other
wf draft set-workflow-output <workspace_id> --revision <n> \
  --map state.value=result --value format='"markdown"'
wf draft set-workflow-output <workspace_id> --revision <n> \
  --bindings-file output-bindings.json
wf draft set-workflow-output <workspace_id> --revision <n> --clear
wf draft set-workflow-output <workspace_id> --revision <n> \
  --merge --map state.other=other
wf draft branch <workspace_id> --revision <n> --step <step_id> --route ok=__end__ --route error=fail
wf draft handle <workspace_id> --revision <n> --to fail --branch lookup:error --branch transform:error
wf draft compile <workspace_id>
wf draft bind <workspace_id> --revision <n> --step <step_id> --from local.report.markdown --to state.report.markdown
wf draft bind <workspace_id> --revision <n> --step <step_id> --from input.title --to local.report.title
wf draft add capability <workspace_id> --revision <n> --step <step_id> --capability <qualified_name> --from-step <prev> --from-outcome ok --route ok=__end__ --route error=fail --input input.title=report.title --bind-output result=state.result
wf draft add interrupt <workspace_id> --revision <n> --step review --kind issue_review \
  --request-schema-file request.schema.json --resume-schema-file resume.schema.json \
  --outcome submitted --outcome cancelled --route submitted=next --route cancelled=revise
wf draft add when <workspace_id> --revision <n> --step decide --condition-file condition.json --then next --otherwise revise
wf draft validate <workspace_id>
wf draft save <workspace_id> --artifact <artifact_id> --version <n> --title <title>

Choose `draft create --capability` when the first step should derive its
contract and wrapper hints from a known capability. Choose `draft create
--name` for control-first, interrupt-first, end-first, or subgraph-first
authoring. An empty draft is expected to remain invalid until its start, steps,
routes, and contract agree.

`draft set-contract` replaces each supplied top-level schema or the complete
outcomes list; it does not deep-merge schemas. Prefer `draft bind` or `draft add
capability` when selected fields should be projected from a known node
contract. Use JSON Patch only for field-level schema surgery not covered by a
focused operation.

Draft creation auto-binds required capability inputs only. Optional inputs are
reported in wrapper-hint notes; bind them explicitly only when the workflow
should expose them. Use `wf draft bind --from input.x --to local.x` for an
existing step when schema projection may be needed; it is safe if the schema
field already exists. Use `wf draft set-input --merge --map input.x=x` for a
compatibility map-only edit when the workflow schema is already declared.

`wf draft bind` names both endpoints explicitly, so local paths keep the
`local.` root. `set-input` and `draft add capability --input` already imply the
local side, so their targets are rootless paths: write
`input.title=report.title`, not `input.title=local.report.title`.

`wf draft set-workflow-output` replaces the complete ordered public output
projection. Nested `input.*` and `state.*` sources can project missing nested
output-schema fields from declared source schemas. Literal values and
`context.*` paths require declared output targets; literals validate against
those targets and do not infer schemas. Use `wf draft bind --from local.x --to
output.y` when the source is a step-local capability output.

When `wf draft validate` returns a `repair_hint`, run that exact focused command
before writing JSON Patch manually. To make one capability output public, use
`wf draft bind <workspace_id> --revision <n> --step <step_id> --from local.x
--to output.y`; it creates the required state intermediary and projects the
field schema into both state and output schemas atomically. Re-run
`wf draft validate` after the repair.

wf artifact create-from-plan workflow.plan.json --artifact <artifact_id> --version <n> --title <title>
wf deploy save <deployment_id> --artifact <artifact_id> --version <n> --binding <logical>=<concrete>
wf deploy create <deployment_id> --artifact <artifact_id> --version <n>
wf deploy validate <deployment_id>
wf run start <deployment_id> --input-file input.json
wf run trace <run_id> --from 0 --limit 25
```

## Public Discovery Order

Use public CLI surfaces before broader documentation or implementation search:

1. `wf status`
2. `wf cap list --format ids`
3. `wf cap inspect <capability>`
4. `wf schema` to list workflow document/component shapes
5. `wf schema draft`, `wf schema raw`, or `wf schema <Component>`
6. `wf explain <diagnostic-code>` after validation failures

Use `wf schema <name> --verbose` only when the complete JSON Schema is required;
the default compact outline is preferred for agent context. `--full` is accepted
as an alias for `--verbose`.

For `draft set-input`, repeated `--map` and `--value` flags define the complete
ordered replacement list. Repeated graph sources are valid and preserve
fan-out. Use `--bindings-file` for the canonical lossless JSON form, or
`--clear` to replace the list with `[]`. `--merge` is compatibility-only and
accepts map-only `--map` edits; compatibility map readers/writers cannot
preserve repeated-source fan-out.

Export, edit, restore, or clear canonical bindings as follows:

```bash
wf draft inspect WS --include-draft |
  jq '.draft.steps.publish.input' > bindings.json

wf draft set-input WS --revision 4 --step publish \
  --map state.report.title=request.title \
  --map state.report.markdown=request.body \
  --value request.format='"markdown"'

wf draft set-input WS --revision 5 --step publish \
  --bindings-file bindings.json

wf draft set-input WS --revision 6 --step publish --clear
```

For `draft set-output`, repeated `--map` flags define the complete ordered
canonical binding list and preserve repeated-source fan-out. The canonical
file form is lossless, and `--clear` explicitly replaces the list with no
bindings:

```bash
wf draft set-output WS --revision 4 --step analyze \
  --map report.title=state.report.title \
  --map report.title=state.audit.title

wf draft inspect WS --include-draft |
  jq '.draft.steps.analyze.output' > output-bindings.json

wf draft set-output WS --revision 5 --step analyze \
  --bindings-file output-bindings.json

wf draft set-output WS --revision 6 --step analyze --clear
```

`--merge --map` is compatibility-only and may collapse existing fan-out. Use
it only when a lossy map edit is acceptable.

Use `set-workflow-output` without `--merge` when replacing the complete public
output projection. Use `--bindings-file` when exact path/value interleaving
must round-trip, and `--clear` to restore implicit same-name state fallback.
Use `--merge --map` only when a lossy compatibility edit is acceptable.

Prefer `draft bind` when a capability step binding also needs schema
projection. Use `input/state -> local` for step inputs and `local ->
state/output` for step outputs. It requires a capability-backed step with
`use`; use JSON Patch for non-capability/control draft steps.

To add a capability step, prefer `wf draft add capability` over raw
JSON Patch when the route, input bindings, and output-to-state bindings are
known. It is explicit and does not guess missing maps.
If a capability has multiple outcomes, pass one `--route OUTCOME=TARGET` for
each declared outcome; extra outcome names are rejected.
Repeat `--input` and `--bind-output` once per mapping. Do not put multiple
mappings after one flag.

```bash
wf draft add capability <workspace_id> --revision <n> --step <step_id> --capability <qualified_name> --description "Publish report" --retry 2 --timeout-seconds 30 --input state.title=title --value format='"markdown"' --bind-output markdown=state.markdown
wf draft update capability <workspace_id> --revision <n> --step <step_id> --clear-description --retry 0 --clear-timeout
```

For `update capability`, omission preserves a field and `--clear-*` removes
the selected metadata. Any `--input`/`--value` update replaces the complete
ordered input list; use `--bindings-file` for exact path/value interleaving or
`--clear-input` for `[]`. The update preserves `use`, routes, and outputs.
Use separate focused commands for routes/outputs, and remove/add to change the
capability.

Use the matching `wf draft add <kind>` command for control steps. `when`,
`choose`, and `match` embed their targets and do not accept `--route`.
Interrupt and subgraph commands preserve their explicit schema contracts.
Intermediate drafts may remain `status: invalid`; run `wf draft validate`
after the intended steps and routes are present.

`wf draft compile` prints the raw plan JSON directly on success. Do not expect a
top-level `compiled_plan` key from the CLI output.

- To undo a bad draft edit, prefer `wf draft remove-route`,
  `wf draft remove-step`, or `wf draft remove-binding` over JSON Patch.

## Rules

- For interrupted runs, call `wf run inspect <run_id>` before resuming. If the
  interrupt includes `resume_schema`, shape `wf run resume --payload` to that
  schema instead of guessing field names.
- Use explicit `--config <path>` for examples, challenge workspaces, and
  non-root configs. The default is `wf.config.json` in the current working
  directory.
- Prefer `--input-file` for large JSON.
- Prefer `--format ids` or `--format compact` for discovery.
- Use `wf cap call` as a cheap smoke test before creating a draft.
- Prefer draft workspaces for iterative authoring; use `artifact create-from-plan`
  only when you already have a complete raw JSON/YAML workflow plan.
- Do not request unbounded traces.
- Do not treat wrapper hints as semantic guarantees.
- If validation fails, run `wf explain <code>` or `wf explain --input-file <validation-output.json>`.
- For draft validation errors, run `wf explain <code>`. If routes point to a
  missing step, create the target step first or repair routes with
  `wf draft handle` / `wf draft branch`.
- Do not use planning-session specs or implementation plans as user-facing runtime guidance.
- `set-input --map` is `GRAPH_SOURCE=BARE_LOCAL_FIELD`; never prefix the target
  with `local.`.
- For `wf draft add capability --route`, route only outcomes reported by `wf cap inspect` or
  the command error's `declared_outcomes` field.
- Do not confuse draft shape with raw plan shape: drafts use `steps/routes/use`;
  raw plans use `nodes/edges/node`.
- Use `wf schema` to list workflow document/component shapes.
- Use `wf schema draft`, `wf schema raw`, or `wf schema <Component>` for compact
  JSON guidance before authoring.
- Add `--verbose` only when a complete JSON Schema document is required; it may
  be large. `--full` is an alias if you already tried that spelling.
- Prefer `wf schema` over searching tests or implementation code for draft/raw
  plan shape.
- Treat compact schema output as authoring guidance; use validation commands as
  the source of truth for a concrete document.
- If public commands and supplied skills are insufficient, report the exact
  blocker instead of guessing undocumented fields.
- When artifact save returns `suggested_bindings`, copy those values into
  `wf deploy save --binding`; otherwise choose the concrete source explicitly.
- `status: invalid` from a draft edit is not always a command failure. Inspect
  diagnostics and continue repairing the same workspace unless the command
  reports a conflict or malformed patch.
