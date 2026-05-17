# Nested Authoring State Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `wf_authoring` project nested authored state schemas into the flat exact-path state-field index that `wf_core` now supports.

**Architecture:** Keep authored JSON Schema nested for users and LLM clients. Add a focused flattening helper for state-field projection only, emitting both parent object paths and descendant paths. Resolve nested `BaseModel` metadata by authored path where available, while leaving non-`BaseModel` authored types schema-capable with default merge metadata.

**Tech Stack:** Python, Pydantic, pytest, existing `wf_authoring` schema adapter.

---

## File Structure

- Modify `src/wf_authoring/schemas.py`
  - flatten nested schema properties into exact-path `StateField`s
  - gather nested `BaseModel` metadata by authored path
- Modify `tests/authoring/helpers.py`
  - add nested state models used by tests
- Modify `tests/authoring/test_schemas.py`
  - pin nested projection behavior and nested metadata
- Update `docs/core_state_mapping_and_merge.md`
  - note that authoring now projects nested authored models into the flat core index

## Tasks

### Task 1: Pin Nested Projection

- [ ] Add tests proving:
  - nested authored state keeps parent and child declarations
  - nested child metadata such as `append` lands on the exact child path
  - parent object declaration remains independent from child declarations
- [ ] Run the focused authoring tests and confirm they fail under current top-level-only projection.

### Task 2: Implement Projection Helpers

- [ ] Add a schema-walking helper that yields `(path, property_schema)` for parent and descendant properties.
- [ ] Add nested `BaseModel` metadata traversal keyed by dotted path.
- [ ] Update `state_schema_from()` to build `StateField`s from the flattened path stream.
- [ ] Keep JSON Schema generation unchanged; flatten only the core `StateSchema.fields` index.
- [ ] Run the focused authoring tests and confirm they pass.

### Task 3: Document and Verify

- [ ] Update the core state mapping doc with the authoring projection rule.
- [ ] Run `uv run --with pytest pytest tests/authoring -q`
- [ ] Run `uv run --with pytest pytest -q`
- [ ] Run `uv run basedpyright --level error`

## Non-Goals

- custom metadata support for every Pydantic-supported type form
- changing `SchemaRef` shape
- reducer registries
- automatic deep merge behavior
