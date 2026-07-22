# Atomic Step Input Bindings Design

## Goal

Expose the canonical step input-binding list through focused draft authoring so
an agent or operator can assemble one structured node input from graph paths and
literal values in one revision-checked edit.

## Problem

The runtime and persisted workflow model already represent node input assembly
as an ordered list of `InputPathBinding | InputValueBinding`. Each binding writes
one graph-sourced or literal value to a node-local path, and several bindings can
therefore build one nested input object.

Focused draft authoring narrows this list into a source-to-target dictionary.
That surface cannot express literal values or one source feeding several local
targets. Building a structured input across several focused bind commands also
advances the draft revision after every field and can leave an incomplete
authoring state between commands.

The missing concept is not a new runtime binding. It is one atomic authoring
operation over the canonical binding list.

## Terms

- **Step input binding** is the existing canonical `InputPathBinding` or
  `InputValueBinding` stored on a node-like step.
- **Structured input assembly** is the runtime result of applying several step
  input bindings to nested node-local targets.
- **Binding replacement** replaces the complete input-binding list for one
  step. It does not merge bindings by source or target.

Do not introduce a `CompositeBinding` model. Composition is behavior produced
by the existing binding list, not a separate persisted domain object.

## Scope

This slice adds an atomic, focused operation for replacing the complete input
bindings of one capability-backed draft step. It supports:

- several graph sources assembling one nested node-local object;
- one graph source feeding several distinct node-local targets;
- literal JSON values, including explicit `null`;
- nested and whole-payload node-local targets;
- authoring-time workflow input/state schema projection from the capability
  input contract;
- local API, JSON-RPC, remote client, MCP, and CLI access.

The stored workflow shape, core runtime behavior, and canonical path models do
not change.

## Out Of Scope

This slice does not:

- add incremental add/update/remove semantics to the canonical operation;
- add revision amend, rebase, fast-forward, or history semantics;
- change step output bindings or workflow output bindings;
- solve output fan-out or literal workflow outputs;
- add focused step metadata or update-step operations;
- add TypeScript JSON-RPC parity or code generation;
- introduce a structured template language such as `$path` expressions;
- implement general JSON Schema reference resolution or schema assignability.

## Canonical Interface

Add the following method to `WorkflowApiSurface` and its local implementation:

```python
async def set_step_input_bindings(
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    bindings: Sequence[InputBinding],
) -> dict[str, Any]: ...
```

Expose the same request through:

- JSON-RPC method
  `workflow.draft_workspaces.set_step_input_bindings`;
- `RpcWorkflowApiClient`;
- the MCP workflow surface.

Transport models reuse `wf_core.models.steps.InputBinding`. They must not define
parallel path/value binding models.

The operation replaces the complete ordered list. It preserves caller order in
the stored draft. Repeated graph source paths are valid when their local targets
are distinct. Equal or ancestor/descendant local targets overlap and are
rejected, regardless of list order.

Example request bindings:

```json
[
  {"path": "state.report.title", "target": "request.title"},
  {"path": "state.report.markdown", "target": "request.body"},
  {"value": "markdown", "target": "request.format"}
]
```

## Revision And Mutation Semantics

The operation follows the established semantic-authoring precedence:

1. Validate the request envelope and canonical binding shapes.
2. Load the workspace and compare the expected revision.
3. Return the canonical `revision_conflict` result immediately when stale.
4. Resolve the current step and capability contract.
5. Validate binding semantics and compute schema projections.
6. Replace the binding list and projected schemas through one JSON Patch call.
7. Let the mutation-time revision guard protect against races after preflight.

No partial patch is persisted when any binding fails. A changed replacement
creates exactly one new draft revision. After revision and semantic validation,
an exact replacement whose canonical bindings and projected schemas equal the
stored values returns the current workspace summary without advancing the
revision.

## Semantic Validation

The authoring operation resolves the capability-backed step and validates the
complete replacement before mutation.

### Local Targets

Every binding target must resolve against the capability input schema. Nested
targets may traverse bounded local `#/$defs/...` or `#/definitions/...`
references. The whole-payload target `.` addresses the complete capability
input schema.

Targets must not overlap. For example, `request` and `request.title` cannot
appear together because the runtime would otherwise make the result depend on
write order. Two bindings with the same target are also overlapping. The same
source may feed `request.title` and `audit.title`.

### Path Bindings

`InputPathBinding.path` continues accepting canonical workflow-readable
`input.*`, `state.*`, and `context.*` paths.

For `input.*` and `state.*` sources:

- reuse an already-declared workflow schema path;
- when the source path is missing, project its schema from the corresponding
  capability-input target schema;
- apply every projection to staged schemas and commit them with the binding
  replacement.

Existing source schemas are not subjected to a new assignability algorithm.
They retain current bind behavior and remain subject to draft/runtime
validation. `context.*` bindings are valid but do not project workflow schemas.

### Literal Bindings

`InputValueBinding.value` accepts any JSON-compatible value, including `null`,
arrays, and objects. Validate a literal against the capability schema selected
by its local target before mutation. A literal targeting `.` must be an object
that satisfies the complete capability input schema because the runtime whole
payload operation requires a mapping.

## Shared JSON Schema Operations

Deepen `wf_api.schema_projection` rather than adding traversal to draft
authoring. Add one reusable schema-path selection/validation operation that:

- selects inline nested schemas;
- follows bounded local `$defs` and legacy `definitions` references;
- retains enough root definition context to validate selected fragments;
- rejects remote, unresolved, cyclic, and non-object intermediate references
  precisely;
- supports the existing projection helpers and literal validation.

The exact private/public helper split is an implementation choice, but schema
path traversal, local-reference handling, projection, and literal validation
must remain localized in `wf_api.schema_projection`.

## CLI Design

Keep the existing command name:

```text
wf draft set-input WORKSPACE --revision N --step STEP ...
```

Preferred canonical replacement forms are:

```bash
wf draft set-input WS \
  --revision 4 \
  --step publish \
  --map state.report.title=request.title \
  --map state.report.markdown=request.body \
  --value request.format='"markdown"'
```

and:

```bash
wf draft set-input WS \
  --revision 4 \
  --step publish \
  --bindings-file bindings.json
```

CLI behavior:

- repeatable `--map SOURCE=LOCAL_TARGET` creates path bindings;
- repeatable `--value LOCAL_TARGET=JSON` creates literal bindings;
- `--bindings-file` accepts the exact canonical JSON array;
- `--bindings-file` is mutually exclusive with `--map` and `--value`;
- `--clear` explicitly replaces the list with `[]`;
- no bindings and no `--clear` is an input error;
- the canonical replacement path does not support `--merge`.

`--bindings-file` preserves exact list order. Convenience flags serialize path
bindings in `--map` order followed by literal bindings in `--value` order.
Because overlapping targets are rejected, this cross-kind ordering cannot
change the assembled payload.

The existing map-only API/RPC operation and its merge behavior remain as a
compatibility adapter for real callers. Existing CLI `--merge` may continue to
delegate to that adapter only for map-only requests; it must reject combinations
with `--value`, `--bindings-file`, or `--clear`. New help and agent instructions
describe replacement as the preferred behavior.

Current bindings remain exportable without another endpoint:

```bash
wf draft inspect WS --include-draft |
  jq '.draft.steps.publish.input' > bindings.json
```

## Error Contract

Semantic errors identify the binding index and complete canonical path where
possible. Representative messages are:

- `bindings[1].target 'request.missing' is not declared by capability ...`;
- `bindings[0].target 'request' overlaps bindings[1].target 'request.title'`;
- `bindings[2].value does not satisfy the schema at 'request.format'`;
- `bindings[0].path 'input.report.title' cannot be projected from target ...`.

Malformed canonical binding objects fail request-envelope validation. After
that validation, stale revision wins over missing steps, unknown capabilities,
schema lookup, overlap, and literal-value errors. All failures leave the draft
document and revision unchanged.

## Testing

### Schema Projection

Add focused tests for:

- selecting inline and nested schema paths;
- selecting paths through `$defs` and `definitions` references;
- preserving definition context during literal validation;
- valid and invalid literal scalars, objects, arrays, and explicit `null`;
- remote, unresolved, cyclic, and non-object intermediate references.

### Python Authoring

Add API tests for:

- several path bindings assembling one nested capability input;
- path and literal bindings in one replacement;
- one source fanning out to several targets;
- explicit `null` and whole-payload bindings;
- stable binding order in the stored draft;
- input and state schema projection across several bindings;
- context bindings without schema projection;
- missing, duplicate, and ancestor/descendant targets;
- invalid literals;
- stale revision precedence and no mutation on every failure class;
- replacement rather than merge semantics;
- compatibility of the existing map-only operation.

Compile the resulting draft and execute one representative workflow to prove
the runtime receives the intended nested input object.

### Transport And CLI

Add tests proving:

- JSON-RPC, remote client, and MCP preserve canonical path/value unions and
  binding order;
- CLI `--map` and `--value` compose one replacement request;
- `--bindings-file` round-trips an exported inspected list;
- `--clear` is explicit and an empty accidental invocation fails;
- canonical replacement rejects `--merge` combinations;
- the legacy map-only merge path remains operational;
- expected errors remain compact through local and remote CLI targets.

## Documentation And Issue State

After verification:

- check the atomic structured node-input assembly issue;
- check the focused literal node-input binding issue;
- leave input/output fan-out map loss open unless the implementation also
  migrates every lossy reader and writer to canonical lists;
- leave workflow-output literals, nested workflow-output projection, focused
  step updates, and TypeScript parity open;
- update `wf_cli` and agent skill documentation with replacement, literal, and
  export examples;
- add a completed roadmap entry linking to the archived implementation plan;
- archive the implementation plan under
  `docs/historical/superpowers/plans/`.

## Success Criteria

- One focused operation replaces a step's complete canonical input-binding list
  in one revision.
- Structured nested assembly, path fan-out, literal values, explicit `null`,
  and whole-payload targets use the existing runtime model unchanged.
- All local targets are validated against the capability input schema before
  mutation.
- Missing input/state source schemas are projected atomically with the binding
  replacement.
- Existing map-only callers retain their current behavior through a compatibility
  adapter, while new callers use canonical bindings.
- No new persisted binding type or template language is introduced.
- Focused API/RPC/MCP/CLI tests, Ruff, formatting, basedpyright, compile, and
  runtime regressions pass.
