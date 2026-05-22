# Concurrent Foreach Barrier Write Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce deterministic and explicit write semantics when concurrent foreach sibling item lineages commit at the barrier.

**Architecture:** Keep per-node patch building unchanged. Add a barrier-only validation step before replaying item patches: inspect all item patch destination paths, reject ambiguous sibling writes, and allow multi-writer paths only when the exact declared state path has a reducer whose metadata is `mergeable`. Barrier replay still happens in item-index order through existing reducer logic.

**Tech Stack:** Python 3.14, dataclasses, Pydantic v2 models, pytest, `StatePath`, `StateSchema.field_index()`, `StatePatch`, `ForeachBarrierState`, and existing reducer definitions.

---

## Semantics

This slice owns sibling write policy at a foreach barrier.

Allowed:

- A destination path written by exactly one item lineage uses normal state rules.
- A destination path written by multiple item lineages is allowed only if that exact declared state path has a `mergeable` reducer.
- Multi-writer reducer replay is deterministic item-index order.
- Multiple nodes inside the same item lineage may write multiple paths; that is item-local overlay behavior from Slice 2.

Rejected:

- Multiple sibling item lineages writing the same destination path with missing reducer/default replace.
- Multiple sibling item lineages writing the same destination path with an `exclusive` reducer such as `wf.std.replace`.
- Sibling item lineages writing ancestor/descendant paths such as `state.person` and `state.person.name`.

Important distinction:

- This is **not** normal node output validation. Node-level `build_output_patch(...)` still rejects overlapping output paths inside one node.
- This is **not** reducer implementation work. Existing reducers stay pure and domain-agnostic.
- This is **not** deep merge policy. Ancestor/descendant sibling writes are rejected for now.

---

## Files

- Modify: `src/wf_core/runtime/ops/state.py`
  - Add barrier write validation helpers.
  - Call them from `build_barrier_patch(...)` before replay.
- Test: `tests/core/test_concurrent_foreach.py`
  - Add end-to-end concurrent foreach conflict tests.
- Test: `tests/core/test_atomic_state_patches.py`
  - Add focused `build_barrier_patch(...)` unit tests if end-to-end setup becomes too noisy.
- Modify: `docs/adr/0002-concurrent-foreach-policy-and-barrier-commits.md`
  - Mark write semantics as implemented.
- Modify: `docs/superpowers/plans/2026-05-22-concurrent-foreach-phase4-roadmap.md`
  - Link this plan under Slice 3.

---

### Task 1: Add Focused Barrier Same-Path Tests

**Files:**
- Modify: `tests/core/test_atomic_state_patches.py`

- [ ] **Step 1: Add imports**

Ensure `tests/core/test_atomic_state_patches.py` imports:

```python
from wf_core.runtime.ops.state import StatePatch, build_barrier_patch
```

If `StatePatch` is already imported, only add `build_barrier_patch`.

- [ ] **Step 2: Add test for same-path writes without reducer**

Append:

```python
def test_barrier_rejects_sibling_same_path_writes_without_reducer() -> None:
    workflow = Workflow(
        name="barrier_conflict",
        input_schema=SchemaRef(properties={}),
        state_schema=StateSchema.from_field_map(
            {"value": StateField(type="string")}
        ),
        output_schema=SchemaRef(properties={}),
        node_defs=[],
        start="unused",
        nodes=[],
        edges=[],
    )

    with pytest.raises(WorkflowExecutionError, match="multiple sibling writes"):
        build_barrier_patch(
            workflow,
            [
                StatePatch(changes={"state.value": "a"}),
                StatePatch(changes={"state.value": "b"}),
            ],
            {},
        )
```

- [ ] **Step 3: Add test for explicit replace still rejected**

Append:

```python
def test_barrier_rejects_sibling_same_path_writes_with_explicit_replace() -> None:
    workflow = Workflow(
        name="barrier_replace_conflict",
        input_schema=SchemaRef(properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "value": StateField(
                    type="string",
                    reducer=ReducerRef(name="wf.std.replace"),
                )
            }
        ),
        output_schema=SchemaRef(properties={}),
        node_defs=[],
        start="unused",
        nodes=[],
        edges=[],
    )

    with pytest.raises(WorkflowExecutionError, match="requires an explicit reducer"):
        build_barrier_patch(
            workflow,
            [
                StatePatch(changes={"state.value": "a"}),
                StatePatch(changes={"state.value": "b"}),
            ],
            {},
        )
```

- [ ] **Step 4: Add test for explicit reducer allowing same-path writes**

Append:

```python
def test_barrier_allows_sibling_same_path_writes_with_non_replace_reducer() -> None:
    workflow = Workflow(
        name="barrier_reducer",
        input_schema=SchemaRef(properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "seen": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                )
            }
        ),
        output_schema=SchemaRef(properties={}),
        node_defs=[],
        start="unused",
        nodes=[],
        edges=[],
    )

    patch = build_barrier_patch(
        workflow,
        [
            StatePatch(changes={"state.seen": "a"}),
            StatePatch(changes={"state.seen": "b"}),
        ],
        {},
    )

    assert patch.changes["state.seen"] == ["a", "b"]
```

- [ ] **Step 5: Run tests and verify failures**

Run:

```bash
uv run pytest tests/core/test_atomic_state_patches.py::test_barrier_rejects_sibling_same_path_writes_without_reducer tests/core/test_atomic_state_patches.py::test_barrier_rejects_sibling_same_path_writes_with_explicit_replace tests/core/test_atomic_state_patches.py::test_barrier_allows_sibling_same_path_writes_with_non_replace_reducer -q
```

Expected before implementation:

```text
two reject tests fail because current barrier accepts replace semantics
```

The reducer test may already pass.

---

### Task 2: Add Ancestor/Descendant Conflict Tests

**Files:**
- Modify: `tests/core/test_atomic_state_patches.py`

- [ ] **Step 1: Add ancestor/descendant conflict test**

Append:

```python
def test_barrier_rejects_sibling_ancestor_descendant_writes() -> None:
    workflow = Workflow(
        name="barrier_ancestor_conflict",
        input_schema=SchemaRef(properties={}),
        state_schema=StateSchema.from_field_map(
            {
                "person": StateField(
                    type="object",
                    properties={"name": {"type": "string"}},
                ),
                "person.name": StateField(type="string"),
            }
        ),
        output_schema=SchemaRef(properties={}),
        node_defs=[],
        start="unused",
        nodes=[],
        edges=[],
    )

    with pytest.raises(WorkflowExecutionError, match="overlapping sibling writes"):
        build_barrier_patch(
            workflow,
            [
                StatePatch(changes={"state.person": {"name": "Ada"}}),
                StatePatch(changes={"state.person.name": "Grace"}),
            ],
            {},
        )
```

- [ ] **Step 2: Add same-item ancestor/descendant note test only if needed**

Do **not** add a same-item ancestor/descendant test unless current behavior changes unexpectedly. Same-node output overlap is already rejected by `build_output_patch(...)`, and multi-node same-item writes are item-local overlay behavior. This slice only owns sibling conflicts.

- [ ] **Step 3: Run focused test and verify failure**

Run:

```bash
uv run pytest tests/core/test_atomic_state_patches.py::test_barrier_rejects_sibling_ancestor_descendant_writes -q
```

Expected before implementation:

```text
FAILED because current barrier replays both writes
```

---

### Task 3: Implement Barrier Write Analysis

**Files:**
- Modify: `src/wf_core/runtime/ops/state.py`

- [ ] **Step 1: Add helper dataclass**

Near `StatePatch`, add:

```python
@dataclass(slots=True, frozen=True)
class _BarrierWrite:
    """One item-lineage write observed before a barrier commit."""

    item_index: int
    path: StatePath
    source_key: str
```

- [ ] **Step 2: Add explicit reducer predicate**

Add below `build_barrier_patch(...)` or near private helpers:

```python
def _has_explicit_non_replace_reducer(
    path: StatePath,
    state_fields: Mapping[StatePath, StateFieldDecl],
) -> bool:
    field = state_fields.get(path)
    if field is None or field.reducer is None:
        return False
    return field.reducer.name != "wf.std.replace"
```

If `StateFieldDecl.reducer` is never `None` for undeclared/default fields, inspect the actual model and adjust:

```python
    return field.reducer.name != "wf.std.replace"
```

but preserve the rule: only an explicit declared non-replace reducer allows sibling same-path writes.

- [ ] **Step 3: Add overlap predicate for barrier paths**

Add:

```python
def _state_paths_overlap(left: StatePath, right: StatePath) -> bool:
    left_parts = left.parts
    right_parts = right.parts
    return left_parts == right_parts or _is_prefix(left_parts, right_parts) or _is_prefix(
        right_parts,
        left_parts,
    )
```

- [ ] **Step 4: Add write collection helper**

Add:

```python
def _barrier_writes(item_patches: Sequence[StatePatch]) -> list[_BarrierWrite]:
    writes: list[_BarrierWrite] = []
    for item_index, item_patch in enumerate(item_patches):
        for destination in item_patch.changes:
            path = StatePath.parse(destination)
            writes.append(
                _BarrierWrite(
                    item_index=item_index,
                    path=path,
                    source_key=destination,
                )
            )
    return writes
```

Important: `item_index` here is the order in `item_patches`, which `foreach.py` already passes sorted by real item index. Do not infer item ids from path strings.

- [ ] **Step 5: Add validation helper**

Add:

```python
def validate_barrier_writes(
    item_patches: Sequence[StatePatch],
    state_fields: Mapping[StatePath, StateFieldDecl],
) -> None:
    """Reject ambiguous sibling writes before replaying a foreach barrier.

    Normal node patch validation handles one node output. This helper handles
    writes from different foreach item lineages that will commit together.
    """
    writes = _barrier_writes(item_patches)
    for index, left in enumerate(writes):
        for right in writes[index + 1 :]:
            if left.item_index == right.item_index:
                continue
            if left.path == right.path:
                if _has_explicit_non_replace_reducer(left.path, state_fields):
                    continue
                raise WorkflowExecutionError(
                    "multiple sibling writes to "
                    f"{left.source_key!r} require an explicit reducer"
                )
            if _state_paths_overlap(left.path, right.path):
                raise WorkflowExecutionError(
                    "overlapping sibling writes are not supported at a foreach "
                    f"barrier: {left.source_key!r} and {right.source_key!r}"
                )
```

- [ ] **Step 6: Call validation from `build_barrier_patch(...)`**

In `build_barrier_patch(...)`, after:

```python
    state_fields = workflow.state_schema.field_index()
```

add:

```python
    validate_barrier_writes(item_patches, state_fields)
```

- [ ] **Step 7: Verify focused unit tests**

Run:

```bash
uv run pytest tests/core/test_atomic_state_patches.py::test_barrier_rejects_sibling_same_path_writes_without_reducer tests/core/test_atomic_state_patches.py::test_barrier_rejects_sibling_same_path_writes_with_explicit_replace tests/core/test_atomic_state_patches.py::test_barrier_allows_sibling_same_path_writes_with_non_replace_reducer tests/core/test_atomic_state_patches.py::test_barrier_rejects_sibling_ancestor_descendant_writes -q
```

Expected: pass.

---

### Task 4: Add End-To-End Concurrent Foreach Coverage

**Files:**
- Modify: `tests/core/test_concurrent_foreach.py`

- [ ] **Step 1: Add same-path no-reducer workflow helper**

Append:

```python
def _same_path_replace_workflow() -> Workflow:
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "concurrent",
            "concurrent": {"max_active": 2, "max_outstanding": 2},
        }
    )
    return Workflow(
        name="concurrent_foreach_replace_conflict",
        input_schema=SchemaRef(
            type="object",
            properties={"items": {"type": "array"}},
        ),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "winner": StateField(type="string"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="write_winner",
                input_schema=SchemaRef(
                    type="object",
                    properties={"value": {}},
                    required=["value"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"winner": {}},
                    required=["winner"],
                ),
                outcomes=["ok"],
            )
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "write_winner",
                    "type": "node",
                    "node": "write_winner",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "winner", "target": "state.winner"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate(
                {"from": "each", "outcome": "loop", "to": "write_winner"}
            ),
            Edge.model_validate({"from": "write_winner", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
```

- [ ] **Step 2: Add end-to-end rejection test**

Append:

```python
def test_sync_concurrent_foreach_rejects_sibling_replace_writes() -> None:
    workflow = _same_path_replace_workflow()

    with pytest.raises(WorkflowExecutionError, match="explicit reducer"):
        execute_workflow(
            workflow,
            {"items": ["a", "b"]},
            {
                "write_winner": lambda payload, _ctx: {
                    "outcome": "ok",
                    "output": {"winner": payload["value"]},
                }
            },
        )
```

- [ ] **Step 3: Strengthen existing happy path**

The existing `test_sync_concurrent_foreach_interleaves_items_and_commits_at_barrier`
already proves explicit `wf.std.append` allows sibling writes to `state.seen`.
Do not duplicate it.

- [ ] **Step 4: Run focused end-to-end tests**

Run:

```bash
uv run pytest tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_rejects_sibling_replace_writes tests/core/test_concurrent_foreach.py::test_sync_concurrent_foreach_interleaves_items_and_commits_at_barrier -q
```

Expected: pass.

---

### Task 5: Update Docs

**Files:**
- Modify: `docs/adr/0002-concurrent-foreach-policy-and-barrier-commits.md`
- Modify: `docs/superpowers/plans/2026-05-22-concurrent-foreach-phase4-roadmap.md`

- [ ] **Step 1: Update ADR merge rules current state**

In `docs/adr/0002-concurrent-foreach-policy-and-barrier-commits.md`, under
`## Merge and Reducer Rules`, append:

```markdown
Current barrier validation enforces this policy for sibling foreach item
lineages. Same-path sibling writes require a `mergeable` reducer on the exact
destination state path. Ancestor/descendant sibling writes are rejected until a
future explicit deep merge policy exists.
```

- [ ] **Step 2: Update roadmap Slice 3**

In `docs/superpowers/plans/2026-05-22-concurrent-foreach-phase4-roadmap.md`,
under Slice 3, add:

```markdown
Plan:

- See [`2026-05-22-concurrent-foreach-barrier-write-semantics.md`](2026-05-22-concurrent-foreach-barrier-write-semantics.md).
```

If implementing immediately, also mark it as implemented in Current State after tests pass.

- [ ] **Step 3: Verify docs mentions**

Run:

```bash
rg -n "sibling writes|ancestor/descendant|explicit reducer|barrier write" docs/adr/0002-concurrent-foreach-policy-and-barrier-commits.md docs/superpowers/plans/2026-05-22-concurrent-foreach-phase4-roadmap.md
```

Expected: the ADR and roadmap both mention the semantics.

---

### Task 6: Verification

**Files:**
- No new source files.

- [ ] **Step 1: Run focused core tests**

Run:

```bash
uv run pytest tests/core/test_atomic_state_patches.py tests/core/test_concurrent_foreach.py tests/core/test_foreach_barrier_state.py -q
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

- Spec coverage: the plan covers same-path sibling writes, explicit reducer requirements, replace rejection, ancestor/descendant rejection, deterministic reducer order, end-to-end foreach behavior, and docs.
- Placeholder scan: all tasks include concrete code or exact commands; no TBD placeholders.
- Type consistency: the plan uses existing `StatePatch`, `StatePath`, `StateFieldDecl`, `ReducerRef`, `StateSchema.from_field_map`, and `WorkflowExecutionError`.
