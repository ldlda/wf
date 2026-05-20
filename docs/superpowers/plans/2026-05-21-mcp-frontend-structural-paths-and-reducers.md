# MCP Frontend Structural Paths and Reducers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose structural graph paths, canonical builder bindings, and structural reducer refs through the MCP/workflow frontend so LLM clients stop learning dotted-string separator conventions as canonical.

**Architecture:** Treat MCP as a frontend over the platform model, not the source of truth. The MCP tools should accept compatibility strings where existing users need them, but list/inspect/create responses should prefer canonical structs: `input` / `output` binding lists, path `{root, parts}` objects, and reducer refs with structural `ref` objects for configured reducers. Existing raw-plan escape hatches remain, but the recommended workflow-authoring path should produce canonical model-shaped JSON.

**Tech Stack:** Python 3.14, Pydantic v2, `wf_mcp.workflow_surface`, `wf_artifacts.drafts`, `wf_artifacts.factory`, `wf_core` models, pytest, basedpyright, ruff.

---

## Dependency

Run this plan **after**:

```text
2026-05-21-reducer-ref-structural-capability.md
```

because MCP should expose the final `ReducerRef` model shape, not invent a parallel frontend shape.

---

## Current Problems

MCP/workflow frontend still has several old shapes:

- workflow plans and draft APIs often show `in_map`, `input_values`, `out_map`
- state schema examples still use legacy `fields`
- reducer refs are often shown as dotted strings only
- inspect/list tool outputs may not clearly distinguish canonical structs from display strings

The result: an LLM client can build runnable workflows, but it learns the wrong authoring shape and then has to guess separator semantics.

---

## Target Frontend Shape

Recommended node use shape:

```json
{
  "id": "echo",
  "type": "node",
  "node": "demo.echo",
  "input": [
    {
      "target": {"root": "local", "parts": ["text"]},
      "path": {"root": "input", "parts": ["text"]}
    },
    {
      "target": {"root": "local", "parts": ["limit"]},
      "value": 3
    }
  ],
  "output": [
    {
      "source": {"root": "local", "parts": ["echoed"]},
      "target": {"root": "state", "parts": ["echoed"]}
    }
  ]
}
```

Recommended configured reducer shape:

```json
{
  "ref": {"source": "wf.std", "capability_key": "modulo_add"},
  "config": {"modulus": 10}
}
```

Compact unconfigured reducer shorthand remains accepted:

```json
"wf.std.add"
```

---

## File Structure

- Inspect/modify: `src/wf_mcp/workflow_surface/models.py`
  - Request/response models for create/compile/validate/call workflow tools

- Inspect/modify: `src/wf_mcp/workflow_surface/handlers.py`
  - create draft/workflow helpers
  - source/capability inspection payloads

- Inspect/modify: `src/wf_mcp/workflow_surface/tools.py`
  - MCP tool schemas/descriptions

- Inspect/modify: `src/wf_artifacts/drafts/models.py`
  - draft step/input/output shape if drafts still generate raw maps

- Inspect/modify: `src/wf_artifacts/drafts/adapter.py`
  - draft-to-builder compile path; should use canonical `input` / `output`

- Inspect/modify docs:
  - `docs/wf_mcp_operator_manual.md`
  - `docs/workflow_drafts.md`
  - `docs/wf_mcp_end_to_end_runbook.md`
  - `docs/structural_refs.md`

- Tests:
  - `tests/wf_mcp/test_workflow_surface.py`
  - `tests/wf_mcp/test_workflow_wrapper_hints.py`
  - `tests/artifacts/test_draft_adapter.py`
  - `tests/artifacts/test_draft_models.py`
  - `tests/artifacts/test_draft_api.py`

---

## Task 1: Inventory MCP/Draft Surfaces That Emit Map Sugar

**Files:**
- Read-only first:
  - `src/wf_mcp/workflow_surface/models.py`
  - `src/wf_mcp/workflow_surface/handlers.py`
  - `src/wf_artifacts/drafts/models.py`
  - `src/wf_artifacts/drafts/adapter.py`

- [ ] **Step 1: Search old map fields**

Run:

```bash
rg -n '"in_map"|in_map|input_values|"out_map"|out_map|fields' src/wf_mcp src/wf_artifacts tests/wf_mcp tests/artifacts docs -g '*.py' -g '*.md'
```

- [ ] **Step 2: Categorize each hit**

Use these categories:

- compatibility input still accepted
- canonical output should be changed
- test fixture using old shape intentionally
- docs/example should migrate

- [ ] **Step 3: Write findings into this plan or a short docs note**

Add a small checklist under this task before implementation. Do not blindly replace all strings.

Findings from the first inventory pass:

- `src/wf_artifacts/drafts/adapter.py` is the highest-value runtime hit: it still
  calls `WorkflowBuilder.use_ref(..., in_map=..., input_values=..., out_map=...)`
  and `WorkflowBuilder.use(..., out_map=...)`, causing deprecation warnings from
  MCP draft/workspace tests. This should be changed to canonical binding lists.
- Raw workflow-plan tests in `tests/wf_mcp/test_service.py`,
  `tests/wf_mcp/test_broker_server.py`, `tests/wf_mcp/test_workflow_surface.py`,
  and `tests/artifacts/test_factory.py` intentionally exercise raw-plan
  compatibility. Do not bulk-rewrite those while raw-plan escape hatches remain.
- Draft model tests still use `state_schema.fields` as compatibility input. That
  can stay as parse input, but new docs/examples should prefer JSON Schema
  `properties`.
- Docs already explain parse-only compatibility in several places, but older
  operator/runbook examples still need canonical `input` / `output` examples.

---

## Task 2: Draft Adapter Emits Canonical Builder Bindings

**Files:**
- Modify: `src/wf_artifacts/drafts/adapter.py`
- Modify: `tests/artifacts/test_draft_adapter.py`

- [ ] **Step 1: Add/adjust test**

Add a test proving a draft compiles through `WorkflowBuilder.use_ref(..., input=[...], output=[...])` or directly produces canonical `NodeUse.input` / `output`.

Expected assertion:

```python
node = workflow.nodes[0]
dumped = node.model_dump(mode="json")
assert "in_map" not in dumped
assert "out_map" not in dumped
assert dumped["input"][0]["target"] == {"root": "local", "parts": ["text"]}
assert dumped["input"][0]["path"] == {"root": "input", "parts": ["text"]}
```

- [ ] **Step 2: Update adapter**

Where it currently calls:

```python
builder.use_ref(..., in_map=step.in_, input_values=..., out_map=step.out)
```

convert draft structures into:

```python
input=[...]
output=[...]
```

If draft models still store maps, transform them into canonical binding dicts at the adapter boundary.

- [ ] **Step 3: Run draft adapter tests**

```bash
uv run --with pytest pytest tests/artifacts/test_draft_adapter.py -q
```

Expected: pass and no new deprecation warnings from the adapter.

---

## Task 3: Workflow Surface Requests Prefer Canonical Shapes

**Files:**
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Add schema tests for canonical binding request fields**

Find the create/compile draft request model and assert its JSON Schema includes:

```json
"input": {"type": "array", ...}
"output": {"type": "array", ...}
```

and does not force `in_map` / `out_map` as the primary example.

- [ ] **Step 2: Update Pydantic models**

Prefer these field names in MCP-facing request models:

```python
input: list[InputBindingLike] = Field(default_factory=list, description=...)
output: list[OutputBindingLike] = Field(default_factory=list, description=...)
```

If compatibility maps remain:

```python
in_map: dict[str, str] | None = Field(default=None, deprecated=True, description=...)
out_map: dict[str, str] | None = Field(default=None, deprecated=True, description=...)
```

If Pydantic `deprecated=True` causes schema issues, document deprecation in descriptions instead.

- [ ] **Step 3: Update handlers**

Handlers should pass canonical lists to builder/artifact APIs.

- [ ] **Step 4: Run workflow surface tests**

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface.py -q
```

Expected: pass.

---

## Task 4: Inspect/List Outputs Show Canonical Refs and Display Strings Separately

**Files:**
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `src/wf_platform/sources.py` if inventory models need fields
- Modify: tests in `tests/wf_mcp`

- [ ] **Step 1: Add response-shape assertions**

For source/capability inspection responses, assert reducers include enough info:

```json
{
  "name": "wf.std.add",
  "ref": {"source": "wf.std", "capability_key": "add"},
  "description": "..."
}
```

Use `name` as display, `ref` as canonical.

- [ ] **Step 2: Update inventory models only if needed**

If `ReducerInventory` currently has only `name`, add:

```python
ref: CapabilityRef
```

or a serializable equivalent.

Keep old `name` for display.

- [ ] **Step 3: Run platform/MCP inventory tests**

```bash
uv run --with pytest pytest tests/platform/test_inventory.py tests/wf_mcp/test_service.py tests/wf_mcp/test_workflow_surface.py -q
```

Expected: pass.

---

## Task 5: Docs and MCP Tool Descriptions

**Files:**
- Modify: `docs/wf_mcp_operator_manual.md`
- Modify: `docs/workflow_drafts.md`
- Modify: `docs/wf_mcp_end_to_end_runbook.md`
- Modify: `docs/structural_refs.md`
- Modify MCP tool descriptions in `src/wf_mcp/workflow_surface/tools.py` if needed

- [ ] **Step 1: Replace primary examples**

Replace examples that teach:

```json
"in_map": {"input.text": "text"}
```

with:

```json
"input": [{"target": {"root": "local", "parts": ["text"]}, "path": {"root": "input", "parts": ["text"]}}]
```

- [ ] **Step 2: Keep compatibility notes**

Add:

```text
`in_map`, `input_values`, and `out_map` are compatibility inputs. New MCP/JSON
clients should use `input` and `output` binding lists.
```

- [ ] **Step 3: Update reducer examples**

Show:

```json
"reducer": "wf.std.add"
```

for compact unconfigured reducers, and:

```json
"reducer": {
  "ref": {"source": "wf.std", "capability_key": "modulo_add"},
  "config": {"modulus": 10}
}
```

for configured reducers.

---

## Task 6: Verification

- [ ] **Step 1: Focused artifact/MCP tests**

```bash
uv run --with pytest pytest tests/artifacts/test_draft_adapter.py tests/artifacts/test_draft_models.py tests/artifacts/test_draft_api.py tests/wf_mcp/test_workflow_surface.py tests/wf_mcp/test_workflow_wrapper_hints.py -q
```

- [ ] **Step 2: Full tests**

```bash
uv run --with pytest pytest -q
```

- [ ] **Step 3: Static checks**

```bash
uvx ruff check src/wf_mcp src/wf_artifacts tests/wf_mcp tests/artifacts
uvx ruff format --check src/wf_mcp src/wf_artifacts tests/wf_mcp tests/artifacts
uv run basedpyright --level error src/wf_mcp src/wf_artifacts tests/wf_mcp tests/artifacts
```

Expected:

- tests pass
- ruff passes
- basedpyright reports `0 errors`

---

## Self-Review Checklist

- MCP-facing examples prefer canonical binding lists.
- Compatibility maps remain accepted where documented.
- Draft adapter no longer emits deprecated builder sugar warnings.
- Reducer refs display `name` and canonical `ref` distinctly where inventory exposes them.
- No MCP handler reparses reducer dotted names by first/last dot.
