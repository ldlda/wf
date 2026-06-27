# Draft Bind From/To Design

## Status

Implemented. This design replaces `bind-output-to-state` with the general
`bind --from ... --to ...` operation. `bind-output-to-state` was introduced
recently as an incomplete narrow helper and should be removed rather than
preserved as compatibility.

## Problem

Agents authoring drafts repeatedly hit the same boundary: step input/output
bindings are not just path edits. They often require workflow-level schema
declarations too.

Today:

- `wf draft set-input` edits a step input map, but it does not declare
  `input_schema.properties.<field>`.
- `wf draft bind-output-to-state` declares one root state field and writes a
  step output binding, but only covers `local.output -> state.field`. It is too
  narrow now that input-side schema projection is needed too.
- Agents interpret this split inconsistently, then fall back to raw JSON Patch.

The product needs one capability-aware operation with the mental model:

```text
bind <destination> from <source>
```

## User-Facing Shape

Primary CLI:

```powershell
wf draft bind <workspace_id> `
  --revision <n> `
  --step <step_id> `
  --from <path> `
  --to <path>
```

Examples:

```powershell
# Workflow input into a capability input.
wf draft bind browser_ws --revision 2 --step click `
  --from input.simulate `
  --to local.simulate
```

```powershell
# Capability output into workflow state.
wf draft bind browser_ws --revision 3 --step click `
  --from local.after `
  --to state.after
```

```powershell
# Capability output into final workflow output.
wf draft bind report_ws --revision 7 --step render `
  --from local.markdown `
  --to output.markdown
```

## Semantics

`bind` is capability-aware and step-scoped. The step must be a capability-backed
draft step with a `use` field.

Supported directions:

| From | To | Draft edit | Schema projection |
|---|---|---|---|
| `input.*` | `local.*` | add/merge step input binding | copy capability input schema for `local.*` into workflow `input_schema` at `input.*` |
| `state.*` | `local.*` | add/merge step input binding | copy capability input schema for `local.*` into workflow `state_schema` at `state.*` |
| `local.*` | `state.*` | add/merge step output binding | copy capability output schema for `local.*` into workflow `state_schema` at `state.*` |
| `local.*` | `output.*` | add/merge step output binding | copy capability output schema for `local.*` into workflow `output_schema` at `output.*` |

Unsupported directions should fail clearly:

- `local.* -> local.*`
- `input.* -> state.*`
- `state.* -> output.*`
- `output.* -> local.*`
- Any path root outside `input`, `state`, `output`, or `local`

## Schema Projection

The schema projection helper should be generalized from the current
output-to-state helper.

Requirements:

- Use `jsonschema.Draft202012Validator.check_schema` to validate input schemas
  and projected schemas. Do not hand-roll JSON Schema validation.
- Copy the selected local field schema from the capability input/output schema.
- Preserve `$defs` and `definitions`, rejecting conflicting definitions.
- Insert the copied field schema at the target workflow path.
- Support nested target paths such as `state.options.timeout_seconds`.
- Create missing ancestor object schemas only when the ancestor does not exist.
- Reject inserting through an existing non-object ancestor.
- Reject overwriting an existing target property by default.

Nested insertion example:

```json
{
  "type": "object",
  "properties": {
    "options": {
      "type": "object",
      "properties": {
        "timeout_seconds": { "type": "number" }
      }
    }
  }
}
```

This is a schema projection operation, not a general JSON Schema editor. It only
copies one capability local input/output field schema to one workflow graph path.

## API Shape

Add the general method:

```python
async def bind_draft(
    self,
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    source_path: str,
    target_path: str,
) -> dict[str, Any]:
    ...
```

Name notes:

- User-facing CLI says `bind --from ... --to ...`.
- Python/RPC names should avoid reserved words and use
  `source_path` / `target_path`.
- Remove `bind_output_to_state` end-to-end. It has no long-lived compatibility
  contract and is replaced by `bind_draft`.

## RPC And MCP

New JSON-RPC method:

```text
workflow.draft_workspaces.bind
```

Params:

```json
{
  "workspace_id": "browser_ws",
  "revision": 3,
  "step_id": "click",
  "source_path": "local.after",
  "target_path": "state.after"
}
```

New MCP tool:

```text
wf.workflow.bind
```

Remove existing RPC/MCP `bind_output_to_state` surfaces during this slice.

## Repair Hints

Existing invalid-destination hints currently recommend:

```text
wf draft bind-output-to-state ...
```

They should instead recommend:

```text
wf draft bind <workspace_id> --revision <n> --step <step_id> --from local.<field> --to state.<field>
```

Future missing-input-schema diagnostics can also point to:

```text
wf draft bind <workspace_id> --revision <n> --step <step_id> --from input.<field> --to local.<field>
```

## Non-Goals

- Do not preserve `bind-output-to-state` as a compatibility alias.
- Do not add arbitrary schema editing commands.
- Do not support array item schema projection.
- Do not infer routes.
- Do not mutate bindings without revision checks.

## Acceptance Criteria

- Agents can fix browser-click input schema issues with `wf draft bind --from
  input.simulate --to local.simulate` instead of raw JSON Patch.
- Agents can bind outputs with `wf draft bind --from local.after --to
  state.after`; the old `bind-output-to-state` command/method/tool is gone.
- Nested target paths are handled safely or rejected with clear errors.
