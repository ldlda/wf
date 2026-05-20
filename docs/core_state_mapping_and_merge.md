# Core State Mapping and Merge Semantics

This document records the intended direction for `wf_core` mapping and state
updates before the next round of core implementation work.

## Why This Exists

The current core model is intentionally explicit:

- graph data moves between steps through workflow state
- nodes declare their own input and output contracts
- graph use-sites map between graph data and node-local data
- merge behavior belongs to workflow state, not to node implementations

That model is still right. The next pressure comes from structured tools and
future nested execution:

- real tools often accept deep payloads such as `user.name` and `job.title`
- real tools often return deep payloads such as `job.wage`
- wrappers should not need extra runtime nodes for pure boundary wiring
- future native subgraphs and parallel foreach both need a stronger commit model
- nested state reducers can become a differentiator over systems that only merge
  whole top-level values

## Canonical Binding Rule

The graph-facing side of a binding is a graph path. The node-facing side is a
node-local path. Core stores node use-site wiring as explicit lists of binding
objects, not as path-keyed maps.

```text
NodeUse.input:
  path binding:  graph source path -> node-local input path
  value binding: JSON value -> node-local input path

NodeUse.output:
  node-local output path -> graph state destination path
```

Examples:

```json
{
  "input": [
    {"target": "user.name", "path": "state.person.name"},
    {"target": "user.email", "path": "state.digital.email"},
    {"target": "job.title", "path": "state.job.title"},
    {"target": "mode", "value": "fast"}
  ],
  "output": [
    {"source": "job.wage", "target": "state.job.wage"},
    {"source": "job.years", "target": "state.experience.years"},
    {"source": "user.age", "target": "state.person.age"}
  ]
}
```

Whole-object mapping remains valid:

```json
{
  "input": [{"target": "user", "path": "state.person"}],
  "output": [{"source": "user", "target": "state.person"}]
}
```

Whole-payload mapping uses the local root path `"."`:

```json
{
  "input": [{"target": ".", "path": "state.rates"}],
  "output": [{"source": ".", "target": "state.rates"}]
}
```

Deprecated compatibility inputs are still accepted at model-parse boundaries:
`in_map`, `input_values`, and `out_map`. Validated `NodeUse` models store and
dump only canonical `input` and `output` bindings. `wf_authoring` exposes the
same canonical binding lists and keeps `in_map`, `input_values`, and `out_map`
only as deprecated Python-builder sugar that compiles into canonical bindings.

## Explicitness Rules

### Node-local writes must not overlap

`NodeUse.input` constructs node input payloads. Its target node-local paths must
be pairwise non-overlapping.

Valid:

```json
[
  {"target": "user.name", "path": "state.person.name"},
  {"target": "user.email", "path": "state.person.email"}
]
```

Invalid:

```json
[
  {"target": "user", "path": "state.person"},
  {"target": "user.name", "path": "state.person.name"}
]
```

The invalid form would require implicit object patch precedence. Authors must
choose either whole-object mapping or explicit child mapping.

### State writes must not overlap in one commit

`NodeUse.output` mutates workflow state. Its target graph paths must be
pairwise non-overlapping inside one logical commit.

Invalid:

```json
[
  {"source": "user", "target": "state.person"},
  {"source": "user.name", "target": "state.person.name"}
]
```

The target model rejects these writes before mutating state.

### Read overlap is allowed

Overlap is forbidden on write targets, not read sources. It is valid to read
both a whole object and one child into separate destinations when no constructed
target overlaps.

## Required Mapped Paths

Mapped paths are assertions by the workflow author.

- a missing graph source path in an input path binding is a runtime error
- a missing node-local output path in an output binding is a runtime error
- an explicit `null` value is different from a missing path
- optional/default behavior must be modeled explicitly later, not inferred from
  a missing path

## State Patch Commit

A successful step should produce a logical state patch before state is mutated:

1. resolve all mapped output paths
2. ensure every required output path exists
3. ensure destination state paths do not overlap
4. prepare the complete write set
5. stage the write set on a copy
6. validate affected declared state schemas
7. commit the write set according to state merge rules

This preserves the existing “no partial state commit before success” rule and
creates a reusable boundary for:

- ordinary node completion
- serial foreach iteration completion
- future parallel foreach result combination
- future subgraph completion

State validation happens against the staged state before the original state is
mutated. Runtime validates the exact destination schema when declared, declared
ancestor schemas that could reject the write, and declared descendant schemas
that exist after a parent replacement. This lets strict object schemas reject
bad partial writes without committing half a patch.

## State Declarations and Merge Rules

State merge behavior is attached to declared exact state paths. The canonical
schema shape is ordinary JSON Schema. `reducer` is a wf_core extension keyword
on property schemas; JSON Schema validators ignore it, while wf_core validates
and uses it for state writes.

```json
{
  "type": "object",
  "properties": {
    "person": {
      "type": "object",
      "properties": {
        "name": {"type": "string", "reducer": "wf.std.replace"},
        "tags": {"type": "array", "reducer": "wf.std.append"}
      }
    },
    "profile": {
      "type": "object",
      "reducer": "wf.std.merge_object"
    }
  }
}
```

Deprecated `fields` state declarations are still accepted at parse boundaries:

```json
{
  "fields": {
    "person.name": {"type": "string", "reducer": "wf.std.replace"}
  }
}
```

Validated `StateSchema` models store and dump the canonical JSON Schema shape.
`StateSchema.field_map()` compiles an internal exact-path index for runtime
reducer lookup.

`wf_authoring` keeps authored schemas nested for humans and LLM clients, and
injects state metadata such as `reducer` into the generated JSON Schema
properties. For example, a Pydantic `person: Person` field can produce nested
properties for `person.name` and `person.tags` without forcing the author to
spell those paths manually.

### Exact-path ownership

Merge behavior belongs only to the exact declared state path being written.

- no ancestor inheritance
- no descendant declarations altering parent writes
- writing `state.profile` uses only the rule for `profile`
- writing `state.profile.avatar` uses only the rule for `profile.avatar`

If a path is undeclared, it defaults to `replace`, as undeclared state does
today.

### Built-in strategies

Existing built-in reducers remain distinct:

- `wf.std.replace`
- `wf.std.append`
- `wf.std.max`
- `wf.std.merge_object`
- `wf.std.set_union`

`wf.std.merge_object` means shallow object merge at the exact destination path, similar
to `dict.update` or `operator.or_`. It is not a recursive deep merge.

If recursive merge is ever needed, it should be explicit rather than hidden
inside `merge_object`.

## Future Reducers

Reducers are a capability family, similar to reusable node specs:

- named
- source-owned
- inspectable
- dependency-trackable

State fields reference reducers declaratively. String reducer names are accepted
as shorthand for unconfigured reducers; configured reducers use a structural
`ref` plus JSON-compatible `config`. Workflow artifacts do not embed arbitrary
Python callables.

```python
StateField(
    type="integer",
    reducer={
        "ref": {"source": "wf.std", "capability_key": "modulo_add"},
        "config": {"modulus": 10},
    },
)
```

Reducers should be pure:

```text
current_value, incoming_value -> merged_value
```

They should not receive node ids, frame ids, loop indexes, timestamps, or other
runtime context. If behavior depends on workflow context, that is business logic
and belongs in nodes or graph structure.

Reducers are meant to remove write boilerplate, not absorb domain decisions.
If a node needs to decide whether to increment two counters, reset both
counters, reset one counter, or preserve one counter, that decision belongs in
the node or in an explicit graph branch. A reducer should only describe how a
declared state path combines the node's write with the current state value.

This distinction matters for fragmented outputs. It is valid for a node to emit
a delta if the node is explicitly a delta-producing node, such as
`countdown_delta = -1` written through `wf.std.add`. It is a smell if a node
returns artificial fragments only to trigger reducer behavior while hiding the
actual domain operation. In that case prefer a clearer node output, an explicit
shaping node, or a default map on the node spec that is still validated at the
use site.

Examples a future reducer library could support:

- `max`
- `modulo_add` with configuration such as modulus `10`

## Implementation Phases

### Phase 1: Nested node-local mappings

- allow nested node-local paths on canonical input binding targets
- allow nested node-local paths on canonical output binding sources
- reject overlapping write targets
- commit node output through a validated state patch
- validate top-level node-local roots statically; validate deeper shape when the
  existing node schema makes that practical

This phase is implemented in core. It helps wrappers and structured tools while
preserving explicit state merge behavior.

### Phase 2: Nested declared state paths

Implemented in core:

- exact nested state path declarations
- merge strategies resolved by exact destination path only
- undeclared paths remain `replace`
- `merge_object` remains shallow

### Phase 3: Reducer capabilities

Implemented in core:

- state metadata references named reducers instead of merge strategies
- built-ins are registered as `wf.std.replace`, `wf.std.append`, and
  `wf.std.merge_object`
- runtime resolves reducer names before state writes

Still future:

- source-owned reducer specs beyond the built-ins
- reducer dependency references at deployment/platform level

### Phase 4: Core features that depend on this foundation

- native subgraphs should reuse the same mapping and patch semantics at graph
  boundaries
- parallel foreach should combine validated patches and reject conflicts unless
  exact-path merge rules permit combination

## Non-Goals for the First Implementation

- direct node-to-node data wires outside workflow state
- implicit object patching from overlapping mapped paths
- recursive deep merge hidden inside `merge_object`
- arbitrary Python reducer callables stored in workflow models
- shipping native subgraphs or parallel foreach as part of nested mapping work
