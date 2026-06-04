# Nested Node-Local Mappings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let workflow maps address nested node-local input/output paths while preserving explicit state-mediated data flow and preparing state writes for future reducer libraries.

**Architecture:** Keep graph-facing paths unchanged. Add a small node-local path helper layer, validate non-overlapping write targets, construct nested node inputs from `in_map`, resolve nested node outputs from `out_map`, and refactor state writes into a prepared patch commit. Extract built-in merge-rule application behind a focused reducer-like module so future named reducer libraries can replace the dispatch seam without changing patch semantics.

**Tech Stack:** Python, Pydantic, pytest, existing `wf_core` path/state runtime.

---

## File Structure

- Modify `src/wf_core/paths.py`
  - keep graph-path helpers
  - add reusable path-overlap utility if it belongs at the generic path layer
- Create `src/wf_core/local_paths.py`
  - node-local dotted path parsing
  - nested get/set for node-local payloads
  - overlap checks for write targets
- Create `src/wf_core/runtime/ops/merges.py`
  - built-in exact-path merge-rule implementations
  - future seam for named reducer registry
- Modify `src/wf_core/runtime/ops/state.py`
  - replace per-write mutation loop with prepared patch commit
  - delegate merge-rule application to `merges.py`
- Modify `src/wf_core/runtime/ops/nodes.py`
  - build nested node inputs from `in_map`
  - resolve nested node outputs into state patch writes
- Modify `src/wf_core/validation/steps.py`
  - validate node-local top-level roots
  - reject overlapping write targets
- Add/modify tests under `tests/core/`
  - nested `in_map`
  - nested `out_map`
  - whole-object mapping still works
  - overlapping write targets rejected
  - missing nested output path fails
  - merge dispatch remains behaviorally unchanged

---

### Task 1: Pin Node-Local Path Behavior

**Files:**

- Modify: `tests/core/test_validation.py`
- Modify: `tests/core/test_runtime.py`

- [ ] **Step 1: Add failing validation tests**

Cover:

```python
def test_validation_allows_nested_node_local_paths() -> None:
    ...


def test_validation_rejects_overlapping_node_input_destinations() -> None:
    ...


def test_validation_rejects_overlapping_state_write_destinations() -> None:
    ...
```

Expected rules:

- `state.person.name -> user.name` is valid when `user` exists in the node input schema
- `user -> state.person` and `user.name -> state.person.name` in one `out_map` is invalid because destination state paths overlap
- `state.person -> user` plus `state.person.name -> user.name` in one `in_map` is invalid because destination node-local paths overlap

- [ ] **Step 2: Add failing runtime tests**

Cover:

```python
def test_runtime_builds_nested_node_input_from_in_map() -> None:
    ...


def test_runtime_reads_nested_node_output_from_out_map() -> None:
    ...


def test_runtime_missing_nested_node_output_path_fails() -> None:
    ...
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
uv run --with pytest pytest tests/core/test_validation.py tests/core/test_runtime.py -q
```

Expected: FAIL because node-local map sides are top-level-only today.

### Task 2: Add Node-Local Path Helpers

**Files:**

- Create: `src/wf_core/local_paths.py`
- Modify: `src/wf_core/validation/steps.py`

- [ ] **Step 1: Add minimal helper API**

Implement:

```python
def split_local_path(path: str) -> list[str]: ...
def get_local_value(payload: Mapping[str, Any], path: str) -> Any: ...
def set_local_value(payload: dict[str, Any], path: str, value: Any) -> None: ...
def paths_overlap(left: str, right: str) -> bool: ...
def has_overlapping_paths(paths: Iterable[str]) -> bool: ...
```

Rules:

- dotted local paths only
- no empty segments
- overlap means same path or ancestor/descendant path

- [ ] **Step 2: Update validation**

Use node-local path roots for schema checks:

```python
input_root = split_local_path(destination_path)[0]
output_root = split_local_path(source_path)[0]
```

Reject:

- overlapping `in_map` destination local paths
- overlapping `out_map` destination state paths

- [ ] **Step 3: Run focused validation tests**

Run:

```bash
uv run --with pytest pytest tests/core/test_validation.py -q
```

Expected: PASS for validation-specific cases.

### Task 3: Execute Nested Local Mappings

**Files:**

- Modify: `src/wf_core/runtime/ops/nodes.py`
- Modify: `src/wf_core/runtime/ops/state.py`

- [ ] **Step 1: Build nested node inputs**

Replace flat input construction with:

```python
resolved_input: dict[str, Any] = {}
for source_path, destination_path in node.in_map.items():
    value = safe_resolve_path(...)
    set_local_value(resolved_input, destination_path, value)
```

- [ ] **Step 2: Resolve nested node outputs**

When preparing mapped output writes, use `get_local_value()` for each `out_map`
source path instead of indexing only top-level output keys.

- [ ] **Step 3: Preserve missing-path failures**

Raise `WorkflowExecutionError` when a mapped nested output path is missing.

- [ ] **Step 4: Run focused runtime tests**

Run:

```bash
uv run --with pytest pytest tests/core/test_runtime.py -q
```

Expected: PASS for nested mapping behavior.

### Task 4: Introduce Prepared Patch Commits and Extract Merge Dispatch

**Files:**

- Create: `src/wf_core/runtime/ops/merges.py`
- Modify: `src/wf_core/runtime/ops/state.py`
- Modify: `tests/core/test_state_ops.py`

- [ ] **Step 1: Add failing patch-level tests**

Cover:

```python
def test_state_patch_rejects_overlapping_destinations_before_mutation() -> None:
    ...


def test_builtin_merge_rules_preserve_existing_behavior() -> None:
    ...
```

- [ ] **Step 2: Extract built-in merge implementations**

Move the current strategy body out of `write_state_value()` into focused helpers:

```python
def apply_builtin_merge(
    *,
    strategy: str,
    current_value: Any,
    incoming_value: Any,
    destination_path: str,
) -> Any: ...
```

Keep current semantics:

- `replace`
- `append`
- shallow `merge_object`

Add a docstring that this is the future seam for source-owned named reducers,
not custom reducer support yet.

- [ ] **Step 3: Prepare full write sets before mutation**

Refactor output mapping so it:

1. resolves all mapped output values
2. validates destination overlap
3. prepares the patch
4. applies merge behavior

No state changes should occur before all mapped output paths are known-good.

- [ ] **Step 4: Run state/runtime tests**

Run:

```bash
uv run --with pytest pytest tests/core/test_state_ops.py tests/core/test_runtime.py -q
```

Expected: PASS.

### Task 5: Keep Authoring and Docs Aligned

**Files:**

- Modify: `src/wf_authoring/builder/mapping.py`
- Modify: `docs/core_state_mapping_and_merge.md` if implementation details differ
- Modify: `docs/scratchpad.md` only if wording drift appears
- Modify/Add: authoring tests as needed

- [ ] **Step 1: Confirm authoring auto-maps remain top-level**

Automatic maps should stay conservative unless there is an explicit reason to
infer nested paths. The new feature is for explicit maps first.

- [ ] **Step 2: Add one authoring regression**

Prove that a builder can compile a workflow using explicit nested local map
paths without extra helper nodes.

- [ ] **Step 3: Update docs only for implementation drift**

The design doc already states the target behavior. Keep docs in sync with final
names and module boundaries, but do not broaden scope into nested state
declarations yet.

### Task 6: Verify the Whole Project

**Files:**

- No additional files.

- [ ] **Step 1: Run focused suites**

```bash
uv run --with pytest pytest tests/core tests/authoring -q
```

- [ ] **Step 2: Run the full suite**

```bash
uv run --with pytest pytest -q
```

- [ ] **Step 3: Run type checking**

```bash
uv run basedpyright --level error
```

Expected:

- tests pass
- any remaining basedpyright failures are called out explicitly if they come
  from existing generated/build/doc-fixture noise rather than this work

---

## Deliberate Non-Goals

- nested declared state merge metadata
- reducer capability registry
- deep merge behavior
- native subgraphs
- parallel foreach
- automatic inference of nested maps from schemas

## Follow-On Plans

After this lands:

1. nested declared state paths with exact-path merge lookup
2. reducer capability model / registry seam
3. native subgraph design on the same map + patch boundary
4. async-only parallel foreach using patch combination rules
