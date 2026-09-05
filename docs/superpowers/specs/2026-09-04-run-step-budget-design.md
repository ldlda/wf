# Run Step Budget Design

## Status

Proposed for review on 2026-09-04. This document specifies a persisted
run-wide guard against unbounded graph execution. It is independent of foreach
control-region validation and structured runtime context.

## Purpose

Valid workflows may contain ordinary or data-dependent cycles:

```text
a -> b
^    |
|____|
```

Static validation cannot prove that such a cycle eventually exits. The runtime
therefore needs a deterministic step budget that stops a runaway run without
pretending every legal loop can be rejected during validation.

The intended core configuration is:

```python
RunLimits(max_steps=10_000)
```

The budget belongs to the run, covers all of its frames and subgraph scopes,
and survives checkpoint/resume.

## Terminology

**Run Limits** are immutable execution limits captured when a run is created.
They are runtime policy, not workflow graph semantics.

**Step Attempt** is one admitted attempt to execute a selected workflow `Step`
in one frame. Node uses, conditions, foreach controllers, subgraph boundaries,
interrupt nodes, and explicit end nodes all count.

**Step Number** is the one-based ordinal assigned to an admitted step attempt
within a run.

**Step Budget Exhaustion** occurs when the runtime would begin another step
after `max_steps` attempts have already been admitted.

## Configuration and State

Core runtime state gains JSON-compatible limit and progress fields:

```python
@dataclass(frozen=True, slots=True)
class RunLimits:
    max_steps: int = 10_000


@dataclass(slots=True)
class RunState:
    limits: RunLimits = field(default_factory=RunLimits)
    steps_executed: int = 0
```

`max_steps` must be a positive integer. The first implementation does not add
an unlimited sentinel: callers that intentionally need large runs can choose a
larger explicit value while every run retains a finite protection boundary.

New execution entry points accept optional limits and capture the normalized
value in `RunState`:

```python
execute_workflow(
    workflow,
    workflow_input,
    registry,
    limits=RunLimits(max_steps=50_000),
)
```

Resume entry points use the limits stored in the run. They do not silently
reset the counter or accept a replacement budget. A future administrative
operation may deliberately extend a stopped run, but ordinary resume is not
that operation.

The platform may enforce a lower deployment- or account-level maximum when it
creates the core `RunLimits`. Core state still records the effective value so
inspection and resume do not depend on mutable external configuration.

## Counting Semantics

The runtime consumes one budget unit after selecting a runnable frame and
resolving its current `Step`, immediately before dispatching that step's
behavior. The counter is incremented before user code or external capability
code begins, so failures and interrupts still consume the attempt that caused
them.

For a durable run, admission is checkpointed before dispatch. The checkpoint
contains the incremented counter, assigned step number, selected frame and
node, and an admitted-but-not-completed marker. Dispatch may begin only after
that checkpoint succeeds. If the process stops at that boundary, restore keeps
the attempt consumed, clears the abandoned admission marker, and requeues the
frame; a retry is a new attempt with a new step number. The in-memory executor
applies the same counter transition without requiring a persistence backend.
As with any crash after external dispatch and before result persistence, retry
may repeat external effects; the budget records attempts and does not provide
exactly-once execution.

If `steps_executed == max_steps`, the next attempted dispatch is denied. A
budget of one therefore admits exactly one step. The denied step does not
increment the counter and does not invoke a handler.

Repeated visits count independently:

- each trip through an ordinary graph cycle counts each selected step;
- each foreach-controller dispatch counts, including admissions and final
  barrier completion;
- each foreach item body step counts in its item frame;
- starting and later completing a subgraph boundary are separate attempts;
- every step executed inside the child subgraph counts against the same run;
- an interrupt activation counts once; supplying its external resume payload
  completes that admitted activation without consuming another step; and
- an explicit `EndNode` counts, while the legacy `END` token itself does not
  because it is a transition target rather than an executable `Step`.

The counter is deliberately not `len(run.trace)`. Some attempts fail before a
normal trace entry is emitted, and scheduler/control-flow implementation may
record traces differently. Budget correctness must not depend on observability.

## Sync and Async Admission

Sync execution consumes one unit before each `step_workflow()` dispatch.

Async execution applies the same rule. The concurrent foreach fast path may
claim several item frames and invoke their node handlers together; it reserves
one step number per admitted frame in deterministic ready-queue order before
launching any handler. It may claim at most the remaining budget.

For example, with three units remaining and five otherwise eligible item
frames, the runtime admits the first three frames in ready-queue order. It does
not start the other two. After the admitted batch settles deterministically,
the next dispatch observes exhaustion and fails the run.

Reserved async attempts remain consumed even if one handler raises. This
matches the rule that admission, rather than successful completion, consumes
the budget and avoids making counts depend on task completion timing.

The runtime awaits every handler in an admitted batch before finalizing any
result. It then finalizes in reserved ready-queue order. Handled foreach item
failures follow their declared `skip` or `collect` policy. At the first
unhandled failure in that order, preceding successful results have committed,
the run fails, and later sibling results are discarded without state or trace
commits. Because all handler tasks have already settled, no sibling can mutate
the failed checkpoint afterward; external effects performed inside a handler
remain outside rollback.

## Exhaustion Behavior

Exhaustion is a runtime failure, not a workflow outcome. The runtime raises a
specific `WorkflowStepLimitExceeded` derived from `WorkflowExecutionError` and
marks the run failed through the same raising-versus-result conventions used by
existing execution entry points.

The error reports at least:

```text
workflow name
configured max_steps
steps_executed
selected frame id
selected scope id
next node id
```

No edge may catch the failure as an `error` outcome. A node's declared error
outcome remains ordinary graph control flow and consumes a step like every
other completed attempt.

The failed run retains its frames, ready queue, state, lineages, trace, and
counter for inspection. The denied handler is never invoked. Whether a future
administrative rerun can raise the budget is outside ordinary resume semantics.

## Persistence and Resume

`RunLimits` and `steps_executed` are serialized inside the persisted `RunState`
checkpoint. An interrupted run resumes with its original maximum and cumulative
count.

A checkpoint that predates step budgets receives one explicit, prospective
upgrade: assign the default limit and `steps_executed = 0`, mark the envelope as
budget-initialized, and persist the upgraded checkpoint before admitting any
new work. Attempts made before the upgrade cannot be reconstructed and are
explicitly outside the new budget; every attempt after it is cumulative. A
missing counter on an already budget-initialized envelope is corrupt state, not
another request for defaults. If the one-time upgrade cannot be persisted,
resume fails before dispatch. The persisted envelope version or equivalent
migration marker must distinguish these cases.

Subgraph scopes do not receive independent counters. They are part of the same
run and consume the root run's budget. This prevents an outer workflow from
bypassing its protection by repeatedly entering children.

## Trace and Future Time Travel

Each normal `TraceEntry` emitted for an admitted step should carry its assigned
`step_number`. Step numbers are allocated in deterministic scheduler order;
async batch traces retain those numbers regardless of handler completion
order. The interrupt request persists its assigned number, and both the
initial `interrupt` trace entry and its later resume-completion entry use that
same number because they describe one admitted interrupt activation.

Trace step numbers support inspection and future checkpoint/trace navigation,
but gaps are valid when an attempt fails or interrupts before a normal trace
entry exists. `RunState.steps_executed` remains authoritative for enforcement
and resume.

A future time-machine system may use step numbers to correlate checkpoints,
trace events, frames, and state changes. This design does not require replaying
runtime state from trace alone and does not choose event-sourcing semantics.

## Relationship to Other Limits

The step budget protects against unbounded control flow. It does not replace:

- foreach `max_active`, which limits simultaneously active item work;
- foreach `max_outstanding`, which limits admitted and blocked item frames;
- a future global active-node-call limit, which bounds simultaneous expensive
  handler calls;
- source-, account-, or provider-specific rate limits; or
- input-expression depth and node-count validation limits.

These limits measure different resources. A workflow can stay below every
concurrency limit while looping forever, and it can exhaust concurrency or
provider capacity long before reaching its step budget.

## Public Inspection

Core and client-facing run inspection should expose:

```python
run.limits.max_steps
run.steps_executed
run.steps_remaining
```

`steps_remaining` is a computed convenience value, not separately persisted:

```python
max(run.limits.max_steps - run.steps_executed, 0)
```

Run creation accepts an optional requested limit where the surrounding
platform authorizes it. Inspection returns the effective limit actually stored
with the run.

## Required Tests

### Core counting

- A budget of one admits exactly one step and denies the second.
- Node, condition, foreach, subgraph, interrupt, and explicit end steps
  count.
- A transition to legacy `END` does not create an extra attempt.
- Handler failure still consumes its admitted step.
- A node `error` outcome remains normal control flow and consumes one step.
- An ordinary closed cycle fails at the configured limit.
- A data-dependent loop that exits within the budget completes normally.

### Frames and scopes

- Foreach controller and item-frame attempts share one counter.
- Re-entered foreach activations continue the same run budget.
- Child subgraph attempts consume the parent run budget.
- Interrupt resume completes the admitted interrupt activation without
  consuming a second step.
- Execution after interrupt resume continues from the persisted cumulative
  count.
- Budget exhaustion does not invoke the denied node handler.

### Async execution

- Concurrent foreach batching reserves one unit per item frame.
- A batch claims no more frames than the remaining budget.
- Step numbers follow ready-queue order rather than completion order.
- Reserved attempts remain counted when one async handler fails.
- A still-running sibling settles before an unhandled handler failure is
  checkpointed, and its later result does not commit state or trace data.
- Sync and async runs produce the same count for equivalent serial execution.

### Persistence and API

- Limits and counts round-trip through `dump_run_state()` and
  `load_run_state()`.
- A stored interrupted run resumes without resetting or replacing its budget.
- A pre-budget checkpoint receives its defaults once, persists the upgraded
  envelope before dispatch, and cannot receive another fresh budget on reload.
- Stopping after the admission checkpoint but before handler start leaves the
  attempt consumed; retrying the requeued frame consumes a new attempt.
- Run inspection exposes effective maximum, executed, and remaining counts.
- Trace entries expose deterministic step numbers without becoming the source
  of enforcement truth.

## Non-Goals

- Static termination proofs.
- Treating budget exhaustion as a routable workflow outcome.
- Per-subgraph or per-foreach step budgets.
- Changing concurrency, rate-limit, or provider-admission policy.
- An ordinary-resume option that resets or extends a budget.
- Full time-machine, event-sourcing, or trace-replay semantics.
