# Core Path Bindings Design

## Purpose

`wf_core` currently uses plain strings for graph paths, local node paths, input
maps, output maps, and state field keys. That made the early system simple, but
it also pushes too much meaning into ad hoc string parsing. This design makes
paths and bindings first-class core concepts while keeping JSON serialization
simple.

The goal is not to make every dynamic JSON traversal statically provable. The
goal is to make normal workflow data movement explicit, validated, serializable,
and easy for authoring/MCP layers to generate.

## Goals

- Replace loose map fields with canonical list-of-struct binding models.
- Store typed path value objects internally while serializing them as strings.
- Keep missing values distinct from explicit `null`.
- Make state writes atomic and reducer-aware.
- Keep compatibility with old workflow shapes through parse-only deprecated
  fields.
- Keep dynamic/open-object traversal out of core and in explicit nodes.

## Non-Goals

- No list/index path syntax such as `items.0.name` or `items[0].name`.
- No arbitrary JSON-pointer support.
- No whole-state replacement writes in this pass.
- No implicit defaults for missing paths.
- No business logic in reducers or bindings.
- No custom schema language replacing JSON Schema.

## Path Types

Core introduces distinct path value objects:

```text
LocalPath(parts)
GraphSourcePath(root, parts)  # root: input | state | context
StatePath(parts)              # serializes as state.<parts>
```

These objects are immutable/hashable and are accepted by Pydantic from either
strings or existing instances. JSON serialization emits strings.

Examples:

```text
LocalPath.of("user.name")                -> "user.name"
LocalPath.root()                         -> "."
GraphSourcePath.state("person.name")     -> "state.person.name"
GraphSourcePath.parse("input")           -> "input"
StatePath.of("person.name")              -> "state.person.name"
```

Path parsing rules:

- Segments use `[A-Za-z_][A-Za-z0-9_]*`.
- Dots separate segments.
- Empty segments are invalid.
- Numeric/positional list segments are rejected.
- `LocalPath.root()` / `"."` is the only local root marker.
- Root-only graph source paths `input`, `state`, and `context` are valid reads.

`StatePath` write targets should not accept bare `state` in this pass. Whole
state replacement is too broad because it interacts with reducers, validation,
trace, and accidental deletion.

There is no reducer for bare `state`. Reducers attach only to declared non-root
`StatePath` fields.

## Canonical Node Bindings

`NodeUse` gets canonical binding fields:

```text
NodeUse.input: list[InputBinding]
NodeUse.output: list[OutputBinding]
```

Input bindings are distinguished by shape, not by an extra `kind` field:

```text
InputPathBinding:
  target: LocalPath
  path: GraphSourcePath

InputValueBinding:
  target: LocalPath
  value: JsonValue
```

Output bindings are:

```text
OutputBinding:
  source: LocalPath
  target: StatePath
```

The same field name can mean different path kinds by position. For example,
input binding `target` is node-local, while output binding `target` is workflow
state. Documentation and model field descriptions should make this explicit.

Root local path `"."` is valid:

- input target `"."` means the whole node input payload.
- output source `"."` means the whole node output payload.
- a `"."` input binding must be the only input binding.

Examples:

```json
{
  "input": [
    {"target": "user.email", "path": "state.person.email"},
    {"target": "mode", "value": "fast"}
  ],
  "output": [
    {"source": "result", "target": "state.result"}
  ]
}
```

Whole payload input:

```json
{
  "input": [
    {"target": ".", "path": "state.rates"}
  ]
}
```

Whole payload literal input:

```json
{
  "input": [
    {"target": ".", "value": {"mode": "fast"}}
  ]
}
```

## Compatibility

Old fields are accepted only as deprecated parse inputs:

```text
in_map
input_values
out_map
```

After validation, `NodeUse` stores only canonical `input` and `output`
bindings. Canonical serialization emits only the new fields. Payloads that mix
canonical fields with deprecated fields should fail instead of merging two
styles.

This shape makes it easy to remove compatibility later: delete the parser
adapters without changing runtime internals.

State schema gets the same compatibility shape. The canonical form is:

```text
StateSchema.fields: list[StateFieldDecl]

StateFieldDecl:
  path: StatePath
  schema: SchemaRef
  reducer: ReducerRef
```

Old dict-shaped fields can be accepted at parse time and normalized:

```json
{
  "fields": {
    "person.tags": {"type": "array", "reducer": "wf.std.append"}
  }
}
```

Canonical serialization should emit list-of-structs with serialized state paths.

## Runtime Semantics

Node execution flow:

1. Validate workflow input against `workflow.input_schema`.
2. Resolve node input bindings into the node payload.
3. Validate node payload against `node_def.input_schema`.
4. Execute the node.
5. Coerce the node result.
6. Validate node output against `node_def.output_schema`.
7. Prepare an atomic state patch from output bindings.
8. Validate focused state patch values.
9. Commit the patch.
10. At `END`, project final output from top-level state fields using
    `workflow.output_schema.properties`.

State writes are atomic. Runtime should resolve all output sources, detect
overlap conflicts, compute reducer results, validate patch values, then commit.
If any step fails, prior state is unchanged.

Reducers run during patch preparation. They receive current value, incoming
value, and optional config, then return the merged value. Reducers must not
mutate workflow state directly.

## Missing, Null, And Dynamic Data

Explicit `null` is a real value. It is not the same as a missing path.

Rules:

- `exists(path)` returns true when the path resolves, even if the value is null.
- `exists(path)` returns false when the path is missing.
- Comparisons such as `eq(null)` and `ne(null)` are valid.
- Comparisons against missing paths fail clearly.
- Input path bindings fail before node execution when the source path is
  missing.
- Missing source paths must not silently bind null.
- Input value bindings may intentionally bind null.

`allow extra` / open object schemas do not authorize speculative deep traversal.
If a workflow needs dynamic object traversal, it should use an explicit node
that receives the relevant value and decides what to extract. For example, use
an `extract_title` node instead of trying to make core prove
`state.person.occupations.1.title`.

## Validation Rules

Path value objects validate syntax and path kind only. Workflow validation checks
whether a path is legal in a particular workflow.

Examples of workflow-specific checks:

- `input.foo` exists in `workflow.input_schema` when statically knowable.
- `state.foo` has a declared state root.
- write destinations are `StatePath`.
- output write targets do not overlap.

Overlap rules:

- read paths may overlap.
- input targets must not overlap.
- output targets must not overlap.
- exact duplicate targets are invalid.
- parent/child write targets such as `state.person` and `state.person.name`
  are invalid together.

State write validation:

- Validate against the exact declared state field schema when one exists.
- Do not validate the whole workflow state on every write.
- Replacement writes must satisfy the full target schema.
- Replacement writes with forbidden extra fields fail.
- Partial object patches require an explicit merge-style reducer such as
  `merge_object`.
- Do not silently treat `replace` as merge.

## JSON Schema Boundary

Core should not invent a schema language. `SchemaRef` should represent a JSON
Schema object boundary and be validated with the standard `jsonschema` library.

Rules:

- Respect `$schema` when present with `jsonschema.validators.validator_for`.
- Default to Draft 2020-12 when `$schema` is absent.
- Validate workflow input/output schemas and node input/output schemas at model
  boundaries.
- Keep JSON Schema object keys separate from workflow path syntax.

Path fields should expose clear JSON Schema as strings with pattern and
description metadata, not `{root, parts}` objects.

## Authoring Layer

`wf_authoring` keeps ergonomic helpers:

- `state_path(...)`
- `input_path(...)`
- `context_path(...)`
- expression helpers such as `eq`, `ne`, `lt`, `le`, `gt`, `ge`, and `exists`

Those helpers should compile to core path objects and core `Condition` models.
Authoring may infer mappings for convenience, but it must emit explicit
canonical bindings into core models.

## Tracing

Runtime may use flat `dict[StatePath, value]` patches internally. Public trace
serialization should prefer list-of-structs:

```text
StateChange:
  path: StatePath
  value: JsonValue
```

This avoids custom JSON object-key serialization and gives MCP/LLM clients
clearer output.

## Implementation Phases

1. Add core path value objects and parser helpers.
2. Add canonical binding models with parse-only compatibility for old fields.
3. Update validation to reason over path objects and binding structs.
4. Update runtime input resolution and output patching to use canonical
   bindings.
5. Add focused state patch preparation with atomic commit semantics.
6. Add JSON Schema validation hardening for `SchemaRef`.
7. Update `wf_authoring` builders/helpers to emit canonical bindings.
8. Update docs/examples and mark old fields as deprecated.

Each phase should keep existing tests green, with compatibility tests proving
old shapes still parse until support is intentionally removed.

## Open Risks

- Pydantic core-schema hooks for frozen path value objects may need careful
  implementation to keep JSON Schema clean.
- Existing examples and MCP-facing draft tools may rely on old dict-shaped maps.
  Compatibility adapters should isolate that churn.
- Focused schema validation for nested state writes depends on how much schema
  information is available for exact declared state paths.
- Workflow input currently seeds initial state. This design keeps that
  compatibility for now, but explicit initialization remains the target
  direction.
