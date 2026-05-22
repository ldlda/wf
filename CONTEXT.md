# Workflow Runtime Context

This context defines the core workflow runtime language used by `wf_core`,
`wf_authoring`, and the MCP-facing workflow platform.

## Language

**Scheduler Foundation**:
The runtime model that selects runnable frames and advances workflow execution without assuming there is only one active cursor.
_Avoid_: Foreach feature, concurrent foreach implementation

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
The future runtime configuration that decides concurrent foreach admission, item failure handling, and quiescence behavior.
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
The rule that a concurrent child frame sees parent-visible state plus its own ancestor writes, but not sibling branch writes.
_Avoid_: Global committed state

**Barrier**:
A merge boundary that waits for multiple child or upstream frames and combines their lineage patches before continuation.
_Avoid_: Noop join

**Gather Node**:
A future graph step that exposes an explicit barrier for waiting on multiple branches and merging their results.
_Avoid_: Promise.all node, converge node

**Lineage Token**:
A future runtime marker for one branch lineage that can be consumed and merged by gather-style barriers.
_Avoid_: Edge id

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
- Concurrent foreach and native subgraphs depend on the **Scheduler Foundation**.
- Concurrent foreach requires a **Foreach Policy** before public support is
  enabled.
- Future concurrent foreach should be bounded by default. `max_active` and
  `max_outstanding` prevent one workflow from spawning unbounded MCP, HTTP,
  browser, or external service calls.
- Future concurrency-specific foreach settings should live in a nested
  policy object rather than expanding `ForeachNode` with many top-level fields.
- Item error handling is foreach-wide, not concurrent-only. Today, serial
  foreach supports `fail`; concurrent foreach supports `fail`, `skip`, and
  `collect`. Future serial foreach can reuse the same `skip`/`collect` policy
  shape when its execution path is upgraded.
- `collect` item error policy must declare an explicit destination for
  structured item errors. Collected errors should be ordered by item index, not
  async completion order.
- Item error policy handles runtime failures inside an item frame, such as
  thrown handler errors, schema failures, runtime-error utility nodes, or
  invalid graph execution. It does not intercept normal graph outcomes like
  `error` when those outcomes are routed.
- A collected or skipped item failure should leave that item frame `FAILED`.
  The foreach parent/barrier decides whether that failed child is handled and
  whether the run may continue.
- `skip` item error policy writes no hidden state. Failed frame status and
  trace/observability are the record; use `collect` when structured error state
  is needed.
- `collect` writes structured item error records before emitting an aggregate
  error outcome. Records include item index, frame id, failing node id, error
  type/message, and the item value when it can be represented safely.
- `collect` destinations must be state array fields. The foreach barrier writes
  the full ordered error list once, so users should not expect per-item append
  writes. Authoring and MCP validation should surface this clearly.
- `completed_with_errors` is the canonical foreach aggregate outcome when all
  items have finished but one or more item failures were handled by `collect` or
  `skip`.
- `completed_with_errors` is barrier aggregate vocabulary, not foreach-only.
  Future explicit barriers may emit it when handled branch failures occurred.
- Aggregate control-flow outcomes use result nouns/adjectives such as `done`,
  `completed_with_errors`, and optionally `failed`. Policy actions use verbs
  such as `fail`.
- If a foreach policy can emit `completed_with_errors`, validation should treat
  it as a required routable outcome. Users may route it to the same target as
  `done` explicitly.
- `collect` writes an empty list to its destination when all items succeed and
  emits `done`. It emits `completed_with_errors` only when at least one item
  failure was collected.
- `skip` emits `completed_with_errors` when one or more item failures were
  skipped. It emits `done` only when all items succeed.
- Concurrent `fail` item policy should stop scheduling new items, drain already
  started jobs to a quiescent point, capture their results safely, and then fail
  the run. It should not assume hard cancellation is safe.
- After `fail` trips, drained sibling results are for trace/observability and
  cleanup only. They should not commit normal state progress after the failure
  boundary.
- Foreach modes that continue after item failure, such as `collect` and `skip`,
  should buffer item state patches until the foreach barrier completes. Future
  concurrent foreach should always use barrier-buffered commits.
- Serial `fail` may keep immediate commits for compatibility. Commit strategy
  should be extracted into runtime helpers instead of being smeared through
  foreach execution code.
- Barrier-buffered commits should store pending state patches/results, not full
  state snapshots. Patch creation and commit must extract/reuse the existing
  node output validation, output binding, and reducer logic rather than creating
  a second write system.
- Foreach barrier commits should merge item results in item index order, not
  completion order. Reducer behavior such as list appends should therefore be
  deterministic.
- Successful item results may exist as pending barrier results before commit,
  but they are not visible as workflow state until the barrier commits.
- Pending barrier results must live in resumable `RunState`/frame metadata, not
  only in trace. Trace records history; runtime state is what resume/checkpoint
  uses.
- Concurrent item frames need lineage-local pending state: later nodes in the same
  item lineage can read earlier pending patches from that item, while sibling
  items cannot. The exact aggregate output API for committing item results to
  parent state is deferred.
- Lineage-local state should be represented as patch overlays over parent-visible
  state, not deep-copied full state snapshots.
- Patch overlays conceptually belong to lineage tokens, not execution frames.
  A scoped foreach implementation may start by storing them in item/parent
  metadata, but future Fork/Gather needs first-class lineage ownership.
- `RunState.state` remains committed parent/global state. Future frame execution
  should resolve reads against a frame-specific visible state view built from
  committed state plus visible lineage overlays.
- At a barrier, missing reducer means default replace only for single-writer
  paths. Multiple sibling lineages writing the same path require an explicit
  reducer; otherwise barrier commit raises a runtime error with writer details.
- Barrier conflict detection should use the same write-overlap rules as normal
  state writes. Ancestor/descendant writes from different lineages are conflicts
  unless an explicit merge strategy covers them.
- Reducers at barriers apply incrementally in deterministic lineage order by
  default: item index order for foreach, declared branch token order for future
  gather. Completion-order merging is a possible explicit barrier policy, not
  reducer behavior.
- Collected error records follow the same barrier merge order policy. The
  default is deterministic lineage order.
- Trace `state_changes` should mean committed state changes only. Do not encode
  pending barrier patches there unless a future typed trace field is added.
- Foreach may keep implicit barrier/iteration state on the foreach parent frame
  because it owns item spawning and refill. General branch convergence should
  become an explicit **Gather Node** later. Shared barrier merge/result helpers
  should prevent foreach and future barriers from duplicating patch ordering,
  conflict checks, and failure aggregation.
- Future Fork/Gather needs **Lineage Tokens**, not raw edge ids. A fork produces
  branch lineage tokens; a gather consumes a declared set of tokens and produces
  a new merged token. This supports partial gathers such as merging branches
  `a+b` before later merging with `c`.
- Explicit Fork/Gather is deferred until lineage tokens are designed. Parallel
  foreach remains the nearer target because its implicit lineage tokens are item
  indexes owned by one foreach activation.
- Future foreach metadata should evolve into inherited structured lineage
  context. Alias lookup such as `context.document` can remain authoring sugar,
  but runtime metadata should preserve nested foreach lineage without flat key
  collisions.
- Nested active foreach aliases should not shadow each other. Alias collisions
  in inherited context scope should be validation errors.
- Core runtime context should be structural, not alias-first. Foreach lineage
  should be addressable through paths such as `context.foreach.<id>.index`;
  `wf_authoring` can provide ergonomic alias helpers such as
  `context_path(foreach_ref("docs").index)`.
- Python `RuntimeContext` should eventually expose typed structured foreach
  context, such as `ctx.foreach["docs"].index`, while serialized frame metadata
  remains JSON-compatible dictionaries.
- Structured foreach context keys should be foreach node ids. The `as_` alias is
  authoring sugar for current item access, not the canonical runtime key.
- `wf_authoring.WorkflowBuilder.foreach(...)` should eventually return a richer
  ref exposing context selectors such as `.item` and `.index`, so users do not
  hand-write `context.foreach.<id>...` paths.
- Normal node authors should receive foreach values through mapped input.
  Inspecting `RuntimeContext.foreach` is an advanced escape hatch for nodes that
  genuinely need index/frame/lineage context.
- `as_` remains useful ergonomic sugar and human-readable trace/docs context,
  but structured foreach refs should be preferred for non-trivial authoring.
- Future foreach policy shape should validate cross-field rules: `collect`
  requires `collect_to`, non-collect actions forbid `collect_to`,
  `mode="concurrent"` requires a concurrent policy, and `mode="serial"` forbids
  a concurrent policy. Deprecated top-level `on_item_error` may parse into the
  nested item error policy, but canonical dumps should use the nested shape.
- `ForeachConcurrentPolicy` should split limits into `max_active` and
  `max_outstanding`. Defaults are `max_active=4` and `max_outstanding=20`;
  validation requires `max_outstanding >= max_active`. Ready or running item
  frames consume active capacity; blocked item frames consume outstanding
  capacity but not active capacity.
- A blocked non-interrupt item frame frees active capacity and may let foreach
  start another item when `max_outstanding` also has room. A run-level interrupt
  still stops scheduling.
- The foreach parent frame owns refill decisions. Scheduler wakes/schedules
  frames; foreach-specific policy decides whether to start more children,
  finish, or fail.
- When an item frame becomes blocked, it frees active capacity only for its
  nearest foreach capacity owner. Future item metadata should identify that
  owner rather than waking arbitrary ancestors.
- Foreach capacity is local correctness policy, not total process protection.
  Future runtime should also have basic global run limits in `wf_core`; source-
  or tool-specific limits belong in the platform layer.
- A future global `wf_core` runtime limit should count active node handler calls,
  not all active frames. Control-flow frames are scheduler work; node calls are
  the expensive external/user-code execution boundary.
- Global node-call limits do not replace foreach caps. Foreach caps bound local
  scheduling fairness, outstanding frame count, memory, and pending results;
  global node-call limits bound expensive handler execution across the run.
- Platform source/tool/account limits should be enforced at the node-handler
  boundary, before invoking the external call. They layer on top of core global
  node-call admission instead of replacing it.
- Node calls waiting on platform source/tool/account limits still count as
  active node calls. Core global node-call admission should happen before
  platform-specific semaphore acquisition.
- Waiting on a source/tool/account semaphore keeps the frame `RUNNING`; it is
  backpressure inside the admitted node-call boundary, not workflow-level
  `BLOCKED` state that frees foreach active capacity.
- An **Interrupt** pauses the whole **Run**, even if the interrupted frame is a
  child of future concurrent work.
- A **Runtime Failure** is distinct from a node returning an `error` outcome.
  Outcomes are graph control flow; runtime failures are scheduler stops unless
  a policy handles them.
- A node `error` outcome remains normal graph control flow. A runtime-error
  utility node or engine exception is what turns control flow into a
  **Runtime Failure**.
- Missing edges for declared outcomes are validation errors, not normal runtime
  branch policy.
- Unsupported concurrent foreach semantics should be rejected by validation before
  runtime. Runtime may stay defensive, but validation owns the user-facing gate.
- `on_item_error="collect"` and `"skip"` are supported for concurrent foreach.
  Serial foreach still behaves as fail-only until its execution path explicitly
  adopts barrier-buffered item error handling.
- A **Trace** records actual scheduler execution order; grouping or sorting by
  foreach index is a presentation concern.
- Concurrent child frames may write to the same state path only through a
  **Reducer**.
- Future concurrent frames should produce **State Patches** that the scheduler
  commits atomically.
- A frame's **State Visibility** excludes uncommitted sibling writes.
- Future concurrent branches require **Lineage Isolation**: sibling branch writes
  are invisible unless the graph explicitly joins or merges them.
- A **Barrier** is the explicit merge boundary for concurrent lineage patches.
- Foreach may own an implicit **Barrier**; future graph-level convergence may use
  an explicit barrier node.

## Example Dialogue

> **Dev:** "Are we implementing concurrent foreach now?"
> **Domain expert:** "No. First we are implementing the **Scheduler Foundation** so a **Run** can eventually manage multiple runnable **Frames** safely."

## Flagged Ambiguities

- "concurrent foreach" is the future workflow mode. The resolved current scope is
  **Scheduler Foundation**: deterministic internal runtime prep before public
  concurrent foreach support.
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
- `mode="concurrent"` stays unsupported until **Foreach Policy** and parent
  completion semantics are explicit.
- A **Run** has at most one outstanding **Interrupt**. Resume wakes the frame
  referenced by that interrupt and scheduling continues from the **Ready Queue**.
- When a child frame interrupts, only that frame becomes `INTERRUPTED`.
  Ancestors waiting on it remain `BLOCKED`; the **Run** status carries the
  global pause.
- Ready sibling frames are preserved during an **Interrupt**, but the resumed
  frame is placed at the front of the **Ready Queue** before scheduling
  continues.
- Future concurrent execution should not assume in-flight node calls can be
  safely cancelled. When an **Interrupt** occurs, scheduling should stop; already
  started jobs should drain to pending results before resume/commit policy
  decides what becomes visible.
- Future concurrent interrupts should return control to the caller only at a
  quiescent pause point: no new work is scheduled, already-started jobs have
  drained, and their results are captured without unsafe commits.
- Future async execution must protect append-only **Trace** writes, but should
  not change trace semantics. Async runtime is an execution capability for
  simultaneous async node handlers, not a separate foreach workflow mode.
- Scheduler block/wake events should not be added to the public **Trace** in
  the first pass. Future observability, including OpenTelemetry-style spans, is
  a separate concern.
- Frame identifiers remain strings in the first pass, but construction should be
  centralized so a future structural frame id can replace the string format.
- Typed runtime metadata helpers should return `None` for the wrong frame kind,
  but raise for malformed metadata on the right kind. Corrupt runtime metadata
  is a runtime invariant failure.
- First-pass **Block Reason** support only needs child-frame blocking; future
  interrupt, subgraph, and concurrent barrier reasons can extend the same shape.
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
  not an acceptable merge policy for concurrent child frames.
- Serial execution may continue mutating state immediately until concurrent
  execution needs scheduler-controlled **State Patch** commits.
- Concurrent sibling frames must not depend on observing each other's writes. Use
  serial foreach or explicit graph structure for ordered dependencies.
- Missing reducers mean replace only within a single serial lineage. At a
  **Barrier**, multiple writes to the same path without a reducer are conflicts,
  not last-writer-wins replacements.
- Current `JoinNode` should not silently become a **Barrier**. It may be
  repurposed later only through an explicit design pass.
- The first **Scheduler Foundation** implementation should create ready/block/wake
  seams only. **Lineage Isolation** and **Barrier** merge behavior are future
  concurrent semantics, not first-pass behavior.
- First-pass scheduler code should add durable seams such as ready queue,
  block/wake helpers, and typed foreach metadata. It should not add public
  concurrent policy, barrier, snapshot, or lineage-patch fields before those
  semantics are enforced.
- Scheduler rules are shared by sync and async runtime paths; only node handler
  execution differs.
- The first scheduler helpers should live in a scheduler module, not a
  concurrency module. Actual async task orchestration can get separate
  concurrency code later.
- Scheduler helpers are internal runtime infrastructure in the first pass and
  should not be exported as public `wf_core` API yet.
