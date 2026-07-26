# Draft Workspaces Reference

Use draft workspaces for iterative workflow authoring. They are mutable and
revisioned; artifacts are immutable and versioned.

Before writing or patching a draft, inspect the current public shape:

    wf schema draft
    wf schema DraftUseStep

## Draft Shape

A draft has:

- `name`
- `input_schema`
- `state_schema`
- `output_schema`
- `start`
- `steps`
- `routes`
- optional top-level `output`

`steps` are keyed by stable ids. `routes` map outcomes to another step id or
`__end__`.

## Mapping Rules

Step input bindings read graph values into node-local input:

```json
{
  "target": "text",
  "path": "input.text"
}
```

Step output bindings write node-local output into workflow state:

```json
{
  "source": "echoed",
  "target": "state.echoed"
}
```

Top-level workflow output uses `path` / `target`, not step-level
`source` / `target`:

```json
{
  "path": "state.echoed",
  "target": "echoed"
}
```

## Workspace Flow

1. Create workspace from capability.
2. Get workspace with `include_draft=true` before patching.
3. Patch with current `revision`.
4. Validate workspace.
5. Save artifact or wrapper from workspace.

Capability-backed creation auto-binds required capability inputs only. Optional
inputs remain declared by the capability but are omitted from the initial step
input map. Add one deliberately when the workflow should expose it:

```bash
wf draft bind report_ws --revision 2 --step call --from input.path --to local.path
```

If a patch returns `revision_conflict`, fetch the workspace again and retry
against the latest revision.

Forward routes in drafts are allowed as invalid intermediate state. If
`wf draft add capability --route ok=collect` returns `status: invalid`, add the
missing `collect` step next, then run `wf draft validate`. Do not save or
compile until validation is valid.

## Focused Helpers

Prefer focused helpers over JSON Patch for common edits:

- `set_draft_name`
- `set_draft_route`
- `set_step_input_map`
- `set_step_output_bindings`
- `set_step_output_map`
- `set_workflow_output_bindings`
- `set_workflow_output_map` (compatibility-only map adapter)
- `bind_draft`
- `add_step`
- `add_step_from_capability`
- `branch_draft`
- `handle_draft`
- `compile_draft_workspace`

CLI equivalents:

```bash
wf draft set-name <workspace_id> --revision <n> --name <name>
wf draft set-route <workspace_id> --revision <n> --step <step_id> --outcome ok --to <target>
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
wf draft add interrupt <workspace_id> --revision <n> --step review --kind issue_review --request-schema-file request.schema.json --resume-schema-file resume.schema.json --outcome submitted --outcome cancelled --route submitted=next --route cancelled=revise
wf draft add when <workspace_id> --revision <n> --step decide --condition-file condition.json --then next --otherwise revise
```

`set-workflow-output` replaces the complete ordered top-level
`WorkflowDraft.output` binding list. It accepts graph source paths
(`input.*`, `state.*`, or `context.*`) and literal values; `set-output` edits
one step's local-to-state bindings. Nested `input.*` and `state.*` sources can
project missing output-schema fields from their declared source schemas.
Literal values and `context.*` paths require declared output targets, and
literal values are validated against those targets rather than inferred.

`set-input` direction: `input.title=report.title` means graph source
`input.title` maps to node-local target `local.report.title`. Targets are
rootless node-local paths; never prefix the target with `local.`. Existing
single-field targets such as `input.text=text` remain valid. Repeated graph
sources are allowed and preserve fan-out to distinct local targets.

Canonical replacement can mix ordered path and literal bindings:

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

Replacement is the default and `--bindings-file` is the canonical lossless
form. `--merge` is retained only for compatibility map-only edits. Do not use
it to add literals or when canonical ordering or repeated-source fan-out must
survive. Existing literal bindings are retained during a map-only merge.

`set-output` direction: `text=state.text` means node-local source `local.text`
maps to graph target `state.text`.

Without `--merge`, `set-input` replaces the whole ordered binding list;
`set-output` replaces its complete ordered canonical binding list. Repeated
sources are valid fan-out when their state targets differ. Use the canonical
file form for a lossless round-trip, or `--clear` to replace the list with no
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

`--clear` replaces the list with `[]` and restores the implicit same-name state
fallback. `--merge --map` is compatibility-only and may collapse existing
fan-out; it cannot preserve literals or canonical ordering. Use it only when a
lossy map edit is acceptable.

`bind input.title -> local.report.title` is schema-aware and idempotent when
`input.title` is already declared. Bind names both rooted endpoints explicitly.
Use it for repair hints or schema projection. Use
`set-input --merge --map input.title=report.title` when you only need to update
a compatibility step input map; that command already implies the local side.

- `bind_draft`

  Declares a workflow input/state/output schema field from a capability local
  input/output schema and merges the matching step binding. Use `input/state ->
  local` for step inputs and `local -> state/output` for step outputs. Prefer
  this over manual JSON Patch when validation says a target schema field is
  missing. The selected step must have `use` so the helper can find the
  capability schema. It intentionally rejects non-capability/control steps
  instead of guessing. A `local.x -> output.y` bind is atomic: it projects the
  capability field schema into both workflow state and output schemas, writes
  `local.x -> state.y` on the step, and publishes `state.y -> output.y` at the
  workflow boundary.

```bash
wf draft bind <workspace_id> --revision <n> --step <step_id> --from local.report.markdown --to state.report.markdown
wf draft bind <workspace_id> --revision <n> --step <step_id> --from input.title --to local.report.title
wf draft bind <workspace_id> --revision <n> --step <step_id> --from local.report.markdown --to output.report.markdown
wf draft validate <workspace_id>
```

- `add_step_from_capability`

  Adds a new capability-backed step with explicit route, input bindings, and
  output-to-state schema/binding wiring in one revision. It can set the incoming
  edge, outgoing edges, input map, and output-to-state schema/binding. Use
  `--route OUTCOME=TARGET` for each outcome; when omitted and the capability
  declares a single outcome, that outcome routes to `__end__`. Multi-outcome
  capabilities require exact route coverage; missing or unknown outcomes are
  rejected before mutation. When `wf draft add capability --route` rejects an
  outcome, the
  error reports declared outcomes and direct add/remove repair guidance. Remove
  unknown route entries and add one route for each missing declared outcome. It
  still requires explicit choices; if you do not
  know a map, inspect the capability or run validation rather than guessing.
  Explicit `--input input.title=report.title` and
  `--input state.title=report.title` mappings project the corresponding
  workflow input/state schema paths from the nested capability input schema.

```bash
wf draft add capability <workspace_id> --revision <n> --step <step_id> --capability <qualified_name> --from-step <prev> --from-outcome ok --route ok=__end__ --route error=fail --input input.text=text --input input.other=other --bind-output result=state.result --bind-output title=state.title
wf draft validate <workspace_id>
```

Repeat `--input` and `--bind-output` once per mapping. Do not write
`--bind-output title=state.title summary=state.summary`; the second mapping is
an unexpected extra argument because it is not attached to its own flag.

- `add_step`

  Adds any typed `DraftStep` with optional incoming and outgoing route wiring in
  one revision. The CLI exposes one command per kind under `wf draft add`:
  `interrupt`, `foreach`, `join`, `end`, `when`, `choose`, `match`, and
  `subgraph`. Decision targets are embedded and reject `--route`. Interrupts
  and subgraphs preserve JSON Schema boundary contracts. Invalid intermediate
  drafts remain saveable in the workspace but must pass `wf draft validate`
  before compile or artifact save.

- `branch_draft`

  Updates routes for an existing step in one revision without rewriting the
  full routes object. Supply `--route OUTCOME=TARGET` for each outcome to
  set or update.

- `handle_draft`

  Routes multiple source step outcomes to a common target. Supply
  `--branch STEP:OUTCOME` for each source outcome and `--to TARGET` for the
  shared destination.

- `compile_draft_workspace`

  API/RPC/MCP returns the compiled raw plan plus required capabilities without
  mutating or saving the draft workspace. The CLI prints only the raw plan JSON
  on success. On invalid draft status, it returns structured diagnostics without
  a `compiled_plan`.

Validation repair hints are product guidance. If a diagnostic suggests
`wf draft bind`, run that exact focused command before hand-editing schemas or
step bindings, then validate the new revision.

Remove commands are for recovery. They do not delete schema fields and
`remove-step` does not remove inbound routes. Validate after removal and repair
the resulting diagnostics explicitly.

Use JSON Patch for structural edits the helpers do not cover.

For larger patches, write a JSON Patch array to a file and pass it with
`--input-file`:

```bash
wf draft patch <workspace_id> --revision <n> --input-file draft-patch.json
```

The patch file must be an RFC 6902 JSON Patch array, not a full draft object.
