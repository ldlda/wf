# Atomic Workflow Output Bindings Design

## Status

Approved for implementation planning on 2026-07-23.

## Problem

`WorkflowDraft.output` already stores the canonical ordered union of
`InputPathBinding | InputValueBinding`. These bindings construct the public
workflow output from workflow input, state, context, or literal JSON values.

The focused `set_workflow_output_map(...)` authoring surface narrows that model
to `dict[str, str]`. It cannot add literal outputs, cannot preserve every
canonical list shape, and only projects output schemas for single-field
top-level `input.*` and `state.*` sources. Nested sources such as
`state.report.title` therefore require separate schema patches even though the
source schema already declares the selected value.

The runtime behavior is already sufficient. The missing concept is one atomic
authoring operation over the existing canonical workflow-output binding list.

## Goals

- Replace the complete ordered workflow-output binding list in one
  revision-checked operation.
- Support path and literal bindings through the existing `InputBinding` union.
- Project missing nested public output schemas from declared workflow input or
  state source schemas.
- Validate literal outputs against already-declared public output schemas.
- Preserve the current implicit same-name state fallback when the explicit
  binding list is empty.
- Expose the canonical operation through Python, JSON-RPC, MCP, and CLI.
- Keep the existing map operation for compatibility callers while documenting
  its limitations.
- Reuse `wf_api.schema_projection` rather than adding another JSON Schema
  traversal or inference system.

## Non-Goals

- Changing `WorkflowDraft.output`, `Workflow.output`, or runtime output
  projection.
- Moving output projection into end nodes. End nodes remain control-flow nodes;
  workflow output is still projected after execution finishes.
- Inferring JSON Schema from literal values.
- Deleting output schema declarations when bindings are replaced or cleared.
- Removing the implicit output fallback for workflows with no explicit output
  bindings.
- Replacing every compatibility map reader or writer in this slice.
- Adding a generic binding editor shared by step inputs, step outputs, and
  workflow outputs.
- Generating TypeScript RPC contracts.

## Existing Runtime Semantics

The runtime distinction remains explicit:

- when `workflow.output` contains bindings, the runtime applies those bindings
  in order to construct the public output object;
- when `workflow.output` is empty, the runtime retains its current fallback and
  reads same-named top-level state fields declared by `output_schema`.

`--clear` therefore restores the existing implicit fallback. It does not mean
"produce an empty output" and does not change end-node behavior.

## Canonical Operation

Add this operation to the public workflow API:

```python
async def set_workflow_output_bindings(
    *,
    workspace_id: str,
    revision: int,
    bindings: Sequence[InputBinding],
) -> dict[str, Any]:
    """Replace canonical workflow output bindings atomically."""
```

The operation performs these steps in order:

1. Validate the request envelope and canonical binding union.
2. Check the expected draft revision before semantic inspection.
3. Validate every path source against its available workflow schema.
4. Reject duplicate or ancestor/descendant output targets.
5. Stage output-schema projection and literal validation.
6. Replace `/output` and any changed `/output_schema` through one patch.

An identical binding list with an identical projected output schema is an exact
no-op and does not advance the draft revision.

## Binding Semantics

The operation accepts the existing model unchanged:

```json
[
  {"path": "state.report.title", "target": "report.title"},
  {"path": "state.report.title", "target": "audit.title"},
  {"value": "markdown", "target": "format"}
]
```

- `path` is a `GraphSourcePath` rooted at `input`, `state`, or `context`.
- `target` is a rootless `LocalPath` inside the public output payload.
- `value` is any JSON-compatible literal, including explicit `null`, arrays,
  and objects.
- Binding order is preserved exactly.
- Repeating a path source is valid and represents public-output fan-out.
- Repeating a target is invalid.
- Ancestor/descendant targets such as `report` and `report.title` are invalid
  because applying both is order-dependent.
- Empty bindings clear the explicit list and restore implicit fallback.
- Replacing or clearing bindings never removes existing output-schema fields.

The root target `.` remains valid because it is part of the canonical
`LocalPath` model. It overlaps every other target and therefore must be the only
binding. A root path binding requires its selected source schema to be exactly
equivalent to the complete declared `output_schema`; a root literal must be a
mapping that validates against the complete declared `output_schema`. The
operation does not replace or infer the root output schema.

## Path Source And Schema Rules

For `input.*` and `state.*` path bindings:

1. Select the complete nested source fragment from `input_schema` or
   `state_schema` with `schema_fragment_at_path(...)`.
2. Reject an undeclared source path. Output authoring cannot infer a graph
   source that the workflow contract does not declare.
3. If the non-root output target is missing, project the selected fragment into
   that target with `project_schema_path_to_schema_path(...)`.
4. If the target exists, accept it only when its schema is exactly equal to the
   selected source fragment.
5. Reject incompatible targets rather than guessing JSON Schema
   assignability.

For `context.*` path bindings, no workflow-owned context schema exists. The
source remains valid under the existing model, but its output target must
already be declared. The operation cannot project or statically compare a
context source schema. Runtime resolution and final output validation remain
authoritative.

Whole-source paths `state` and `input` use the complete corresponding
schema. They can target a non-root nested output field through ordinary
projection. A whole-source-to-root binding follows the stricter exact-root rule
above.

## Literal Rules

Literal bindings never infer output schemas.

- The output target must already exist in `output_schema`.
- Validate the literal with `validate_json_value_at_schema_path(...)` against
  the selected target schema.
- A root literal must be a mapping because the runtime public output payload is
  an object.
- Explicit `null` is accepted only when the declared schema accepts null.
- Invalid literals fail before mutation and identify their binding index and
  target.

This keeps `output_schema` authoritative. Authors can use `set-contract` first
when introducing a new literal output field.

## Shared JSON Schema Operations

`wf_api.schema_projection` remains the only JSON Schema traversal and
projection implementation. This slice reuses:

- `schema_fragment_at_path(...)` for nested input/state sources;
- `schema_path_exists(...)` for declared output targets;
- `project_schema_path_to_schema_path(...)` for missing output paths;
- `validate_json_value_at_schema_path(...)` for literals.

The literal-validation helper currently uses capability-input wording in one
internal diagnostic label. Generalize that label parameter rather than adding a
workflow-output-specific validator.

Local `$defs` and legacy `definitions` references must remain self-contained
when projected. Target-side local references must be traversed through their
definition objects. Remote, unresolved, cyclic, non-object, and conflicting
references fail through the shared helper errors.

Projection is monotonic. A replacement can add missing output schema paths but
cannot delete or silently rewrite incompatible declarations.

## Revision And Error Semantics

The operation follows established semantic-authoring precedence:

1. malformed request shapes fail transport validation;
2. stale revision returns the canonical `revision_conflict` result;
3. source-path errors are reported in binding order;
4. target overlap is rejected;
5. schema projection and literal validation errors are reported in binding
   order;
6. mutation-time revision checking remains the final race guard.

Every semantic failure leaves the draft and revision unchanged. Representative
errors are:

- `bindings[0].path 'state.report.missing' is not declared`;
- `bindings[0].target 'report' overlaps bindings[1].target 'report.title'`;
- `bindings[1].target 'report.title' already has an incompatible schema`;
- `bindings[2].value does not satisfy output schema at 'format'`;
- `bindings[0].path 'context.user' requires a declared output target`.

## Compatibility Boundary

Keep `set_workflow_output_map(...)` and
`workflow.draft_workspaces.set_workflow_output_map` for existing callers.
`merge=True` remains a compatibility adapter. It preserves existing literal
records where possible but cannot add literals or faithfully represent every
ordered canonical list.

New code and documentation prefer canonical replacement. The combined map-loss
issue remains open until compatibility map readers and writers can no longer
rewrite canonical fan-out or ordering.

## Transport Design

Add these surfaces:

- Python API: `set_workflow_output_bindings`;
- JSON-RPC:
  `workflow.draft_workspaces.set_workflow_output_bindings`;
- remote RPC client method: `set_workflow_output_bindings`;
- MCP tool: `wf.workflow.set_workflow_output_bindings`.

RPC and MCP request models use `list[InputBinding]` directly. They must preserve
path/value union shapes and caller order without translating through a map.
Malformed or ambiguous binding objects fail request-envelope validation before
semantic authoring logic runs.

## CLI Design

Keep the existing command name:

```text
wf draft set-workflow-output WORKSPACE --revision N ...
```

Preferred canonical forms are:

```bash
wf draft set-workflow-output WS \
  --revision 4 \
  --map state.report.title=report.title \
  --map state.report.markdown=report.markdown \
  --value format='"markdown"'
```

and:

```bash
wf draft set-workflow-output WS \
  --revision 4 \
  --bindings-file output-bindings.json
```

CLI behavior:

- repeatable `--map GRAPH_SOURCE=LOCAL_TARGET` creates path bindings;
- repeatable `--value LOCAL_TARGET=JSON` creates literal bindings;
- convenience flags serialize all `--map` bindings in flag order followed by
  all `--value` bindings in flag order;
- `--bindings-file` accepts the exact canonical JSON array and preserves order;
- `--bindings-file` is mutually exclusive with `--map` and `--value`;
- `--clear` explicitly replaces the list with `[]`;
- no bindings and no `--clear` is an input error;
- canonical replacement does not support `--merge`;
- `--merge --map ...` delegates to the compatibility map operation;
- `--merge` rejects `--value`, `--bindings-file`, and `--clear`.

Current bindings remain exportable without another endpoint:

```bash
wf draft inspect WS --include-draft |
  jq '.draft.output' > output-bindings.json
```

## Testing

### Python Authoring And Runtime

Add focused tests for:

- ordered nested input/state path replacement;
- one source fanning out to several output targets;
- path and literal bindings in one replacement;
- nested output-schema projection from nested input and state sources;
- whole-source projection to a nested output target;
- exact-equivalent and incompatible existing target schemas;
- context paths with declared and missing output targets;
- literal scalars, objects, arrays, explicit null, and invalid values;
- root target exact-schema, mapping-literal, and overlap behavior;
- duplicate and ancestor/descendant targets;
- exact no-op behavior;
- explicit clearing without output-schema deletion;
- stale revision precedence and no mutation for every failure class;
- compatibility of the existing map-only merge operation.

Compile and execute one representative draft proving nested path projection,
literal output, source fan-out, and the empty-list fallback where practical.

### Transport And CLI

Add tests proving:

- JSON-RPC, remote client, and MCP preserve path/value unions and order;
- malformed binding objects fail request validation;
- CLI repeated `--map` and `--value` flags produce one canonical request;
- `--bindings-file` round-trips an exported inspected list;
- `--clear` is explicit and an empty accidental invocation fails;
- canonical replacement rejects `--merge` combinations;
- compatibility `--merge --map` remains operational;
- local and remote CLI targets invoke the same canonical operation.

## Documentation And Issue State

After verification:

- check the focused workflow-output literal authoring issue;
- check the nested workflow-output schema projection issue;
- keep compatibility input/output map loss open;
- leave focused step metadata updates and TypeScript parity open;
- update CLI help, user docs, MCP inventories, and agent skills with canonical
  replacement, literal, nested projection, clear, fallback, compatibility, and
  export examples;
- add a completed roadmap entry linking to the archived implementation plan;
- archive the implementation plan under
  `docs/historical/superpowers/plans/`.

## Success Criteria

- One focused operation replaces the complete canonical workflow-output
  binding list in one revision.
- Nested input/state sources, fan-out, literals, explicit null, context paths,
  and whole-source bindings use the existing runtime model unchanged.
- Missing nested output schemas are projected atomically from declared source
  schemas.
- Literal and context bindings never trigger schema inference.
- Clearing explicit bindings restores the existing same-name state fallback.
- Existing compatibility map callers retain their current behavior.
- No new persisted binding type, end-node behavior, template language, or JSON
  Schema implementation is introduced.
- Focused API, runtime, RPC, MCP, CLI, Ruff, formatting, and basedpyright checks
  pass.
