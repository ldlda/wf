# Nested Local Draft Bindings Design

## Goal

Bring focused draft authoring into parity with the canonical runtime model for
nested node-local paths. Agents and operators should be able to bind structured
capability inputs and outputs without raw JSON Patch, while the implementation
reuses canonical path types and one shared JSON Schema projection module.

## Problem

`LocalPath`, workflow validation, runtime input assembly, runtime output reads,
and `WorkflowBuilder` already support paths such as `report.title`. Focused
draft authoring is narrower:

- `wf draft bind --from input.title --to local.report.title` rejects the target
  because `bind_draft` requires one local path segment;
- the inverse output direction rejects nested local sources for the same
  reason;
- capability-step insertion persists nested input targets but silently skips
  schema projection whenever the local path has more than one segment;
- CLI help describes step input targets as bare fields rather than canonical
  node-local paths.

The limitation is not in the workflow model. It is duplicated path and schema
handling in the focused authoring layer.

## Scope

This slice supports nested node-local paths for:

- workflow input or state to capability input:
  `input.title -> local.report.title`;
- capability output to workflow state:
  `local.report.markdown -> state.report.markdown`;
- capability output to public workflow output, using the existing durable-state
  lowering:
  `local.report.markdown -> output.report.markdown` becomes a node output
  binding to `state.report.markdown` plus a workflow output binding from that
  state path;
- capability-step input maps such as
  `--map input.title=report.title`, where the node-local root remains implied by
  the existing command interface.

The slice also centralizes repeated authoring-time JSON Schema path operations
and updates CLI/agent-facing path documentation.

## Out Of Scope

This slice does not:

- add literal node-input or workflow-output bindings;
- replace dictionary maps with a fan-out-safe binding-list interface;
- add the atomic structured-input assembly helper tracked separately in
  `ISSUES.md`;
- add step metadata or focused update-step operations;
- add TypeScript JSON-RPC operations or code generation;
- change route, revision, deployment, or runtime semantics;
- implement a general JSON Schema resolver or support remote references;
- change existing CLI command names or request fields.

## Canonical Path Interfaces

No new path model is introduced.

- `GraphSourcePath` parses workflow-readable `input.*`, `state.*`, and
  `context.*` paths.
- `LocalPath` parses rootless node-local paths such as `report.title` and the
  whole-payload marker `.`.
- `wf draft bind` continues using explicit endpoint roots because both sides
  are endpoints: `--from input.title --to local.report.title`.
- capability-add and set-input maps continue using rootless local targets
  because their interface already implies the node-local side:
  `--map input.title=report.title`.

The CLI parser must validate rootless map targets with `LocalPath.parse` instead
of checking only whether they start with `local.`. Existing single-segment map
syntax remains valid. Rooted `local.*` map targets remain rejected with an exact
repair example because changing that syntax is a separate migration.

Transport request fields remain strings. Their endpoint role is determined by
the existing command/method interface, and the semantic authoring module parses
them through the canonical path classes. Do not create duplicate Pydantic path
schemas or endpoint unions in RPC models for this slice.

## Shared JSON Schema Projection Module

Deepen `wf_api.schema_projection` so authoring code does not perform schema
traversal itself.

### Public Operations

The module exposes:

```python
def schema_path_exists(
    schema: Mapping[str, Any],
    parts: Sequence[str],
) -> bool: ...


def project_schema_path_to_schema_path(
    *,
    target_schema: JsonObject,
    source_schema: JsonObject,
    source_parts: tuple[str, ...],
    target_parts: tuple[str, ...],
    allow_existing_equivalent: bool = False,
) -> JsonObject: ...
```

`project_property_to_schema_path` remains as a compatibility-preserving
root-property wrapper and delegates to the new operation with
`source_parts=(source_field,)`. Existing callers and error wording remain
stable where practical.

### Responsibilities

The module:

1. validates source and target documents with `jsonschema`;
2. traverses nested object `properties` using path segments supplied by
   canonical path types;
3. resolves bounded local references used by repository-generated schemas,
   including `#/$defs/...` and `#/definitions/...`;
4. copies the selected source subschema into the requested target object path;
5. carries `$defs` and `definitions` blocks needed by copied local references;
6. validates the projected result;
7. reports missing source paths, non-object intermediate paths, unsupported
   references, and conflicting target paths precisely.

This is authoring-time schema projection, not schema inference. The module does
not create new Pydantic models mirroring capability schemas and does not
evaluate arbitrary combinators or remote references. Capability schemas remain
the documents emitted by `NodeSpec` contracts or Pydantic
`model_json_schema()`.

The duplicate `_schema_path_exists` implementations in `wf_api.drafts` and
`wf_api.draft_authoring` move into this module. Both callers import the shared
operation so target-path behavior has one implementation.

## Authoring Data Flow

### Focused Bind: Workflow Data To Nested Capability Input

For `input.title -> local.report.title`:

1. revision preflight runs before semantic work;
2. `GraphSourcePath` parses `input.title`;
3. `LocalPath` parses rootless `report.title` from the explicit `local.*`
   endpoint;
4. the capability input schema is selected from its explicit contract or
   Pydantic model;
5. `project_schema_path_to_schema_path` copies the capability schema at
   `report.title` into the workflow input schema at `title` when absent;
6. `input_bindings_payload` serializes the canonical nested local target;
7. the existing revision-checked patch operation persists both changes.

Existing workflow source schema paths are reused without projection, preserving
current idempotent behavior.

### Focused Bind: Nested Capability Output To State Or Output

For `local.report.markdown -> state.report.markdown`, the capability output
schema at `report.markdown` is copied to the requested state path and the step
output binding stores the complete nested `LocalPath`.

For `local.report.markdown -> output.report.markdown`, the existing output
lowering remains unchanged except that the nested capability subschema is used.
The operation projects that subschema into both state and public output schemas,
writes the node output into state, and projects workflow output from the same
state path.

### Capability-Step Insertion

For `input.title=report.title`:

1. `GraphSourcePath.parse` validates the graph source;
2. `LocalPath.parse` validates the rootless local target;
3. the complete local parts tuple selects the nested capability input
   subschema;
4. that subschema is projected into the workflow input/state source path when
   the workflow schema does not already declare it;
5. the nested input binding is persisted in the same atomic patch as the new
   step and routes.

Remove the current `len(local_parts) != 1` skip. A valid nested local path must
never silently disable schema projection.

## Errors And Compatibility

Current single-field bindings keep their response shapes and semantics.

For current revisions:

- an absent nested capability schema path raises a precise `ValueError` naming
  the complete path;
- traversing through a scalar or otherwise non-object schema raises a precise
  `ValueError` naming the blocking prefix;
- an unsupported or unresolved reference raises a precise `ValueError` rather
  than silently skipping projection;
- an existing workflow input/state source path is reused unchanged, preserving
  current bind behavior;
- output/state projection continues accepting exact equivalent target schemas
  and rejecting incompatible existing targets;
- no patch is persisted when projection fails.

Revision precedence from the preceding slice remains intact: after intrinsic
request validation, stale requests return `revision_conflict` before path or
schema errors derived from current workspace/catalog state.

Transport fields and response envelopes do not change. RPC, remote-client, and
CLI layers inherit behavior through existing delegation. Documentation-only
description changes may clarify nested examples but must not introduce parallel
request schemas.

## Testing

### Schema Projection

Add focused unit tests for:

- inline nested source properties;
- nested source properties behind Pydantic-style `#/$defs` references;
- legacy `#/definitions` local references;
- copied definition blocks remaining resolvable;
- missing source paths;
- non-object intermediate source paths;
- conflicting and equivalent target paths;
- centralized `schema_path_exists` behavior.

### Python Authoring

Add API tests for:

- input and state binding to nested local targets;
- nested local output binding to nested state;
- nested local output binding to public output through state;
- capability-step insertion with nested input target and missing workflow schema
  projection;
- current-revision invalid nested capability paths producing clear errors and
  no mutation;
- stale revision winning over nested-path semantic errors;
- existing single-segment and idempotent cases remaining unchanged.

### Transport And CLI

Add delegation/regression tests proving:

- JSON-RPC and the remote client preserve nested path strings unchanged;
- `wf draft bind` accepts explicit rooted nested local endpoints;
- capability-add and set-input map parsing accept rootless nested local paths;
- rooted `local.*` map targets remain rejected with a repair example;
- help and agent instructions distinguish explicit bind endpoints from implied
  local map targets.

Compile or validate the resulting draft to prove the stored canonical bindings
are accepted by the existing workflow model. Runtime nested mapping behavior is
already covered in `tests/core/test_nested_mappings.py` and should not be
reimplemented in this slice.

## Documentation And Issue State

After verification:

- check the nested `wf draft bind` limitation;
- check the capability-step nested projection limitation;
- check the CLI help/agent instruction limitation;
- leave atomic structured-input assembly, literal bindings, fan-out maps,
  nested workflow-output source projection, step metadata, and TypeScript parity
  open;
- add a completed roadmap entry linking to the archived implementation plan;
- archive the implementation plan under
  `docs/historical/superpowers/plans/`.

## Success Criteria

- Focused bind supports nested `LocalPath` values in both input and output
  directions.
- Capability-step insertion projects schemas for nested local input targets
  instead of silently skipping them.
- Existing single-segment bind and map behavior remains compatible.
- No new transport request schema or duplicate path type is introduced.
- Common schema path lookup, local-reference handling, existence checks, and
  projection live in `wf_api.schema_projection`.
- Resulting drafts compile or validate through the existing canonical workflow
  model.
- Focused API/RPC/CLI tests, Ruff, formatting, basedpyright, and relevant core
  regressions pass.
