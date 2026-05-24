# Lineage State Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add runtime scopes and lineages before native subgraphs so sibling branches/items can own isolated replayable state writes and later merge through barriers.

**Architecture:** Implements [`../specs/2026-05-24-lineage-state-runtime-design.md`](../specs/2026-05-24-lineage-state-runtime-design.md). Keep `RunState.state` as the committed root-scope compatibility state, add `RuntimeScope`, `LineageState`, and `StateWrite`, and migrate concurrent foreach from foreach-specific overlays to lineage-backed state views. A frame says where execution is; a scope says which workflow state root execution belongs to; a lineage says which pending writes that execution can see.

**Tech Stack:** Python 3.14, dataclasses, existing `StatePatch`, `StatePath`, `ReducerRef`, `ForeachBarrierState`, pytest, basedpyright, ruff.

---

## Current Implementation Status

This plan is being implemented incrementally. The full `RuntimeScope` /
`LineageState` storage model below is still future work, but the runtime now has
the compatibility subset needed before native subgraphs:

- `StateWrite` exists and records `incoming_value` for replay plus
  `visible_value` for same-lineage reads.
- `StatePatch` stores ordered `writes` while preserving `changes` as the
  trace/compatibility view.
- `LineageStateView` materializes committed state plus visible lineage writes.
- Concurrent foreach item overlays read `StateWrite.visible_value`.
- Foreach pending result metadata persists write records and `lineage_id`.
- `ExecutionFrame` and `RuntimeContext` carry `scope_id`, `lineage_id`, and
  `parent_lineage_id`.
- Concurrent foreach child frames receive deterministic, opaque lineage ids,
  including nested foreach frames.
- `RunState` has root scope/lineage storage, scope-aware state views, and
  generic non-root node writes buffer into `RunState.lineages`.
- New concurrent foreach item writes are stored in `RunState.lineages`.
  `ForeachBarrierState` now keeps scheduling/result metadata plus compatibility
  patches for old serialized barrier data.

Direct commits currently go through `is_root_lineage_frame(frame)`, which is the
migration shortcut for root scope/root lineage. The eventual better shape is an
explicit scope/lineage commit target, feasible once native subgraph completion
can declare whether child writes commit to child scope, parent lineage, or only
through boundary output bindings.

Remaining work should avoid jumping straight into a broad rewrite. Native
subgraph scaffolding is now present (`SubgraphNode`, structural `WorkflowRef`,
terminal workflow outcomes, and authoring helpers). The next runtime slice can
execute a non-interrupting prepared child graph using the current scope/lineage
primitives; interrupt bubbling and saved/deployed workflow resolution remain
later work.

---

## File Structure

- Modify: `src/wf_core/run_state.py`
  - Add `RuntimeScope`, `StateWrite`, `LineageState`.
  - Add `ExecutionFrame.scope_id` and `ExecutionFrame.lineage_id`.
  - Add `RunState.scopes` and `RunState.lineages`.
- Modify: `src/wf_core/runtime/ops/state.py`
  - Change `StatePatch` from only path-value maps to ordered `StateWrite` records while preserving `changes` as a compatibility/trace view.
- Create: `src/wf_core/runtime/lineage.py`
  - Own scope/lineage lookup, state view materialization, append writes, and conversion of completed lineage writes into barrier patches.
- Modify: `src/wf_core/runtime/ops/runs.py`
  - Initialize root scope and root lineage.
- Modify: `src/wf_core/runtime/ops/nodes.py`
  - Resolve node input from frame scope/lineage view and buffer non-root writes into lineage records.
- Modify: `src/wf_core/runtime/ops/foreach.py`
  - Create concurrent item lineages and commit completed lineage writes through the barrier.
- Modify: `src/wf_core/runtime/foreach_state.py`
  - Store completed lineage ids in pending item results; keep old patch metadata parse-compatible.
- Modify: `src/wf_core/runtime/ops/overlays.py`
  - Reduce to a compatibility facade over lineage state views.
- Test: `tests/core/test_lineage_state.py`
  - Unit tests for root scope/lineage, state views, write records, and non-root write buffering.
- Test: `tests/core/test_atomic_state_patches.py`
  - Tests for ordered `StateWrite` records and compatibility `changes`.
- Test: `tests/core/test_concurrent_foreach.py`
  - Regression tests for sibling isolation, same-item visibility, and deterministic barrier commits.
- Docs: `docs/wf_core_architecture.md`, `docs/current_roadmap.md`, `docs/superpowers/specs/2026-05-24-native-subgraphs-design.md`
  - Document scope/lineage as the prerequisite for native subgraphs.

---

## Core Shape

Target runtime state types:

```python
@dataclass(slots=True)
class StateWrite:
    """One reducer-aware write record owned by a lineage or patch."""

    path: StatePath
    incoming_value: Any
    visible_value: Any
    reducer: ReducerRef


@dataclass(slots=True)
class RuntimeScope:
    """Committed state root for one workflow activation."""

    id: str
    workflow_name: str
    committed_state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LineageState:
    """Pending ordered writes visible to frames in one lineage."""

    id: str
    scope_id: str
    parent_id: str | None = None
    writes: list[StateWrite] = field(default_factory=list)
```

Target patch shape:

```python
@dataclass(slots=True)
class StatePatch:
    """Validated state writes produced by one step before commit."""

    writes: list[StateWrite] = dataclass_field(default_factory=list)
    _staged_state: dict[str, Any] = dataclass_field(default_factory=dict, repr=False)

    @property
    def changes(self) -> dict[str, Any]:
        return {str(write.path): write.incoming_value for write in self.writes}

    @property
    def visible_values(self) -> dict[str, Any]:
        return {str(write.path): write.visible_value for write in self.writes}
```

Compatibility requirement: existing tests and callers that read `patch.changes`
should continue to work. New lineage code must use ordered `writes`, not
flattened final values.

---

## Task 1: Add Ordered StateWrite Records to StatePatch

Status: implemented as the compatibility shape. `StatePatch.changes` remains a
stored compatibility dict rather than a derived-only property for now.

**Files:**

- Modify: `src/wf_core/runtime/ops/state.py`
- Test: `tests/core/test_atomic_state_patches.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def test_output_patch_records_incoming_and_visible_values() -> None:
    workflow = _workflow_with_state_field(
        path="state.count",
        schema={"type": "integer"},
        reducer="wf.std.add",
    )
    state = {"count": 2}

    patch = build_output_patch(
        workflow,
        [OutputBinding.model_validate({"source": "delta", "target": "state.count"})],
        {"delta": 3},
        state,
    )

    assert patch.changes["state.count"] == 3
    assert patch.visible_values["state.count"] == 5
    assert patch.writes[0].incoming_value == 3
    assert patch.writes[0].visible_value == 5


def test_barrier_replays_incoming_values_not_lineage_visible_values() -> None:
    workflow = _workflow_with_state_field(
        path="state.number",
        schema={"type": "integer"},
        reducer="wf.std.add",
    )
    patch = build_barrier_patch(
        workflow,
        [
            StatePatch(
                writes=[
                    StateWrite(
                        path=StatePath(("number",)),
                        incoming_value=3,
                        visible_value=5,
                        reducer=ReducerRef(name="wf.std.add"),
                    )
                ]
            ),
            StatePatch(
                writes=[
                    StateWrite(
                        path=StatePath(("number",)),
                        incoming_value=1,
                        visible_value=3,
                        reducer=ReducerRef(name="wf.std.add"),
                    )
                ]
            ),
        ],
        {"number": 2},
    )

    assert patch.changes["state.number"] == 6
    assert patch.visible_values["state.number"] == 6
```

Add imports:

```python
from wf_core.models.reducers import ReducerRef
from wf_core.paths import StatePath
from wf_core.run_state import StateWrite
```

- [ ] **Step 2: Run expected failing tests**

Run:

```bash
uv run pytest tests/core/test_atomic_state_patches.py::test_output_patch_records_incoming_and_visible_values tests/core/test_atomic_state_patches.py::test_barrier_replays_incoming_values_not_lineage_visible_values -q
```

Expected: failure because `StateWrite`, `StatePatch.writes`, and `visible_values`
do not exist.

- [ ] **Step 3: Implement `StateWrite` and patch views**

In `src/wf_core/run_state.py`, add `StateWrite` near runtime dataclasses:

```python
@dataclass(slots=True)
class StateWrite:
    path: StatePath
    incoming_value: Any
    visible_value: Any
    reducer: ReducerRef
```

Import `ReducerRef` and `StatePath`.

In `src/wf_core/runtime/ops/state.py`, change `StatePatch` to store ordered
writes and expose `changes` / `visible_values` properties. Keep `_staged_state`.

- [ ] **Step 4: Build write records in `build_output_patch`**

When `prepare_state_value(...)` returns a merged value, also capture the reducer
used for the destination. If needed, extract reducer lookup from
`prepare_state_value(...)` into a helper:

```python
def reducer_for_state_path(
    path: StatePath,
    state_fields: Mapping[StatePath, StateFieldDecl],
) -> ReducerRef:
    field = state_fields.get(path)
    return field.reducer if field and field.reducer else ReducerRef(name="wf.std.replace")
```

Create:

```python
StateWrite(
    path=destination_path,
    incoming_value=value,
    visible_value=merged_value,
    reducer=reducer,
)
```

- [ ] **Step 5: Replay incoming values in `build_barrier_patch`**

Update `build_barrier_patch(...)` to iterate over `item_patch.writes`, not over
`item_patch.changes.items()`. Replay `write.incoming_value` against the staged
state. The resulting barrier patch should contain one `StateWrite` per final
destination with both incoming and visible values set to the final committed
aggregate value, because the barrier is the public commit point.

- [ ] **Step 6: Run atomic patch tests**

Run:

```bash
uv run pytest tests/core/test_atomic_state_patches.py -q
```

Expected: pass.

---

## Task 2: Add Runtime Scopes and Root Lineage

Status: partially implemented. Frames and runtime context carry `scope_id`,
`lineage_id`, and `parent_lineage_id`, but `RunState.scopes`,
`RunState.lineages`, `RuntimeScope`, and `LineageState` are not implemented yet.
This is deliberate; foreach still stores pending writes in barrier metadata.

**Files:**

- Modify: `src/wf_core/run_state.py`
- Modify: `src/wf_core/runtime/ops/runs.py`
- Test: `tests/core/test_lineage_state.py`

- [ ] **Step 1: Add root initialization test**

Create `tests/core/test_lineage_state.py` with a local minimal workflow helper
that builds a tiny core `Workflow`. Then add:

```python
def test_create_run_state_initializes_root_scope_and_lineage() -> None:
    workflow = minimal_workflow()

    run = create_run_state(workflow, {"value": "seed"})

    assert run.scopes["root"].id == "root"
    assert run.scopes["root"].workflow_name == workflow.name
    assert run.scopes["root"].committed_state["value"] == "seed"
    assert run.lineages["root"].id == "root"
    assert run.lineages["root"].scope_id == "root"
    assert run.lineages["root"].parent_id is None
    assert run.lineages["root"].writes == []
    assert run.frames["root"].scope_id == "root"
    assert run.frames["root"].lineage_id == "root"
```

- [ ] **Step 2: Run expected failing test**

Run:

```bash
uv run pytest tests/core/test_lineage_state.py::test_create_run_state_initializes_root_scope_and_lineage -q
```

Expected: failure because `scopes`, `lineages`, `scope_id`, and `lineage_id`
do not exist.

- [ ] **Step 3: Add dataclasses and fields**

In `src/wf_core/run_state.py`, add `RuntimeScope` and `LineageState`. Add
`scope_id: str = "root"` and `lineage_id: str = "root"` to `ExecutionFrame`.
Add `scopes` and `lineages` to `RunState`.

- [ ] **Step 4: Initialize root scope and lineage**

In `src/wf_core/runtime/ops/runs.py`, initialize:

```python
run = RunState(
    workflow_name=workflow.name,
    status=RunStatus.PENDING,
    workflow_input=dict(workflow_input),
    state=state,
    scopes={
        "root": RuntimeScope(
            id="root",
            workflow_name=workflow.name,
            committed_state=state,
        )
    },
    lineages={"root": LineageState(id="root", scope_id="root")},
    current_frame_id="root",
    current_node_id=workflow.start,
)
```

The root scope may share the same dict object as `RunState.state` during this
migration.

- [ ] **Step 5: Run focused test**

Run:

```bash
uv run pytest tests/core/test_lineage_state.py -q
```

Expected: pass.

---

## Task 3: Add Lineage Runtime Helpers

Status: partially implemented. `LineageStateView` and
`lineage_writes_for_frame(run, frame)` exist in `src/wf_core/runtime/lineage.py`,
backed by current foreach metadata.

**Files:**

- Create: `src/wf_core/runtime/lineage.py`
- Test: `tests/core/test_lineage_state.py`

- [ ] **Step 1: Add helper tests**

Append:

```python
def test_lineage_state_view_applies_visible_values_only_for_reads() -> None:
    workflow = minimal_workflow()
    run = create_run_state(workflow, {"number": 2})
    add_lineage(run, scope_id="root", lineage_id="branch", parent_id="root")
    append_lineage_writes(
        run,
        scope_id="root",
        lineage_id="branch",
        writes=[
            StateWrite(
                path=StatePath(("number",)),
                incoming_value=3,
                visible_value=5,
                reducer=ReducerRef(name="wf.std.add"),
            )
        ],
    )

    view = lineage_state_view(run, scope_id="root", lineage_id="branch")

    assert view["number"] == 5
    assert run.state["number"] == 2


def test_lineage_write_patch_preserves_incoming_values_for_barrier_replay() -> None:
    workflow = minimal_workflow()
    run = create_run_state(workflow, {"number": 2})
    add_lineage(run, scope_id="root", lineage_id="branch", parent_id="root")
    append_lineage_writes(
        run,
        scope_id="root",
        lineage_id="branch",
        writes=[
            StateWrite(
                path=StatePath(("number",)),
                incoming_value=3,
                visible_value=5,
                reducer=ReducerRef(name="wf.std.add"),
            )
        ],
    )

    patch = lineage_patch(run, scope_id="root", lineage_id="branch")

    assert patch.writes[0].incoming_value == 3
    assert patch.writes[0].visible_value == 5
```

- [ ] **Step 2: Run expected failing tests**

Run:

```bash
uv run pytest tests/core/test_lineage_state.py -q
```

Expected: import failure for `wf_core.runtime.lineage`.

- [ ] **Step 3: Implement `runtime.lineage`**

Create helpers:

```python
def add_lineage(
    run: RunState, *, scope_id: str, lineage_id: str, parent_id: str
) -> None: ...

def append_lineage_writes(
    run: RunState,
    *,
    scope_id: str,
    lineage_id: str,
    writes: Sequence[StateWrite],
) -> None: ...

def lineage_patch(run: RunState, *, scope_id: str, lineage_id: str) -> StatePatch: ...

def lineage_state_view(
    run: RunState, *, scope_id: str, lineage_id: str
) -> dict[str, Any]: ...
```

`lineage_state_view(...)` should deep-copy `run.scopes[scope_id].committed_state`
and apply `write.visible_value` from ancestor/current lineage writes in order.
`lineage_patch(...)` should return ordered writes with incoming values intact.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/core/test_lineage_state.py -q
```

Expected: pass.

---

## Task 4: Route Node Reads and Non-Root Writes Through Lineage

**Files:**

- Modify: `src/wf_core/runtime/ops/overlays.py`
- Modify: `src/wf_core/runtime/ops/nodes.py`
- Test: `tests/core/test_lineage_state.py`

- [ ] **Step 1: Add non-root write buffering test**

Add a test with a one-node workflow that reads `state.value`, writes
`state.value`, and runs the frame with `lineage_id="child"`. Assert:

```python
assert result.state_changes == {}
assert run.state["value"] == "root"
assert run.lineages["child"].writes[0].incoming_value == "root-child"
assert lineage_state_view(run, scope_id="root", lineage_id="child")["value"] == "root-child"
```

- [ ] **Step 2: Run expected failing test**

Run:

```bash
uv run pytest tests/core/test_lineage_state.py::test_non_root_lineage_node_writes_are_buffered_not_committed -q
```

Expected: failure because node execution still commits or cannot read through
lineage.

- [ ] **Step 3: Update overlay facade**

`state_view_for_frame(run, frame)` should call:

```python
lineage_state_view(run, scope_id=frame.scope_id, lineage_id=frame.lineage_id)
```

For root scope/root lineage it may return `run.state` directly as an optimization.

- [ ] **Step 4: Update node finalization**

In `_finalize_node_execution(...)`:

- if `is_root_lineage_frame(frame)`, commit patch to `run.state`
- otherwise append `patch.writes` to the frame lineage and return empty committed
  `state_changes`

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/core/test_lineage_state.py tests/core/test_atomic_state_patches.py -q
```

Expected: pass.

---

## Task 5: Migrate Concurrent Foreach to Lineages

Status: implemented for new concurrent foreach results. Concurrent foreach
child frames have lineage ids, nested item lineages are tested, item writes are
stored in `RunState.lineages`, and pending item results persist `lineage_id`.
`ForeachBarrierState.patch` remains as a compatibility fallback.

**Files:**

- Modify: `src/wf_core/runtime/ops/foreach.py`
- Modify: `src/wf_core/runtime/foreach_state.py`
- Test: `tests/core/test_concurrent_foreach.py`
- Test: `tests/core/test_foreach_barrier_state.py`

- [ ] **Step 1: Add item lineage regression**

Add:

```python
def test_concurrent_foreach_item_frames_use_distinct_lineages() -> None:
    workflow = _workflow(mode="concurrent", concurrent={"max_active": 2})
    run = execute_workflow(workflow, {"items": ["a", "b"]}, {"record": _record_handler})

    item_frames = [frame for frame in run.frames.values() if frame.kind == "foreach_iteration"]

    assert len(item_frames) == 2
    assert item_frames[0].lineage_id != "root"
    assert item_frames[1].lineage_id != "root"
    assert item_frames[0].lineage_id != item_frames[1].lineage_id
```

- [ ] **Step 2: Add same-item read regression**

Add or keep a multi-step concurrent foreach test where item node 1 writes
`state.scratch`, item node 2 reads `state.scratch`, and siblings do not see each
other's scratch.

- [ ] **Step 3: Store lineage id on pending item result**

Add `lineage_id: str | None = None` to `PendingItemResult`, parse it from
metadata, and serialize it back. Keep old `patch` parse compatibility.

- [ ] **Step 4: Create item lineages on admission**

In `_admit_concurrent_children(...)`, before adding the child frame:

```python
child_lineage_id = child_id
add_lineage(
    run,
    scope_id=frame.scope_id,
    lineage_id=child_lineage_id,
    parent_id=frame.lineage_id,
)
```

Pass `scope_id=frame.scope_id` and `lineage_id=child_lineage_id` to the child
`ExecutionFrame`.

- [ ] **Step 5: Record completed lineage ids**

When a child completes, record `child.lineage_id` on the barrier pending result.
Do not copy flattened visible values into the barrier.

- [ ] **Step 6: Build barrier from lineage patches**

In `_finish_concurrent_foreach(...)`, construct `success_patches` from
`lineage_patch(run, scope_id=frame.scope_id, lineage_id=result.lineage_id)` for
new results. Keep existing `result.patch` fallback for old metadata.

- [ ] **Step 7: Run foreach tests**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py tests/core/test_concurrent_foreach_async.py tests/core/test_foreach_barrier_state.py -q
```

Expected: pass.

---

## Task 6: Remove Foreach-Specific Overlay Coupling

**Files:**

- Modify: `src/wf_core/runtime/ops/overlays.py`
- Modify: `src/wf_core/runtime/ops/nodes.py`
- Test: `tests/core`

- [ ] **Step 1: Remove foreach imports from node/overlay state path**

Ensure `ops/nodes.py` and `ops/overlays.py` do not import
`ForeachBarrierState` or `item_frame_owner`.

- [ ] **Step 2: Run core tests**

Run:

```bash
uv run pytest tests/core -q
```

Expected: pass.

---

## Task 7: Update Docs

**Files:**

- Modify: `docs/wf_core_architecture.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-05-24-native-subgraphs-design.md`

- [ ] **Step 1: Document scope/lineage**

Add a section explaining:

- scope is workflow state root
- frame is scheduler position
- lineage is pending write ownership
- concurrent foreach uses child lineages
- native subgraphs require child scopes

- [ ] **Step 2: Update native subgraph spec**

Ensure it says native subgraphs depend on child runtime scopes plus lineages,
not lineage alone.

- [ ] **Step 3: Run doc red-flag scan**

Run:

```bash
rg -n "U[N]RESOLVED|I[N]COMPLETE|F[I]LL_ME|D[E]CIDE_ME" docs/wf_core_architecture.md docs/current_roadmap.md docs/superpowers/specs/2026-05-24-native-subgraphs-design.md
```

Expected: no output.

---

## Task 8: Full Verification

- [ ] **Step 1: Run tests**

```bash
uv run pytest -q
```

- [ ] **Step 2: Run type check**

```bash
uv run basedpyright --level error src tests examples
```

- [ ] **Step 3: Run lint**

```bash
uvx ruff check src tests examples
```

- [ ] **Step 4: Run format check**

```bash
uvx ruff format --check src tests examples
```

---

## Self-Review

Spec coverage:

- Scope is represented explicitly and is available for native subgraph state
  roots.
- Lineage stores ordered replayable writes, not full state and not only visible
  values.
- `StatePatch` preserves incoming values for gather/barrier replay.
- Same-lineage reads use visible values.
- Concurrent foreach is the first migration target.

Type consistency:

- `StateWrite.incoming_value` is replay/trace input.
- `StateWrite.visible_value` is same-lineage read value.
- `RuntimeScope.committed_state` is scope-local committed state.
- `ExecutionFrame.scope_id` and `lineage_id` select visibility.
