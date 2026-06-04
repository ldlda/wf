# ReducerRef Structural Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move reducer references from ambiguous dotted strings toward structural capability refs while preserving string reducer names as parse-only shorthand.

**Architecture:** Reducers are source-owned capabilities, not graph paths. `ReducerRef` should carry a structural `CapabilityRef` plus config, while old `name` strings continue to validate at compatibility boundaries. Runtime reducer lookup can keep using display names temporarily through a compatibility property; artifact dependency extraction should stop reparsing dotted reducer names manually.

**Tech Stack:** Python 3.14, Pydantic v2, `wf_platform.refs.CapabilityRef`, `wf_core.models.reducers.ReducerRef`, `wf_artifacts.factory`, pytest, basedpyright, ruff.

---

## Current State

`src/wf_core/models/reducers.py`:

```python
class ReducerRef(BaseModel):
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
```

`src/wf_artifacts/factory.py` extracts reducer dependencies by reparsing the display name:

```python
reducer_ref = CapabilityRef.parse(reducer.name)
requirements[reducer.name] = RequiredCapability(ref=reducer_ref, kind="reducer")
```

This is the same separator problem in another domain. `wf.std.add` is a capability ref, not a graph path.

---

## Canonical Shape

New canonical reducer ref:

```json
{
  "ref": { "source": "wf.std", "capability_key": "add" },
  "config": {}
}
```

Compatibility inputs:

```json
"wf.std.add"
```

```json
{ "name": "wf.std.add", "config": { "modulus": 10 } }
```

For now, `ReducerRef.name` remains available as a display/registry key compatibility property. Runtime reducer registries are still keyed by strings such as `wf.std.add`.

---

## File Structure

- Modify: `src/wf_core/models/reducers.py`
  - Add `ref: CapabilityRef`
  - Keep `name` as computed/display compatibility property
  - Parse old string and old `name` object shapes
  - Dump canonical `ref` shape in JSON/Python model dumps

- Modify: `src/wf_artifacts/factory.py`
  - Use `reducer.ref` for required capabilities
  - Keep dependency key as `reducer.name` for now

- Modify tests:
  - `tests/core/test_nested_state_paths.py`
  - `tests/core/test_schema_validation.py`
  - `tests/artifacts/test_factory.py`
  - `tests/artifacts/test_validation.py` if needed

- Modify docs:
  - `docs/structural_refs.md`
  - `docs/core_state_mapping_and_merge.md`

---

## Task 1: Pin ReducerRef Compatibility and Canonical Dump

**Files:**

- Modify: `tests/core/test_nested_state_paths.py`

- [ ] **Step 1: Add reducer ref tests**

Add:

```python
from wf_platform import CapabilityRef


def test_reducer_ref_accepts_string_shorthand_and_dumps_structural_ref() -> None:
    reducer = ReducerRef.model_validate("wf.std.add")

    assert reducer.ref == CapabilityRef(source="wf.std", capability_key="add")
    assert reducer.name == "wf.std.add"
    assert reducer.model_dump(mode="json") == {
        "ref": {"source": "wf.std", "capability_key": "add"},
        "config": {},
    }


def test_reducer_ref_accepts_legacy_name_object_with_config() -> None:
    reducer = ReducerRef.model_validate({
        "name": "wf.std.modulo_add",
        "config": {"modulus": 10},
    })

    assert reducer.ref == CapabilityRef(source="wf.std", capability_key="modulo_add")
    assert reducer.name == "wf.std.modulo_add"
    assert reducer.config == {"modulus": 10}


def test_reducer_ref_accepts_canonical_ref_object() -> None:
    reducer = ReducerRef.model_validate({
        "ref": {"source": "wf.std", "capability_key": "append"},
    })

    assert reducer.name == "wf.std.append"
```

- [ ] **Step 2: Run focused tests to verify red**

```bash
uv run --with pytest pytest tests/core/test_nested_state_paths.py::test_reducer_ref_accepts_string_shorthand_and_dumps_structural_ref tests/core/test_nested_state_paths.py::test_reducer_ref_accepts_legacy_name_object_with_config tests/core/test_nested_state_paths.py::test_reducer_ref_accepts_canonical_ref_object -q
```

Expected: fail because `ReducerRef` does not parse strings and has no `ref`.

---

## Task 2: Implement Structural ReducerRef

**Files:**

- Modify: `src/wf_core/models/reducers.py`

- [ ] **Step 1: Update imports**

Add:

```python
from collections.abc import Mapping
from pydantic import computed_field, model_validator
from wf_platform import CapabilityRef
```

- [ ] **Step 2: Change model fields**

Change `ReducerRef` to:

```python
class ReducerRef(BaseModel):
    """Reference to one reducer capability plus JSON-compatible configuration."""

    ref: CapabilityRef
    config: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 3: Add compatibility validator**

Add:

```python
@model_validator(mode="before")
@classmethod
def _coerce_legacy_shapes(cls, value: object) -> object:
    if isinstance(value, str):
        return {"ref": CapabilityRef.parse(value)}
    if not isinstance(value, Mapping):
        return value
    data = dict(value)
    if "ref" not in data and "name" in data:
        data["ref"] = CapabilityRef.parse(str(data.pop("name")))
    return data
```

Do not parse arbitrary dotted strings anywhere else.

- [ ] **Step 4: Add name compatibility property**

Add:

```python
@computed_field
@property
def name(self) -> str:
    """Display/registry compatibility key for existing reducer catalogs."""
    return str(self.ref)
```

If `CapabilityRef.__str__` does not produce `source.capability_key`, use its display helper or add one there.

- [ ] **Step 5: Run reducer ref tests**

```bash
uv run --with pytest pytest tests/core/test_nested_state_paths.py::test_reducer_ref_accepts_string_shorthand_and_dumps_structural_ref tests/core/test_nested_state_paths.py::test_reducer_ref_accepts_legacy_name_object_with_config tests/core/test_nested_state_paths.py::test_reducer_ref_accepts_canonical_ref_object -q
```

Expected: pass.

---

## Task 3: Update Reducer Field Serializers and Existing Expectations

**Files:**

- Modify: `src/wf_core/models/schemas.py`
- Modify tests that assert reducer dumps

- [ ] **Step 1: Inspect current reducer dump helper**

Current helper:

```python
def _dump_reducer_keyword(reducer: ReducerRef) -> str | dict[str, Any]:
    if not reducer.config:
        return reducer.name
    return reducer.model_dump(mode="json")
```

Decide canonical output:

- For no-config reducers, keep string shorthand in JSON Schema `reducer` keyword for readability.
- For configured reducers, dump canonical object:

```json
{
  "ref": { "source": "wf.std", "capability_key": "modulo_add" },
  "config": { "modulus": 10 }
}
```

This keeps common schema compact while avoiding string parsing for config objects.

- [ ] **Step 2: Update helper**

Use:

```python
def _dump_reducer_keyword(reducer: ReducerRef) -> str | dict[str, Any]:
    if not reducer.config:
        return reducer.name
    return reducer.model_dump(mode="json")
```

This may already work after `ReducerRef.model_dump()` changes. Keep the helper but update tests.

- [ ] **Step 3: Run schema tests**

```bash
uv run --with pytest pytest tests/core/test_schema_validation.py tests/core/test_nested_state_paths.py -q
```

Expected: pass after updating expectations for configured reducer dumps if needed.

---

## Task 4: Update Artifact Reducer Dependency Extraction

**Files:**

- Modify: `src/wf_artifacts/factory.py`
- Modify: `tests/artifacts/test_factory.py`

- [ ] **Step 1: Add/adjust artifact test**

In `tests/artifacts/test_factory.py`, ensure reducer dependencies assert structural refs:

```python
def test_create_workflow_artifact_from_plan_adds_reducer_dependencies() -> None:
    ...
    reducer = artifact.required_capability_map()["wf.std.max"]
    assert reducer.ref.source == "wf.std"
    assert reducer.ref.capability_key == "max"
    assert reducer.logical_source == "wf.std"
    assert reducer.capability_name == "max"
    assert reducer.kind == "reducer"
```

Add a configured reducer payload test:

```python
def test_create_workflow_artifact_from_plan_accepts_structural_reducer_ref() -> None:
    plan = minimal_plan()
    plan["state_schema"] = {
        "type": "object",
        "properties": {
            "score": {
                "type": "integer",
                "reducer": {
                    "ref": {"source": "wf.std", "capability_key": "max"},
                    "config": {},
                },
            }
        },
    }

    artifact = create_workflow_artifact_from_plan(...)

    assert "wf.std.max" in artifact.required_capability_map()
```

- [ ] **Step 2: Update extraction**

Change:

```python
reducer_ref = CapabilityRef.parse(reducer.name)
requirements[reducer.name] = RequiredCapability(ref=reducer_ref, kind="reducer")
```

to:

```python
requirements[reducer.name] = RequiredCapability(ref=reducer.ref, kind="reducer")
```

- [ ] **Step 3: Run artifact tests**

```bash
uv run --with pytest pytest tests/artifacts/test_factory.py tests/artifacts/test_validation.py -q
```

Expected: pass.

---

## Task 5: Runtime Compatibility Check

**Files:**

- Tests only unless failures require runtime changes

- [ ] **Step 1: Run reducer runtime tests**

```bash
uv run --with pytest pytest tests/core/test_nested_state_paths.py tests/core/test_atomic_state_patches.py -q
```

Expected: pass because `reducer.name` remains a compatibility registry key.

- [ ] **Step 2: If runtime fails**

Only if needed, update lookup code to use `reducer.name` as the compatibility string key. Do not make runtime registries structural in this pass.

---

## Task 6: Docs

**Files:**

- Modify: `docs/structural_refs.md`
- Modify: `docs/core_state_mapping_and_merge.md`

- [ ] **Step 1: Update reducer docs**

In `docs/structural_refs.md`, replace temporary wording with:

```text
Canonical configured reducer refs use `ref`:

{
  "ref": {"source": "wf.std", "capability_key": "modulo_add"},
  "config": {"modulus": 10}
}

String reducer names such as `wf.std.add` remain shorthand for unconfigured
reducers and compatibility display.
```

- [ ] **Step 2: Update merge docs**

In `docs/core_state_mapping_and_merge.md`, update examples with both compact and configured forms:

```json
"reducer": "wf.std.add"
```

and:

```json
"reducer": {
  "ref": {"source": "wf.std", "capability_key": "modulo_add"},
  "config": {"modulus": 10}
}
```

---

## Task 7: Verification

- [ ] **Step 1: Focused tests**

```bash
uv run --with pytest pytest tests/core/test_nested_state_paths.py tests/core/test_schema_validation.py tests/artifacts/test_factory.py tests/artifacts/test_validation.py -q
```

- [ ] **Step 2: Full tests**

```bash
uv run --with pytest pytest -q
```

- [ ] **Step 3: Static checks**

```bash
uvx ruff check src/wf_core src/wf_artifacts tests/core tests/artifacts
uvx ruff format --check src/wf_core src/wf_artifacts tests/core tests/artifacts
uv run basedpyright --level error src/wf_core src/wf_artifacts tests/core tests/artifacts
```

Expected:

- tests pass
- ruff passes
- basedpyright reports `0 errors`

---

## Self-Review Checklist

- `ReducerRef` canonical shape has `ref`, not only `name`.
- String shorthand still parses.
- Legacy `{name, config}` still parses.
- Runtime reducer lookup still works through `reducer.name`.
- Artifact dependency extraction uses `reducer.ref`.
- No graph path parser is used for reducer refs.
