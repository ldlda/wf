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

If a patch returns `revision_conflict`, fetch the workspace again and retry
against the latest revision.

Forward routes in drafts are allowed as invalid intermediate state. If
`wf draft add-step --route ok=collect` returns `status: invalid`, add the
missing `collect` step next, then run `wf draft validate`. Do not save or
compile until validation is valid.

## Focused Helpers

Prefer focused helpers over JSON Patch for common edits:

- `set_draft_name`
- `set_draft_route`
- `set_step_input_map`
- `set_step_output_map`
- `bind_draft`
- `add_step_from_capability`
- `branch_draft`
- `handle_draft`
- `compile_draft_workspace`

CLI equivalents:

```bash
wf draft set-name <workspace_id> --revision <n> --name <name>
wf draft set-route <workspace_id> --revision <n> --step <step_id> --outcome ok --to <target>
wf draft set-input <workspace_id> --revision <n> --step <step_id> --map input.text=text
wf draft set-input <workspace_id> --revision <n> --step <step_id> --merge --map input.other=other
wf draft set-output <workspace_id> --revision <n> --step <step_id> --map text=state.text
wf draft set-output <workspace_id> --revision <n> --step <step_id> --merge --map other=state.other
wf draft branch <workspace_id> --revision <n> --step <step_id> --route ok=__end__ --route error=fail
wf draft handle <workspace_id> --revision <n> --to fail --branch lookup:error --branch transform:error
wf draft compile <workspace_id>
wf draft bind <workspace_id> --revision <n> --step <step_id> --from local.<field> --to state.<field>
wf draft bind <workspace_id> --revision <n> --step <step_id> --from input.<field> --to local.<field>
wf draft add-step <workspace_id> --revision <n> --step <step_id> --capability <qualified_name> --from-step <prev> --from-outcome ok --route ok=__end__ --route error=fail --input input.text=text --bind-output result=state.result
```

`set-input` direction: `input.text=text` means graph source `input.text` maps to
node-local target `local.text`.

`set-output` direction: `text=state.text` means node-local source `local.text`
maps to graph target `state.text`.

Without `--merge`, `set-input` and `set-output` replace the whole map for that
step. Use repeated `--map` flags in one command for a complete replacement. Use
`--merge` only when adding/updating entries over multiple revisions.

- `bind_draft`

  Declares a workflow input/state/output schema field from a capability local
  input/output schema and merges the matching step binding. Use `input/state ->
  local` for step inputs and `local -> state/output` for step outputs. Prefer
  this over manual JSON Patch when validation says a target schema field is
  missing. The selected step must have `use` so the helper can find the
  capability schema. It intentionally rejects non-capability/control steps
  instead of guessing.

```bash
wf draft bind <workspace_id> --revision <n> --step <step_id> --from local.<field> --to state.<field>
wf draft bind <workspace_id> --revision <n> --step <step_id> --from input.<field> --to local.<field>
wf draft validate <workspace_id>
```

- `add_step_from_capability`

  Adds a new capability-backed step with explicit route, input bindings, and
  output-to-state schema/binding wiring in one revision. It can set the incoming
  edge, outgoing edges, input map, and output-to-state schema/binding. Use
  `--route OUTCOME=TARGET` for each outcome; when omitted and the capability
  declares a single outcome, that outcome routes to `__end__`. Multi-outcome
  capabilities require exact route coverage; missing or unknown outcomes are
  rejected before mutation. It still requires explicit choices; if you do not
  know a map, inspect the capability or run validation rather than guessing.

```bash
wf draft add-step <workspace_id> --revision <n> --step <step_id> --capability <qualified_name> --from-step <prev> --from-outcome ok --route ok=__end__ --route error=fail --input input.text=text --input input.other=other --bind-output result=state.result --bind-output title=state.title
wf draft validate <workspace_id>
```

Repeat `--input` and `--bind-output` once per mapping. Do not write
`--bind-output title=state.title summary=state.summary`; the second mapping is
an unexpected extra argument because it is not attached to its own flag.

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
`wf draft bind`, use it before hand-editing schemas or step bindings.

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
