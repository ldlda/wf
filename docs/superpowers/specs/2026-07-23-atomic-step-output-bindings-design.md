# Atomic Step Output Bindings Design

## Status

Approved for implementation planning on 2026-07-23.

## Problem

Canonical step outputs are ordered `OutputBinding` records that map one
node-local output path into one workflow state path. The focused authoring
surface currently reduces those records to a `dict[str, str]`. That map cannot
represent one local source feeding several state targets, so reading and later
merging a valid canonical list can silently discard fan-out.

The existing focused operation also patches only the binding list. Callers must
separately declare matching state schema paths even when the capability output
schema already describes the source values. This makes a common authoring edit
multi-step and exposes an avoidable intermediate invalid revision.

## Goals

- Replace one capability step's complete ordered output-binding list in one
  revision-checked operation.
- Preserve source fan-out and nested local/state paths without lowering through
  a dictionary.
- Project missing state schema paths from the capability output schema in the
  same atomic mutation.
- Expose the canonical operation through Python, JSON-RPC, MCP, and CLI.
- Keep the existing map operation for real compatibility callers while making
  its lossy behavior explicit.
- Reuse the existing schema path and projection helpers instead of adding a
  second JSON Schema implementation.

## Non-Goals

- Changing the persisted `OutputBinding` model or runtime output application.
- Supporting literal step outputs. Step outputs read values produced by a node;
  literal bindings belong to workflow output projection, not this operation.
- Solving top-level workflow output literals or nested workflow output schema
  projection.
- Replacing every legacy output-map reader in this slice.
- Adding a generic input/output binding replacement framework.
- Generating TypeScript RPC contracts.

## Canonical Operation

Add this operation to the public workflow API:

```python
async def set_step_output_bindings(
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    bindings: Sequence[OutputBinding],
) -> dict[str, Any]:
    """Replace one capability step's canonical output bindings atomically."""
```

The operation performs these steps in order:

1. Validate the request envelope before entering semantic authoring logic.
2. Check the expected draft revision before reading the step or capability.
3. Require the selected draft step to declare a capability through `use`.
4. Resolve that capability's output schema contract.
5. Validate every local `source` against the capability output schema.
6. Reject duplicate or ancestor/descendant state `target` paths.
7. Project each missing state target from its selected capability output schema
   fragment, preserving local `$defs` and `definitions` references.
8. Accept an existing state target only when its schema is exactly equal to the
   selected capability output fragment.
9. Replace the step output list and any changed `state_schema` in one patch.

An identical binding list with an identical projected state schema is an exact
no-op: return the current workspace summary without incrementing the revision.

## Binding Semantics

The operation accepts the existing core model unchanged:

```json
[
  {"source": "report.title", "target": "state.report.title"},
  {"source": "report.title", "target": "state.audit.title"},
  {"source": ".", "target": "state.raw_result"}
]
```

- `source` is a rootless `LocalPath`. `.` selects the complete capability
  output payload.
- `target` is a non-root `StatePath`, serialized with the `state.` prefix.
- Binding order is preserved exactly.
- Repeating a source is valid and represents fan-out.
- Repeating a target is invalid.
- Ancestor/descendant targets such as `state.report` and
  `state.report.title` are invalid because applying both is order-dependent.
- Empty bindings are valid and clear the step output list; they do not remove
  previously declared state schema fields.

## Schema Projection

`wf_api.schema_projection` remains the only implementation of JSON Schema path
selection and projection. Output authoring uses
`schema_fragment_at_path(...)`, `schema_path_exists(...)`, and
`project_schema_path_to_schema_path(...)` rather than introducing output-only
schema traversal.

For each binding:

- select `source.parts` from the capability output schema;
- if `target.parts` is absent from the draft state schema, copy the selected
  fragment into that target path;
- if the target exists with the exact same schema, leave it unchanged;
- if the target exists with a different schema, reject the operation rather
  than guessing JSON Schema compatibility;
- reject unresolved, remote, cyclic, or conflicting schema references through
  the existing projection errors.

Projection is monotonic. Replacing or clearing bindings never deletes state
schema declarations because other steps or reducers may still depend on them.

## Compatibility Boundary

Keep `set_step_output_map(...)` and
`workflow.draft_workspaces.set_step_output_map` unchanged for existing callers.
Its `merge=True` mode remains a compatibility adapter and remains inherently
lossy when canonical fan-out already exists.

New code and documentation prefer canonical replacement. The issue describing
lossy compatibility maps remains open until all map readers and writers are
removed or made incapable of rewriting canonical fan-out.

## Transport Design

Add these surfaces:

- Python API: `set_step_output_bindings`;
- JSON-RPC: `workflow.draft_workspaces.set_step_output_bindings`;
- remote RPC client method: `set_step_output_bindings`;
- MCP tool: `wf.workflow.set_step_output_bindings`.

RPC and MCP request models use `list[OutputBinding]` directly. They must preserve
the canonical list order and must not translate through `DraftPathMap`.
Malformed objects fail Pydantic/request-envelope validation before semantic
authoring logic runs.

## CLI Design

Keep the existing command name:

```text
wf draft set-output WORKSPACE --revision N --step STEP ...
```

Preferred canonical forms are:

```bash
wf draft set-output WS \
  --revision 4 \
  --step analyze \
  --map report.title=state.report.title \
  --map report.title=state.audit.title
```

and:

```bash
wf draft set-output WS \
  --revision 4 \
  --step analyze \
  --bindings-file output-bindings.json
```

CLI behavior:

- repeatable `--map LOCAL_SOURCE=STATE_TARGET` creates canonical bindings in
  flag order;
- `--bindings-file` accepts the exact canonical JSON array and preserves order;
- `--clear` explicitly replaces the list with `[]`;
- no bindings and no `--clear` is an input error;
- `--bindings-file` and `--clear` are mutually exclusive with `--map`;
- canonical replacement does not support `--merge`;
- `--merge --map ...` delegates to the legacy map operation and is documented
  as compatibility-only and potentially lossy.

Current bindings remain exportable without another endpoint:

```bash
wf draft inspect WS --include-draft |
  jq '.draft.steps.analyze.output' > output-bindings.json
```

## Error Contract

Semantic failures should identify the binding index and canonical path where
possible. Representative errors are:

- `bindings[1].source 'missing' is not declared by capability 'report.analyze'`;
- `bindings[0].target 'state.report' overlaps bindings[1].target 'state.report.title'`;
- `bindings[0].target 'state.report.title' already has an incompatible schema`;
- `bindings[2].source '.' cannot be projected to 'state.raw_result': ...`.

After request-envelope validation, stale revision wins over missing steps,
unknown capabilities, schema lookup, overlap, and projection errors. Every
failure leaves the draft and revision unchanged.

## Testing

### Python Authoring

Add focused tests for:

- ordered replacement with nested local and state paths;
- one local source fanning out to several state targets;
- whole-payload `.` projection;
- missing nested state schema projection;
- exact-equivalent existing target schemas;
- incompatible existing target schemas;
- missing local sources;
- duplicate and ancestor/descendant state targets;
- stable binding order in the stored draft;
- exact no-op behavior;
- explicit clearing without state schema deletion;
- stale revision precedence and no mutation for every failure class;
- compatibility of the existing map-only merge operation.

Compile and execute one representative draft to prove runtime output fan-out
writes the expected values to both state paths.

### Transport And CLI

Add tests proving:

- JSON-RPC, remote client, and MCP preserve canonical output-binding order and
  duplicate sources;
- malformed binding objects fail request validation;
- CLI repeated `--map` flags preserve order and fan-out;
- `--bindings-file` round-trips an exported inspected list;
- `--clear` is explicit and an empty accidental invocation fails;
- canonical replacement rejects `--merge` combinations;
- compatibility `--merge --map` remains operational;
- local and remote CLI targets use the same canonical operation.

## Documentation And Issue State

After verification:

- keep the combined input/output map-loss issue open, but update it to state
  that both canonical replacements preserve fan-out while map compatibility
  operations remain lossy;
- leave workflow-output literals, nested workflow-output projection, focused
  step updates, and TypeScript parity open;
- update CLI help, user docs, and agent skills with canonical replacement,
  fan-out, clear, compatibility, and export examples;
- add a completed roadmap entry linking to the archived implementation plan;
- archive the implementation plan under
  `docs/historical/superpowers/plans/`.

## Success Criteria

- One focused operation replaces a step's complete canonical output-binding
  list in one revision.
- Nested paths, source fan-out, and whole-payload output use the existing core
  binding model unchanged.
- Every local source is validated against the capability output schema before
  mutation.
- Missing state target schemas are projected atomically with the binding list.
- Existing map-only callers retain their current behavior through a clearly
  documented compatibility adapter.
- No new persisted binding type, template language, or JSON Schema traversal is
  introduced.
- Focused API, runtime, RPC, MCP, CLI, Ruff, formatting, and basedpyright checks
  pass.
