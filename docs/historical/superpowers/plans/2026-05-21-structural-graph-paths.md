# Structural Graph Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save canonical graph paths as structural objects while keeping old dotted strings as parse-only compatibility input.

**Architecture:** The core already has first-class path types: `GraphSourcePath`, `StatePath`, and `LocalPath`. Update those Pydantic hooks to accept structural dict input and serialize structurally in JSON mode. Keep `str(path)` for display and legacy fields. Do not redesign `NodeUse.input` / `output`; those structs already replaced deprecated `in_map` / `out_map`.

**Tech Stack:** Python 3.14, Pydantic core schema hooks, `wf_core.paths`, `wf_core.models.steps`, pytest.

---

## Current State

Canonical node bindings already exist:

```json
{
  "input": [{ "path": "input.message", "target": "message" }],
  "output": [{ "source": "echoed", "target": "state.echoed" }]
}
```

Internally these parse to:

- `GraphSourcePath`
- `LocalPath`
- `StatePath`

The remaining problem is serialization. These path objects currently dump as strings, so saved JSON still relies on dot-separated path grammar.

## Canonical Shape

Graph source paths:

```json
{ "root": "state", "parts": ["person", "name"] }
```

State write paths:

```json
{ "root": "state", "parts": ["person", "name"] }
```

Local node paths:

```json
{ "root": "local", "parts": ["payload", "text"] }
```

Local root remains explicit:

```json
{ "root": "local", "parts": [] }
```

Old strings such as `"state.person.name"` and `"."` remain accepted input.

---

## Task 1: Add Structural Serialization for Path Types

**Files:**

- Modify: `src/wf_core/paths.py`
- Test: `tests/core/test_path_values.py`

- [ ] **Step 1: Update tests first**

Change `test_pydantic_accepts_path_strings_and_serializes_strings` into structural JSON expectations:

```python
dumped = payload.model_dump(mode="json")
assert dumped["source"] == {"root": "input", "parts": ["user"]}
assert dumped["target"] == {"root": "state", "parts": ["person"]}
assert dumped["local"] == {"root": "local", "parts": ["user"]}
```

Keep `model_dump()` expectations if useful for Python-mode compatibility only if the implementation intentionally keeps Python mode as strings. Otherwise assert structural dumps in both modes.

- [ ] **Step 2: Add structural input tests**

Add a test:

```python
payload = Payload.model_validate({
    "source": {"root": "input", "parts": ["user.name"]},
    "target": {"root": "state", "parts": ["person.name"]},
    "local": {"root": "local", "parts": ["payload.text"]},
})

assert payload.source == GraphSourcePath.input("user.name")
assert payload.target == StatePath.of("person.name")
assert payload.local == LocalPath.of("payload.text")
```

This documents that structural `parts` are literal field names. Old string inputs still split on dots for compatibility, but structural parts such as `"user.name"` are not split again.

- [ ] **Step 3: Implement path serializers**

In `src/wf_core/paths.py`, update each path type:

- `LocalPath` accepts string, object instance, and dict `{"root": "local", "parts": list[str]}`
- `GraphSourcePath` accepts string, object instance, and dict `{"root": "input"|"state"|"context", "parts": list[str]}`
- `StatePath` accepts string, object instance, and dict `{"root": "state", "parts": list[str]}`

Serialize as dicts in JSON mode:

```python
{"root": "local", "parts": list(value.parts)}
{"root": value.root, "parts": list(value.parts)}
{"root": "state", "parts": list(value.parts)}
```

- [ ] **Step 4: Run focused path tests**

Run:

```bash
uv run --with pytest pytest tests/core/test_path_values.py -q
```

Expected: all tests pass.

---

## Task 2: Update Canonical Node Binding Dumps

**Files:**

- Test: `tests/core/test_canonical_node_bindings.py`
- Test: `tests/authoring/test_builder.py`

- [ ] **Step 1: Update canonical node dump expectations**

In `tests/core/test_canonical_node_bindings.py`, update JSON-mode expectations:

```python
assert dumped["input"][1]["path"] == {"root": "input", "parts": ["message"]}
assert dumped["input"][1]["target"] == {"root": "local", "parts": ["message"]}
assert dumped["output"][0]["source"] == {"root": "local", "parts": ["echoed"]}
assert dumped["output"][0]["target"] == {"root": "state", "parts": ["echoed"]}
```

Deprecated `in_map` / `out_map` inputs should continue parsing, but dumps must omit those old fields and emit structural paths.

- [ ] **Step 2: Update authoring serialization expectations**

In `tests/authoring/test_builder.py`, update any `model_dump(mode="json")` expectations that currently assert path strings.

- [ ] **Step 3: Run focused binding/authoring tests**

Run:

```bash
uv run --with pytest pytest tests/core/test_canonical_node_bindings.py tests/authoring/test_builder.py -q
```

Expected: all tests pass.

---

## Task 3: Update Docs

**Files:**

- Modify: `docs/structural_refs.md`
- Modify: any path/core docs if directly relevant.

- [ ] **Step 1: Add graph path note**

Extend the path note in `docs/structural_refs.md`:

```text
New canonical graph path JSON uses root/parts objects. Old strings are accepted
at parse boundaries for compatibility.
```

- [ ] **Step 2: Add examples**

Include examples:

```json
{"root": "input", "parts": ["message"]}
{"root": "state", "parts": ["echoed"]}
{"root": "local", "parts": []}
```

---

## Task 4: Verification

- [ ] **Step 1: Run focused tests**

```bash
uv run --with pytest pytest tests/core/test_path_values.py tests/core/test_canonical_node_bindings.py tests/authoring/test_builder.py -q
```

- [ ] **Step 2: Run full tests**

```bash
uv run --with pytest pytest -q
```

- [ ] **Step 3: Run checks**

```bash
uvx ruff check src/wf_core/paths.py tests/core/test_path_values.py tests/core/test_canonical_node_bindings.py tests/authoring/test_builder.py
uv run basedpyright --level error src/wf_core/paths.py tests/core/test_path_values.py tests/core/test_canonical_node_bindings.py tests/authoring/test_builder.py
```

---

## Self-Review Notes

- This plan does not revive `in_map` / `out_map`; those remain deprecated parse-only fields.
- This plan relaxes path segment validation. Structural `parts` preserve literal field names, including dots and spaces. Old dotted string inputs still split on dots for compatibility.
- This plan changes saved JSON shape for canonical path fields, so broad tests are required.
