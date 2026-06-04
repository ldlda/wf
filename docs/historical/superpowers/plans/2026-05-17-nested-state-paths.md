# Nested State Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `wf_core` declare nested workflow state paths and apply merge behavior by exact destination path.

**Architecture:** Keep state declarations internally flat and path-keyed. Continue allowing undeclared state paths, but only exact declared paths receive typed merge behavior; parent declarations do not implicitly govern descendants. Reuse the state patch boundary added in Phase 1 and change only schema wording, validation coverage, runtime lookup, and docs.

**Tech Stack:** Python, Pydantic, pytest, existing `wf_core` state runtime.

---

## File Structure

- Modify `src/wf_core/models/schemas.py`
  - clarify that `StateField` / `StateSchema` are path-keyed, not root-only
- Modify `src/wf_core/runtime/ops/state.py`
  - resolve merge metadata by exact written state path
- Add `tests/core/test_nested_state_paths.py`
  - exact nested path merge behavior
  - ancestor declarations do not govern descendants
  - undeclared nested paths still replace
- Update `docs/core_state_mapping_and_merge.md`
  - mark nested declared state paths as implemented
- Update `docs/schema_validation.md`
  - clarify that runtime state merge metadata is now exact-path capable

### Task 1: Pin Exact-Path State Behavior

- [ ] Add failing tests proving:
  - `state.person.tags` uses a declaration for `"person.tags"` with `append`
  - a declaration for `"person"` does not cause `state.person.tags` to inherit `merge_object`
  - undeclared `state.person.tags` defaults to `replace`
- [ ] Run the focused tests and confirm the nested exact-path cases fail under the current root-only lookup.

### Task 2: Implement Exact-Path Lookup

- [ ] Update state model docstrings to describe path-keyed declarations.
- [ ] In `write_state_value()`, look up `workflow.state_schema.fields[".".join(parts)]` instead of only the first path segment.
- [ ] Keep undeclared paths as `replace`.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Keep Docs Honest

- [ ] Update the core mapping design doc so Phase 2 is recorded as implemented, not future work.
- [ ] Update schema-validation docs to note exact-path state metadata without broadening payload validation claims.

### Task 4: Verify

- [ ] Run `uv run --with pytest pytest tests/core -q`
- [ ] Run `uv run --with pytest pytest -q`
- [ ] Run `uv run basedpyright --level error`
- [ ] Call out any residual type-check failures that are unrelated to this work.

## Non-Goals

- flatten nested authoring schemas from `wf_authoring`
- reducer registries or custom reducer capabilities
- changing `merge_object` from shallow to deep
- making parent declarations inherit into child paths
- `START` token model changes
