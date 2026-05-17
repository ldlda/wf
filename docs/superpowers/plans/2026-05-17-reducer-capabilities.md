# Reducer Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `merge_strategy` with named pure reducer references across core and authoring, using `wf.std.replace` as the default reducer.

**Architecture:** Introduce a small reducer registry in `wf_core`, register the current three built-ins as reducers, and have state writes resolve every declared reducer name through that registry. Keep undeclared state paths using default replace semantics. Migrate `wf_authoring.state_field()` and all state metadata/tests/docs to reducer names in the same pass so there is one merge concept in the codebase.

**Tech Stack:** Python, Pydantic, pytest, existing `wf_core` runtime and `wf_authoring` schema projection.

---

## File Structure

- Modify `src/wf_core/models/schemas.py`
  - replace `merge_strategy` with `reducer`
- Replace/refactor `src/wf_core/runtime/ops/merges.py`
  - reducer callable type
  - built-in reducer functions
  - default reducer registry
  - reducer application helper
- Modify `src/wf_core/runtime/ops/state.py`
  - resolve reducer names from state fields
  - use default replace reducer for undeclared paths
- Modify `src/wf_authoring/schemas.py`
  - expose `state_field(reducer=...)`
  - project reducer metadata through flattened state paths
- Modify tests under `tests/core/`, `tests/authoring/`, and `tests/rewrite/`
  - migrate old metadata
  - add unknown reducer coverage
- Update docs mentioning `merge_strategy`

## Tasks

### Task 1: Pin Reducer Semantics

- [ ] Add tests proving:
  - `StateField(type="string")` defaults to `wf.std.replace`
  - `wf.std.append` preserves append behavior
  - `wf.std.merge_object` preserves shallow object merge behavior
  - unknown reducer names fail clearly
  - exact nested state paths still use their own reducer
- [ ] Run focused core tests and confirm failure before implementation.

### Task 2: Replace Core Merge Strategy With Reducers

- [ ] Replace `merge_strategy` on `StateField` with `reducer`.
- [ ] Add reducer functions for `wf.std.replace`, `wf.std.append`, and `wf.std.merge_object`.
- [ ] Add a registry lookup path that raises for unknown reducer names.
- [ ] Update `write_state_value()` to resolve declared reducers and use `wf.std.replace` for undeclared paths.
- [ ] Run focused core tests and confirm reducer behavior is green.

### Task 3: Migrate Authoring

- [ ] Change `StateFieldMetadata` and `state_field()` to use `reducer`.
- [ ] Preserve nested metadata projection under reducer names.
- [ ] Update authoring/rewrite fixtures from `merge_strategy=` to `reducer=`.
- [ ] Run focused authoring tests and confirm they pass.

### Task 4: Update Docs

- [ ] Replace docs that describe `merge_strategy` with reducer terminology.
- [ ] Update examples to show reducer names, including the default replace reducer.
- [ ] Keep the design point that reducers are pure and source-owned.

### Task 5: Verify

- [ ] Run `uv run --with pytest pytest tests/core tests/authoring tests/rewrite -q`
- [ ] Run `uv run --with pytest pytest -q`
- [ ] Run `uv run basedpyright --level error`

## Non-Goals

- custom user-authored reducer registration through MCP/platform sources
- reducer parameters/configuration
- async reducers
- parallel foreach
- compatibility shims for `merge_strategy`
