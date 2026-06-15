# Draft Workspaces Reference

Use draft workspaces for iterative workflow authoring. They are mutable and
revisioned; artifacts are immutable and versioned.

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
  "target": { "root": "local", "parts": ["text"] },
  "path": { "root": "input", "parts": ["text"] }
}
```

Step output bindings write node-local output into workflow state:

```json
{
  "source": { "root": "local", "parts": ["echoed"] },
  "target": { "root": "state", "parts": ["echoed"] }
}
```

Top-level workflow output uses `path` / `target`, not step-level
`source` / `target`:

```json
{
  "path": { "root": "state", "parts": ["echoed"] },
  "target": { "root": "local", "parts": ["echoed"] }
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

## Focused Helpers

Prefer focused helpers over JSON Patch for common edits:

- `set_draft_name`
- `set_draft_route`
- `set_step_input_map`
- `set_step_output_map`

CLI equivalents:

```bash
wf draft set-name <workspace_id> --revision <n> --name <name>
wf draft set-route <workspace_id> --revision <n> --step <step_id> --outcome ok --to <target>
wf draft set-input <workspace_id> --revision <n> --step <step_id> --map input.text=text
wf draft set-output <workspace_id> --revision <n> --step <step_id> --map text=state.text
```

`set-input` direction: `input.text=text` means graph source `input.text` maps to
node-local target `local.text`.

`set-output` direction: `text=state.text` means node-local source `local.text`
maps to graph target `state.text`.

Use JSON Patch for structural edits the helpers do not cover.

For larger patches, write a JSON Patch array to a file and pass it with
`--input-file`:

```bash
wf draft patch <workspace_id> --revision <n> --input-file draft-patch.json
```

The patch file must be an RFC 6902 JSON Patch array, not a full draft object.
