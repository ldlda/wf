# Scheduler Foundation Before Parallel Foreach

Status: accepted

We will introduce an explicit scheduler foundation in `wf_core` before enabling
parallel foreach. The first implementation preserves deterministic serial
behavior while adding ready/block/wake semantics, because parallel foreach and
native subgraphs both require multiple runnable frames without treating
`current_frame_id` as the whole runtime state.

## Context

The current runtime behaves like a stack cursor. `RunState.current_frame_id` and
`current_node_id` identify the active frame, and foreach creates one child frame
at a time before control collapses back to the parent. This works for serial
execution, but it does not give the runtime a clear way to represent multiple
runnable frames, blocked parent frames, interrupt resume priority, or future
parallel branch merge semantics.

Parallel foreach is not just `asyncio.gather` over node calls. It changes state
visibility, error handling, interrupt behavior, trace ordering, reducer rules,
and parent completion semantics. Enabling it before those concepts exist would
make the runtime fragile.

## Decision

Add an internal scheduler foundation first. The first pass will keep serial
workflow behavior intact and will not enable `foreach(mode="parallel")`.

The scheduler model is:

- `RunState.frames` is the frame set and source of truth for live runtime
  cursors.
- `RunState.ready_frame_ids` is an explicit FIFO ready queue and is serialized
  with run state.
- `current_frame_id` and `current_node_id` remain compatibility fields for the
  selected cursor, not the source of all runnable work.
- A selected frame is removed from the ready queue, marked `RUNNING`, and stepped
  once.
- A normal non-terminal step advance marks the same frame `PENDING` and
  re-enqueues it.
- Terminal, blocked, interrupted, and failed frames are not re-enqueued.
- `FrameStatus.BLOCKED` represents a live frame waiting on child completion or a
  future internal event.
- Blocked frames carry typed block-reason metadata so wakeups and deadlocks are
  explainable.
- Scheduler helpers live in an internal runtime scheduler module, not public
  `wf_core` exports.
- Sync and async runtime loops use the same scheduler rules; only node handler
  execution differs.

Serial foreach keeps its current behavior through clearer runtime mechanics:
the foreach parent blocks on one iteration child, the child runs until
completion/interruption/failure, and child completion wakes the parent to create
the next item or finish.

## Rejected Alternatives

**Patch parallelism directly into foreach.**
This would keep the stack-cursor model and force foreach to own scheduling,
interrupt, merge, and failure policy. It would not help native subgraphs.

**Infer runnable frames by scanning `RunState.frames`.**
This hides scheduling order in dictionary iteration, cleanup behavior, and frame
creation side effects. A ready queue makes the policy testable and preserves
resume/checkpoint order.

**Treat `RUNNING` as async-in-flight immediately.**
The first pass is deterministic and serial. `RUNNING` means the scheduler has
selected the frame for the current step. Actual async task orchestration can
refine this later.

**Upgrade `JoinNode` into a real merge barrier now.**
The future barrier semantics are larger than the current join node. `JoinNode`
may be repurposed later, but not silently in this scheduler pass.

## Future Parallel Semantics

Parallel foreach and graph-level convergence require additional semantics before
they are enabled:

- A future foreach policy must define batching, `max_concurrency`, item failure
  handling, and cancellation/drain behavior.
- A future barrier must wait for multiple child or upstream frames and merge
  their lineage patches.
- Missing reducers mean replace only within one serial lineage. At a barrier,
  multiple writes to the same path without a reducer are conflicts.
- Future parallel child frames should produce state patches that the scheduler
  commits atomically.
- Parallel branches require lineage isolation: a child frame sees parent-visible
  state plus its own ancestor writes, not sibling branch writes.
- Public trace remains append-only chronological execution history. Scheduler
  block/wake events are not added to public trace in this pass.

## Interrupt Semantics

A run has at most one outstanding interrupt. If any frame interrupts, the whole
run pauses and scheduling stops. Only the requesting frame becomes
`INTERRUPTED`; ancestors waiting on that frame remain `BLOCKED`.

Resume wakes the interrupted frame, clears the run interrupt, and places the
resumed frame at the front of the ready queue. Ready sibling frames are preserved
but do not run while the interrupt is outstanding.

Future parallel execution should not assume in-flight node calls can be safely
cancelled. If one frame interrupts while sibling jobs are already started, the
runtime should stop scheduling new work, let started jobs drain to pending
results, and defer sibling state commits until resume/commit policy decides what
becomes visible. User-facing control should return only at a quiescent pause
point: no new work is scheduled, already-started jobs have drained, and their
results have been captured without unsafe commits. The first scheduler pass has
no simultaneous node jobs, so an interrupt still stops scheduling immediately.

## Failure Semantics

A runtime failure is distinct from a node returning an `error` outcome. Outcomes
are graph control flow. Runtime failures stop scheduling unless a future policy
explicitly handles them.

In the first scheduler pass, any runtime failure fails the whole run. Future
parallel foreach policies may support `collect` or `skip`, but those are policy
features and should not be treated as implemented until runtime support exists.

## Compatibility Requirements

The first scheduler pass should be additive and regression-safe:

- Existing valid serial workflows keep the same final state, output, node
  execution order, foreach item count, interrupt resume behavior, and meaningful
  trace order.
- `RunState.to_dict()` may grow `ready_frame_ids`, but existing run fields and
  trace entry shape should not churn.
- Completed frames remain in the frame set for the lifetime of an in-memory run.
  Persistence can add explicit compaction later.
- Frame identifiers remain strings for now, but construction should be
  centralized so structural frame IDs can replace the string format later.

## Test Boundary

The scheduler foundation is not complete without tests for:

- root frame initialization in the ready queue
- selecting a frame pops it and marks it `RUNNING`
- normal step advance re-enqueues the same frame
- duplicate frame creation rejection
- duplicate enqueue prevention and priority move-to-front
- blocked frames not being selectable
- empty ready queue resolution into completed, interrupted, failed, or deadlock
- serial foreach regression and parent block/child wake behavior
- interrupt resume priority and single outstanding interrupt behavior
