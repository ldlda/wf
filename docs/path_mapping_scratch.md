# Path And Mapping Scratch

This is a focused scratchpad for the `wf_core` path/mapping design thread.
Clean this into real docs later.

## Current Mapping Roles

`in_map` maps graph/runtime paths into node-local input paths:

```text
input.text -> text
state.person.name -> user.name
context.item -> document
```

`out_map` maps node-local output paths into workflow state destinations:

```text
echoed -> state.echoed
user.age -> state.person.age
. -> state.rates
```

`input_values` maps node-local input paths to literal values:

```text
mode -> "fast"
retry.count -> 3
```

## Path Kinds

Graph paths live in workflow/run space:

- `input.*`: original workflow invocation input.
- `state.*`: mutable workflow state.
- `context.*`: runtime frame context.

Node-local paths live inside one node input/output payload:

- `user.name`
- `job.years`
- `.` for the whole local payload.

## Context Paths

`context.*` currently exists. It is generated from the current execution frame,
not stored in workflow state.

Current context fields include:

- `context.prior_outcome`
- `context.activated_incoming_edge`
- foreach frames: `context.loop_item`
- foreach frames: `context.loop_index`
- foreach frames: `context.<loop_alias>` when the foreach node declares `as`.

Context paths are valid graph source paths for `in_map` when validation allows
context. They are not valid `out_map` destinations.

## Typed Internal Model Idea

Keep serialized maps as strings for JSON compatibility, but parse them at
runtime/validation boundaries:

```text
GraphPath(root="input", parts=("text",))          <-> "input.text"
GraphPath(root="state", parts=("person", "name")) <-> "state.person.name"
GraphPath(root="context", parts=("item",))        <-> "context.item"
LocalPath(parts=("user", "name"))                 <-> "user.name"
LocalPath.root()                                  <-> "."
```

This lets validation reason about roots and parts without repeated string
prefix checks.

## Decisions So Far

Canonical path parsing/validation should live in `wf_core`.

`wf_authoring` should keep ergonomic constructors and condition wrappers, but
those should be thin wrappers around core path types.

Condition path fields should use typed graph source paths, not arbitrary
strings:

```text
PathOperand.path: GraphSourcePath
ExistsCondition.path: GraphSourcePath
```

Node input mapping should merge the old `in_map` and `input_values` concepts
into one list of binding structs:

```text
InputPathBinding:
  target: LocalPath
  path: GraphSourcePath

InputValueBinding:
  target: LocalPath
  value: JsonValue
```

Do not add a `kind` discriminator if the shape can be distinguished by `path`
vs `value`. Use strict models so `{path, value}` and `{}` fail.

Node output mapping should become a list of binding structs:

```text
OutputBinding:
  source: LocalPath
  target: StatePath
```

The same field name can mean different path kinds by position:

- input binding `target` is a node-local input path
- output binding `target` is a workflow state path

Root local path `"."` remains valid:

- input target `"."` means the whole node input payload is the mapped path/value
- output source `"."` means the whole node output payload is written
- literal input value binding to `"."` is valid and means the literal value is
  the entire node input payload
- `"."` input binding must still be the only input binding on that node use

Overlap rules:

- if an input binding targets `"."`, it must be the only input binding
- input targets must not overlap, e.g. `user` and `user.name`
- output targets must not overlap, e.g. `state.person` and
  `state.person.name`
- exact duplicate input targets are invalid
- exact duplicate output targets are invalid
- if output writes a parent, it cannot also write a child
- read paths may overlap; write paths may not overlap

State path validation and write behavior:

- writable `StatePath` must have its root declared in `state_schema.fields`
- whole-state write targets such as bare `state` stay out of scope for now
- nested state subpaths are allowed once the root exists in the schema
- exact nested state declarations are reducer/schema hints, not root ownership
- reducers apply only to the exact declared destination path
- missing object parents are created during runtime writes
- descending through an existing non-object parent fails at runtime

Runtime traversal helpers:

- all get/set traversal should go through focused helpers
- do not scatter `dict`/`getattr` logic through runtime code
- helpers may support mappings, Pydantic models, and dataclasses where safe
- exact supported object kinds can be implementation-defined, but the behavior
  should be centralized and tested

Read vs write traversal:

- reads may support richer object access through centralized helpers
- writes are stricter
- nested writes require mutable mapping parents
- typed model/dataclass parents are not patched field-by-field
- strict typed values should be replaced as a whole, not partially mutated
- full replacements must adhere to the declared schema when validation exists

State write validation:

- validate writes against the exact declared state field schema when one exists
- replacement writes must satisfy the full target schema
- replacement writes that contain fields not allowed by the target schema fail
- partial object patches require an explicit merge-style reducer such as
  `merge_object`; do not silently treat replace as merge
- do not validate the whole workflow state on every write
- undeclared nested subpaths under declared object roots remain flexible
- this keeps validation focused and avoids heavy whole-state checks

Workflow input/output validation:

- validate full workflow input against `workflow.input_schema` at run start
- keep workflow output as top-level projection from state for now
- `workflow.output_schema.properties` decides which top-level state fields are
  exposed as final output
- do not add workflow-level output bindings in this path refactor
- if shaped output is needed, use a final node to shape state before END

Execution validation order:

1. validate workflow input at run start
2. resolve node input bindings into node payload
3. validate node payload against `node_def.input_schema`
4. execute node
5. coerce node result
6. validate node result output against `node_def.output_schema`
7. apply output bindings to state with focused state field validation
8. project final workflow output from state at END

Principle:

- validate node output before mutating state
- strange node results should fail fast and not pollute workflow state

State patch atomicity:

- output binding application is one atomic patch to workflow state
- no gradual state mutation while processing individual bindings
- resolve all sources first
- check overlaps first
- compute reducer/merged values first
- validate patch values first
- commit the patch only after preparation succeeds
- failed output binding application leaves prior state unchanged

Reducers:

- reducers run during patch preparation, not during commit
- reducers receive current value, incoming value, and optional config
- reducers return the merged value for the patch
- reducers must not mutate workflow state directly
- reducer failure aborts the whole patch before commit

Patch representation:

- public mappings are list-of-structs
- internal prepared patches can be flat path-keyed maps
- key type should be `StatePath`, not raw string
- flat patches make overlap checks, reducer lookup, validation, tracing, and
  commit performance simpler
- do not expose flat path-keyed patch maps as the public authoring shape

Trace state changes:

- use typed `StatePath` internally
- prefer list-of-structs for public trace serialization/schema
- target shape:

```text
StateChange:
  path: StatePath
  value: JsonValue
```

- this avoids custom JSON object key serialization problems
- it gives cleaner schema and clearer MCP/LLM output

Runtime state value domain:

- workflow definitions and static binding values should be JSON-compatible
- in-memory runtime state may remain `Any`-ish for now
- persisted/checkpointed run state should require JSON-compatible values
- checkpoint serialization should be the strict boundary for non-serializable
  runtime objects

Current initialization behavior:

- workflow input is currently copied into initial state by `init_run_state`
- this makes `input.foo` and `state.foo` both available at run start when the
  input has `foo`
- target direction is explicit initialization, closer to LangGraph: input stays
  input, state is mutated only by explicit graph behavior
- keep implicit seeding for now as compatibility unless/until there is a
  dedicated migration

Canonical node binding shape:

```text
NodeUse.input: list[InputBinding]
NodeUse.output: list[OutputBinding]
```

Old `in_map`, `input_values`, and `out_map` can be accepted as parse-only
compatibility inputs, but the canonical model should store and serialize the new
list-of-structs shape.

Naming caveat:

- `NodeUse.input` means "bindings that build this node's input payload"
- graph path root `input.*` means "the workflow run input"

Docs must make this distinction explicit. The repeated word is acceptable only
if examples clearly show `input` as the binding list and `input.foo` as a graph
source path.

Static value bindings:

- `InputValueBinding.value` should be JSON-compatible
- workflow models should stay serializable/storable
- non-serializable runtime objects such as callbacks should not be embedded in
  workflow definitions
- future LangGraph-store-like behavior should use explicit store/reference
  mechanisms, not arbitrary Python objects inside the model

Context paths:

- `context.*` stays a first-class graph source path
- it is read-only and source-only
- root-only graph source paths are allowed for whole-container reads:
  `input`, `state`, and `context`
- root-only graph source paths are useful for explicitly passing whole workflow
  input/state/context into a node
- conditions can use `context.*`
- node input path bindings can use `context.*`
- output/write bindings cannot target `context.*`
- workflow validation does not need to statically prove every context key exists
- `exists(context.x)` returns false when missing
- comparisons against missing context paths fail clearly

Validation responsibility split:

- path types validate that a value is a well-formed path of the right kind
- workflow validation checks whether that path is legal in a specific workflow
- examples of workflow-specific checks:
  - `input.foo` root exists in `input_schema`
  - `state.foo` root exists in `state_schema`
  - write destinations are state paths
  - write destinations do not overlap
- path types should not need access to workflow schemas

Path segment syntax:

- use strict identifier-like segments:
  `[A-Za-z_][A-Za-z0-9_]*`
- dots separate path segments
- empty segments are invalid
- arbitrary JSON keys containing dots or punctuation are not supported yet
- bracket/index syntax is out of scope until deliberately designed
- this tightens current behavior, which mostly split strings without much
  segment validation

List indexing:

- no list indexing in core paths
- paths address object/dict/model fields, not list positions
- numeric/positional list segments are rejected
- encoding workflow meaning by array position is discouraged
- use foreach for item-wise behavior
- future continue/break-style foreach behavior may cover many selection cases
- explicit helper nodes such as an authoring `index` node can handle positional
  lookup without complicating core path syntax

Local path syntax:

- `LocalPath` uses the same strict segment rules as graph paths
- valid examples: `user.name`, `job.years`, `.`
- invalid examples: `user..name`, `user-name`, `items.0`, `user["name"]`
- no external path library is planned; a small parser with a compiled segment
  regex is enough because these paths have workflow-specific roots and rules

Hashability:

- path objects should be immutable/hashable
- use frozen dataclasses or equivalent immutable models
- public node bindings should still be list-of-structs, not dicts keyed by paths
- hashable paths are useful internally for lookups, sets, duplicate detection,
  and overlap validation

Implementation choice:

- use frozen dataclass value objects with Pydantic core-schema hooks
- avoid Pydantic `BaseModel` for tiny path values unless hooks become too costly
- Pydantic should accept strings or existing path objects and store path objects
- JSON serialization should emit strings

Planned core path value objects:

```text
LocalPath(parts)
GraphSourcePath(root, parts)  # root is input | state | context
StatePath(parts)              # serializes with state. prefix
```

Shared internals:

- use shared parsing/segment/overlap helpers for all path kinds
- do not expose one generic public `Path` for every position
- distinct public path types preserve semantics:
  - `LocalPath` for node-local payloads
  - `GraphSourcePath` for readable graph sources
  - `StatePath` for writable state destinations
- a small shared `PathParts` value or shared helper functions are both fine;
  choose whichever keeps implementation simplest

Constructors and authoring sugar:

- core path types should have boring constructors/parsers for tests and runtime
- `wf_authoring` keeps pretty helpers such as `state_path`, `input_path`,
  `context_path`, and condition expression sugar
- `Expr` and `PathExpr` stay in `wf_authoring`
- core owns `Condition` models and path value types
- authoring wrappers can behave like a trait/mixin over comparable path-like
  values, adding `eq`, `ne`, `lt`, `le`, `gt`, `ge`, operator overloads, and
  `exists`

Core constructor ergonomics:

- constructors may accept dotted strings and/or multiple fragments
- fragments are flattened by splitting on `.`
- examples:
  - `GraphSourcePath.state("person.name")`
  - `GraphSourcePath.state("person", "name")`
  - `GraphSourcePath.state("foo", "bar.baz")`
- all final segments still pass strict segment validation
- empty fragments/segments are rejected
- `LocalPath.root()` / serialized `"."` is the only root marker exception

Parse vs construction:

- `parse()` reads the full serialized JSON form
- `of()` / root-specific constructors are ergonomic Python construction
- both use the same segment parsing/validation internals
- examples:
  - `StatePath.parse("state.person.name")`
  - `StatePath.of("person.name")`
  - `GraphSourcePath.state("person.name")`
  - `LocalPath.of("user.name")`

String form:

- `str(path)` returns the serialized JSON form
- examples:
  - `str(StatePath.of("person.name")) == "state.person.name"`
  - `str(GraphSourcePath.state("person.name")) == "state.person.name"`
  - `str(LocalPath.of("user.name")) == "user.name"`
  - `str(LocalPath.root()) == "."`

JSON Schema:

- path fields should expose as strings, not `{root, parts}` objects
- use pattern and description metadata where possible
- examples:
  - `StatePath`: string matching `state.<segment>(.<segment>)*`
  - `GraphSourcePath`: string matching `(input|state|context).<segment>(.<segment>)*`
  - `LocalPath`: string matching `.` or `<segment>(.<segment>)*`
- use Pydantic hook / annotation metadata magic to keep external schemas clear
  while storing rich path value objects internally

Error messages:

- path parsing errors should name the expected path kind
- include examples in errors where practical
- expected examples:
  - graph source path: `input.foo`, `state.foo`, or `context.foo`
  - state path: `state.foo`
  - local path: `user.name` or `.`
- this should improve current error + hint behavior for MCP/LLM users

Missing paths:

- binding path reads should fail when missing
- do not add `on_missing` to core bindings now
- optional/default/missing behavior belongs in explicit nodes or conditions
- this keeps bindings as data movement, not hidden behavior

Binding descriptions:

- no `description` / `desc` fields on `wf_core` binding structs for now
- descriptions are useful in higher layers such as drafts, artifacts, authoring
  helpers, or MCP-facing planning surfaces
- core bindings should stay structural/runtime-focused

Binding order:

- binding order is preserved
- runtime may apply bindings in order for deterministic traces/debugging
- order must not resolve conflicts
- overlapping write targets are validation errors, not "last write wins"
- future priority/override behavior must be explicit, not implicit list order

Core explicitness:

- empty `NodeUse.input` means empty node payload
- empty `NodeUse.output` means no state writes
- core performs no auto-mapping
- authoring/builder layers may infer mappings, but must emit explicit canonical
  bindings into core models

State schema fields:

- move toward list-of-structs instead of dict keys
- canonical shape:

```text
StateSchema.fields: list[StateFieldDecl]

StateFieldDecl:
  path: StatePath
  type: string
  reducer: ReducerRef
```

- serialized field paths include `state.` prefix, e.g. `state.person.tags`
- accept old dict shape at parse time for compatibility:

```text
fields = {
  "person.tags": {"type": "array", "reducer": "wf.std.append"}
}
```

- normalize old shape to canonical list internally
- canonical serialization emits list shape
- duplicate field paths are validation errors
- exact reducer matching uses exact `StatePath`

Input/output JSON Schemas:

- do not replace JSON Schema with a custom schema language
- introduce a named JSON Schema boundary type or model
- validate schemas with the standard `jsonschema` library
- validation cost is acceptable at model/config boundaries
- this applies to workflow input/output schemas and node input/output schemas
- JSON Schema object keys are standard and should not be treated like workflow
  path-map dict keys
- respect `$schema` when present using `jsonschema.validators.validator_for`
- default to Draft 2020-12 when `$schema` is absent
- keep `SchemaRef` as the core schema type for now
- make `SchemaRef` honest: it represents a JSON Schema object boundary
- strengthen `SchemaRef` with standard JSON Schema validation instead of
  introducing a parallel `JsonSchema` type

Placement:

- canonical path value objects live in `wf_core.paths`
- `wf_core.models.*`, validation, runtime, and authoring import those types
- split `wf_core.paths` into a package later only if it grows too large

Compatibility fields:

- old `in_map`, `input_values`, and `out_map` are parse-only compatibility
  inputs
- they should be treated as deprecated
- validated `NodeUse` stores only canonical `input` and `output` bindings
- canonical serialization emits only the new fields
- avoid dual state inside the model
- reject payloads that mix canonical fields with deprecated compatibility fields
- do not merge old and new syntax
- compatibility conversion preserves dict insertion order when converting old
  maps into binding lists
- JSON Schema should advertise only canonical `input` / `output` fields
- deprecated compatibility fields should not be shown to new callers

Null and missing semantics:

- explicit null is a real value, not an omitted binding/value
- `exists(path)` means the path can be resolved, even when its value is null
- missing path and present-null path are different states
- compare against null explicitly when needed, e.g. `state.foo == null` or
  `state.foo != null`
- null comparisons are valid anywhere normal conditions work
- missing paths still fail clearly for comparisons; only `exists(path)` treats
  missing as false instead of an error
- input value bindings may intentionally bind null; this must not be treated as
  "no value provided"
- input path bindings fail before node execution when the source path is
  missing
- missing source paths must not silently bind null
- softer/defaulting behavior belongs in authoring helpers or explicit shaping
  nodes, not implicit core behavior

Schema openness:

- JSON Schema / Pydantic-style `extra` controls what object keys are allowed
  inside a value
- schema openness does not change path existence semantics
- core should not use "allow extra" as permission for speculative deep path
  traversal
- if a workflow needs dynamic traversal through arbitrary/extra object shape,
  use an explicit node that receives the relevant state value and decides what
  to extract
- this avoids pretending static path validation can prove paths such as
  `state.person.occupations.1.title` exist inside open-ended objects
