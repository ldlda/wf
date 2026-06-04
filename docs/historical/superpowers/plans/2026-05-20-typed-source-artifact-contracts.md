# Typed Source Artifact Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace persisted dict-key source/capability contract shapes with explicit list-of-struct models backed by `SourceRef` and `CapabilityRef`.

**Architecture:** Keep dot-joined strings as the JSON wire format for refs, but make Python/Pydantic fields use first-class ref objects. Accept old dict shapes as parse-only compatibility and dump the new list shapes. Runtime code should use helper indexes such as `binding_map()` and `required_capability_map()` instead of depending on serialized dict keys.

**Tech Stack:** Python, Pydantic v2, `wf_platform` refs, `wf_artifacts` models, pytest, ruff, basedpyright.

---

### Task 1: Make Platform Refs Pydantic Boundary Types

**Files:**

- Modify: `src/wf_platform/refs.py`
- Modify: `tests/refs/test_platform_refs.py`

- [ ] **Step 1: Add tests for Pydantic validation and serialization**

Add tests that prove:

```python
class Payload(BaseModel):
    source: SourceRef
    capability: CapabilityRef

payload = Payload.model_validate(
    {"source": "demo.personal", "capability": "demo.personal.echo_tool"}
)

assert payload.source == SourceRef.parse("demo.personal")
assert payload.capability == CapabilityRef.parse("demo.personal.echo_tool")
assert payload.model_dump(mode="json") == {
    "source": "demo.personal",
    "capability": "demo.personal.echo_tool",
}
```

- [ ] **Step 2: Implement Pydantic core-schema hooks**

Use `__get_pydantic_core_schema__` on `SourceRef` and `CapabilityRef` so both accept existing instances or strings and serialize back to strings.

- [ ] **Step 3: Tighten segment validation modestly**

Reject whitespace-only refs and empty segments. Do not over-restrict valid MCP/source names yet; external systems can use dashes, underscores, and other non-empty string segments.

### Task 2: Convert Deployment Bindings to List-of-Struct

**Files:**

- Modify: `src/wf_artifacts/models.py`
- Modify: `tests/artifacts/test_models.py`
- Modify: `tests/artifacts/test_store.py`

- [ ] **Step 1: Add `SourceBinding`**

```python
class SourceBinding(BaseModel):
    logical_source: SourceRef
    concrete_source: SourceRef
```

- [ ] **Step 2: Change `WorkflowDeployment.bindings`**

Canonical model field:

```python
bindings: list[SourceBinding] = Field(default_factory=list)
```

Parse-only compatibility:

```json
{ "bindings": { "demo": "demo.personal" } }
```

should normalize to:

```json
{
  "bindings": [{ "logical_source": "demo", "concrete_source": "demo.personal" }]
}
```

- [ ] **Step 3: Add `binding_map()`**

```python
def binding_map(self) -> dict[str, str]:
    return {
        str(binding.logical_source): str(binding.concrete_source)
        for binding in self.bindings
    }
```

Reject duplicate `logical_source` values during validation.

### Task 3: Convert Required Capabilities to List-of-Struct

**Files:**

- Modify: `src/wf_artifacts/models.py`
- Modify: `src/wf_artifacts/factory.py`
- Modify: `src/wf_artifacts/references.py`
- Modify: `tests/artifacts/test_models.py`
- Modify: `tests/artifacts/test_factory.py`

- [ ] **Step 1: Update `RequiredCapability`**

Canonical field:

```python
ref: CapabilityRef
```

Keep compatibility properties:

```python
@property
def logical_source(self) -> str: ...

@property
def capability_name(self) -> str: ...
```

Parse-only compatibility should accept old payloads with `logical_source` and `capability_name` and build `ref`.

- [ ] **Step 2: Change `WorkflowArtifact.required_capabilities`**

Canonical model field:

```python
required_capabilities: list[RequiredCapability] = Field(default_factory=list)
```

Parse-only compatibility:

```json
{
  "required_capabilities": {
    "demo.echo_tool": {
      "logical_source": "demo",
      "capability_name": "echo_tool",
      "kind": "node_spec"
    }
  }
}
```

should normalize to a list and dump as:

```json
{
  "required_capabilities": [
    {
      "ref": "demo.echo_tool",
      "kind": "node_spec"
    }
  ]
}
```

- [ ] **Step 3: Add `required_capability_map()`**

```python
def required_capability_map(self) -> dict[str, RequiredCapability]:
    return {str(capability.ref): capability for capability in self.required_capabilities}
```

Reject duplicate `ref` values during validation.

### Task 4: Update Call Sites to Use Helper Maps

**Files:**

- Modify: `src/wf_artifacts/validation.py`
- Modify: `src/wf_artifacts/catalog.py`
- Modify: `src/wf_mcp/workflow_surface/runtime_dependencies.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_mcp/broker/artifact_tools.py`
- Modify tests that directly index `.bindings` or `.required_capabilities`.

- [ ] **Step 1: Replace `deployment.bindings.get(...)`**

Use:

```python
bindings = deployment.binding_map()
bound_source_id = bindings.get(required.logical_source)
```

- [ ] **Step 2: Replace `artifact.required_capabilities.items()`**

Use:

```python
for logical_ref, required in artifact.required_capability_map().items():
    ...
```

- [ ] **Step 3: Keep API input compatibility**

MCP tools that accept `required_capabilities` from callers may still accept dict input, but constructed `WorkflowArtifact` should dump the canonical list shape.

### Task 5: Update Docs

**Files:**

- Modify: `docs/workflow_artifacts.md`

- [ ] **Step 1: Replace dict binding examples**

Use:

```json
{
  "bindings": [
    { "logical_source": "context7", "concrete_source": "context7.default" }
  ]
}
```

- [ ] **Step 2: Replace dict required capability examples**

Use:

```json
{
  "required_capabilities": [
    {
      "ref": "context7.query-docs",
      "kind": "node_spec",
      "input_schema_hash": "sha256:..."
    }
  ]
}
```

State that old dict shapes are accepted at parse boundaries but not emitted by model dumps.

### Task 6: Verification

**Files:**

- All touched files

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --with pytest pytest tests/refs/test_platform_refs.py tests/artifacts/test_models.py tests/artifacts/test_store.py tests/artifacts/test_factory.py tests/artifacts/test_validation.py -q
```

- [ ] **Step 2: Run full suite**

Run:

```bash
uv run --with pytest pytest -q
```

- [ ] **Step 3: Run static checks**

Run:

```bash
uvx ruff check
uv run basedpyright --level error
```

---

## Self-Review

- Spec coverage: covers typed refs, deployment binding list shape, required capability list shape, compatibility parsing, helper indexes, docs, and tests.
- Placeholder scan: no placeholders remain.
- Type consistency: `SourceRef`, `CapabilityRef`, `SourceBinding`, `RequiredCapability`, `WorkflowArtifact`, and `WorkflowDeployment` names match current code or are introduced in this plan.
