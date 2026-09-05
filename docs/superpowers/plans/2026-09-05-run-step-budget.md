# Run Step Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one finite, persisted step-attempt budget shared by every frame
and subgraph scope in a workflow run.

**Architecture:** Core owns immutable `RunLimits`, the cumulative counter, and
admission immediately before step dispatch. Each frame remembers its latest
assigned step number so ordinary, batched, and resumed-interrupt traces use the
correct identity. Existing stopped-run checkpoints persist the counter; this
slice deliberately does not introduce per-step write-ahead checkpoints.

**Tech Stack:** Python 3.14 dataclasses, Pydantic 2 codecs, synchronous and
async workflow runtimes, FastAPI JSON-RPC, the Python workflow client, pytest.

**Spec:**
[`../specs/2026-09-04-run-step-budget-design.md`](../specs/2026-09-04-run-step-budget-design.md)

## Global Constraints

- `RunLimits.max_steps` defaults to `10_000` and must be a positive non-boolean
  integer.
- One run-wide counter covers root frames, foreach item frames, and child
  subgraph scopes.
- Admission increments before handler dispatch; a denied handler never runs.
- Resume uses the persisted effective limit and cannot replace or reset it.
- Version-1 checkpoints receive defaults once; version-2 checkpoints missing
  budget fields are corrupt.
- Budget exhaustion is `WorkflowStepLimitExceeded`, never a workflow outcome.
- Async batches reserve in ready-queue order and finalize in that same order.

---

### Task 1: Core limit model, admission, and codec migration

**Files:**

- Modify: `src/wf_core/run_state.py`
- Modify: `src/wf_core/errors.py`
- Create: `src/wf_core/runtime/limits.py`
- Modify: `src/wf_core/runtime/ops/runs.py`
- Modify: `src/wf_core/run_codec.py`
- Modify: `src/wf_core/__init__.py`
- Test: `tests/core/test_run_step_budget.py`
- Test: `tests/core/test_run_codec.py`

**Interfaces:**

- Produces: `RunLimits(max_steps: int = 10_000)`.
- Produces: `admit_step_attempt(run, frame, node_id) -> int`.
- Produces: `remaining_step_attempts(run) -> int`.
- Produces: `load_run_state_with_upgrade(payload) -> tuple[RunState, bool]`.

- [ ] **Step 1: Write failing model, admission, and codec tests**

Cover positive validation, the default, a budget of one, denied admission not
incrementing, error details, v2 round-trip, v1 default injection, and v2
missing-field corruption. The public shape is:

```python
limits = RunLimits(max_steps=1)
run = create_run_state(workflow, {}, limits=limits)
number = admit_step_attempt(run, run.current_frame(), workflow.start)

assert number == 1
assert run.steps_executed == 1
assert run.steps_remaining == 0
with pytest.raises(WorkflowStepLimitExceeded):
    admit_step_attempt(run, run.current_frame(), workflow.start)
```

- [ ] **Step 2: Run the new tests and verify they fail for missing symbols**

Run:

```text
uv run pytest tests/core/test_run_step_budget.py tests/core/test_run_codec.py -q
```

- [ ] **Step 3: Implement the minimal core model and admission module**

```python
@dataclass(frozen=True, slots=True)
class RunLimits:
    max_steps: int = 10_000

    def __post_init__(self) -> None:
        if isinstance(self.max_steps, bool) or not isinstance(self.max_steps, int):
            raise TypeError("max_steps must be an integer")
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")


def admit_step_attempt(
    run: RunState, frame: ExecutionFrame, node_id: str
) -> int:
    if run.steps_executed >= run.limits.max_steps:
        raise WorkflowStepLimitExceeded.from_run(run, frame, node_id)
    run.steps_executed += 1
    frame.step_number = run.steps_executed
    return frame.step_number
```

Add `limits`, `steps_executed`, and computed `steps_remaining` to `RunState`;
add `step_number: int | None` to `ExecutionFrame`; pass optional limits through
`create_run_state()`.

- [ ] **Step 4: Implement strict v2 output and explicit v1 loading**

`dump_run_state()` writes envelope version 2. Version 1 may omit the three new
fields and receives defaults. Version 2 validates that `limits`,
`steps_executed`, and each serialized frame's `step_number` field are present
before using the dataclass adapter. Return `upgraded=True` only for v1.

- [ ] **Step 5: Run the focused tests and commit**

Run:

```text
uv run pytest tests/core/test_run_step_budget.py tests/core/test_run_codec.py -q
```

Commit: `feat: add persisted run step budget state`

### Task 2: Sync dispatch and trace numbering

**Files:**

- Modify: `src/wf_core/runtime/step.py`
- Modify: `src/wf_core/runtime/ops/flow.py`
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Modify: `src/wf_core/runtime/ops/interrupts.py`
- Modify: `src/wf_core/run_state.py`
- Test: `tests/core/test_run_step_budget.py`

**Interfaces:**

- Consumes: `admit_step_attempt(...) -> int`.
- Produces: `TraceEntry.step_number: int`.
- Produces: `InterruptRequest.step_number: int`.

- [ ] **Step 1: Add failing sync behavior tests**

Test NodeUse, condition, foreach controller/body, subgraph entry/return,
interrupt/resume, explicit End, legacy `END`, handler failure, handled `error`
outcome, a closed cycle, an exiting loop, and denial without handler invocation.
Assert trace numbers rather than inferring counts from trace length.

- [ ] **Step 2: Verify the focused tests fail before dispatch is counted**

Run: `uv run pytest tests/core/test_run_step_budget.py -q`

- [ ] **Step 3: Admit after resolving the selected step and before dispatch**

Call `admit_step_attempt()` exactly once in the non-batched paths of
`step_workflow()` and `step_workflow_async()`. Make `append_trace()` fail closed
when the named frame has no assigned number and copy that number into every
trace produced during the dispatch. Store the interrupt activation's number on
`InterruptRequest`; its resume-completion trace reuses that value and does not
admit another attempt.

- [ ] **Step 4: Verify sync semantics and commit**

Run:

```text
uv run pytest tests/core/test_run_step_budget.py tests/core/test_interrupts.py
uv run pytest tests/core/test_subgraphs.py
uv run pytest tests/core/test_foreach_back_edges.py -q
```

Commit: `feat: enforce step budget during sync dispatch`

### Task 3: Deterministic async batch reservation

**Files:**

- Modify: `src/wf_core/runtime/step.py`
- Modify: `src/wf_core/runtime/limits.py`
- Test: `tests/core/test_run_step_budget_async.py`
- Test: `tests/core/test_foreach_concurrent.py`

**Interfaces:**

- Consumes: `remaining_step_attempts(run) -> int`.
- Consumes: `admit_step_attempt(...) -> int`.
- Produces: bounded `_claim_matching_async_item_frames(..., limit: int)`.

- [ ] **Step 1: Write failing async reservation tests**

Use handlers gated by `asyncio.Event` to prove that a three-unit remainder
starts only the first three eligible frames, assigns numbers in queue order,
keeps reservations after a handler failure, settles siblings before raising,
and discards later sibling state/trace commits after the first unhandled result
in reservation order.

- [ ] **Step 2: Verify the tests fail because batching claims every sibling**

Run: `uv run pytest tests/core/test_run_step_budget_async.py -q`

- [ ] **Step 3: Bound claims and reserve before creating handler tasks**

Before `_step_async_foreach_item_batch()` creates any coroutine, require one
unit for `first_frame`, claim at most `remaining - 1` matching frames, then call
`admit_step_attempt()` for the resulting ordered frame list. Do not launch any
task until every selected frame has its number.

- [ ] **Step 4: Verify async and parity suites and commit**

Run:

```text
uv run pytest tests/core/test_run_step_budget_async.py
uv run pytest tests/core/test_foreach_concurrent.py
uv run pytest tests/core/test_run_step_budget.py -q
```

Commit: `feat: reserve async workflow step attempts`

### Task 4: Stopped-run migration and inspection

**Files:**

- Modify: `src/wf_api/run_lifecycle.py`
- Modify: `src/wf_api/runs.py`
- Modify: `src/wf_api/models/runs.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/operation_context.py`
- Modify: `src/wf_server/context.py`
- Modify: `src/wf_mcp/broker/service/workflow_runtime.py`
- Test: `tests/wf_api/test_runs.py`
- Test: `tests/wf_api/test_run_lifecycle.py`

**Interfaces:**

- Consumes: `load_run_state_with_upgrade(...)`.
- Produces: optional `max_steps` on run creation only.
- Produces: `max_steps`, `steps_executed`, and `steps_remaining` in run results.

- [ ] **Step 1: Write failing API and migration tests**

Pin requested/effective limit inspection, interrupted resume preserving the
counter, resume accepting no replacement, and a v1 interrupted checkpoint being
rewritten as v2 before runtime dispatch. Make the fake runtime assert it has not
been called until the upgraded checkpoint exists.

- [ ] **Step 2: Verify the API tests fail on the missing fields**

Run:

```text
uv run pytest tests/wf_api/test_runs.py tests/wf_api/test_run_lifecycle.py -q
```

- [ ] **Step 3: Thread limits through creation and project inspection fields**

`WorkflowRunApi.run_deployment(..., max_steps: int | None = None)` constructs
`RunLimits(max_steps=max_steps)` when supplied and otherwise uses the default.
The runtime operation-context protocol accepts `limits: RunLimits | None` and
passes it to the core async executor. `_run_payload()` always includes:

```python
"max_steps": run.limits.max_steps,
"steps_executed": run.steps_executed,
"steps_remaining": run.steps_remaining,
```

- [ ] **Step 4: Persist a v1 upgrade before resume dispatch**

In `restore_interrupted_run()`, load the raw latest checkpoint with the upgrade
flag. If true, call `persist_stopped_run()` with the same run id and pinned
environment, producing a v2 interrupted checkpoint before returning the run to
the caller. Ordinary inspection may decode v1 prospectively without mutation.

- [ ] **Step 5: Verify API behavior and commit**

Run:

```text
uv run pytest tests/wf_api/test_runs.py tests/wf_api/test_run_lifecycle.py
uv run pytest tests/wf_api/test_resume_concurrency.py -q
```

Commit: `feat: persist and inspect run step budgets`

### Task 5: Python client, HTTP transport, and CLI

**Files:**

- Modify: `src/wf_client/protocols.py`
- Modify: `src/wf_client/_http_port.py`
- Modify: `src/wf_client/deployments.py`
- Modify: `src/wf_client/runs.py`
- Modify: `src/wf_client/codec.py`
- Modify: `src/wf_transport_rpc_http/methods/runs.py`
- Modify: `src/wf_transport_rpc_http/client/runs.py`
- Modify: `src/wf_cli/commands/runs.py`
- Test: `tests/wf_client/test_deployments.py`
- Test: `tests/wf_client/test_runs.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_cli/test_app.py`

**Interfaces:**

- Produces: `Deployment.run(input, *, max_steps: int | None = None) -> Run`.
- Produces: immutable client `Run.max_steps`, `.steps_executed`, and
  `.steps_remaining`.
- Produces: CLI `wf run start --max-steps INTEGER`.

- [ ] **Step 1: Write failing round-trip and client reconstruction tests**

Assert the request includes `max_steps` only when supplied; the response
decoder requires all three inspection fields; refresh/resume preserve them;
and CLI rejects zero before making an API request.

- [ ] **Step 2: Verify transport/client tests fail**

Run:

```text
uv run pytest tests/wf_client/test_deployments.py tests/wf_client/test_runs.py
uv run pytest tests/wf_transport_rpc_http/test_client.py
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_cli/test_app.py -q
```

- [ ] **Step 3: Thread the optional creation value and reconstruct results**

Keep `max_steps` off resume signatures. Validate the CLI option with Typer
`min=1`; server-side `RunLimits` remains authoritative for non-CLI callers.

- [ ] **Step 4: Regenerate contracts, verify, and commit**

Run:

```text
uv run python -m wf_contract_manifest write
pnpm --dir web --filter @lda/workflow-rpc contract:write
uv run pytest tests/wf_contract_manifest tests/wf_transport_rpc_http
uv run pytest tests/wf_client tests/wf_cli/test_app.py -q
pnpm --dir web --filter @lda/workflow-rpc contract:check
```

Commit: `feat: expose run step budgets to clients`

### Task 6: Documentation and final verification

**Files:**

- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Move after completion:
  `docs/superpowers/plans/2026-09-05-run-step-budget.md` to
  `docs/historical/superpowers/plans/2026-09-05-run-step-budget.md`

**Interfaces:** None.

- [ ] **Step 1: Document creation, inspection, exhaustion, and resume**

Show `Deployment.run(..., max_steps=50_000)`, `wf run start --max-steps`, the
three inspection fields, and that resume cannot reset the budget. Remove the
step-budget item from the active roadmap and leave runtime identity resolution
as the next fork/gather prerequisite.

- [ ] **Step 2: Run focused and full verification**

Run:

```text
uv run pytest tests/core/test_run_step_budget.py
uv run pytest tests/core/test_run_step_budget_async.py
uv run pytest tests/wf_api tests/wf_client
uv run pytest tests/wf_transport_rpc_http tests/wf_cli -q
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
pnpm --dir web test
pnpm --dir web typecheck
```

- [ ] **Step 3: Retire the completed plan and commit**

Commit: `docs: complete run step budget slice`

## Self-Review

- Spec coverage: model, positive validation, run-wide counting, every current
  step kind, async reservations, trace identity, v1 migration, stopped-run
  persistence, API/client/CLI inspection, and non-goals each map to a task.
- Deliberate exclusion: per-step durable admission checkpoints were removed
  from the spec because the current engine persists only externally stopped
  runs; no task quietly invents a write-ahead runtime.
- Placeholder scan: no deferred implementation placeholder remains.
- Type consistency: `max_steps` is creation-only; `RunLimits` is core policy;
  `steps_remaining` is computed; frame step numbers drive trace projection.
