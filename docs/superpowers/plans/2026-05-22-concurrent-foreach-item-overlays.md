# Concurrent Foreach Item Overlays Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make concurrent foreach item frames read their own buffered state writes so multi-step item bodies are safe.

**Architecture:** Keep `RunState.state` as committed parent state. Store item-local overlay patches in the foreach parent barrier, keyed by item index/frame id. `state_view_for_frame(...)` should return parent state plus that item's staged overlay; sibling overlays remain invisible. This plan does not implement sibling write conflict policy; Slice 3 owns write semantics across different item lineages.

**Tech Stack:** Python 3.14, dataclasses, pytest, existing `StatePatch`, `ForeachBarrierState`, `safe_resolve_path`, and runtime scheduler modules.

---

## Boundary With Slice 3

This slice answers:

- Can node B in the same concurrent item read node A's buffered state write?
- Can multi-step item bodies run without reading stale parent state?
- Are sibling item overlays isolated from each other?

This slice does **not** answer:

- Should two sibling items be allowed to write the same state path without a reducer?
- Should ancestor/descendant sibling writes conflict?
- Should barrier trace `state_changes` show raw per-item inputs or final aggregate values?

Those are Slice 3 write semantics. Do not add broad write-conflict policy here except what is already enforced by `build_output_patch(...)` for a single node output.

---

## Files

- Modify: `src/wf_core/runtime/foreach_state.py`
  - Accumulate successful item patches per item instead of storing only one patch.
  - Expose helpers to get item overlay patches by frame/index.
- Modify: `src/wf_core/runtime/ops/overlays.py`
  - Replace the current no-op seam with parent-state plus item-local staged writes.
- Modify: `src/wf_core/runtime/ops/nodes.py`
  - Build output patches against the frame-visible state view, not always `run.state`.
  - Append item-local patches for concurrent item frames.
- Modify: `src/wf_core/runtime/ops/foreach.py`
  - Remove the single-node item-body guard.
  - Keep `item_error.action != "fail"` unsupported.
- Test: `tests/core/test_concurrent_foreach.py`
  - Add multi-step item-body tests.
- Test: `tests/core/test_foreach_barrier_state.py`
  - Add item patch accumulation tests.

---

### Task 1: Add Failing Multi-Step Overlay Tests

**Files:**
- Modify: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Add a two-node item body test**

Append this test:

```python
def test_sync_concurrent_foreach_item_reads_own_buffered_write() -> None:
    workflow = _workflow(
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "scratch": StateField(type="string"),
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
    workflow.node_defs.extend(
        [
            NodeDef(
                name="read_scratch",
                input_schema=SchemaRef(
                    type="object",
                    properties={"scratch": {}},
                    required=["scratch"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"seen": {}},
                    required=["seen"],
                ),
                outcomes=["ok"],
            )
        ]
    )
    workflow.nodes.append(
        NodeUse.model_validate(
            {
                "id": "read_scratch",
                "type": "node",
                "node": "read_scratch",
                "input": [{"target": "scratch", "path": "state.scratch"}],
                "output": [{"source": "seen", "target": "state.seen"}],
            }
        )
    )
    workflow.edges = [
        Edge.model_validate({"from": "each", "outcome": "loop", "to": "record"}),
        Edge.model_validate({"from": "record", "outcome": "ok", "to": "read_scratch"}),
        Edge.model_validate({"from": "read_scratch", "outcome": "ok", "to": END}),
        Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
    ]

    run = execute_workflow(
        workflow,
        {"items": ["a", "b", "c"]},
        {
            "record": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"scratch": f"scratch:{payload['value']}"},
            },
            "read_scratch": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["scratch"]},
            },
        },
    )

    assert run.state["seen"] == ["scratch:a", "scratch:b", "scratch:c"]
```

Important detail: update the existing `record` `NodeUse` in `_workflow(...)` or inside this test so it writes `scratch` to `state.scratch` for this workflow. If `_workflow(...)` is too fixed for that, create a small dedicated helper for this test instead of making `_workflow(...)` harder to read.

- [ ] **Step 2: Add a sibling isolation test**

Append this test:

```python
def test_sync_concurrent_foreach_sibling_overlays_do_not_leak() -> None:
    workflow = _workflow(
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "scratch": StateField(type="string"),
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
    workflow.node_defs.extend(
        [
            NodeDef(
                name="read_scratch",
                input_schema=SchemaRef(
                    type="object",
                    properties={"scratch": {}},
                    required=["scratch"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"seen": {}},
                    required=["seen"],
                ),
                outcomes=["ok"],
            )
        ]
    )
    workflow.nodes.append(
        NodeUse.model_validate(
            {
                "id": "read_scratch",
                "type": "node",
                "node": "read_scratch",
                "input": [{"target": "scratch", "path": "state.scratch"}],
                "output": [{"source": "seen", "target": "state.seen"}],
            }
        )
    )
    workflow.edges = [
        Edge.model_validate({"from": "each", "outcome": "loop", "to": "record"}),
        Edge.model_validate({"from": "record", "outcome": "ok", "to": "read_scratch"}),
        Edge.model_validate({"from": "read_scratch", "outcome": "ok", "to": END}),
        Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
    ]

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"]},
        {
            "record": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"scratch": payload["value"]},
            },
            "read_scratch": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["scratch"]},
            },
        },
    )

    assert run.state["seen"] == ["a", "b"]
```

This catches the bad implementation where item `b` sees item `a`'s staged write or vice versa.

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_item_reads_own_buffered_write tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_sibling_overlays_do_not_leak -q
```

Expected before implementation:

```text
FAILED with "concurrent foreach v1 only supports loop bodies with one node"
```

or, if the guard was already removed by another worker:

```text
FAILED because state.scratch is missing/stale
```

---

### Task 2: Accumulate Per-Item Patches

**Files:**
- Modify: `src/wf_core/runtime/foreach_state.py`
- Modify: `tests/core/test_foreach_barrier_state.py`

- [ ] **Step 1: Add patch accumulation tests**

Append to `tests/core/test_foreach_barrier_state.py`:

```python
def test_foreach_barrier_accumulates_multiple_patches_for_one_item() -> None:
    barrier = ForeachBarrierState(mode="concurrent")

    barrier.add_success_patch(
        index=0,
        frame_id="child-0",
        patch=StatePatch(changes={"state.scratch": "a"}),
    )
    barrier.add_success_patch(
        index=0,
        frame_id="child-0",
        patch=StatePatch(changes={"state.seen": "a"}),
    )

    result = barrier.pending_results[0]
    assert result.patch.changes["state.scratch"] == "a"
    assert result.patch.changes["state.seen"] == "a"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/core/test_foreach_barrier_state.py::test_foreach_barrier_accumulates_multiple_patches_for_one_item -q
```

Expected before implementation:

```text
FAILED with "already recorded"
```

- [ ] **Step 3: Replace duplicate rejection with patch merge**

In `src/wf_core/runtime/foreach_state.py`, change `add_success_patch(...)` to merge changes for the same item:

```python
    def add_success_patch(
        self, *, index: int, frame_id: str, patch: StatePatch
    ) -> None:
        """Buffer or extend successful item patches by item index.

        A multi-step item body may produce multiple node patches. They are
        accumulated for the same item lineage and replayed by the barrier in
        item index order. Overlap inside one item remains governed by the normal
        node output patch rules for each node; Slice 3 owns sibling conflict
        policy at the barrier.
        """
        existing = self.pending_results.get(index)
        if existing is None:
            self.pending_results[index] = PendingItemResult(
                index=index,
                frame_id=frame_id,
                status="succeeded",
                patch=patch,
            )
            return
        if existing.frame_id != frame_id:
            raise WorkflowExecutionError(
                f"foreach item result for index {index!r} belongs to frame "
                f"{existing.frame_id!r}, got {frame_id!r}"
            )
        existing.patch.changes.update(patch.changes)
```

This intentionally updates only `changes`; the barrier replays changes into a fresh staged state later. Do not try to merge `_prepared_writes` here.

- [ ] **Step 4: Update duplicate test**

Replace the prior duplicate-item-result test with a frame-mismatch test:

```python
def test_foreach_barrier_rejects_item_result_frame_mismatch() -> None:
    barrier = ForeachBarrierState(mode="concurrent")
    patch = StatePatch(changes={"state.count": 1})

    barrier.add_success_patch(index=0, frame_id="child-0", patch=patch)

    with pytest.raises(WorkflowExecutionError, match="belongs to frame"):
        barrier.add_success_patch(index=0, frame_id="child-1", patch=patch)
```

- [ ] **Step 5: Verify barrier tests**

Run:

```bash
uv run pytest tests/core/test_foreach_barrier_state.py -q
```

Expected: pass.

---

### Task 3: Build Item-Local State Views

**Files:**
- Modify: `src/wf_core/runtime/ops/overlays.py`
- Test: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Implement overlay state view**

Replace `state_view_for_frame(...)` in `src/wf_core/runtime/ops/overlays.py`:

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any

from wf_core.run_state import ExecutionFrame, RunState
from wf_core.runtime.foreach_state import ForeachBarrierState, item_frame_owner
from wf_core.runtime.ops.state import safe_set_nested_value
from wf_core.paths import StatePath


def state_view_for_frame(run: RunState, frame: ExecutionFrame) -> dict[str, Any]:
    """Return committed parent state plus this frame's item-local overlay.

    Concurrent foreach item frames buffer writes in the parent barrier until the
    foreach barrier commits. Later nodes in the same item must still read those
    earlier writes, while sibling item frames must not see them.
    """
    owner = item_frame_owner(frame)
    if owner is None:
        return run.state

    parent_frame_id, foreach_node_id, item_index = owner
    parent_frame = run.frames[parent_frame_id]
    barrier = ForeachBarrierState.from_frame(parent_frame, foreach_node_id)
    if barrier is None or barrier.mode != "concurrent":
        return run.state

    pending = barrier.pending_results.get(item_index)
    if pending is None:
        return run.state

    state_view = deepcopy(run.state)
    for destination, value in pending.patch.changes.items():
        path = StatePath.parse(destination)
        safe_set_nested_value(state_view, list(path.parts), value)
    return state_view
```

Do not apply reducers here. The overlay view is an item-local read model, not the final parent commit. Reducers are applied at patch build time for each node and again at the barrier for aggregate commit.

- [ ] **Step 2: Verify overlay tests still fail on guard**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_item_reads_own_buffered_write -q
```

Expected: if the single-node guard is still present, failure remains the guard. If guard was removed by another worker, this may already pass.

---

### Task 4: Build Output Patches Against Frame State View

**Files:**
- Modify: `src/wf_core/runtime/ops/nodes.py`
- Test: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Reuse the resolved state view for output patching**

Currently `_resolve_node_execution(...)` computes `state_view` but returns only input/context. Change it to return the state view too:

```python
) -> tuple[dict[str, Any], RuntimeContext, dict[str, Any]]:
```

Return:

```python
    return resolved_input, context, state_view
```

Update both callers:

```python
resolved_input, context, state_view = _resolve_node_execution(...)
```

Then pass `state_view` into `_finalize_node_execution(...)`:

```python
        state=state_view,
```

Add a parameter to `_finalize_node_execution(...)`:

```python
    state_view: dict[str, Any],
```

And change `build_output_patch(...)` call from:

```python
        run.state,
```

to:

```python
        state_view,
```

This is required for node B in one item to build a patch using node A's staged value.

- [ ] **Step 2: Run focused overlay test**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_item_reads_own_buffered_write -q
```

Expected: still fails until the single-node guard is removed.

---

### Task 5: Lift The Single-Node Concurrent Body Restriction

**Files:**
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Modify: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Remove the old rejection test**

Delete or rewrite `test_sync_concurrent_foreach_rejects_multi_step_item_body_for_now`.

If preserving regression coverage is preferred, replace it with:

```python
def test_sync_concurrent_foreach_allows_multi_step_item_body_with_overlay() -> None:
    # Use the same workflow shape as
    # test_sync_concurrent_foreach_item_reads_own_buffered_write.
    # Assert the workflow completes and output contains all expected values.
```

Prefer not duplicating the full workflow; extract a helper:

```python
def _multi_step_overlay_workflow() -> Workflow:
    ...
```

- [ ] **Step 2: Remove validation call and helper**

In `src/wf_core/runtime/ops/foreach.py`, remove:

```python
    _validate_single_node_loop_body(index, step)
```

Delete `_validate_single_node_loop_body(...)`.

Remove unused imports:

```python
from wf_core.models.steps import NodeUse
from wf_core.tokens import END
```

Keep graph traversal validation out of this slice. Normal workflow validation and runtime edge lookup still define whether graph topology is routable.

- [ ] **Step 3: Verify multi-step overlay tests**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_item_reads_own_buffered_write tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_sibling_overlays_do_not_leak -q
```

Expected: pass.

---

### Task 6: Document Overlay Semantics

**Files:**
- Modify: `docs/adr/0002-concurrent-foreach-policy-and-barrier-commits.md`
- Modify: `docs/superpowers/plans/2026-05-22-concurrent-foreach-phase4-roadmap.md`

- [ ] **Step 1: Update ADR current-state note**

In `docs/adr/0002-concurrent-foreach-policy-and-barrier-commits.md`, replace the V1 limitation paragraph:

```markdown
Current sync V1 implements the barrier commit path only for `loop -> one node ->
END` item bodies. The runtime includes an explicit no-op overlay seam
(`state_view_for_frame`) so the next slice can add lineage-local reads without
rewiring node execution. Until that seam becomes real, multi-step concurrent
item bodies are rejected instead of reading stale parent state.
```

with:

```markdown
Current sync execution supports item-local read overlays for concurrent foreach
item frames. `RunState.state` remains committed parent state, while
`state_view_for_frame` overlays the current item's buffered writes for reads by
later nodes in the same item lineage. Sibling overlays remain invisible until
the foreach barrier commits.
```

- [ ] **Step 2: Update roadmap slice statuses**

In `docs/superpowers/plans/2026-05-22-concurrent-foreach-phase4-roadmap.md`,
mark Slice 1 as implemented and add/link this plan under Slice 2.

Use:

```markdown
Plan:

- See [`2026-05-22-concurrent-foreach-item-overlays.md`](2026-05-22-concurrent-foreach-item-overlays.md).
```

- [ ] **Step 3: Verify docs reference no stale limitation**

Run:

```bash
rg -n "one node|no-op overlay|multi-step concurrent item bodies are rejected" docs src tests
```

Expected: no stale claims except historical plan text in the already-completed V1 plan.

---

### Task 7: Verification

**Files:**
- No new files unless tests require helper extraction.

- [ ] **Step 1: Run focused core tests**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py tests/core/test_foreach_barrier_state.py tests/core/test_scheduler.py tests/core/test_atomic_state_patches.py -q
```

Expected: pass.

- [ ] **Step 2: Run authoring smoke tests**

Run:

```bash
uv run pytest tests/authoring/test_demo_workflow.py tests/authoring/test_builder.py tests/authoring/test_ops.py -q
```

Expected: pass.

- [ ] **Step 3: Run full suite**

Run:

```bash
uv run pytest -q
```

Expected: pass, allowing known intentional environment-only skips.

- [ ] **Step 4: Run lint/type/format checks**

Run:

```bash
uvx ruff check src tests
uvx ruff format --check src tests docs
uv run basedpyright --level error src tests
```

Expected: all pass with 0 type errors.

---

## Self-Review

- Spec coverage: the plan makes item-local overlays real, supports multi-step concurrent item bodies, keeps sibling overlays isolated, and explicitly defers sibling write conflict policy.
- Placeholder scan: no task uses “TBD” or “add tests” without concrete test content.
- Type consistency: the plan uses current names: `ForeachBarrierState`, `PendingItemResult`, `StatePatch`, `state_view_for_frame`, `item_frame_owner`, and `build_output_patch`.
