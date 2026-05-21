# Parallel Foreach Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement parallel foreach incrementally without breaking serial workflows or duplicating state-write logic.

**Architecture:** The work is split into four independently shippable layers: policy models, state patch extraction, barrier runtime state, and async parallel execution. Each layer preserves current serial behavior and adds tests before implementation. `foreach(mode="parallel")` remains unsupported until the final layer.

**Tech Stack:** Python 3.14, Pydantic v2, dataclasses, pytest, basedpyright, ruff, existing `wf_core` scheduler/runtime modules.

---

## Phase 1: Foreach Policy Models

**Goal:** Add the future policy shape while keeping runtime behavior serial-only.

**Files:**
- Modify: `src/wf_core/models/steps.py`
- Modify: `src/wf_core/validation/outcomes.py`
- Modify: `src/wf_core/validation/steps.py`
- Modify: `src/wf_authoring/builder/core.py`
- Test: `tests/core/test_foreach_policy.py`
- Test: `tests/authoring/test_builder.py`

- [ ] **Step 1: Add failing model tests**

Create `tests/core/test_foreach_policy.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from wf_core.models.steps import ForeachNode


def test_serial_foreach_defaults_to_fail_item_policy() -> None:
    node = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": {"root": "state", "parts": ["items"]},
            "as": "item",
        }
    )

    assert node.mode == "serial"
    assert node.item_error.action == "fail"
    assert node.item_error.collect_to is None
    assert node.parallel is None


def test_collect_item_policy_requires_collect_to() -> None:
    with pytest.raises(ValidationError, match="collect_to"):
        ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": {"root": "state", "parts": ["items"]},
                "as": "item",
                "item_error": {"action": "collect"},
            }
        )


def test_parallel_policy_requires_parallel_mode() -> None:
    with pytest.raises(ValidationError, match="parallel policy"):
        ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": {"root": "state", "parts": ["items"]},
                "as": "item",
                "parallel": {"max_active": 4, "max_outstanding": 20},
            }
        )


def test_parallel_policy_validates_capacity_order() -> None:
    with pytest.raises(ValidationError, match="max_outstanding"):
        ForeachNode.model_validate(
            {
                "id": "each",
                "type": "foreach",
                "over": {"root": "state", "parts": ["items"]},
                "as": "item",
                "mode": "parallel",
                "parallel": {"max_active": 10, "max_outstanding": 4},
            }
        )
```

- [ ] **Step 2: Add policy models**

In `src/wf_core/models/steps.py`, add:

```python
from typing import Self


class ForeachItemErrorPolicy(BaseModel):
    """Policy for runtime failures inside one foreach item lineage."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["fail", "skip", "collect"] = "fail"
    collect_to: StatePath | None = None

    @model_validator(mode="after")
    def _validate_collect_to(self) -> Self:
        if self.action == "collect" and self.collect_to is None:
            raise ValueError("collect item error policy requires collect_to")
        if self.action != "collect" and self.collect_to is not None:
            raise ValueError("collect_to is only valid when action='collect'")
        return self


class ForeachParallelPolicy(BaseModel):
    """Concurrency policy for async parallel foreach execution."""

    model_config = ConfigDict(extra="forbid")

    max_active: int = Field(default=4, ge=1)
    max_outstanding: int = Field(default=20, ge=1)
    interrupt: Literal["quiesce"] = "quiesce"

    @model_validator(mode="after")
    def _validate_capacity(self) -> Self:
        if self.max_outstanding < self.max_active:
            raise ValueError("max_outstanding must be >= max_active")
        return self
```

Update `ForeachNode`:

```python
item_error: ForeachItemErrorPolicy = Field(default_factory=ForeachItemErrorPolicy)
parallel: ForeachParallelPolicy | None = None
on_item_error: Literal["fail", "collect", "skip"] | None = Field(
    default=None,
    exclude=True,
    description="Deprecated parse-only shorthand; use item_error.action.",
)
```

Add a `model_validator(mode="before")` that converts old `on_item_error` into `item_error.action`.

Add a `model_validator(mode="after")` that enforces:

```python
if self.mode == "parallel" and self.parallel is None:
    raise ValueError("parallel foreach requires parallel policy")
if self.mode == "serial" and self.parallel is not None:
    raise ValueError("parallel policy is only valid when mode='parallel'")
```

- [ ] **Step 3: Update derived outcomes**

In `src/wf_core/validation/outcomes.py`, update foreach outcome derivation:

```python
if step.type == "foreach":
    outcomes = {"loop", "done"}
    if step.item_error.action in {"skip", "collect"}:
        outcomes.add("completed_with_errors")
    return outcomes
```

- [ ] **Step 4: Validate collect destination schema**

In `src/wf_core/validation/steps.py`, when `node.item_error.action == "collect"`:

```python
destination_root = _state_destination_root(node.item_error.collect_to)
if destination_root is None or destination_root not in state_root_fields:
    report.add(...)
```

Add a follow-up test that collect-to unknown state root reports a validation issue.

- [ ] **Step 5: Keep runtime unsupported**

In `src/wf_core/runtime/ops/foreach.py`, keep:

```python
if step.mode != "serial":
    raise WorkflowExecutionError("parallel foreach execution is not implemented yet")
```

Add a comment:

```python
# Policy models are accepted before execution support so saved workflows can
# validate shape, but runtime must reject parallel until barrier commits exist.
```

- [ ] **Step 6: Verify phase**

Run:

```bash
uv run pytest tests/core/test_foreach_policy.py tests/authoring/test_builder.py -q
uvx ruff check src tests
uv run basedpyright --level error
```

Expected: all pass.

---

## Phase 2: State Patch Extraction

**Goal:** Split current node output writes into reusable “build patch” and “commit patch” operations without changing current serial behavior.

**Files:**
- Modify: `src/wf_core/runtime/ops/state.py`
- Modify: `src/wf_core/runtime/ops/nodes.py`
- Test: `tests/core/test_atomic_state_patches.py`
- Test: `tests/core/test_nested_state_paths.py`

- [ ] **Step 1: Add state patch model**

In `src/wf_core/runtime/ops/state.py`, add:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StatePatch:
    """Validated state writes produced by one step before commit."""

    changes: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 2: Extract patch builder**

Refactor existing `apply_output_bindings(...)` into:

```python
def build_output_patch(
    workflow: Workflow,
    bindings: Sequence[OutputBinding],
    output: Mapping[str, Any],
    state: MutableMapping[str, Any],
    *,
    reducers: Mapping[str, ReducerDefinition] | None = None,
    missing_field_message: str = "node output is missing required field {field}",
) -> StatePatch:
    ...
```

This function should:
- validate source paths
- validate destination paths
- calculate reducer-aware changes
- not mutate `state`

- [ ] **Step 3: Extract patch committer**

Add:

```python
def commit_state_patch(
    state: MutableMapping[str, Any],
    patch: StatePatch,
) -> dict[str, Any]:
    """Commit a validated patch to state and return committed changes."""
    for path, value in patch.changes.items():
        set_nested_value(state, split_state_path(path), value)
    return dict(patch.changes)
```

Use the existing typed path helpers; do not reintroduce dotted-string parsing if a typed path helper exists.

- [ ] **Step 4: Preserve old API**

Keep `apply_output_bindings(...)` as a wrapper:

```python
patch = build_output_patch(...)
return commit_state_patch(state, patch)
```

Existing callers should keep working.

- [ ] **Step 5: Add equivalence tests**

Add tests that compare:

```python
old_changes = apply_output_bindings(...)
patch = build_output_patch(...)
new_changes = commit_state_patch(state2, patch)
assert old_changes["state.some_path"] == new_changes["state.some_path"]
assert state1["some_path"] == state2["some_path"]
```

Do not assert whole dict equality unless the test intentionally owns the full structure.

- [ ] **Step 6: Verify phase**

Run:

```bash
uv run pytest tests/core/test_atomic_state_patches.py tests/core/test_nested_state_paths.py tests/authoring/test_demo_workflow.py -q
uvx ruff check src tests
uv run basedpyright --level error
```

Expected: all pass; full suite should still pass before moving on.

---

## Phase 3: Foreach Barrier Runtime State

**Goal:** Add resumable barrier metadata and pending result structures without enabling async parallel execution.

**Files:**
- Modify: `src/wf_core/runtime/scheduler.py`
- Create: `src/wf_core/runtime/foreach_state.py`
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Test: `tests/core/test_foreach_barrier_state.py`

- [ ] **Step 1: Add pending result dataclasses**

Create `src/wf_core/runtime/foreach_state.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from wf_core.runtime.ops.state import StatePatch


@dataclass(slots=True)
class ItemErrorRecord:
    """Structured runtime failure record for one foreach item."""

    index: int
    frame_id: str
    node_id: str
    error_type: str
    message: str
    item: Any = None


@dataclass(slots=True)
class PendingItemResult:
    """Buffered item result waiting for foreach barrier commit."""

    index: int
    frame_id: str
    status: Literal["succeeded", "failed"]
    patch: StatePatch = field(default_factory=StatePatch)
    error: ItemErrorRecord | None = None
```

- [ ] **Step 2: Add foreach barrier state**

In the same file:

```python
@dataclass(slots=True)
class ForeachBarrierState:
    """Resumable state owned by one foreach parent frame."""

    next_index: int = 0
    active_frame_ids: tuple[str, ...] = ()
    outstanding_frame_ids: tuple[str, ...] = ()
    pending_results: dict[int, PendingItemResult] = field(default_factory=dict)
```

Add `to_metadata()` / `from_frame()` helpers. Wrong frame kind returns `None`; malformed metadata for a foreach parent raises `WorkflowExecutionError`.

- [ ] **Step 3: Move serial progress into typed state**

Current serial foreach uses:

```python
progress_map = frame.metadata.setdefault("foreach_progress", {})
```

Replace with typed barrier state, but keep behavior equivalent:

```python
barrier = ForeachBarrierState.from_frame(frame) or ForeachBarrierState()
loop_index = barrier.next_index
barrier.next_index += 1
frame.metadata["foreach_barrier"] = barrier.to_metadata()
```

- [ ] **Step 4: Add serialization tests**

Test:

```python
def test_foreach_barrier_state_round_trips_through_frame_metadata() -> None:
    ...
```

Assert specific fields:

```python
assert loaded.next_index == 2
assert loaded.outstanding_frame_ids == ("child-1",)
```

- [ ] **Step 5: Keep serial behavior passing**

Run:

```bash
uv run pytest tests/core/test_foreach_barrier_state.py tests/authoring/test_demo_workflow.py -q
```

Expected: pass.

---

## Phase 4: Async Parallel Foreach

**Goal:** Enable `foreach(mode="parallel")` in async execution only, using policy limits, pending results, and barrier commits.

**Files:**
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Modify: `src/wf_core/runtime/step.py`
- Modify: `src/wf_core/runtime/engine.py`
- Modify: `src/wf_core/runtime/ops/nodes.py`
- Modify: `src/wf_core/runtime/foreach_state.py`
- Test: `tests/core/test_parallel_foreach.py`

- [ ] **Step 1: Add async-only rejection tests**

Create `tests/core/test_parallel_foreach.py` with:

```python
def test_sync_runtime_rejects_parallel_foreach() -> None:
    ...


async def test_async_runtime_accepts_parallel_foreach() -> None:
    ...
```

Expected before implementation: async test fails because runtime still rejects parallel.

- [ ] **Step 2: Add capacity tests**

Use async node handlers that record start/completion order and block on `asyncio.Event`.

Test:

```python
async def test_parallel_foreach_respects_max_active() -> None:
    ...
    assert max_seen_active == 2
```

Use `max_active=2`.

- [ ] **Step 3: Add outstanding tests**

Use a node that blocks internally through a future block helper or controlled async wait.

Test:

```python
async def test_blocked_items_count_against_max_outstanding_not_active() -> None:
    ...
```

This may require a small test-only node that blocks through the runtime-supported internal wait. If internal blocking is not implemented yet, defer this test to subgraph/internal-wait work and keep `max_outstanding` tested through queued children.

- [ ] **Step 4: Add collect/skip tests**

Tests:

```python
async def test_parallel_collect_writes_ordered_errors_and_emits_completed_with_errors() -> None:
    ...


async def test_parallel_skip_emits_completed_with_errors_without_hidden_state() -> None:
    ...
```

Assert:

```python
assert run.state["document_errors"][0]["index"] == 1
assert run.trace[-1].outcome == "completed_with_errors"
```

- [ ] **Step 5: Add barrier commit ordering test**

Use nodes that complete out of order but write list-like results.

Assert committed state is ordered by item index, not completion order.

- [ ] **Step 6: Implement async parallel child scheduling**

In `step_foreach`, branch by mode:

```python
if step.mode == "serial":
    return step_foreach_serial(...)
return step_foreach_parallel(...)
```

`step_foreach_parallel` should:
- inspect `ForeachBarrierState`
- start children while `active < max_active` and `outstanding < max_outstanding`
- block parent when waiting for children
- finish when all items terminal
- commit barrier patches in item index order
- emit `done` or `completed_with_errors`

- [ ] **Step 7: Add async node-call budget seam**

Add execution option shape only if needed by implementation:

```python
@dataclass(slots=True)
class RuntimeLimits:
    max_active_node_calls: int = 16
```

If this is too large for the first async parallel pass, leave global node-call budget as follow-up and rely on foreach `max_active`.

- [ ] **Step 8: Verify phase**

Run:

```bash
uv run pytest tests/core/test_parallel_foreach.py tests/authoring/test_demo_workflow.py -q
uv run pytest -q
uvx ruff check src tests
uv run basedpyright --level error
```

Expected: all pass.

---

## Implementation Order Recommendation

Ship these as separate commits/PRs:

1. Phase 1: policy shape and validation
2. Phase 2: patch extraction with no behavior change
3. Phase 3: barrier metadata with serial behavior unchanged
4. Phase 4: async parallel execution

Do not start Phase 4 until Phase 2 and Phase 3 are stable. Parallel foreach depends on patch extraction and resumable barrier state.

## Self-Review

- Spec coverage: ADR 0002 decisions are represented across the four phases.
- Intentional gaps: explicit Fork/Gather, lineage-token graph nodes, OpenTelemetry, platform source/tool caps, and full run persistence are not included.
- Risk control: phases 1-3 preserve serial behavior and keep `mode="parallel"` unsupported until phase 4.
