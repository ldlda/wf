# State Schema and Reducer Ref Path Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove remaining dotted-string ambiguity from state field paths, then prepare `ReducerRef` to stop treating reducer capability names as opaque dotted strings.

**Architecture:** Do this in two independent passes. First, make `StateSchema` / `StateFieldDecl` preserve `StatePath` semantics internally and serialize state paths structurally where possible. Second, introduce a structural reducer capability ref while keeping string reducer names as parse-only shorthand. The state-schema pass is the immediate correctness fix; reducer refs are a follow-up because they touch artifacts/source dependencies.

**Tech Stack:** Python 3.14, Pydantic v2, `wf_core.paths.StatePath`, `wf_platform.refs.CapabilityRef`, `wf_core.models.schemas`, pytest, basedpyright, ruff.

---

## Why This Plan Exists

We just moved graph/node bindings toward structural paths:

```json
{"root": "state", "parts": ["person.name"]}
```

But state schema indexing still builds rootless dotted strings in places:

```python
path = f"{prefix}.{name}"
StatePath.of(path)
```

That can corrupt JSON Schema property names containing dots:

```json
{
  "type": "object",
  "properties": {
    "person.name": {"type": "string", "reducer": "wf.std.replace"}
  }
}
```

The intended state path is:

```text
state -> "person.name"
```

not:

```text
state -> person -> name
```

Reducer refs have a similar-looking but different issue. `wf.std.add` is not a graph path; it is a capability ref. That cleanup should use `CapabilityRef`, not `StatePath`.

---

## Scope

### In Scope Now

- Keep exact JSON Schema property names as literal `StatePath.parts`.
- Add typed state-field indexing keyed by `StatePath`.
- Keep old string-keyed `field_map()` compatibility.
- Make `StateFieldDecl.path` dumps structural if the rest of the core path dump has already moved structural.
- Add tests proving literal dotted property names are not split.
- Document that state schema paths and reducer refs are different domains.

### Follow-Up Scope

- Change `ReducerRef` to carry a structural `CapabilityRef`.
- Keep `ReducerRef(name="wf.std.add")` shorthand as parse-only compatibility.
- Update artifact dependency extraction to use structural reducer refs.

Do not mix these two passes unless the state schema work forces a reducer model touch.

---

## Current State

Relevant files:

- `src/wf_core/models/schemas.py`
  - `StateFieldDecl.path: StatePath`
  - `StateFieldDecl._serialize_path()` currently returns `str(path)`
  - `StateSchema.field_map()` returns `dict[str, StateFieldDecl]`
  - `_iter_state_field_declarations(...)` builds `path` as dotted string
  - `_set_state_property_schema(...)` receives `path_parts`

- `src/wf_core/models/reducers.py`
  - `ReducerRef.name: str`

- `src/wf_authoring/schemas.py`
  - `_iter_model_metadata(...)` builds rootless dotted strings from Pydantic field names
  - `_flatten_state_properties(...)` and `_lookup_mutable_property_schema(...)` split strings with `.`

- `src/wf_core/runtime/ops/state.py`
  - uses `workflow.state_schema.field_map()` and string keys

Important distinction:

```text
State path: graph data path, should use StatePath
Reducer name: source capability ref, should use CapabilityRef later
```

---

## Task 1: Pin Literal Dotted State Property Behavior

**Files:**
- Test: `tests/core/test_nested_state_paths.py`
- Test: `tests/core/test_schema_validation.py`

- [ ] **Step 1: Add failing StateSchema field-index test**

Add to `tests/core/test_nested_state_paths.py`:

```python
def test_state_schema_preserves_literal_dotted_property_names() -> None:
    schema = StateSchema.model_validate({
        "type": "object",
        "properties": {
            "person.name": {"type": "string", "reducer": "wf.std.replace"}
        },
    })

    fields = schema.field_index()

    assert set(fields) == {StatePath(("person.name",))}
    assert fields[StatePath(("person.name",))].path == StatePath(("person.name",))
```

Expected failure: `field_index()` does not exist, or the path is split as `("person", "name")`.

- [ ] **Step 2: Add compatibility `field_map()` test**

Add:

```python
def test_state_schema_field_map_keeps_display_key_for_literal_dotted_property() -> None:
    schema = StateSchema.model_validate({
        "type": "object",
        "properties": {
            "person.name": {"type": "string", "reducer": "wf.std.replace"}
        },
    })

    fields = schema.field_map()

    assert set(fields) == {"person.name"}
    assert fields["person.name"].path == StatePath(("person.name",))
```

This keeps old callers alive but makes the value typed/correct.

- [ ] **Step 3: Run focused tests to verify red**

```bash
uv run --with pytest pytest tests/core/test_nested_state_paths.py::test_state_schema_preserves_literal_dotted_property_names tests/core/test_nested_state_paths.py::test_state_schema_field_map_keeps_display_key_for_literal_dotted_property -q
```

Expected: fail before implementation.

---

## Task 2: Add Typed State Field Index

**Files:**
- Modify: `src/wf_core/models/schemas.py`
- Test: `tests/core/test_nested_state_paths.py`

- [ ] **Step 1: Add path-parts traversal helper**

In `src/wf_core/models/schemas.py`, replace string-prefix recursion with tuple path parts.

Add helper:

```python
def _append_state_part(prefix: tuple[str, ...], name: str) -> tuple[str, ...]:
    """Append one JSON Schema property name as one literal StatePath segment."""
    return (*prefix, name)
```

- [ ] **Step 2: Add `field_index()`**

Add to `StateSchema`:

```python
def field_index(self) -> dict[StatePath, StateFieldDecl]:
    """Return reducer-aware declarations keyed by exact typed state path."""
    root_schema = self.model_dump(mode="json", exclude_none=True)
    return {
        path: field
        for path, field in _iter_state_field_declarations(
            self.properties,
            root_schema,
            prefix=(),
        )
    }
```

- [ ] **Step 3: Make `field_map()` compatibility wrapper**

Change `field_map()` to:

```python
def field_map(self) -> dict[str, StateFieldDecl]:
    """Return reducer-aware declarations keyed by rootless display path."""
    return {".".join(path.parts): field for path, field in self.field_index().items()}
```

Note: this display map is ambiguous for literal dotted segments, but values are correct. New runtime code should move to `field_index()`.

- [ ] **Step 4: Update `_iter_state_field_declarations` signature**

Change from string prefix:

```python
prefix: str
) -> Iterator[tuple[str, StateFieldDecl]]:
```

to typed prefix:

```python
prefix: tuple[str, ...]
) -> Iterator[tuple[StatePath, StateFieldDecl]]:
```

Inside loop:

```python
path_parts = _append_state_part(prefix, name)
path = StatePath(path_parts)
display_path = ".".join(path.parts)
```

Use `display_path` only in error messages and reducer validation labels.

- [ ] **Step 5: Update yielded `StateFieldDecl` construction**

Change:

```python
"path": StatePath.of(path),
```

to:

```python
"path": path,
```

- [ ] **Step 6: Update recursive calls**

Pass:

```python
prefix=path.parts
```

not a dotted string.

- [ ] **Step 7: Run focused tests**

```bash
uv run --with pytest pytest tests/core/test_nested_state_paths.py::test_state_schema_preserves_literal_dotted_property_names tests/core/test_nested_state_paths.py::test_state_schema_field_map_keeps_display_key_for_literal_dotted_property -q
```

Expected: pass.

---

## Task 3: Move Runtime Lookup to Typed State Paths

**Files:**
- Modify: `src/wf_core/runtime/ops/state.py`
- Test: `tests/core/test_nested_state_paths.py`
- Test: `tests/core/test_atomic_state_patches.py`

- [ ] **Step 1: Inspect current runtime lookup**

Current likely shape:

```python
state_fields = workflow.state_schema.field_map()
field = state_fields.get(".".join(path.parts))
```

This should move to `field_index()` where available.

- [ ] **Step 2: Update runtime type hints**

Change helpers from:

```python
state_fields: Mapping[str, StateFieldDecl]
```

to:

```python
state_fields: Mapping[StatePath, StateFieldDecl]
```

- [ ] **Step 3: Use typed lookup**

When resolving reducer for a write target:

```python
declared_field = state_fields.get(target)
```

where `target` is already a `StatePath`.

If code currently has only path parts, construct:

```python
target = StatePath(tuple(path_parts))
```

- [ ] **Step 4: Update affected-field overlap helper**

If `_affected_state_fields(...)` compares string prefixes, make it compare tuple parts:

```python
def _is_prefix(prefix: tuple[str, ...], parts: tuple[str, ...]) -> bool:
    return parts[: len(prefix)] == prefix
```

This preserves exact path semantics without reparsing dotted display text.

- [ ] **Step 5: Run runtime-focused tests**

```bash
uv run --with pytest pytest tests/core/test_nested_state_paths.py tests/core/test_atomic_state_patches.py -q
```

Expected: pass.

---

## Task 4: Structural `StateFieldDecl.path` Dump

**Files:**
- Modify: `src/wf_core/models/schemas.py`
- Test: `tests/core/test_nested_state_paths.py`
- Test: `tests/core/test_schema_validation.py`

- [ ] **Step 1: Check current expectations**

Existing tests may expect:

```python
{"path": "state.person.name"}
```

Decide based on current path model direction. Since `StatePath` now serializes structurally elsewhere, prefer:

```json
{"path": {"root": "state", "parts": ["person.name"]}}
```

- [ ] **Step 2: Change serializer**

Remove this serializer:

```python
@field_serializer("path")
def _serialize_path(self, path: StatePath) -> str:
    return str(path)
```

or change it to:

```python
@field_serializer("path")
def _serialize_path(self, path: StatePath) -> dict[str, str | list[str]]:
    return StatePath._serialize(path)
```

Prefer removal if Pydantic uses the existing `StatePath` serializer correctly.

- [ ] **Step 3: Update tests**

Update or add:

```python
def test_state_field_decl_model_dump_serializes_path_structurally() -> None:
    field = StateFieldDecl(path=StatePath(("person.name",)), schema={"type": "string"})

    dumped = field.model_dump(mode="json")

    assert dumped["path"] == {"root": "state", "parts": ["person.name"]}
```

- [ ] **Step 4: Run focused schema tests**

```bash
uv run --with pytest pytest tests/core/test_nested_state_paths.py tests/core/test_schema_validation.py -q
```

Expected: pass after expectation updates.

---

## Task 5: Authoring State Metadata Path Sweep

**Files:**
- Modify: `src/wf_authoring/schemas.py`
- Test: `tests/authoring/test_schemas.py`

- [ ] **Step 1: Add failing authoring test for literal dotted Pydantic field alias if possible**

If Pydantic field aliases are already used in this project, add:

```python
class DotAliasState(BaseModel):
    person_name: Annotated[
        str,
        Field(alias="person.name"),
        state_field(reducer="wf.std.replace"),
    ]


def test_state_schema_from_preserves_literal_dotted_alias_paths() -> None:
    schema = state_schema_from(DotAliasState)

    fields = schema.field_index()

    assert StatePath(("person.name",)) in fields
```

If field aliases are not supported by the current authoring schema flow, document that Python model field names remain Python identifiers and alias path support is out of scope.

- [ ] **Step 2: Replace string path traversal with tuple parts**

In `src/wf_authoring/schemas.py`, update metadata collection helpers:

```python
def _iter_model_metadata(
    model_type: type[BaseModel],
    *,
    prefix: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], StateFieldMetadata]]:
```

Use one literal segment per field name or alias:

```python
field_name = field_info.alias or name
path = (*prefix, field_name)
```

- [ ] **Step 3: Update lookup helpers to accept tuple parts**

Change:

```python
_lookup_mutable_property_schema(schema_payload, path)
_state_field_default(value, path, property_schema)
```

to tuple-based forms:

```python
_lookup_mutable_property_schema(schema_payload, path_parts)
_state_field_default(value, path_parts, property_schema)
```

Use field name lookup carefully; default lookup for nested aliases may need to remain conservative.

- [ ] **Step 4: Run authoring schema tests**

```bash
uv run --with pytest pytest tests/authoring/test_schemas.py -q
```

Expected: pass.

---

## Task 6: ReducerRef Capability Ref Plan Stub

**Files:**
- Modify: `docs/structural_refs.md`
- Create: `docs/superpowers/plans/YYYY-MM-DD-reducer-ref-structural-capability.md`

- [ ] **Step 1: Document reducer refs are capability refs**

In `docs/structural_refs.md`, add:

```text
Reducer refs are capability refs, not graph paths. `wf.std.add` is shorthand
for source `wf.std`, capability key `add`. The reducer cleanup should move
ReducerRef toward structural CapabilityRef while keeping string reducer names
as parse-only shorthand.
```

- [ ] **Step 2: Create follow-up plan stub**

Create a separate plan with only the intended boundary:

- `ReducerRef.name: str` remains compatibility display/shorthand for now.
- Add `ReducerRef.ref: CapabilityRef` or replace `name` with a `CapabilityRef` after artifact/source dependency code is ready.
- Update artifact dependency extraction from reducer refs.
- Keep configured reducers as `{ref/name, config}`.

Do not implement reducer structural refs in the state-schema path sweep unless the user explicitly asks to combine them.

---

## Task 7: Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run focused core tests**

```bash
uv run --with pytest pytest tests/core/test_nested_state_paths.py tests/core/test_atomic_state_patches.py tests/core/test_schema_validation.py -q
```

Expected: pass.

- [ ] **Step 2: Run authoring schema tests**

```bash
uv run --with pytest pytest tests/authoring/test_schemas.py -q
```

Expected: pass.

- [ ] **Step 3: Run full tests**

```bash
uv run --with pytest pytest -q
```

Expected: pass.

- [ ] **Step 4: Run lint/type checks**

```bash
uvx ruff check src/wf_core src/wf_authoring tests/core tests/authoring
uvx ruff format --check src/wf_core src/wf_authoring tests/core tests/authoring
uv run basedpyright --level error src/wf_core src/wf_authoring tests/core tests/authoring
```

Expected:

- ruff check passes
- format check passes
- basedpyright reports `0 errors`

---

## Self-Review Checklist

- JSON Schema property names containing dots stay one `StatePath` segment.
- Runtime reducer lookup uses `StatePath`, not rootless dotted strings.
- `field_map()` remains available for compatibility but is not the preferred internal API.
- `StateFieldDecl.path` no longer forces string serialization if the project has moved to structural path JSON.
- Reducer refs are documented as capability refs, not graph paths.
- Reducer structural ref implementation is not accidentally mixed into the state schema path sweep.
