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

## Canonical Mapping Rule

The graph-facing side of a map is a graph path. The node-facing side is a
node-local path.

```text
in_map:
  graph source path -> node-local input path

out_map:
  node-local output path -> graph state destination path
```

Examples:

```python
in_map = {
    "state.person.name": "user.name",
    "state.digital.email": "user.email",
    "state.job.title": "job.title",
}

out_map = {
    "job.wage": "state.job.wage",
    "job.years": "state.experience.years",
    "user.age": "state.person.age",
}
```

Whole-object mapping remains valid:

```python
in_map = {"state.person": "user"}
out_map = {"user": "state.person"}
```

The change from the current implementation is only on the node-local sides:
today they are top-level fields; in the target model they may be nested paths.

## Explicitness Rules

### Node-local writes must not overlap

`in_map` constructs node input payloads. Its destination node-local paths must
be pairwise non-overlapping.

Valid:

```python
{
    "state.person.name": "user.name",
    "state.person.email": "user.email",
}
```

Invalid:

```python
{
    "state.person": "user",
    "state.person.name": "user.name",
}
```

The invalid form would require implicit object patch precedence. Authors must
choose either whole-object mapping or explicit child mapping.

### State writes must not overlap in one commit

`out_map` mutates workflow state. Its destination graph paths must be pairwise
non-overlapping inside one logical commit.

Invalid:

```python
{
    "user": "state.person",
    "user.name": "state.person.name",
}
```

The target model rejects these writes before mutating state.

### Read overlap is allowed

Overlap is forbidden on write targets, not read sources. It is valid to read
both a whole object and one child into separate destinations when no constructed
target overlaps.

## Required Mapped Paths

Mapped paths are assertions by the workflow author.

- a missing graph source path in `in_map` is a runtime error
- a missing node-local output path in `out_map` is a runtime error
- optional/default behavior must be modeled explicitly later, not inferred from
  a missing path

## State Patch Commit

A successful step should produce a logical state patch before state is mutated:

1. resolve all mapped output paths
2. ensure every required output path exists
3. ensure destination state paths do not overlap
4. prepare the complete write set
5. commit the write set according to state merge rules

This preserves the existing “no partial state commit before success” rule and
creates a reusable boundary for:

- ordinary node completion
- serial foreach iteration completion
- future parallel foreach result combination
- future subgraph completion

## State Declarations and Merge Rules

State merge behavior is attached to declared exact state paths while keeping the
internal representation flat:

```python
fields = {
    "person.name": StateField(type="string", reducer="wf.std.replace"),
    "person.tags": StateField(type="array", reducer="wf.std.append"),
    "profile": StateField(type="object", reducer="wf.std.merge_object"),
}
```

Presentation layers may rebuild a tree for humans. Core should keep the simpler
path-keyed representation.

`wf_authoring` keeps authored schemas nested for humans and LLM clients, but
projects nested authored state into this flat exact-path index. For example, a
Pydantic `person: Person` field may produce declarations for `person`,
`person.name`, and `person.tags` without forcing the author to spell those
paths manually.

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
- `wf.std.merge_object`

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

State fields reference reducers declaratively. Workflow artifacts do not embed
arbitrary Python callables.

Reducers should be pure:

```text
current_value, incoming_value -> merged_value
```

They should not receive node ids, frame ids, loop indexes, timestamps, or other
runtime context. If behavior depends on workflow context, that is business logic
and belongs in nodes or graph structure.

Examples a future reducer library could support:

- `max`
- `set_union`
- `modulo_add` with configuration such as modulus `10`

## Implementation Phases

### Phase 1: Nested node-local mappings

- allow nested node-local paths on the destination side of `in_map`
- allow nested node-local paths on the source side of `out_map`
- reject overlapping write targets
- commit node output through a validated state patch
- validate top-level node-local roots statically; validate deeper shape when the
  existing node schema makes that practical

This phase immediately helps wrappers and structured tools while preserving
current state merge behavior.

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
