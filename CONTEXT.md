# Workflow Runtime Context

This context defines the core workflow runtime language used by `wf_core`,
`wf_authoring`, and the MCP-facing workflow platform.

## Language

**Scheduler Foundation**:
The runtime model that selects runnable frames and advances workflow execution without assuming there is only one active cursor.
_Avoid_: Concurrent foreach, parallel foreach foundation

**Frame**:
An execution cursor for one active portion of a workflow run.
_Avoid_: Thread, task

**Frame Set**:
The collection of lifecycle frames owned by a run, including pending, running, interrupted, and completed frames until cleanup rules remove them.
_Avoid_: Running frames

**Runnable Frame**:
A pending frame that the scheduler may select for the next deterministic runtime step.
_Avoid_: Active frame, async task

**Ready Queue**:
The ordered list of runnable frame identifiers that defines deterministic scheduling order.
_Avoid_: Frame scan, implicit dict order

**Foreach Policy**:
The future runtime configuration that decides parallel foreach batching, item failure handling, and cancellation/drain behavior.
_Avoid_: Parallel flag

**Blocked Frame**:
A live frame that is waiting on child frame completion or an external resume event and is not currently runnable.
_Avoid_: Callback, sleeping thread

**Block Reason**:
Typed metadata describing what a blocked frame is waiting for.
_Avoid_: Ad hoc metadata flag

**Interrupt**:
A run-level pause requested by one frame that waits for external input before any more workflow scheduling happens.
_Avoid_: Per-frame prompt queue, background prompt

**Runtime Failure**:
An execution failure that stops scheduling unless a future policy explicitly handles it.
_Avoid_: Error outcome

**Trace**:
An append-only chronological record of executed workflow steps.
_Avoid_: Sorted report, graph view

**Reducer**:
A named merge rule that combines multiple writes to the same state path.
_Avoid_: Last writer wins

**State Patch**:
A validated set of state writes produced by one executed step before it is committed to run state.
_Avoid_: Partial mutation

**State Visibility**:
The committed state a frame may read based on workflow topology and completed upstream work.
_Avoid_: Shared live object

**Lineage Isolation**:
The rule that a parallel child frame sees parent-visible state plus its own ancestor writes, but not sibling branch writes.
_Avoid_: Global committed state

**Barrier**:
A merge boundary that waits for multiple child or upstream frames and combines their lineage patches before continuation.
_Avoid_: Noop join

**Run**:
One execution attempt of a workflow with input, state, frames, trace, and final output.
_Avoid_: Job, invocation

## Relationships

- A **Run** owns one or more **Frames**.
- A **Frame Set** is the source of truth for runtime cursors.
- The **Scheduler Foundation** selects one **Runnable Frame** at a time in the
  first pass.
- The **Ready Queue** defines which **Runnable Frame** is selected next.
- A **Blocked Frame** is intentionally absent from the **Ready Queue** until
  the child/event it waits on wakes it.
- A **Blocked Frame** should carry a **Block Reason** so deadlocks and wakeups
  are explainable.
- Parallel foreach and native subgraphs depend on the **Scheduler Foundation**.
- Parallel foreach requires a **Foreach Policy** before public support is
  enabled.
- An **Interrupt** pauses the whole **Run**, even if the interrupted frame is a
  child of future parallel work.
- A **Runtime Failure** is distinct from a node returning an `error` outcome.
  Outcomes are graph control flow; runtime failures are scheduler stops unless
  a policy handles them.
- A node `error` outcome remains normal graph control flow. A runtime-error
  utility node or engine exception is what turns control flow into a
  **Runtime Failure**.
- Missing edges for declared outcomes are validation errors, not normal runtime
  branch policy.
- Unsupported parallel foreach semantics should be rejected by validation before
  runtime. Runtime may stay defensive, but validation owns the user-facing gate.
- `on_item_error="collect"` and `"skip"` are future policy shapes unless runtime
  support is explicitly implemented. Current scheduler work should make official
  support easier, not pretend it already exists.
- A **Trace** records actual scheduler execution order; grouping or sorting by
  foreach index is a presentation concern.
- Parallel child frames may write to the same state path only through a
  **Reducer**.
- Future parallel frames should produce **State Patches** that the scheduler
  commits atomically.
- A frame's **State Visibility** excludes uncommitted sibling writes.
- Future parallel branches require **Lineage Isolation**: sibling branch writes
  are invisible unless the graph explicitly joins or merges them.
- A **Barrier** is the explicit merge boundary for parallel lineage patches.
- Foreach may own an implicit **Barrier**; future graph-level convergence may use
  an explicit barrier node.

## Example Dialogue

> **Dev:** "Are we implementing parallel foreach now?"
> **Domain expert:** "No. First we are implementing the **Scheduler Foundation** so a **Run** can eventually manage multiple runnable **Frames** safely."

## Flagged Ambiguities

- "concurrent foreach" was used for the next task, but the resolved scope is **Scheduler Foundation**: deterministic internal runtime prep before public parallel foreach support.
- `current_frame_id` / `current_node_id` are compatibility fields for the selected cursor, not the source of truth for all runnable work.
- `current_frame_id` remains persisted for compatibility, but means "the frame
  currently selected by the scheduler", not "the only live frame".
- When the **Ready Queue** is empty, the scheduler must explicitly resolve the
  run as completed, interrupted, failed, or deadlocked. `current_node_id` alone
  is not a terminal-state rule.
- In the first scheduler pass, any **Runtime Failure** fails the whole run and
  stops scheduling.
- `RUNNING` currently means "selected cursor during a deterministic step", not
  "async task already in flight".
- `BLOCKED` should be a first-class frame status for live frames waiting on
  child frame completion or external resume.
- `INTERRUPTED` remains a distinct frame status, not just `BLOCKED` with an
  interrupt reason, because it carries externally visible resume semantics.
- Scheduling order should be explicit through a **Ready Queue**, not inferred
  from frame dictionary iteration.
- `mode="parallel"` stays unsupported until **Foreach Policy** and parent
  completion semantics are explicit.
- A **Run** has at most one outstanding **Interrupt**. Resume wakes the frame
  referenced by that interrupt and scheduling continues from the **Ready Queue**.
- When a child frame interrupts, only that frame becomes `INTERRUPTED`.
  Ancestors waiting on it remain `BLOCKED`; the **Run** status carries the
  global pause.
- Ready sibling frames are preserved during an **Interrupt**, but the resumed
  frame is placed at the front of the **Ready Queue** before scheduling
  continues.
- Future parallel execution should not assume in-flight node calls can be
  safely cancelled. When an **Interrupt** occurs, scheduling should stop; already
  started jobs should drain to pending results before resume/commit policy
  decides what becomes visible.
- Future parallel interrupts should return control to the caller only at a
  quiescent pause point: no new work is scheduled, already-started jobs have
  drained, and their results are captured without unsafe commits.
- Future async execution must protect append-only **Trace** writes, but should
  not change trace semantics.
- Scheduler block/wake events should not be added to the public **Trace** in
  the first pass. Future observability, including OpenTelemetry-style spans, is
  a separate concern.
- Frame identifiers remain strings in the first pass, but construction should be
  centralized so a future structural frame id can replace the string format.
- Typed runtime metadata helpers should return `None` for the wrong frame kind,
  but raise for malformed metadata on the right kind. Corrupt runtime metadata
  is a runtime invariant failure.
- First-pass **Block Reason** support only needs child-frame blocking; future
  interrupt, subgraph, and parallel barrier reasons can extend the same shape.
- Frame creation must reject duplicate frame identifiers. The **Ready Queue**
  must contain only existing pending frames and must never contain duplicate
  frame identifiers.
- Enqueue wakeups may be idempotent: enqueueing an already-ready frame should
  not duplicate it, and priority enqueue may move it to the front.
- Completed frames should remain in the **Frame Set** for the lifetime of an
  in-memory run. Later persistence can add explicit compaction, but scheduler
  correctness should not depend on deleting completed frames.
- Stack-style frame collapse should be demoted in favor of explicit frame
  completion and parent wakeup helpers. Parallel scheduling cannot rely on
  "collapse to parent" semantics.
- The engine/scheduler selects a frame before step preparation. `prepare_step`
  remains a readability helper for resolving the selected frame's current node,
  not for choosing runnable work.
- Sync and async engine loops should migrate to scheduler selection together so
  their runtime semantics do not diverge.
- The **Ready Queue** is part of **Run** state and should be serialized with
  `RunState` so resume/checkpoint behavior preserves scheduler order.
- A new **Run** starts with the root frame pending in the **Ready Queue**.
  Compatibility cursor fields may still point at root initially.
- First-pass serialized `RunState` changes should be additive. `ready_frame_ids`
  may be added, but existing run fields and trace shape should not churn.
- Existing valid serial workflows should keep the same final output/state, node
  execution order, foreach item count, interrupt resume behavior, and meaningful
  trace order after the first scheduler refactor.
- Scheduler foundation is not complete without tests for ready queue selection,
  duplicate protection, block/wake behavior, deadlock detection, serial foreach
  regression, and interrupt resume priority.
- Selecting a **Runnable Frame** removes it from the **Ready Queue** immediately
  and marks it `RUNNING`.
- A normal non-terminal step advance marks the same frame `PENDING` and
  re-enqueues it. Terminal, blocked, interrupted, or failed frames are not
  re-enqueued.
- Ready scheduling is FIFO and one-step-at-a-time. A still-runnable frame goes
  to the back of the **Ready Queue** after each step.
- Serial foreach blocks the parent on one iteration child at a time, so the
  child runs until completion/interruption/failure before the parent wakes.
- Future async execution must protect shared state writes. Last-writer-wins is
  not an acceptable merge policy for parallel child frames.
- Serial execution may continue mutating state immediately until parallel
  execution needs scheduler-controlled **State Patch** commits.
- Parallel sibling frames must not depend on observing each other's writes. Use
  serial foreach or explicit graph structure for ordered dependencies.
- Missing reducers mean replace only within a single serial lineage. At a
  **Barrier**, multiple writes to the same path without a reducer are conflicts,
  not last-writer-wins replacements.
- Current `JoinNode` should not silently become a **Barrier**. It may be
  repurposed later only through an explicit design pass.
- The first **Scheduler Foundation** implementation should create ready/block/wake
  seams only. **Lineage Isolation** and **Barrier** merge behavior are future
  parallel semantics, not first-pass behavior.
- First-pass scheduler code should add durable seams such as ready queue,
  block/wake helpers, and typed foreach metadata. It should not add public
  parallel policy, barrier, snapshot, or lineage-patch fields before those
  semantics are enforced.
- Scheduler rules are shared by sync and async runtime paths; only node handler
  execution differs.
- The first scheduler helpers should live in a scheduler module, not a
  concurrency module. Actual async task orchestration can get separate
  concurrency code later.
- Scheduler helpers are internal runtime infrastructure in the first pass and
  should not be exported as public `wf_core` API yet.
