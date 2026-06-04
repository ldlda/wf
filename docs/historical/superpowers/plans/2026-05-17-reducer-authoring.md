# Reducer Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Python authoring ergonomics for reducer definitions, including optional Pydantic config models.

**Architecture:** Keep `wf_core` reducer execution as the runtime layer. Add `wf_authoring.reducers` as the ergonomic layer that builds `ReducerDefinition` objects from Python functions, similar to how node authoring builds `NodeSpec`s. Config models are optional; when present, they generate `ReducerSpec.config_schema` and receive parsed config objects at call time.

**Tech Stack:** Python, Pydantic `BaseModel`, pytest, existing reducer runtime.

---

## File Structure

- Create `src/wf_authoring/reducers/`
  - `callables.py`: reducer callable protocols
  - `decorator.py`: `@reducer(...)`
  - `catalog.py`: `ReducerCatalog`
  - `__init__.py`: reducer authoring exports
- Modify `src/wf_authoring/__init__.py`
  - export reducer authoring API
- Add `tests/authoring/test_reducers.py`
  - plain reducer authoring
  - configured reducer authoring with BaseModel config
  - catalog specs/definitions

## Tasks

### Task 1: Pin Authoring API

- [ ] Add tests proving:
  - `@reducer(name="wf.std.add")` wraps a two-arg callable
  - `@reducer(name="wf.std.modulo_add", config_model=ModuloConfig)` wraps a callable receiving parsed config
  - config model JSON Schema becomes `ReducerSpec.config_schema`
  - `ReducerCatalog.from_reducers(...)` exposes definitions and specs
- [ ] Run focused tests and confirm failure before implementation.

### Task 2: Implement Reducer Authoring

- [ ] Add typed callable protocols for plain/config reducers.
- [ ] Add a small wrapper object that owns a `ReducerDefinition`.
- [ ] Add `@reducer(...)` overloads for bare and configured reducers.
- [ ] Add `ReducerCatalog`.
- [ ] Export from `wf_authoring`.

### Task 3: Verify

- [ ] Run `uv run --with pytest pytest tests/authoring/test_reducers.py -q`
- [ ] Run `uv run --with pytest pytest tests/authoring -q`
- [ ] Run full suite and basedpyright.

## Non-Goals

- MCP tools for authoring reducers
- LLM-authored reducer code
- external reducer packages
- replacing current built-in registration in this pass
