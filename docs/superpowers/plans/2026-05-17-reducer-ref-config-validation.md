# ReducerRef Config Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace string-only reducer references with `ReducerRef(name, config)` and validate reducer config before state mutation.

**Architecture:** Keep string reducer input as shorthand, normalize it to a `ReducerRef`, and add `config_schema` to reducer specs. Runtime reducer application resolves the reducer spec, validates config through the existing JSON Schema backend, then calls reducer functions with `(current, incoming, config)`.

**Tech Stack:** Python, Pydantic, jsonschema, pytest, existing reducer registry.

---

## File Structure

- Modify `src/wf_core/models/reducers.py`
  - add `ReducerRef`
  - add `config_schema` to `ReducerSpec`
- Modify `src/wf_core/models/schemas.py`
  - make `StateField.reducer` a `ReducerRef` with string shorthand parsing
- Modify `src/wf_core/runtime/ops/merges.py`
  - reducer callable accepts config
  - validate config against reducer spec before merge
- Modify `src/wf_core/runtime/ops/state.py`
  - pass `ReducerRef` to reducer application
- Modify `src/wf_artifacts/factory.py`
  - infer reducer dependencies from `ReducerRef` objects and dict payloads
- Modify tests for core reducers and artifact dependency inference

## Tasks

### Task 1: Pin ReducerRef Behavior

- [ ] Add tests proving string shorthand normalizes to `ReducerRef(name=..., config={})`.
- [ ] Add tests proving object reducer payloads preserve config.
- [ ] Add tests proving invalid config fails before mutation.
- [ ] Run focused tests and confirm failure before implementation.

### Task 2: Implement ReducerRef and Config Validation

- [ ] Add `ReducerRef`.
- [ ] Add `ReducerSpec.config_schema`.
- [ ] Update reducer callables to accept config.
- [ ] Validate config before calling a reducer.
- [ ] Keep existing no-config reducers accepting `{}` only through their empty config schemas.

### Task 3: Update Artifact Dependency Inference

- [ ] Infer reducer dependency names from string reducers and object reducers.
- [ ] Keep dependency key by reducer name, not by reducer config.
- [ ] Run artifact factory tests.

### Task 4: Verify

- [ ] Run focused core/artifact tests.
- [ ] Run full suite.
- [ ] Run basedpyright.

## Non-Goals

- implementing `modulo_add`
- reducer decorator UX
- configurable reducer factories
- caching configured reducers
