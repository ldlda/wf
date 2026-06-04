# Concurrent Foreach V1 Sync Fail-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable `foreach(mode="concurrent")` in the sync runtime for fail-only item policy, using deterministic frame interleaving and barrier-buffered state commits.

**Architecture:** The foreach parent owns admission and refill. Item frames execute through the existing scheduler one step at a time, but their node output writes are buffered as item-local `StatePatch` records instead of mutating `RunState.state`. When all items succeed, the parent barrier commits item patches in item index order and emits `done`.

**Important V1 limitation:** this slice intentionally supports only `loop -> one node -> END` concurrent item bodies. A no-op item-state overlay seam exists at `wf_core.runtime.ops.overlays.state_view_for_frame`, but it still returns parent state. Full multi-step concurrent item bodies require the next slice to make that overlay non-noop so later nodes in one item can read earlier item-local writes.

**Tech Stack:** Python 3.14, dataclasses, Pydantic v2, pytest, `wf_core.runtime.scheduler`, `wf_core.runtime.foreach_state`, `wf_core.runtime.ops.state`.

---

## Files

- Modify: `src/wf_core/runtime/foreach_state.py`
  - Add active/outstanding helpers and pending result mutation helpers.
- Modify: `src/wf_core/runtime/ops/foreach.py`
  - Split serial and concurrent foreach execution.
  - Admit multiple child frames for concurrent mode.
  - Finish parent when all items succeed.
- Modify: `src/wf_core/runtime/step.py`
  - Pass reducer definitions through to foreach barrier commit.
- Modify: `src/wf_core/runtime/ops/state.py`
  - Add a barrier patch helper that reapplies reducers in deterministic item order.
- Modify: `src/wf_core/runtime/ops/nodes.py`
  - Buffer output patches for concurrent foreach item frames.
- Add: `src/wf_core/runtime/ops/overlays.py`
  - Add the no-op state overlay seam for the next item-local overlay slice.
- Modify: `src/wf_core/runtime/scheduler.py`
  - Add a parent wake helper that can wake a foreach parent when any child finishes, not only when all child frames in one block reason are complete.
- Test: `tests/core/test_concurrent_foreach.py`
  - New focused runtime tests.

---

### Task 1: Add Failing Sync Concurrent Foreach Tests

**Files:**

- Create: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Add the test file**

Create `tests/core/test_concurrent_foreach.py`:

```python
from __future__ import annotations

from typing import Any

import pytest

from wf_core import (
    END,
    Edge,
    ForeachNode,
    NodeDef,
    NodeUse,
    SchemaRef,
    StateSchema,
    Workflow,
    WorkflowExecutionError,
    execute_workflow,
)
from wf_core.models.reducers import ReducerRef
from wf_core.models.schemas import StateField


def test_sync_concurrent_foreach_interleaves_items_and_commits_at_barrier() -> None:
    workflow = _workflow(
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
            }
        ),
        foreach=ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": "state.items",
                "as": "item",
                "mode": "concurrent",
                "concurrent": {"max_active": 2, "max_outstanding": 2},
            }
        ),
    )

    run = execute_workflow(
        workflow,
        {"items": ["a", "b", "c"]},
        {"record": lambda payload, _ctx: {"outcome": "ok", "output": payload}},
    )

    assert run.output["seen"] == ["a", "b", "c"]
    assert run.state["seen"] == ["a", "b", "c"]
    foreach_entries = [entry for entry in run.trace if entry.step_type == "foreach"]
    assert foreach_entries[-1].outcome == "done"
    assert foreach_entries[-1].state_changes["state.seen"] == ["a", "b", "c"]


def test_sync_concurrent_foreach_respects_max_active_by_refill_trace() -> None:
    workflow = _workflow(
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(type="array", reducer=ReducerRef(name="wf.std.append")),
            }
        ),
        foreach=ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": "state.items",
                "as": "item",
                "mode": "concurrent",
                "concurrent": {"max_active": 2, "max_outstanding": 2},
            }
        ),
    )

    run = execute_workflow(
        workflow,
        {"items": ["a", "b", "c", "d"]},
        {"record": lambda payload, _ctx: {"outcome": "ok", "output": payload}},
    )

    loop_entries = [
        entry for entry in run.trace if entry.step_type == "foreach" and entry.outcome == "loop"
    ]
    assert loop_entries[0].resolved_input["active_count"] == 0
    assert loop_entries[1].resolved_input["active_count"] == 1
    assert all(entry.resolved_input["active_count"] < 2 for entry in loop_entries)


def test_sync_concurrent_foreach_rejects_non_fail_item_policy_for_now() -> None:
    workflow = _workflow(
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(type="array", reducer=ReducerRef(name="wf.std.append")),
                "errors": StateField(type="array"),
            }
        ),
        foreach=ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": "state.items",
                "as": "item",
                "mode": "concurrent",
                "concurrent": {"max_active": 2, "max_outstanding": 2},
                "item_error": {"action": "collect", "collect_to": "state.errors"},
            }
        ),
    )

    with pytest.raises(WorkflowExecutionError, match="only supports item_error.action='fail'"):
        execute_workflow(
            workflow,
            {"items": ["a"]},
            {"record": lambda payload, _ctx: {"outcome": "ok", "output": payload}},
        )


def test_sync_concurrent_foreach_fails_run_on_item_runtime_error() -> None:
    workflow = _workflow(
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(type="array", reducer=ReducerRef(name="wf.std.append")),
            }
        ),
        foreach=ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": "state.items",
                "as": "item",
                "mode": "concurrent",
                "concurrent": {"max_active": 2, "max_outstanding": 2},
            }
        ),
    )

    def fail_on_b(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        if payload["value"] == "b":
            raise ValueError("bad item")
        return {"outcome": "ok", "output": payload}

    with pytest.raises(WorkflowExecutionError, match="bad item"):
        execute_workflow(workflow, {"items": ["a", "b", "c"]}, {"record": fail_on_b})


def _workflow(*, state_schema: StateSchema, foreach: ForeachNode) -> Workflow:
    return Workflow(
        name="concurrent_foreach_v1",
        input_schema=SchemaRef(
            type="object",
            properties={"items": {"type": "array"}},
        ),
        state_schema=state_schema,
        output_schema=SchemaRef(
            type="object",
            properties={"seen": {"type": "array"}},
        ),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(
                    type="object",
                    properties={"value": {}, "seen": {}},
                    required=["value", "seen"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"value": {}, "seen": {}},
                    required=["seen"],
                ),
                outcomes=["ok"],
            )
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "record",
                    "type": "node",
                    "node": "record",
                    "input": [
                        {"target": "value", "path": "context.item"},
                        {"target": "seen", "path": "context.item"},
                    ],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "record"}),
            Edge.model_validate({"from": "record", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
```

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py -q
```

Expected:

```text
FAILED with message containing "concurrent foreach execution is not implemented yet"
```

---

### Task 2: Add Barrier Admission Helpers

**Files:**

- Modify: `src/wf_core/runtime/foreach_state.py`
- Test: `tests/core/test_foreach_barrier_state.py`

- [ ] **Step 1: Add barrier helper tests**

Append to `tests/core/test_foreach_barrier_state.py`:

```python
def test_foreach_barrier_tracks_active_and_outstanding_children() -> None:
    barrier = ForeachBarrierState()

    barrier.start_child("child-0")
    barrier.start_child("child-1")
    barrier.finish_child("child-0")

    assert barrier.active_frame_ids == ("child-1",)
    assert barrier.outstanding_frame_ids == ("child-1",)


def test_foreach_barrier_rejects_duplicate_child_start() -> None:
    barrier = ForeachBarrierState()
    barrier.start_child("child-0")

    with pytest.raises(WorkflowExecutionError, match="already active"):
        barrier.start_child("child-0")
```

- [ ] **Step 2: Run helper tests and verify failure**

Run:

```bash
uv run pytest tests/core/test_foreach_barrier_state.py -q
```

Expected:

```text
FAILED with AttributeError: 'ForeachBarrierState' object has no attribute 'start_child'
```

- [ ] **Step 3: Implement helper methods**

In `src/wf_core/runtime/foreach_state.py`, add methods to `ForeachBarrierState`:

```python
    def start_child(self, frame_id: str) -> None:
        """Record one admitted child frame as active and outstanding."""
        if frame_id in self.active_frame_ids or frame_id in self.outstanding_frame_ids:
            raise WorkflowExecutionError(f"foreach child frame {frame_id!r} already active")
        self.active_frame_ids = (*self.active_frame_ids, frame_id)
        self.outstanding_frame_ids = (*self.outstanding_frame_ids, frame_id)

    def finish_child(self, frame_id: str) -> None:
        """Record one child frame as no longer active or outstanding."""
        self.active_frame_ids = tuple(
            item for item in self.active_frame_ids if item != frame_id
        )
        self.outstanding_frame_ids = tuple(
            item for item in self.outstanding_frame_ids if item != frame_id
        )
```

- [ ] **Step 4: Verify helper tests**

Run:

```bash
uv run pytest tests/core/test_foreach_barrier_state.py -q
```

Expected: pass.

---

### Task 3: Wake Foreach Parent After Each Child Completion

**Files:**

- Modify: `src/wf_core/runtime/scheduler.py`
- Test: `tests/core/test_scheduler.py`

- [ ] **Step 1: Add a parent-wake test for any completed child**

Append to `tests/core/test_scheduler.py`:

```python
def test_wake_parent_when_child_finishes_for_refill() -> None:
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
    block_frame_on_children(run, "parent", ("child", "other"))
    run.frames["child"].status = FrameStatus.COMPLETED

    wake_parent_for_child_progress(run, "child")

    assert run.frames["parent"].status == FrameStatus.PENDING
    assert run.ready_frame_ids == ["parent"]
```

- [ ] **Step 2: Run scheduler test and verify failure**

Run:

```bash
uv run pytest tests/core/test_scheduler.py::test_wake_parent_when_child_finishes_for_refill -q
```

Expected:

```text
ImportError or NameError for wake_parent_for_child_progress
```

- [ ] **Step 3: Implement wake helper**

In `src/wf_core/runtime/scheduler.py`, add:

```python
def wake_parent_for_child_progress(run: RunState, child_frame_id: str) -> None:
    """Wake a blocked parent after one child finishes so it can refill slots."""
    child = _frame(run, child_frame_id)
    parent_id = child.parent_frame_id
    if parent_id is None:
        return
    parent = _frame(run, parent_id)
    if parent.status != FrameStatus.BLOCKED:
        return
    block = BlockedOnChildren.from_frame(parent)
    if block is None or child_frame_id not in block.child_frame_ids:
        return
    wake_frame(run, parent_id)
```

Keep `wake_parent_if_children_complete(...)` for serial foreach compatibility until all callers are migrated.

- [ ] **Step 4: Import helper in test**

Update `tests/core/test_scheduler.py` import list:

```python
from wf_core.runtime.scheduler import (
    add_frame,
    block_frame_on_children,
    enqueue_frame,
    resolve_no_ready_frames,
    select_next_frame,
    wake_frame,
    wake_parent_for_child_progress,
    wake_parent_if_children_complete,
)
```

- [ ] **Step 5: Verify scheduler tests**

Run:

```bash
uv run pytest tests/core/test_scheduler.py -q
```

Expected: pass.

---

### Task 4: Buffer Node Writes Inside Concurrent Foreach Item Frames

**Files:**

- Modify: `src/wf_core/runtime/ops/nodes.py`
- Modify: `src/wf_core/runtime/foreach_state.py`
- Test: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Add item frame patch helper**

In `src/wf_core/runtime/foreach_state.py`, add:

```python
def item_frame_owner(frame: ExecutionFrame) -> tuple[str, str, int] | None:
    """Return parent frame id, foreach node id, and item index for item frames."""
    if frame.kind != "foreach_iteration" or frame.parent_frame_id is None:
        return None
    metadata = ForeachIterationMetadata.from_frame(frame)
    if metadata is None:
        return None
    return frame.parent_frame_id, metadata.foreach_node_id, metadata.loop_index
```

Add the import at the top:

```python
from wf_core.runtime.scheduler import ForeachIterationMetadata
```

- [ ] **Step 2: Add pending result upsert helper**

In `ForeachBarrierState`, add:

```python
    def add_success_patch(self, *, index: int, frame_id: str, patch: StatePatch) -> None:
        """Buffer one successful item patch by item index."""
        self.pending_results[index] = PendingItemResult(
            index=index,
            frame_id=frame_id,
            status="succeeded",
            patch=patch,
        )
```

- [ ] **Step 3: Change node finalization to buffer patches for concurrent item frames**

In `src/wf_core/runtime/ops/nodes.py`, import:

```python
from wf_core.runtime.foreach_state import ForeachBarrierState, item_frame_owner
from wf_core.runtime.ops.state import build_output_patch, commit_state_patch
```

Replace the direct `apply_output_bindings(...)` call in `_finalize_node_execution(...)` with:

```python
    patch = build_output_patch(
        workflow,
        node.output,
        result.output,
        run.state,
        reducers=reducers,
    )
    owner = item_frame_owner(run.current_frame())
    if owner is None:
        state_changes = commit_state_patch(run.state, patch)
    else:
        parent_frame_id, foreach_node_id, item_index = owner
        parent_frame = run.frames[parent_frame_id]
        barrier = (
            ForeachBarrierState.from_frame(parent_frame, foreach_node_id)
            or ForeachBarrierState()
        )
        barrier.add_success_patch(
            index=item_index,
            frame_id=run.current_frame().id,
            patch=patch,
        )
        barrier.save_to_frame(parent_frame, foreach_node_id)
        state_changes = {}
```

Rationale: child traces should not claim committed state changes; the barrier trace will report committed changes later.

- [ ] **Step 4: Run focused tests and verify expected failures remain**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py tests/core/test_foreach_barrier_state.py -q
```

Expected:

- Barrier helper tests pass.
- Concurrent foreach runtime tests may still fail because parent admission/refill is not implemented yet.

---

### Task 5: Split Serial and Concurrent Foreach Runtime

**Files:**

- Modify: `src/wf_core/runtime/ops/foreach.py`
- Modify: `src/wf_core/runtime/step.py`
- Test: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Split the existing serial implementation**

In `src/wf_core/runtime/ops/foreach.py`, replace `step_foreach(...)` with this
dispatcher:

```python
def step_foreach(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    index: WorkflowIndex,
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> RunState:
    if step.mode == "serial":
        return _step_foreach_serial(workflow, run, step, index)
    return _step_foreach_concurrent(
        workflow,
        run,
        step,
        index,
        reducers=reducers,
    )
```

Move the current body into:

```python
def _step_foreach_serial(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    index: WorkflowIndex,
) -> RunState:
    if step.mode != "serial":
        raise WorkflowExecutionError("serial foreach helper received non-serial mode")

    frame = run.current_frame()
    barrier = ForeachBarrierState.from_frame(frame, step.id) or ForeachBarrierState()

    iterable = _resolve_foreach_iterable(run, frame, step)
    loop_index = barrier.next_index
    if loop_index >= len(iterable):
        outcome = "done"
        next_node_id = index.next_node_id(frame.node_id, outcome)
        append_step_result_trace(
            run,
            frame_id=frame.id,
            node_id=frame.node_id,
            step_type=step.type,
            next_node_id=next_node_id,
            result=StepExecutionResult(
                outcome=outcome,
                resolved_input={"count": len(iterable), "index": loop_index},
                output={},
                state_changes={},
            ),
        )
        advance_frame(run, frame, outcome=outcome, next_node_id=next_node_id)
        return run

    loop_start = index.next_node_id(frame.node_id, "loop")
    item = iterable[loop_index]
    barrier.next_index = loop_index + 1
    barrier.save_to_frame(frame, step.id)
    child_id = f"{frame.id}:{step.id}:{loop_index}"
    add_frame(
        run,
        ExecutionFrame(
            id=child_id,
            kind="foreach_iteration",
            node_id=loop_start,
            status=FrameStatus.PENDING,
            parent_frame_id=frame.id,
            metadata=ForeachIterationMetadata(
                foreach_node_id=step.id,
                loop_index=loop_index,
                loop_item=item,
                loop_alias=step.as_,
            ).to_metadata(),
        ),
        ready=True,
    )
    block_frame_on_children(run, frame.id, (child_id,))
    append_step_result_trace(
        run,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        next_node_id=loop_start,
        result=StepExecutionResult(
            outcome="loop",
            resolved_input={"item": item, "index": loop_index},
            output={},
            state_changes={},
        ),
    )
    run.sync_from_current_frame()
    return run
```

Import the reducer types:

```python
from collections.abc import Mapping
from wf_core.runtime.ops.merges import ReducerDefinition
```

- [ ] **Step 2: Pass reducers from runtime step dispatch**

In `src/wf_core/runtime/step.py`, update both sync and async foreach dispatch:

```python
elif isinstance(step, ForeachNode):
    return step_foreach(workflow, run, step, index, reducers=reducers)
```

- [ ] **Step 3: Add concurrent policy guard**

Add:

```python
def _step_foreach_concurrent(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    index: WorkflowIndex,
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> RunState:
    if step.item_error.action != "fail":
        raise WorkflowExecutionError(
            "concurrent foreach v1 only supports item_error.action='fail'"
        )
    raise WorkflowExecutionError("concurrent foreach execution is not implemented yet")
```

- [ ] **Step 4: Verify the non-fail policy test passes**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_rejects_non_fail_item_policy_for_now -q
```

Expected: pass.

---

### Task 6: Admit Concurrent Child Frames

**Files:**

- Modify: `src/wf_core/runtime/ops/foreach.py`
- Test: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Add admission helpers**

In `src/wf_core/runtime/ops/foreach.py`, add:

```python
def _resolve_foreach_iterable(run: RunState, frame: ExecutionFrame, step: ForeachNode) -> list[object]:
    iterable = safe_resolve_path(
        str(step.over),
        state=run.state,
        workflow_input=run.workflow_input,
        context=frame_context_values(frame),
    )
    if not isinstance(iterable, list):
        raise WorkflowExecutionError(
            f"foreach source {str(step.over)!r} must resolve to a list"
        )
    return iterable
```

Use this helper in both serial and concurrent code.

- [ ] **Step 2: Implement `_admit_concurrent_children`**

Add:

```python
def _admit_concurrent_children(
    *,
    run: RunState,
    frame: ExecutionFrame,
    step: ForeachNode,
    index: WorkflowIndex,
    barrier: ForeachBarrierState,
    iterable: list[object],
) -> int:
    assert step.concurrent is not None
    admitted = 0
    loop_start = index.next_node_id(frame.node_id, "loop")
    while (
        barrier.next_index < len(iterable)
        and len(barrier.active_frame_ids) < step.concurrent.max_active
        and len(barrier.outstanding_frame_ids) < step.concurrent.max_outstanding
    ):
        loop_index = barrier.next_index
        item = iterable[loop_index]
        child_id = f"{frame.id}:{step.id}:{loop_index}"
        barrier.next_index = loop_index + 1
        barrier.start_child(child_id)
        add_frame(
            run,
            ExecutionFrame(
                id=child_id,
                kind="foreach_iteration",
                node_id=loop_start,
                status=FrameStatus.PENDING,
                parent_frame_id=frame.id,
                metadata=ForeachIterationMetadata(
                    foreach_node_id=step.id,
                    loop_index=loop_index,
                    loop_item=item,
                    loop_alias=step.as_,
                ).to_metadata(),
            ),
            ready=True,
        )
        append_step_result_trace(
            run,
            frame_id=frame.id,
            node_id=frame.node_id,
            step_type=step.type,
            next_node_id=loop_start,
            result=StepExecutionResult(
                outcome="loop",
                resolved_input={
                    "item": item,
                    "index": loop_index,
                    "active_count": len(barrier.active_frame_ids) - 1,
                },
                output={},
                state_changes={},
            ),
        )
        admitted += 1
    return admitted
```

- [ ] **Step 3: Implement initial concurrent step body**

Replace `_step_foreach_concurrent` with:

```python
def _step_foreach_concurrent(
    workflow: Workflow,
    run: RunState,
    step: ForeachNode,
    index: WorkflowIndex,
) -> RunState:
    if step.item_error.action != "fail":
        raise WorkflowExecutionError(
            "concurrent foreach v1 only supports item_error.action='fail'"
        )
    if step.concurrent is None:
        raise WorkflowExecutionError("concurrent foreach requires concurrent policy")

    frame = run.current_frame()
    barrier = ForeachBarrierState.from_frame(frame, step.id) or ForeachBarrierState()
    iterable = _resolve_foreach_iterable(run, frame, step)
    _admit_concurrent_children(
        run=run,
        frame=frame,
        step=step,
        index=index,
        barrier=barrier,
        iterable=iterable,
    )
    barrier.save_to_frame(frame, step.id)
    block_frame_on_children(run, frame.id, barrier.outstanding_frame_ids)
    run.sync_from_current_frame()
    return run
```

This still does not finish; the next task handles child completion/refill/finish.

- [ ] **Step 4: Run tests and inspect failure**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_interleaves_items_and_commits_at_barrier -q
```

Expected: failure after first admitted children complete, likely deadlock or no barrier commit.

---

### Task 7: Refill and Finish Concurrent Foreach

**Files:**

- Modify: `src/wf_core/runtime/ops/state.py`
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Modify: `src/wf_core/runtime/ops/flow.py` or current child-completion caller if needed
- Test: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Ensure child completion wakes parent for refill**

In `src/wf_core/runtime/ops/flow.py`, `advance_frame(...)` currently calls
`wake_parent_if_children_complete(run, frame.id)` after a frame reaches `END`.

Replace or augment it with:

```python
wake_parent_for_child_progress(run, frame.id)
```

Import from `wf_core.runtime.scheduler`.

Expected behavior:

- Serial foreach still works because waking the parent after its only child completes is equivalent.
- Concurrent foreach parent wakes after each child completion so it can mark that child finished and refill one slot.

- [ ] **Step 2: Add child-finish cleanup in concurrent step**

At the start of `_step_foreach_concurrent`, after loading `barrier`, add:

```python
    for child_id in tuple(barrier.outstanding_frame_ids):
        child = run.frames[child_id]
        if child.status == FrameStatus.COMPLETED:
            barrier.finish_child(child_id)
        elif child.status == FrameStatus.FAILED:
            raise WorkflowExecutionError(
                f"concurrent foreach item frame {child_id!r} failed"
            )
```

- [ ] **Step 3: Add deterministic barrier patch helper**

In `src/wf_core/runtime/ops/state.py`, add:

```python
def build_barrier_patch(
    workflow: Workflow,
    item_patches: Sequence[StatePatch],
    state: dict[str, Any],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> StatePatch:
    """Build one committed barrier patch by replaying item writes in order.

    Item patches were built against parent-visible state, so reducer-prepared
    writes inside each item patch cannot be blindly merged together. The barrier
    must replay the trace-facing incoming changes against one staged state in
    deterministic item order.
    """
    state_fields = workflow.state_schema.field_index()
    staged_state = deepcopy(state)
    prepared_patch: dict[StatePath, tuple[list[str], Any]] = {}
    committed_changes: dict[str, Any] = {}
    for item_patch in item_patches:
        for destination, incoming_value in item_patch.changes.items():
            destination_path = StatePath.parse(destination)
            key_path, merged_value = prepare_state_value(
                workflow,
                staged_state,
                destination_path,
                incoming_value,
                reducers=reducers,
                state_fields=state_fields,
            )
            safe_set_nested_value(staged_state, key_path, merged_value)
            prepared_patch[destination_path] = (key_path, merged_value)
            committed_changes[destination] = merged_value
    validate_staged_state_patch(staged_state, prepared_patch, state_fields)
    return StatePatch(
        changes=committed_changes,
        _prepared_writes=prepared_patch,
        _staged_state=staged_state,
    )
```

- [ ] **Step 4: Add finish helper**

Add:

```python
def _finish_concurrent_foreach(
    *,
    workflow: Workflow,
    run: RunState,
    frame: ExecutionFrame,
    step: ForeachNode,
    index: WorkflowIndex,
    barrier: ForeachBarrierState,
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> RunState:
    next_node_id = index.next_node_id(frame.node_id, "done")
    combined = build_barrier_patch(
        workflow,
        [
            barrier.pending_results[item_index].patch
            for item_index in sorted(barrier.pending_results)
        ],
        run.state,
        reducers=reducers,
    )
    state_changes = commit_state_patch(run.state, combined)
    append_step_result_trace(
        run,
        frame_id=frame.id,
        node_id=frame.node_id,
        step_type=step.type,
        next_node_id=next_node_id,
        result=StepExecutionResult(
            outcome="done",
            resolved_input={
                "count": barrier.next_index,
                "index": barrier.next_index,
                "committed_items": len(barrier.pending_results),
            },
            output={},
            state_changes=state_changes,
        ),
    )
    advance_frame(run, frame, outcome="done", next_node_id=next_node_id)
    return run
```

Also import `build_barrier_patch`, `commit_state_patch`, `ReducerDefinition`, and
`Mapping` where needed.

- [ ] **Step 5: Finish when no more work remains**

In `_step_foreach_concurrent`, after cleanup and admission:

```python
    if barrier.next_index >= len(iterable) and not barrier.outstanding_frame_ids:
        return _finish_concurrent_foreach(
            workflow=workflow,
            run=run,
            frame=frame,
            step=step,
            index=index,
            barrier=barrier,
            reducers=reducers,
        )
```

If not finished, save barrier and block parent on outstanding children.

- [ ] **Step 6: Run V1 tests**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py -q
```

Expected: the first two tests pass; runtime-error test may still need failure propagation adjustment.

---

### Task 8: Preserve Runtime Failure Semantics

**Files:**

- Modify: `src/wf_core/runtime/engine.py`
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Test: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Verify existing engine behavior**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_fails_run_on_item_runtime_error -q
```

Expected before this task: either pass with the original exception or fail with deadlock. If it passes, skip to Task 9.

- [ ] **Step 2: If child failure becomes deadlock, fail parent on failed child**

In `_step_foreach_concurrent`, keep the failed child check:

```python
        elif child.status == FrameStatus.FAILED:
            raise WorkflowExecutionError(
                f"concurrent foreach item frame {child_id!r} failed"
            )
```

If the original exception text is lost, update engine frame-failure metadata in the existing exception handler so the parent error includes child error text:

```python
frame.metadata["error"] = str(exc)
```

Then use:

```python
message = child.metadata.get("error", "unknown item failure")
raise WorkflowExecutionError(
    f"concurrent foreach item frame {child_id!r} failed: {message}"
)
```

- [ ] **Step 3: Verify failure test**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_fails_run_on_item_runtime_error -q
```

Expected: pass.

---

### Task 9: Regression and Verification

**Files:**

- Modify: docs only if implementation differs from plan.

- [ ] **Step 1: Run focused core tests**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py tests/core/test_foreach_barrier_state.py tests/core/test_scheduler.py tests/core/test_atomic_state_patches.py -q
```

Expected: pass.

- [ ] **Step 2: Run authoring regression tests**

Run:

```bash
uv run pytest tests/authoring/test_demo_workflow.py tests/authoring/test_builder.py -q
```

Expected: pass.

- [ ] **Step 3: Run full suite**

Run:

```bash
uv run pytest -q
```

Expected: pass, except known environment-only skips.

- [ ] **Step 4: Run lint and type checks**

Run:

```bash
uvx ruff check src tests
uv run basedpyright --level error
```

Expected: ruff passes and basedpyright reports 0 errors.

---

## Self-Review

- Spec coverage: this plan implements only sync `mode="concurrent"` with `item_error.action="fail"`, frame admission/refill, buffered item patches, barrier commit, and fail-fast runtime behavior.
- Placeholder scan: async execution, `skip`, `collect`, reducer conflict policy, and interrupt quiescence are explicitly out of scope and covered by the Phase 4 roadmap.
- Type consistency: the plan uses existing `ForeachBarrierState`, `PendingItemResult`, `StatePatch`, `ForeachConcurrentPolicy`, scheduler frame helpers, and canonical `mode="concurrent"` vocabulary.
