# Reducer Source Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Represent reducers as first-class source-owned capabilities and expose the built-in reducer catalog through existing source inventory.

**Architecture:** Add a small immutable `ReducerSpec` model in `wf_core`, keep runtime reducer execution where it is, and extend `wf_mcp` capability buckets with reducer ownership metadata. Register the three built-in reducer specs under `wf.std` so inventory becomes honest without adding reducer-authoring UX yet.

**Tech Stack:** Python, dataclasses/Pydantic, pytest, existing capability source inventory.

---

## File Structure

- Create `src/wf_core/models/reducers.py`
  - reducer capability metadata
- Modify `src/wf_core/models/__init__.py` and `src/wf_core/__init__.py`
  - export `ReducerSpec`
- Modify `src/wf_mcp/broker/service/capability_sources.py`
  - add reducer bucket, counts, and inventory listing
- Modify `src/wf_mcp/broker/service/builtins.py`
  - define/register built-in reducer specs under `wf.std`
- Modify `tests/wf_mcp/test_service.py`
  - assert reducer inventory
- Update `docs/wf_mcp_capability_sources.md`
  - document reducers under `wf.std`
- Update `docs/workflow_capabilities.md`
  - name reducers as workflow-facing capabilities

## Tasks

### Task 1: Pin Inventory Behavior

- [ ] Add failing tests proving:
  - `wf.std` owns built-in reducers
  - source status exposes `reducer_count`
  - source inventory exposes reducer names
- [ ] Run focused service tests and confirm failure before implementation.

### Task 2: Add ReducerSpec and Source Buckets

- [ ] Add `ReducerSpec` with `name`, `description`, and optional value-shape notes.
- [ ] Export `ReducerSpec` from core.
- [ ] Extend `CapabilityBuckets`, `as_status()`, and `as_inventory()` with reducers.
- [ ] Register `wf.std.replace`, `wf.std.append`, and `wf.std.merge_object` in built-ins.
- [ ] Run focused service tests and confirm they pass.

### Task 3: Update Docs

- [ ] Add reducers to the source vocabulary docs.
- [ ] Clarify that reducers are selected from sources; LLMs are not expected to author reducer code.

### Task 4: Verify

- [ ] Run `uv run --with pytest pytest tests/wf_mcp -q`
- [ ] Run `uv run --with pytest pytest -q`
- [ ] Run `uv run basedpyright --level error`

## Non-Goals

- reducer decorators
- reducer runtime dependency resolution from external sources
- reducer MCP tools
- non-built-in reducer libraries
