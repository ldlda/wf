# Native Subgraph Interrupt Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a prepared native child workflow interrupt its parent run and later resume inside the original child scope.

**Architecture:** Add a typed internal interrupt route that distinguishes the public parent-subgraph identity from the actual interrupted child frame. Make interrupt request/resume operations scope-aware, then have engine resume select the prepared child workflow and reducers before applying child resume bindings. The parent `SubgraphNode` remains blocked until the child reaches its ordinary terminal outcome.

**Tech Stack:** Python 3.14, dataclasses, Pydantic workflow models, pytest, Ruff, basedpyright.

---

### Task 1: Child Interrupt Contract

**Files:**

- Modify: `src/wf_core/run_state.py`
- Modify: `tests/core/test_subgraph_step.py`

- [x] **Step 1: Write failing child interrupt/resume tests**

Add a child workflow containing an `InterruptNode` followed by a node or terminal step. Execute it through a parent `SubgraphNode` and assert:

```python
assert run.status == RunStatus.INTERRUPTED
assert run.interrupt is not None
assert run.interrupt.node_id == "child"
assert run.interrupt.payload["question"] == "confirm?"
assert run.frames["root"].status == FrameStatus.BLOCKED

resumed = resume_workflow(
    parent,
    run,
    {},
    resume_payload={"answer": "yes"},
    subgraphs={"child.workflow": prepared_child},
)
assert resumed.status == RunStatus.COMPLETED
assert resumed.output["answer"] == "yes"
```

- [x] **Step 2: Run tests and observe the existing explicit rejection**

Run: `uv run pytest -q tests/core/test_subgraph_step.py`

Expected: FAIL because child `InterruptNode` execution currently raises that child interrupts are unsupported.

- [x] **Step 3: Add structural route state**

Add `InterruptRoute` to `run_state.py` containing the interrupted child
`frame_id`, `node_id`, `scope_id`, `lineage_id`, and `workflow_ref`. Add an
optional `route` field to `InterruptRequest`; root interrupt requests continue
to use `route=None`.

### Task 2: Scope-Aware Interrupt Creation and Resume

**Files:**

- Modify: `src/wf_core/runtime/ops/handlers.py`
- Modify: `src/wf_core/runtime/ops/interrupts.py`
- Modify: `src/wf_core/runtime/preparation.py`
- Modify: `src/wf_core/runtime/step.py`
- Modify: `src/wf_core/runtime/engine.py`

- [x] **Step 1: Permit child interrupts and build their payload from child scope**

Remove the explicit child rejection. Build child interrupt request bindings
from `state_view_for_frame(...)` and `scope_input_for_frame(...)`, not from the
root compatibility dictionaries. For a non-root scope, find the owning parent
subgraph frame for public identity and attach `InterruptRoute` for resume.

- [x] **Step 2: Resume through the routed child workflow**

When an interrupted request has `route`, restore the routed child as the
current frame, resolve its `PreparedSubgraph`, build the child workflow index,
and apply `resume` output bindings into the child scope using normal
scope-aware patch commit logic. Root interrupts retain the existing path.

- [x] **Step 3: Verify parent completion behavior**

After child resume, scheduling must continue child execution first. Only after
the child finishes may the blocked parent subgraph frame wake and map child
output into parent state.

### Task 3: Verification and Documentation

**Files:**

- Modify: `docs/wf_core_architecture.md`
- Modify: `docs/current_roadmap.md`

- [x] **Step 1: Update documented limitations**

Document that prepared child interrupts now bubble and resume locally, while
artifact/deployment resolution for nested children remains outside core.

- [x] **Step 2: Run focused verification**

Run:

```powershell
uv run pytest -q tests/core/test_subgraph_step.py tests/core/test_concurrent_foreach_interrupts.py
uvx ruff check src/wf_core tests/core/test_subgraph_step.py tests/core/test_concurrent_foreach_interrupts.py
uvx ruff format --check src/wf_core tests/core/test_subgraph_step.py tests/core/test_concurrent_foreach_interrupts.py
uv run basedpyright --level error src/wf_core tests/core/test_subgraph_step.py tests/core/test_concurrent_foreach_interrupts.py
```

Expected: all commands exit successfully.
