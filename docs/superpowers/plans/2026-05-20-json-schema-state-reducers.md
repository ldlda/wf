# JSON Schema State Reducers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Workflow.state_schema` a normal JSON Schema object, with `reducer` as an explicit workflow extension keyword on field schemas.

**Architecture:** `StateSchema` should validate as JSON Schema first, then expose helper indexes for workflow runtime metadata. Runtime reducer lookup should compile from `properties` paths instead of requiring a separate path declaration list. Legacy `fields` inputs remain parse-only compatibility during the transition.

**Tech Stack:** Python, Pydantic v2, `jsonschema`, `wf_core` path models, pytest, basedpyright, ruff.

---

### Task 1: Add Canonical State Schema Tests

**Files:**
- Modify: `tests/core/test_nested_state_paths.py`
- Modify: `tests/core/test_schema_validation.py`

- [ ] **Step 1: Add a test for JSON Schema property reducers**

```python
def test_state_schema_uses_json_schema_properties_as_canonical_shape() -> None:
    schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "person": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Display name",
                            "reducer": "wf.std.replace",
                        }
                    },
                },
                "count": {"type": "integer", "reducer": "wf.std.add"},
            },
        }
    )

    fields = schema.field_map()
    assert fields["person.name"].validation_schema.type == "string"
    assert fields["person.name"].reducer == ReducerRef(name="wf.std.replace")
    assert fields["count"].reducer == ReducerRef(name="wf.std.add")
```

- [ ] **Step 2: Add a dump test proving the canonical output is still JSON Schema**

```python
def test_state_schema_dumps_canonical_json_schema_with_reducer_keyword() -> None:
    schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "reducer": "wf.std.add"}
            },
        }
    )

    dumped = schema.model_dump(mode="json")
    assert dumped["type"] == "object"
    assert dumped["properties"]["count"]["type"] == "integer"
    assert dumped["properties"]["count"]["reducer"] == "wf.std.add"
    Draft202012Validator.check_schema(dumped)
```

- [ ] **Step 3: Add a runtime reducer lookup test from canonical schema**

```python
def test_exact_nested_state_path_uses_reducer_from_json_schema_property() -> None:
    workflow = _workflow_from_state_schema(
        StateSchema.model_validate(
            {
                "type": "object",
                "properties": {
                    "person": {
                        "type": "object",
                        "properties": {
                            "tags": {"type": "array", "reducer": "wf.std.append"}
                        },
                    }
                },
            }
        )
    )
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["seed", "next"]
```

- [ ] **Step 4: Run focused tests and confirm failures**

Run: `uv run --with pytest pytest tests/core/test_nested_state_paths.py tests/core/test_schema_validation.py -q`

Expected: new tests fail because `StateSchema` still serializes as `fields: [...]` and reducer lookup is compiled from field declarations only.

### Task 2: Implement JSON-Schema-Native `StateSchema`

**Files:**
- Modify: `src/wf_core/models/schemas.py`

- [ ] **Step 1: Make `StateSchema` inherit JSON Schema fields directly**

`StateSchema` should expose common JSON Schema object fields:

```python
title: str | None = None
type: str | list[str] | None = "object"
properties: dict[str, Any] = Field(default_factory=dict)
required: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Preserve legacy `fields` as parse-only input**

Keep accepting:

```json
{"fields": [{"path": "state.count", "type": "integer", "reducer": "wf.std.add"}]}
```

and:

```json
{"fields": {"count": {"type": "integer", "reducer": "wf.std.add"}}}
```

by converting both into:

```json
{"type": "object", "properties": {"count": {"type": "integer", "reducer": "wf.std.add"}}}
```

- [ ] **Step 3: Add `field_map()` as an internal compiled index**

`field_map()` should walk explicit object `properties` and return `StateFieldDecl` values keyed by rootless state path. It must:

- include every explicit property path
- parse `reducer` with `ReducerRef`
- default missing reducer to `wf.std.replace`
- preserve `trace` and `default` workflow extension keywords
- remove workflow extension keywords from `StateFieldDecl.validation_schema`

- [ ] **Step 4: Validate JSON Schema and extension keyword types**

Use `SchemaRef`/`jsonschema` validation for the complete state schema. Add explicit validation that:

- `reducer` is a string or `ReducerRef`-compatible object
- `trace` is a boolean when present
- `default` is allowed as JSON Schema/default metadata

### Task 3: Update Artifact Reducer Extraction

**Files:**
- Modify: `src/wf_artifacts/factory.py`

- [ ] **Step 1: Extract reducer dependencies from `state_schema.properties`**

Add a helper that walks explicit JSON Schema properties and yields reducer payloads from every property schema.

- [ ] **Step 2: Keep legacy `fields` extraction only as compatibility**

If `state_schema.fields` exists in old artifacts, continue reading it. Prefer canonical `properties` when present.

- [ ] **Step 3: Add tests through existing workflow surface/artifact tests**

Use an existing artifact/dependency test and assert a reducer declared at:

```json
state_schema.properties.count.reducer
```

is included in required capabilities.

### Task 4: Update Authoring Conversion

**Files:**
- Modify: `src/wf_authoring/schemas.py`
- Modify: `tests/authoring/test_schemas.py`

- [ ] **Step 1: Attach reducer metadata directly to generated property schemas**

When `state_schema_from(BaseModel)` sees `Annotated[..., state_field(reducer=...)]`, inject `reducer` and `trace` into that property schema instead of building a separate field map.

- [ ] **Step 2: Preserve model JSON Schema as the state schema**

Return `StateSchema.model_validate(schema_with_reducer_keywords)` so generated state schema remains JSON Schema-shaped.

### Task 5: Update Docs and Examples

**Files:**
- Modify: `docs/core_state_mapping_and_merge.md`
- Modify: `docs/workflow_drafts.md`
- Modify: `docs/wf_mcp_operator_manual.md`
- Modify: `docs/wf_mcp_end_to_end_runbook.md`
- Modify: `examples/raw_canonical_workflow.py`

- [ ] **Step 1: Replace canonical `fields: [...]` examples**

Use JSON Schema:

```json
{
  "type": "object",
  "properties": {
    "count": {
      "type": "integer",
      "description": "Counter value",
      "reducer": "wf.std.add"
    }
  }
}
```

- [ ] **Step 2: Document extension semantics**

State clearly that `reducer` is not standard JSON Schema behavior. JSON Schema validators ignore it; `wf_core` reads it for workflow state writes.

### Task 6: Verification

**Files:**
- All touched files

- [ ] **Step 1: Run focused tests**

Run: `uv run --with pytest pytest tests/core/test_nested_state_paths.py tests/core/test_schema_validation.py tests/authoring/test_schemas.py -q`

- [ ] **Step 2: Run full tests**

Run: `uv run --with pytest pytest -q`

- [ ] **Step 3: Run static checks**

Run:

```bash
uvx ruff check
uv run basedpyright --level error
```

---

## Self-Review

- Spec coverage: covers canonical JSON Schema state shape, reducer extension keyword, compatibility, runtime lookup, artifact dependency extraction, authoring generation, docs, and verification.
- Placeholder scan: no placeholders remain.
- Type consistency: `StateSchema`, `StateFieldDecl`, `ReducerRef`, and `SchemaRef` names match current code.
