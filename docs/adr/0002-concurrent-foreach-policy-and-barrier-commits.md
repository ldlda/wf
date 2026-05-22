# Concurrent Foreach Policy and Barrier Commits

Status: accepted

Concurrent foreach will use bounded scheduling, lineage-local pending state, and
barrier-buffered commits. This keeps item execution deterministic, resumable,
and safe around reducers, interrupts, and external tool calls.

## Context

The scheduler foundation makes multiple runnable frames possible, but concurrent
foreach needs more than multiple node calls. Each item lineage may execute
several nodes, read its own pending writes, fail independently, block, or
interrupt the whole run. Sibling item writes must not leak into each other, and
state commits need deterministic merge behavior.

## Decision

Concurrent foreach is a workflow mode and must be bounded by policy.

The future foreach model should separate item error behavior from concurrency
behavior:

- `item_error` is foreach-wide and applies to serial and concurrent foreach.
- `concurrent` is a nested policy object used only when
  `mode="concurrent"`.
- `concurrent.max_active` defaults to `4`.
- `concurrent.max_outstanding` defaults to `20`.
- Validation requires `max_outstanding >= max_active`.
- Ready or running item frames consume active capacity.
- Blocked item frames consume outstanding capacity but not active capacity.

`foreach(mode="concurrent")` should be executable by the sync runtime as
deterministic frame interleaving: one admitted node handler call at a time. The
async runtime may additionally run admitted async node handler calls
simultaneously. Sync handlers should not be pushed into thread/process
parallelism by default.

## Item Error Policy

Item error policy handles runtime failures inside an item frame, not normal graph
control-flow outcomes. A node returning an `error` outcome is still ordinary
graph routing if the graph declares that edge.

Supported policy actions:

- `fail`: stop scheduling new items, drain already-started jobs to a quiescent
  point, capture results for trace/observability, then fail the run.
- `skip`: mark the failed item frame failed, record no hidden state, continue,
  and emit `completed_with_errors` if any item was skipped.
- `collect`: mark the failed item frame failed, collect a structured item error
  record, continue, and emit `completed_with_errors` if any item was collected.

`collect` must declare an explicit state array destination. The foreach barrier
writes the full ordered error list once. On clean completion, `collect` writes an
empty list and emits `done`.

Collected error records include item index, frame id, failing node id, error
type/message, and the item value when it can be represented safely.

## Aggregate Outcomes

Foreach aggregate outcomes are policy-derived:

- `done`: all items completed cleanly.
- `completed_with_errors`: all items completed but one or more item failures
  were handled by `skip` or `collect`.

Validation should require a routable `completed_with_errors` edge whenever the
policy can emit it. Users may route it to the same target as `done` explicitly.

Aggregate result vocabulary should be shared with future barrier-like graph
steps. `fail` is a policy action; if a future aggregate node emits graph-level
failure as control flow, the outcome should be `failed`.

## Barrier-Buffered Commits

Concurrent foreach item writes are buffered as pending state patches/results, not
committed directly to `RunState.state`.

The state model is:

- `RunState.state` remains committed parent/global state.
- Each item lineage reads a visible state view built from committed state plus
  its own lineage-local patch overlay.
- Sibling item patches are invisible to each other.
- Pending barrier results live in resumable run state/frame metadata, not trace.
- Trace `state_changes` means committed state changes only.

The barrier commits item results in deterministic item-index order by default.
Completion-order merging may exist later as an explicit barrier merge policy,
not reducer behavior.

Patch creation and commit must extract/reuse the existing node output
validation, output binding, and reducer logic. Concurrent foreach must not
create a second write system.

Current sync execution supports item-local read overlays for concurrent foreach
item frames. `RunState.state` remains committed parent state, while
`state_view_for_frame` overlays the current item's buffered writes for reads by
later nodes in the same item lineage. Sibling overlays remain invisible until
the foreach barrier commits.

## Merge and Reducer Rules

At a barrier, missing reducer means default replace only for single-writer
paths. Multiple sibling lineages writing the same state path require an explicit
reducer. Ancestor/descendant overlapping writes across lineages are conflicts
unless an explicit merge strategy covers them.

Reducers apply incrementally in deterministic lineage order. For foreach, that
means item index order.

## Interrupt and Failure Quiescence

Future concurrent execution should not assume in-flight node calls can be safely
cancelled.

If an interrupt or fail policy trips while sibling jobs are already started, the
runtime should:

1. stop scheduling new work
2. let already-started jobs drain to a quiescent point
3. capture their results safely
4. defer or discard commits according to the policy boundary
5. return control only after no hidden background jobs continue mutating state

For `fail`, drained sibling results are for observability/cleanup only and
should not commit normal state progress after the failure boundary.

## Capacity and Runtime Limits

Foreach capacity is local correctness policy, not total process protection.
Future runtime should also support a basic global node-call budget in `wf_core`.
Source-, account-, or tool-specific limits belong in the platform layer.

Global node-call limits count admitted node handler calls, not all frames.
Control-flow frames are scheduler work; node calls are the expensive boundary.
Node calls waiting on platform/source/tool semaphores still count as active
node calls, and those waits keep the frame `RUNNING` rather than `BLOCKED`.

## Context and Lineage

Concurrent item frames need lineage-local pending state. Later nodes in the same
item lineage can read earlier pending patches from that item, while siblings
cannot.

Patch overlays conceptually belong to lineage tokens, not execution frames. A
scoped foreach implementation may begin by storing them in foreach metadata, but
future Fork/Gather needs first-class lineage ownership.

Future foreach metadata should evolve into inherited structured lineage context:

- core runtime context is structural, not alias-first
- foreach structured context keys are foreach node ids
- `as_` remains authoring sugar and human-readable trace/docs context
- Python `RuntimeContext` should eventually expose typed context such as
  `ctx.foreach["docs"].index`
- normal node authors should receive foreach values through mapped input;
  inspecting runtime context is an advanced escape hatch

## Deferred Work

Explicit Fork/Gather is deferred. A future `GatherNode` should expose explicit
barrier semantics, but arbitrary graph convergence needs lineage tokens first.
Forks produce branch lineage tokens; gathers consume declared token sets and
produce merged tokens. This supports partial gathers such as merging `a+b`
before later merging with `c`.

Concurrent foreach remains the nearer target because its implicit lineage tokens
are item indexes owned by one foreach activation.
