# Lineage State Runtime Design

Status: partially implemented

Lineage is the missing primitive between the scheduler frame model and future
native subgraphs / fork-gather. A frame says where execution is. A scope says
which workflow state root execution belongs to. A lineage says what pending
writes execution can see inside that scope.

The current runtime stores committed state directly on `RunState.state` and uses
foreach-specific barrier metadata to emulate item-local overlays. That worked
for concurrent foreach, but native subgraphs and future fork/gather need the
same state-visibility rule in a reusable core concept.

## Current Implementation Status

The first compatibility slices are implemented:

- `StateWrite` records reducer-aware `incoming_value` and `visible_value`.
- `StatePatch` preserves ordered writes while keeping `changes` for trace and
  compatibility.
- `LineageStateView` materializes committed state plus lineage-visible writes.
- Concurrent foreach item reads use `visible_value`, while barriers replay
  `incoming_value`.
- Foreach pending result metadata persists write records and `lineage_id`.
- Frames and runtime context carry `scope_id`, `lineage_id`, and
  `parent_lineage_id`.

The full `RuntimeScope` / `LineageState` store is not implemented yet.
Currently, foreach still owns pending write storage through
`ForeachBarrierState`; the lineage ids are identity and diagnostics, not yet the
primary storage key.

## Problem

`RunState` currently owns too many meanings:

- run status
- scheduler cursor
- frame set
- trace
- interrupt request
- committed workflow state
- temporary state visibility hacks through frame/barrier metadata

This creates pressure when a workflow branches:

```text
root
  fork -> A
       -> B
```

Branch `A` must not see branch `B` writes before an explicit merge point.
Branch `B` must not see branch `A` writes either. A future gather then decides
how to merge both branches back into a parent state view.

The same problem already exists in concurrent foreach item frames. Each item is
a sibling lineage. Current foreach solves it locally with barrier pending
patches. That solution should become a general runtime primitive.

Native subgraphs add one more missing concept: a child workflow has its own
committed state root. A lineage alone is not enough for subgraphs because a
child workflow initializes state from child input/defaults, not from the
parent's state dictionary.

## Vocabulary

```text
Scope   = workflow state root and workflow identity
Frame   = scheduler/control-flow position inside a scope
Lineage = pending write ownership and read overlay inside a scope
```

A frame owns execution lifecycle:

```python
ExecutionFrame(
    id="root:each:0",
    scope_id="root",
    kind="foreach_iteration",
    node_id="work",
    status="pending",
    parent_frame_id="root",
    lineage_id="root:each:0",
)
```

A lineage owns ordered pending writes:

```python
LineageState(
    id="root:each:0",
    scope_id="root",
    parent_id="root",
    writes=[
        StateWrite(
            path=StatePath(("count",)),
            incoming_value=3,
            visible_value=5,
            reducer=ReducerRef(name="wf.std.add"),
        ),
    ],
)
```

The frame, scope, and lineage ids may match in simple cases, but they are not
the same concept and runtime logic must not depend on parsing any of them.

## Core Invariants

- Every executable frame belongs to exactly one scope.
- Every executable frame points at exactly one lineage in that scope.
- The root frame points at the root scope and root lineage.
- `RunState.state` remains the committed root scope state during the migration.
- A non-root lineage stores replayable write records, not a full copied state
  snapshot and not only final visible values.
- A frame reads through its lineage state view.
- A non-root frame write updates its lineage writes and does not mutate
  `RunState.state`.
- A barrier/gather commits lineage write records into a parent lineage or scope
  root state by replaying incoming values through reducers.
- Trace `state_changes` means committed changes only.
- Buffered lineage writes may be visible to later frames in the same lineage,
  but they are not public committed state changes until a barrier commits them.

## Why Write Records Instead of Full State

Lineages should store write records, not full state snapshots.

Full snapshots make reads easy but make merges difficult. At gather time the
runtime would have to diff branch snapshots against a base snapshot to discover
what changed. That becomes fragile with nested objects, defaults, reducers,
missing fields, and JSON Schema validation.

Write-record-owned lineages make the merge boundary explicit:

```text
lineage A wrote incoming value X to state.person.name
lineage B wrote incoming value Y to state.person.email
```

The barrier can then validate conflicts and apply reducers deterministically.

Runtime may cache or materialize state views for performance later. The source
of truth should still be ordered lineage write records.

## Incoming Values vs Visible Values

Existing `StatePatch.changes` is trace-facing. For normal node patches it stores
the incoming values from node output bindings. That is useful for trace and for
barrier replay. It is not enough by itself for same-lineage reads when reducers
are involved.

Example:

```text
committed state.count = 2
node output delta = 3
reducer = add
visible state.count after write = 5
```

Trace should be able to say the node emitted `3`. A later node in the same
lineage must see `5`. A future gather must still replay `3` into the parent,
not replay the visible value `5`.

So the runtime needs ordered writes:

```python
StateWrite(
    path=StatePath(("count",)),
    incoming_value=3,  # trace and barrier replay value
    visible_value=5,   # same-lineage read value
    reducer=ReducerRef(name="wf.std.add"),
)
```

`StatePatch` should preserve ordered `StateWrite` records. Convenience views can
derive incoming trace changes and same-lineage visible values, but lineage must
not discard incoming values.

This matters for fork/gather:

```text
root state.number = 2
fork A and B
A applies add(3), visible in A is 5
B applies add(1), visible in B is 3
gather must commit 2 + 3 + 1 = 6
```

If lineage stored only visible values, gather would incorrectly replay `5` and
`3` instead of `3` and `1`.

## State View

The visible state for a frame is:

```text
committed scope root state
+ ancestor lineage visible values
+ current lineage visible values
```

For v1, materializing this with a deep copy is acceptable because correctness is
more important than performance. The implementation should keep this behind one
helper so copy-on-write or structural sharing can replace it later.

```python
def lineage_state_view(run: RunState, scope_id: str, lineage_id: str) -> dict[str, Any]:
    ...
```

## Relationship to Concurrent Foreach

Concurrent foreach is the first real user of lineage.

Current behavior:

- parent foreach frame stores pending item patches in barrier metadata
- `state_view_for_frame` knows about foreach metadata
- node finalization knows about foreach item ownership

Target behavior:

- each concurrent item frame gets its own lineage
- `state_view_for_frame` delegates to lineage helpers
- node finalization only decides root commit vs lineage buffer
- foreach barrier records completed lineage ids
- barrier commit replays completed lineage write records into the existing
  reducer/conflict validation path

This removes foreach-specific state overlay logic from node execution.

## Relationship to Native Subgraphs

Native subgraphs should build on scopes plus lineage.

A subgraph creates a child scope because the child workflow has a separate
committed state root initialized from child workflow input and child state
defaults. The subgraph root frame runs in that child scope and receives the
child scope's root lineage. Child workflow internal frames may create further
child lineages for foreach or future fork/gather.

Parent state changes only happen when the subgraph boundary completes and
applies explicit output bindings. Child internal writes remain inside the child
scope until that boundary.

This prevents child workflow internals from leaking into parent state and gives
interrupt/resume a stable state-visibility boundary.

## Relationship to Future Fork/Gather

Fork creates sibling lineages within the same scope. Gather consumes declared
lineage ids and commits their writes into a parent lineage or scope root.

Conceptually:

```text
fork parent lineage P
  -> child lineage A
  -> child lineage B
gather A+B into P
```

The gather operation should reuse the same conflict validation and reducer rules
as concurrent foreach barrier commits:

- same-path sibling writes require a mergeable reducer
- ancestor/descendant sibling writes are rejected until a deeper merge policy is
  explicitly designed
- reducer application order is deterministic

## RunState Shape

Initial additive shape:

```python
@dataclass(slots=True)
class StateWrite:
    path: StatePath
    incoming_value: Any
    visible_value: Any
    reducer: ReducerRef


@dataclass(slots=True)
class RuntimeScope:
    id: str
    workflow_name: str
    committed_state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LineageState:
    id: str
    scope_id: str
    parent_id: str | None = None
    writes: list[StateWrite] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionFrame:
    ...
    scope_id: str = "root"
    lineage_id: str = "root"


@dataclass(slots=True)
class RunState:
    ...
    state: dict[str, Any]
    scopes: dict[str, RuntimeScope] = field(default_factory=dict)
    lineages: dict[str, LineageState] = field(default_factory=dict)
```

`RunState.state` remains committed root scope state for compatibility. The root
scope may initially mirror `RunState.state`; native subgraphs should use
`RuntimeScope.committed_state` for child scopes instead of writing child state
into `RunState.state`.

## Explicit END and Gather

An explicit `EndNode` is best understood as a degenerate gather:

```text
END = gather exactly one active lineage and finalize output/outcome
```

That does not mean `EndNode` should secretly merge siblings. It means `EndNode`
and future `GatherNode` should eventually share completion machinery.

For native subgraphs, explicit child end nodes would make it possible for a
child graph to dispatch both:

- final child output
- child completion outcome

For v1 lineage work, no explicit end node is required. The lineage migration
should only avoid blocking that future design.

## Serialization

Scopes and lineages must be serializable with `RunState.to_dict()`. This is
required for future run stores and resume. Lineage state should avoid storing
unserializable objects. Values in `StateWrite` are expected to be
JSON-compatible because they come from validated node outputs and state writes.

If a future node output can produce non-JSON Python objects, that should be
handled by schema/runtime validation before it reaches lineage state.

## Error Handling

Malformed scope or lineage state is runtime corruption and should fail fast with
`WorkflowExecutionError`.

Examples:

- frame references an unknown scope id
- frame references an unknown lineage id
- lineage references an unknown parent lineage id
- lineage belongs to a different scope than its frame
- a lineage path is not a valid `StatePath`
- a barrier tries to commit a lineage that is still active or failed
- a barrier sees sibling writes without a mergeable reducer

## Migration Strategy

Do not rewrite the whole runtime at once.

1. Add scope and lineage models while preserving current root-state behavior.
2. Add ordered state write records to `StatePatch`.
3. Route state reads through lineage helpers.
4. Buffer non-root frame writes in lineage state.
5. Move concurrent foreach item overlays onto lineages.
6. Remove foreach-specific overlay coupling from node execution.
7. Document native subgraphs as depending on scopes plus lineage.

This gives the project a stable primitive before adding native subgraphs.

## Out of Scope

- Native subgraph implementation.
- Fork/gather implementation.
- Persistent run store.
- Copy-on-write state view optimization.
- Recursive workflow detection.
- Multiple subgraph outcome schemas.

## Open Design Questions

- Should serial foreach item frames also get item lineages immediately, or only
  concurrent foreach item frames in the first migration?
- Should v1 implement non-root lineage commits into parent lineage, or can v1
  only commit to root scope through foreach barriers?
- Should `TraceEntry` gain explicit `scope_id` and `lineage_id` fields, or
  should those ids stay inspectable through frames and run state?
- Should `LineageState` store all ordered `StateWrite` records indefinitely, or
  compact same-lineage writes by path while preserving enough incoming values for
  future gather replay?

## Recommendation

Implement lineage before native subgraphs, and include runtime scopes in the
design now even if root scope is the only implemented scope in the first code
slice.

Start with concurrent foreach because it already has the same semantics in a
localized form. Once foreach no longer owns custom overlay logic, native
subgraph design gets much cleaner: child workflow state becomes another scope
with its own lineage tree instead of another special case in `RunState`.
