# Scheduler Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the internal scheduler foundation needed for future parallel foreach and native subgraphs while preserving current serial workflow behavior.

**Architecture:** `RunState.frames` remains the source of frame lifecycle state, and a new serialized `ready_frame_ids` queue defines deterministic scheduling order. A new internal `wf_core.runtime.scheduler` module owns frame creation, enqueue/select, block/wake, and no-ready-frame resolution. Existing sync and async engines both use scheduler selection before `prepare_step`; node execution stays split between sync and async paths.

**Tech Stack:** Python 3.14, dataclasses, pytest, Pydantic workflow models, existing `wf_core` runtime modules.

---

## Files

- Modify: `src/wf_core/run_state.py`
  - Add `FrameStatus.BLOCKED`.
  - Add `RunState.ready_frame_ids: list[str]`.
- Create: `src/wf_core/runtime/scheduler.py`
  - Internal scheduler helpers and typed block/foreach metadata helpers.
- Modify: `src/wf_core/runtime/ops/runs.py`
  - Initialize root frame and ready queue.
- Modify: `src/wf_core/runtime/ops/flow.py`
  - Re-enqueue normal frame advances and complete terminal frames through scheduler helpers.
- Modify: `src/wf_core/runtime/ops/foreach.py`
  - Use typed foreach metadata, explicit child frame creation, block parent, enqueue child.
- Modify: `src/wf_core/runtime/ops/frames.py`
  - Keep context helpers; demote stack-collapse usage or leave compatibility wrappers that call scheduler helpers.
- Modify: `src/wf_core/runtime/preparation.py`
  - Stop relying on `collapse_completed_frames()` for selection.
  - Resume interrupt by waking/enqueueing the resumed frame.
- Modify: `src/wf_core/runtime/engine.py`
  - Use scheduler loop for sync and async resume.
- Modify: `src/wf_core/runtime/step.py`
  - Keep `prepare_step()` boundary; ensure selected frame is already chosen by scheduler.
- Test: `tests/core/test_scheduler.py`
  - Unit tests for scheduler helpers.
- Test: `tests/core/test_run_state.py`
  - Add serialization/additive field checks if needed.
- Test: existing foreach/interrupt tests under `tests/authoring/` and `tests/core/`
  - Add focused regressions where the behavior is not already covered.

---

### Task 1: Add RunState Scheduler Fields

**Files:**
- Modify: `src/wf_core/run_state.py`
- Test: `tests/core/test_scheduler.py`

- [ ] **Step 1: Write failing tests for ready queue serialization and frame status**

Create `tests/core/test_scheduler.py` with:

```python
from __future__ import annotations

from wf_core.run_state import FrameStatus, RunState, RunStatus


def test_run_state_serializes_ready_frame_ids() -> None:
    run = RunState(
        workflow_name="demo",
        status=RunStatus.PENDING,
        workflow_input={},
        state={},
        ready_frame_ids=["root"],
    )

    dumped = run.to_dict()

    assert dumped["ready_frame_ids"] == ["root"]


def test_frame_status_has_blocked() -> None:
    assert FrameStatus.BLOCKED == "blocked"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/core/test_scheduler.py -q
```

Expected: fails because `ready_frame_ids` and `FrameStatus.BLOCKED` do not exist.

- [ ] **Step 3: Implement minimal state fields**

In `src/wf_core/run_state.py`:

```python
class FrameStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
```

Add to `RunState`:

```python
ready_frame_ids: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Verify**

Run:

```bash
uv run pytest tests/core/test_scheduler.py -q
```

Expected: pass.

---

### Task 2: Create Internal Scheduler Helpers

**Files:**
- Create: `src/wf_core/runtime/scheduler.py`
- Test: `tests/core/test_scheduler.py`

- [ ] **Step 1: Add failing scheduler helper tests**

Append tests:

```python
import pytest

from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import ExecutionFrame
from wf_core.runtime.scheduler import (
    add_frame,
    block_frame_on_children,
    enqueue_frame,
    select_next_frame,
    wake_frame,
)


def _run() -> RunState:
    return RunState(
        workflow_name="demo",
        status=RunStatus.RUNNING,
        workflow_input={},
        state={},
    )


def test_add_frame_rejects_duplicate_frame_ids() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="root", kind="root", node_id="a"))

    with pytest.raises(WorkflowExecutionError, match="duplicate frame id"):
        add_frame(run, ExecutionFrame(id="root", kind="root", node_id="a"))


def test_enqueue_is_unique_and_priority_moves_to_front() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="a", kind="root", node_id="a"))
    add_frame(run, ExecutionFrame(id="b", kind="root", node_id="b"))

    enqueue_frame(run, "a")
    enqueue_frame(run, "b")
    enqueue_frame(run, "a")
    enqueue_frame(run, "a", front=True)

    assert run.ready_frame_ids == ["a", "b"]


def test_select_next_frame_pops_and_marks_running() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="root", kind="root", node_id="a"))
    enqueue_frame(run, "root")

    frame = select_next_frame(run)

    assert frame is not None
    assert frame.id == "root"
    assert frame.status == FrameStatus.RUNNING
    assert run.ready_frame_ids == []
    assert run.current_frame_id == "root"
    assert run.current_node_id == "a"


def test_blocked_frame_is_not_selectable_until_woken() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="parent", kind="root", node_id="foreach"))
    block_frame_on_children(run, "parent", ("child",))

    assert select_next_frame(run) is None

    wake_frame(run, "parent")
    selected = select_next_frame(run)

    assert selected is not None
    assert selected.id == "parent"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/core/test_scheduler.py -q
```

Expected: fails because `wf_core.runtime.scheduler` does not exist.

- [ ] **Step 3: Implement scheduler helpers**

Create `src/wf_core/runtime/scheduler.py`:

```python
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from wf_core.errors import WorkflowExecutionError
from wf_core.run_state import ExecutionFrame, FrameStatus, RunState, RunStatus


@dataclass(slots=True, frozen=True)
class BlockedOnChildren:
    """Typed block reason for frames waiting on child frame completion."""

    child_frame_ids: tuple[str, ...]

    @classmethod
    def from_frame(cls, frame: ExecutionFrame) -> "BlockedOnChildren | None":
        raw = frame.metadata.get("blocked_on")
        if raw is None:
            return None
        if not isinstance(raw, dict) or raw.get("type") != "child_frames":
            raise WorkflowExecutionError(
                f"malformed block reason for frame {frame.id!r}"
            )
        raw_ids = raw.get("frame_ids")
        if not isinstance(raw_ids, list) or not all(
            isinstance(item, str) for item in raw_ids
        ):
            raise WorkflowExecutionError(
                f"malformed child frame ids for frame {frame.id!r}"
            )
        return cls(tuple(raw_ids))

    def to_metadata(self) -> dict[str, object]:
        return {"type": "child_frames", "frame_ids": list(self.child_frame_ids)}


def add_frame(run: RunState, frame: ExecutionFrame, *, ready: bool = False) -> None:
    """Add a frame once; frame id reuse is always a runtime invariant error."""
    if frame.id in run.frames:
        raise WorkflowExecutionError(f"duplicate frame id {frame.id!r}")
    run.frames[frame.id] = frame
    if ready:
        enqueue_frame(run, frame.id)


def enqueue_frame(run: RunState, frame_id: str, *, front: bool = False) -> None:
    """Put a pending frame in the ready queue without creating duplicates."""
    frame = _frame(run, frame_id)
    if frame.status != FrameStatus.PENDING:
        raise WorkflowExecutionError(
            f"cannot enqueue frame {frame_id!r} with status {frame.status!s}"
        )
    if frame_id in run.ready_frame_ids:
        run.ready_frame_ids.remove(frame_id)
    if front:
        run.ready_frame_ids.insert(0, frame_id)
    else:
        run.ready_frame_ids.append(frame_id)


def select_next_frame(run: RunState) -> ExecutionFrame | None:
    """Select the next ready frame and expose it through compatibility cursor fields."""
    while run.ready_frame_ids:
        frame_id = run.ready_frame_ids.pop(0)
        frame = _frame(run, frame_id)
        if frame.status != FrameStatus.PENDING:
            raise WorkflowExecutionError(
                f"ready frame {frame_id!r} has status {frame.status!s}"
            )
        frame.status = FrameStatus.RUNNING
        run.current_frame_id = frame.id
        run.sync_from_current_frame()
        return frame
    return None


def mark_frame_pending(run: RunState, frame_id: str, *, front: bool = False) -> None:
    """Mark a live frame pending and enqueue it for future execution."""
    frame = _frame(run, frame_id)
    frame.status = FrameStatus.PENDING
    enqueue_frame(run, frame_id, front=front)


def block_frame_on_children(
    run: RunState, frame_id: str, child_frame_ids: Sequence[str]
) -> None:
    """Mark a frame blocked on child completion and remove it from the ready queue."""
    frame = _frame(run, frame_id)
    run.ready_frame_ids = [item for item in run.ready_frame_ids if item != frame_id]
    frame.status = FrameStatus.BLOCKED
    frame.metadata["blocked_on"] = BlockedOnChildren(
        tuple(child_frame_ids)
    ).to_metadata()


def wake_frame(run: RunState, frame_id: str, *, front: bool = False) -> None:
    """Wake a blocked or interrupted frame and enqueue it as pending."""
    frame = _frame(run, frame_id)
    if frame.status not in {FrameStatus.BLOCKED, FrameStatus.INTERRUPTED}:
        raise WorkflowExecutionError(
            f"cannot wake frame {frame_id!r} with status {frame.status!s}"
        )
    frame.status = FrameStatus.PENDING
    frame.metadata.pop("blocked_on", None)
    enqueue_frame(run, frame_id, front=front)


def resolve_no_ready_frames(run: RunState) -> RunStatus:
    """Classify an empty ready queue into a terminal or blocked run state."""
    if run.status == RunStatus.INTERRUPTED:
        return RunStatus.INTERRUPTED
    if any(frame.status == FrameStatus.FAILED for frame in run.frames.values()):
        return RunStatus.FAILED
    if run.frames and all(
        frame.status == FrameStatus.COMPLETED for frame in run.frames.values()
    ):
        return RunStatus.COMPLETED
    if any(frame.status == FrameStatus.BLOCKED for frame in run.frames.values()):
        raise WorkflowExecutionError("run has no ready frames and is deadlocked")
    raise WorkflowExecutionError("run has no ready frames")


def _frame(run: RunState, frame_id: str) -> ExecutionFrame:
    frame = run.frames.get(frame_id)
    if frame is None:
        raise WorkflowExecutionError(f"unknown frame id {frame_id!r}")
    return frame
```

- [ ] **Step 4: Verify helper tests**

Run:

```bash
uv run pytest tests/core/test_scheduler.py -q
```

Expected: pass.

---

### Task 3: Initialize Root Through Scheduler

**Files:**
- Modify: `src/wf_core/runtime/ops/runs.py`
- Test: `tests/core/test_scheduler.py`

- [ ] **Step 1: Add root initialization test**

Append:

```python
from wf_core import SchemaRef, StateSchema, Workflow
from wf_core.runtime.ops.runs import create_run_state


def test_create_run_state_queues_root_frame() -> None:
    workflow = Workflow(
        name="demo",
        input_schema=SchemaRef(properties={}),
        state_schema=StateSchema(fields={}),
        output_schema=SchemaRef(properties={}),
        node_defs=[],
        start="first",
        nodes=[],
        edges=[],
    )

    run = create_run_state(workflow, {})

    assert run.current_frame_id == "root"
    assert run.current_node_id == "first"
    assert run.ready_frame_ids == ["root"]
    assert run.frames["root"].status == FrameStatus.PENDING
```

- [ ] **Step 2: Run failing test if needed**

Run:

```bash
uv run pytest tests/core/test_scheduler.py::test_create_run_state_queues_root_frame -q
```

Expected: fails until root ready queue initialization exists.

- [ ] **Step 3: Update run creation**

In `src/wf_core/runtime/ops/runs.py`, create the root frame through `add_frame(..., ready=True)` and set compatibility cursor fields.

- [ ] **Step 4: Verify**

Run:

```bash
uv run pytest tests/core/test_scheduler.py -q
```

Expected: pass.

---

### Task 4: Re-Enqueue Normal Frame Advances

**Files:**
- Modify: `src/wf_core/runtime/ops/flow.py`
- Modify: `src/wf_core/runtime/step.py`
- Test: `tests/core/test_scheduler.py`

- [ ] **Step 1: Add normal advance test**

Append:

```python
from wf_core.runtime.ops.flow import advance_frame


def test_advance_frame_requeues_non_terminal_frame() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="root", kind="root", node_id="a"))
    run.current_frame_id = "root"
    run.sync_from_current_frame()
    frame = run.current_frame()
    frame.status = FrameStatus.RUNNING

    advance_frame(run, frame, outcome="ok", next_node_id="b")

    assert frame.status == FrameStatus.PENDING
    assert run.ready_frame_ids == ["root"]
    assert run.current_node_id == "b"
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/core/test_scheduler.py::test_advance_frame_requeues_non_terminal_frame -q
```

Expected: fails because `advance_frame` currently leaves non-terminal status as running and does not enqueue.

- [ ] **Step 3: Update `advance_frame`**

In `src/wf_core/runtime/ops/flow.py`, after setting node state:

```python
from wf_core.runtime.scheduler import mark_frame_pending
```

Use:

```python
if next_node_id == END:
    frame.status = FrameStatus.COMPLETED
    frame.finished_at_node_id = END
else:
    frame.finished_at_node_id = None
    mark_frame_pending(run, frame.id)
run.sync_from_current_frame()
```

- [ ] **Step 4: Verify focused tests**

Run:

```bash
uv run pytest tests/core/test_scheduler.py -q
```

Expected: pass.

---

### Task 5: Migrate Engine Loops To Scheduler Selection

**Files:**
- Modify: `src/wf_core/runtime/engine.py`
- Modify: `src/wf_core/runtime/preparation.py`
- Modify: `src/wf_core/runtime/step.py`
- Test: existing workflow tests

- [ ] **Step 1: Add regression tests if existing coverage is insufficient**

Before adding new tests, run:

```bash
uv run pytest tests/authoring/test_demo_workflow.py tests/core/test_scheduler.py -q
```

Expected before implementation: likely failures after Task 4 until engine selection is updated.

- [ ] **Step 2: Update engine loops**

Change `resume_workflow` and `resume_workflow_async` to:

```python
while True:
    frame = select_next_frame(run)
    if frame is None:
        status = resolve_no_ready_frames(run)
        if status == RunStatus.COMPLETED:
            break
        return run
    step_workflow(...)
    if run.status == RunStatus.INTERRUPTED:
        return run
```

Use the same selection flow in the async loop before `await step_workflow_async(...)`.

- [ ] **Step 3: Remove stack collapse from step preparation**

In `prepare_step`, remove `collapse_completed_frames(run)` and keep it focused on resolving the selected frame’s node. It should still return `None` for interrupted/end states.

- [ ] **Step 4: Verify serial workflows**

Run:

```bash
uv run pytest tests/authoring/test_demo_workflow.py tests/core/test_scheduler.py -q
```

Expected: pass.

---

### Task 6: Make Serial Foreach Use Block/Wake

**Files:**
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Modify: `src/wf_core/runtime/ops/frames.py`
- Create or extend: `tests/core/test_scheduler.py`
- Test: `tests/authoring/test_demo_workflow.py`

- [ ] **Step 1: Add foreach block/wake regression test**

Add a focused test using an existing demo workflow or a small builder workflow that asserts:

```python
foreach_entries = [entry for entry in run.trace if entry.step_type == "foreach"]
assert foreach_entries
assert all(frame.status != FrameStatus.BLOCKED for frame in run.frames.values())
assert any(frame.kind == "foreach_iteration" for frame in run.frames.values())
```

Then add a lower-level test if needed for child completion waking parent:

```python
def test_child_completion_wakes_blocked_parent() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="parent", kind="root", node_id="foreach"))
    add_frame(
        run,
        ExecutionFrame(
            id="child",
            kind="foreach_iteration",
            node_id="__end__",
            parent_frame_id="parent",
        ),
    )
    block_frame_on_children(run, "parent", ("child",))
    run.frames["child"].status = FrameStatus.COMPLETED

    wake_parent_if_children_complete(run, "child")

    assert run.frames["parent"].status == FrameStatus.PENDING
    assert run.ready_frame_ids == ["parent"]
```

- [ ] **Step 2: Implement typed foreach metadata**

In `src/wf_core/runtime/scheduler.py` or a small sibling module if the file grows too large:

```python
@dataclass(slots=True, frozen=True)
class ForeachIterationMetadata:
    foreach_node_id: str
    loop_index: int
    loop_item: object
    loop_alias: str

    @classmethod
    def from_frame(cls, frame: ExecutionFrame) -> "ForeachIterationMetadata | None":
        if frame.kind != "foreach_iteration":
            return None
        ...

    def to_metadata(self) -> dict[str, object]:
        ...
```

Wrong frame kind returns `None`; malformed foreach iteration metadata raises `WorkflowExecutionError`.

- [ ] **Step 3: Implement parent wake helper**

Add:

```python
def wake_parent_if_children_complete(run: RunState, child_frame_id: str) -> None:
    child = _frame(run, child_frame_id)
    parent_id = child.parent_frame_id
    if parent_id is None:
        return
    parent = _frame(run, parent_id)
    block = BlockedOnChildren.from_frame(parent)
    if block is None:
        return
    if all(run.frames[item].status == FrameStatus.COMPLETED for item in block.child_frame_ids):
        wake_frame(run, parent_id)
```

- [ ] **Step 4: Update foreach child creation**

In `step_foreach`, replace direct `run.frames[child_id] = ...` with `add_frame(..., ready=True)`, then call `block_frame_on_children(run, frame.id, (child_id,))`. Parent should not stay in ready queue while child runs.

- [ ] **Step 5: Verify foreach behavior**

Run:

```bash
uv run pytest tests/authoring/test_demo_workflow.py tests/core/test_scheduler.py -q
```

Expected: pass.

---

### Task 7: Resume Interrupt Through Ready Queue

**Files:**
- Modify: `src/wf_core/runtime/preparation.py`
- Modify: `src/wf_core/runtime/ops/interrupts.py`
- Test: existing interrupt tests or new focused tests

- [ ] **Step 1: Find existing interrupt tests**

Run:

```bash
rg -n "interrupt|resume_payload|resume_outcome" tests src -g '*.py'
```

- [ ] **Step 2: Add/adjust test for resume priority**

Add a focused test that creates an interrupted frame plus another ready frame and verifies resume places interrupted frame first:

```python
def test_resume_wakes_interrupted_frame_at_front() -> None:
    run = _run()
    add_frame(run, ExecutionFrame(id="waiting", kind="root", node_id="ask"))
    add_frame(run, ExecutionFrame(id="sibling", kind="root", node_id="work"))
    run.frames["waiting"].status = FrameStatus.INTERRUPTED
    run.frames["sibling"].status = FrameStatus.PENDING
    run.ready_frame_ids = ["sibling"]

    wake_frame(run, "waiting", front=True)

    assert run.ready_frame_ids == ["waiting", "sibling"]
```

- [ ] **Step 3: Update resume code**

After `resume_interrupt(...)`, wake/enqueue the resumed frame at the front. Keep one outstanding `run.interrupt`.

- [ ] **Step 4: Verify interrupt tests**

Run focused interrupt tests found in Step 1 plus:

```bash
uv run pytest tests/core/test_scheduler.py -q
```

Expected: pass.

---

### Task 8: Full Verification

**Files:**
- Potentially update docs if implementation differs from ADR.

- [ ] **Step 1: Run focused workflow tests**

Run:

```bash
uv run pytest tests/core/test_scheduler.py tests/authoring/test_demo_workflow.py -q
```

Expected: pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: pass, except known environment-only skips.

- [ ] **Step 3: Run lint/type checks**

Run:

```bash
uvx ruff check src tests
uv run basedpyright --level error
```

Expected: ruff passes and basedpyright reports 0 errors.

- [ ] **Step 4: Review docs**

Check:

```bash
git diff -- CONTEXT.md docs/adr/0001-scheduler-foundation-before-parallel-foreach.md docs/current_roadmap.md
```

Expected: docs remain aligned with implemented first-pass behavior.

---

## Self-Review

- Spec coverage: ADR decisions are covered by tasks for `BLOCKED`, ready queue, scheduler helpers, sync/async engine migration, serial foreach block/wake, interrupt resume priority, and verification.
- Intentional gaps: no `foreach(mode="parallel")`, no `ParallelForeachPolicy`, no lineage patches, no BarrierNode, and no public scheduler exports.
- Type consistency: helper names are stable across tasks: `add_frame`, `enqueue_frame`, `select_next_frame`, `mark_frame_pending`, `block_frame_on_children`, `wake_frame`, `wake_parent_if_children_complete`, and `resolve_no_ready_frames`.
