# Structural Capability Refs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop treating dotted capability names as authoritative data by making source/capability/workflow refs structural in saved artifacts and internal runtime paths.

**Architecture:** Public MCP/tool arguments may keep accepting old string names for compatibility, but model validation normalizes them into structural refs immediately. Saved artifacts, deployments, and generated JSON should write structured fields; display strings are derived only for UI/tool readability. Runtime resolution binds by explicit source fields, not by guessing where a dot-separated string should split.

**Tech Stack:** Python 3.14, Pydantic models, `wf_platform` refs, `wf_artifacts` models, `wf_mcp` workflow surface and broker service tests.

---

## Current Problem

Dotted names currently carry multiple meanings:

- `context7.default.query-docs` means provider/profile/capability.
- `wf.std.replace` means system source/capability.
- `workflow.echo_wrapper.v1` means workflow artifact/version.
- `demo.foo.bar` may mean source `demo` with capability key `foo.bar`, or source `demo.foo` with capability key `bar`.

No parser can infer the right boundary from the string alone. Dotted strings are still useful as display names and human-entered compatibility inputs, but they must not be the stored source of truth.

## Canonical Shapes

### Source Identity

Use `SourceRef` for concrete or logical source identity.

```json
{
  "provider": "context7",
  "profile": "default"
}
```

System sources may omit profile:

```json
{
  "provider": "wf.std",
  "profile": null
}
```

For the first implementation pass, this can still serialize through the current `SourceRef` string internally, but the plan should leave room for `profile: null`.

### Capability Ref

Use an object with a source and a local key:

```json
{
  "source": "demo",
  "capability_key": "foo.bar"
}
```

`capability_key` is the name inside a known source. It may contain dots. It is not parsed for source meaning.

### Workflow Artifact Capability Ref

Workflow artifacts are not external source capabilities. Store them separately:

```json
{
  "artifact_id": "echo_wrapper",
  "version": 1
}
```

The display string `workflow.echo_wrapper.v1` remains computable for list output and old input parsing.

---

## File Structure

- Modify `src/wf_platform/refs.py`
  - Add structural capability ref input/output support.
  - Keep compact-string parsing for old inputs.
  - Make JSON serialization emit object shape for canonical saves.

- Modify `src/wf_artifacts/refs.py`
  - Add Pydantic validation/serialization for `WorkflowCapabilityRef`.
  - Accept old `workflow.<artifact_id>.v<version>` strings as parse-only input.
  - Serialize new saves as `{"artifact_id": "...", "version": 1}`.

- Modify `src/wf_artifacts/models.py`
  - Make `RequiredCapability.ref` canonical structural JSON.
  - Keep `logical_source` and `capability_name` as compatibility accessors only.
  - Keep accepting old dict/map/string shapes.
  - Make `WorkflowDeployment.bindings` save as structural list, not dict.

- Modify `src/wf_artifacts/references.py`
  - Replace string-concatenated `logical_ref` construction with structural `CapabilityRef`.
  - Return display strings only where legacy maps still require them.

- Modify `src/wf_mcp/workflow_surface/refs.py`
  - Parse workflow-surface ids into a union of structural refs.
  - Keep old string input compatibility for MCP tool calls.

- Modify `src/wf_mcp/workflow_surface/runtime_dependencies.py`
  - Keep source-prefix binding logic for legacy plan node strings.
  - Add a path for structural plan node refs when the plan model supports them.
  - Keep the current dotted-local-name regression test.

- Modify `src/wf_mcp/workflow_surface/handlers.py`
  - When saving artifacts from plans/drafts/workspaces, emit structural required capability refs.
  - Keep response display names for humans/LLMs.

- Add or modify tests:
  - `tests/wf_platform/test_refs.py`
  - `tests/wf_artifacts/test_refs.py`
  - `tests/wf_mcp/test_workflow_surface_refs.py`
  - `tests/wf_mcp/test_service.py`
  - `tests/wf_mcp/test_workflow_surface.py`

---

## Task 1: Make `CapabilityRef` Serialize Structurally

**Files:**
- Modify: `src/wf_platform/refs.py`
- Test: `tests/wf_platform/test_refs.py`

- [ ] **Step 1: Write failing tests**

Add tests that prove three things:

```python
from pydantic import BaseModel

from wf_platform import CapabilityRef, SourceRef


class RefHolder(BaseModel):
    ref: CapabilityRef


def test_capability_ref_accepts_legacy_string_input() -> None:
    holder = RefHolder.model_validate({"ref": "demo.foo.bar"})

    # Legacy parsing is best-effort only. It stays for old input compatibility.
    assert str(holder.ref) == "demo.foo.bar"


def test_capability_ref_accepts_structural_input() -> None:
    holder = RefHolder.model_validate(
        {"ref": {"source": "demo", "capability_key": "foo.bar"}}
    )

    assert holder.ref.source == SourceRef.parse("demo")
    assert holder.ref.name == "foo.bar"


def test_capability_ref_serializes_structurally() -> None:
    holder = RefHolder(
        ref=CapabilityRef(source=SourceRef.parse("demo"), name="foo.bar")
    )

    assert holder.model_dump(mode="json")["ref"] == {
        "source": "demo",
        "capability_key": "foo.bar",
    }
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
uv run --with pytest pytest tests/wf_platform/test_refs.py -q
```

Expected: structural input or structural serialization fails because `CapabilityRef` currently serializes as a string.

- [ ] **Step 3: Implement structural validation/serialization**

Update `CapabilityRef.__get_pydantic_core_schema__` to:

- accept existing `CapabilityRef`
- accept legacy string via `CapabilityRef.parse`
- accept dict `{"source": str, "capability_key": str}`
- serialize as dict `{"source": str(self.source), "capability_key": self.name}`

Keep `__str__` unchanged because display strings are still useful.

- [ ] **Step 4: Run tests to verify green**

Run:

```bash
uv run --with pytest pytest tests/wf_platform/test_refs.py -q
```

Expected: all tests pass.

---

## Task 2: Make `WorkflowCapabilityRef` Structural

**Files:**
- Modify: `src/wf_artifacts/refs.py`
- Test: `tests/wf_artifacts/test_refs.py`

- [ ] **Step 1: Write failing tests**

```python
from pydantic import BaseModel

from wf_artifacts import WorkflowCapabilityRef


class WorkflowRefHolder(BaseModel):
    ref: WorkflowCapabilityRef


def test_workflow_capability_ref_accepts_legacy_string_input() -> None:
    holder = WorkflowRefHolder.model_validate({"ref": "workflow.echo_wrapper.v1"})

    assert holder.ref.artifact_id == "echo_wrapper"
    assert holder.ref.version == 1


def test_workflow_capability_ref_accepts_structural_input() -> None:
    holder = WorkflowRefHolder.model_validate(
        {"ref": {"artifact_id": "echo_wrapper", "version": 1}}
    )

    assert holder.ref.artifact_id == "echo_wrapper"
    assert holder.ref.version == 1


def test_workflow_capability_ref_serializes_structurally() -> None:
    holder = WorkflowRefHolder(ref=WorkflowCapabilityRef("echo_wrapper", 1))

    assert holder.model_dump(mode="json")["ref"] == {
        "artifact_id": "echo_wrapper",
        "version": 1,
    }
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
uv run --with pytest pytest tests/wf_artifacts/test_refs.py -q
```

Expected: Pydantic validation fails because `WorkflowCapabilityRef` has no schema hook.

- [ ] **Step 3: Implement Pydantic schema hook**

Add a Pydantic core schema method to `WorkflowCapabilityRef` that accepts legacy string and structural dict input, then serializes structurally.

- [ ] **Step 4: Run tests to verify green**

Run:

```bash
uv run --with pytest pytest tests/wf_artifacts/test_refs.py -q
```

Expected: all tests pass.

---

## Task 3: Save Required Capabilities in New Shape

**Files:**
- Modify: `src/wf_artifacts/models.py`
- Modify: `src/wf_artifacts/references.py`
- Test: `tests/wf_artifacts/test_models.py`
- Test: existing workflow-surface artifact creation tests

- [ ] **Step 1: Write failing model serialization tests**

Add tests proving old inputs parse and new outputs dump structurally:

```python
from wf_artifacts import RequiredCapability, WorkflowArtifact


def test_required_capability_accepts_legacy_logical_fields_but_dumps_ref_object() -> None:
    capability = RequiredCapability.model_validate(
        {
            "logical_source": "demo",
            "capability_name": "foo.bar",
            "kind": "node_spec",
        }
    )

    assert capability.logical_source == "demo"
    assert capability.capability_name == "foo.bar"
    assert capability.model_dump(mode="json")["ref"] == {
        "source": "demo",
        "capability_key": "foo.bar",
    }


def test_workflow_artifact_accepts_legacy_required_capability_map_but_dumps_list() -> None:
    artifact = WorkflowArtifact.model_validate(
        {
            "id": "echo",
            "version": 1,
            "title": "Echo",
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "outcomes": ["completed"],
            "plan": {"name": "echo", "nodes": [], "edges": []},
            "required_capabilities": {
                "demo.foo.bar": {"kind": "node_spec"},
            },
        }
    )

    dumped = artifact.model_dump(mode="json")
    assert dumped["required_capabilities"][0]["ref"] == {
        "source": "demo.foo",
        "capability_key": "bar",
    }
```

This test documents legacy string parsing as best-effort. New artifact creation should avoid this path when source bindings are known.

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
uv run --with pytest pytest tests/wf_artifacts/test_models.py -q
```

Expected: dumps still contain old string refs.

- [ ] **Step 3: Update model serialization**

After Task 1, `RequiredCapability.ref` should dump structurally automatically. Ensure `WorkflowArtifact._reject_duplicate_required_capabilities` still works by using `str(capability.capability_ref())` only for internal duplicate checking.

- [ ] **Step 4: Update reference creation**

In `src/wf_artifacts/references.py`, replace this conceptual behavior:

```python
logical_ref = "demo.foo.bar"
RequiredCapability(ref=CapabilityRef.parse(logical_ref), ...)
```

with structural construction:

```python
capability_ref = CapabilityRef(
    source=SourceRef.parse(logical_source),
    name=capability_name,
)
RequiredCapability(ref=capability_ref, ...)
```

Only derive `str(capability_ref)` for compatibility map keys.

- [ ] **Step 5: Run tests to verify green**

Run:

```bash
uv run --with pytest pytest tests/wf_artifacts/test_models.py tests/wf_mcp/test_workflow_surface.py -q
```

Expected: artifact creation still works; saved dumps use structural refs.

---

## Task 4: Make Deployment Bindings Structural on Save

**Files:**
- Modify: `src/wf_artifacts/models.py`
- Test: `tests/wf_artifacts/test_models.py`
- Test: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Write failing binding serialization test**

```python
from wf_artifacts import WorkflowDeployment


def test_workflow_deployment_accepts_legacy_binding_map_but_dumps_structural_list() -> None:
    deployment = WorkflowDeployment.model_validate(
        {
            "id": "echo.personal",
            "artifact_id": "echo",
            "artifact_version": 1,
            "bindings": {"demo": "demo.personal", "wf.std": "wf.std"},
        }
    )

    dumped = deployment.model_dump(mode="json")
    assert dumped["bindings"] == [
        {"logical_source": "demo", "concrete_source": "demo.personal"},
        {"logical_source": "wf.std", "concrete_source": "wf.std"},
    ]
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
uv run --with pytest pytest tests/wf_artifacts/test_models.py -q
```

Expected: output may already be a list, but confirm `SourceRef` serialization remains stable.

- [ ] **Step 3: Keep current binding shape but document it as structural**

`SourceBinding` already separates logical and concrete source fields. Add docstrings explaining:

- `logical_source` is an artifact-local alias.
- `concrete_source` is the deployment-selected source id.
- neither field is a capability name.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --with pytest pytest tests/wf_artifacts/test_models.py tests/wf_mcp/test_workflow_surface.py -q
```

Expected: all tests pass.

---

## Task 5: Stop Parsing Workflow Capability Strings as Generic Capabilities

**Files:**
- Modify: `src/wf_mcp/workflow_surface/refs.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_mcp/test_workflow_surface_refs.py`
- Test: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Write tests for separate ref domains**

```python
from wf_artifacts import WorkflowCapabilityRef
from wf_mcp.workflow_surface.refs import parse_workflow_surface_capability_id
from wf_platform import CapabilityRef


def test_workflow_surface_ref_parser_keeps_workflow_artifacts_separate() -> None:
    parsed = parse_workflow_surface_capability_id("workflow.echo_wrapper.v1")

    assert isinstance(parsed, WorkflowCapabilityRef)
    assert parsed.artifact_id == "echo_wrapper"
    assert parsed.version == 1


def test_workflow_surface_ref_parser_keeps_source_capabilities_structural() -> None:
    parsed = parse_workflow_surface_capability_id(
        {"source": "demo", "capability_key": "foo.bar"}
    )

    assert isinstance(parsed, CapabilityRef)
    assert str(parsed.source) == "demo"
    assert parsed.name == "foo.bar"
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface_refs.py -q
```

Expected: dict input fails because parser currently accepts strings only.

- [ ] **Step 3: Update parser input type**

Allow parser input as:

```python
str | dict[str, object]
```

Rules:

- if string starts with `workflow.`, try `WorkflowCapabilityRef.parse`
- if dict has `artifact_id` and `version`, parse as workflow artifact ref
- otherwise parse as `CapabilityRef`

- [ ] **Step 4: Run workflow surface tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface_refs.py tests/wf_mcp/test_workflow_surface.py -q
```

Expected: all tests pass.

---

## Task 6: Keep Runtime Binding Source-Aware

**Files:**
- Modify: `src/wf_mcp/workflow_surface/runtime_dependencies.py`
- Test: `tests/wf_mcp/test_service.py`

- [ ] **Step 1: Keep the dotted-local-name regression**

Ensure this test remains:

```python
def test_service_runs_logical_source_plan_with_dotted_local_name() -> None:
    ...
    plan = _single_echo_plan("logical_dotted_local_name_plan", "demo.foo.bar")
    ...
    bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}]
    ...
    assert run.output["echoed"] == "hello"
```

- [ ] **Step 2: Add a unit test for longest binding prefix**

Add a focused test through public runtime behavior where both `demo` and `demo.pro` are bound, and `demo.pro.foo.bar` resolves through `demo.pro`.

- [ ] **Step 3: Keep `_bound_node_names` or move it to a shared helper**

If more than one module needs source-prefix binding, move the helper to a small module such as:

```text
src/wf_artifacts/bindings.py
```

Do not move it preemptively if runtime remains the only caller.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_service.py -q
```

Expected: all tests pass.

---

## Task 7: Update Docs to State the Rule

**Files:**
- Modify: `docs/workflow_capabilities.md`
- Create or modify: `docs/structural_refs.md`

- [ ] **Step 1: Add the core rule**

Add this rule prominently:

```text
Qualified names are display strings. They are not authoritative identifiers.
Saved workflow artifacts and deployments should store structural refs.
Old strings are accepted at API boundaries only for compatibility.
```

- [ ] **Step 2: Add examples**

Include examples for:

```json
{"source": "demo", "capability_key": "foo.bar"}
```

```json
{"artifact_id": "echo_wrapper", "version": 1}
```

```json
{"logical_source": "demo", "concrete_source": "demo.personal"}
```

- [ ] **Step 3: Mention path refs are separate**

Add:

```text
Capability refs and graph paths are different domains. Path strings such as
state.person.name should migrate separately to path models.
```

---

## Task 8: Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --with pytest pytest tests/wf_platform tests/wf_artifacts tests/wf_mcp/test_service.py tests/wf_mcp/test_workflow_surface.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full tests when workspace is stable**

Run:

```bash
uv run --with pytest pytest -q
```

Expected: full suite passes, except any explicitly user-owned temporary rewrite tests if the user says to ignore them.

- [ ] **Step 3: Run linters/type checker**

Run:

```bash
uvx ruff check
uv run basedpyright --level error
```

Expected: no new errors.

---

## Self-Review Notes

- This plan does not require changing all workflow plan node refs in one pass. Runtime accepts legacy plan strings while artifact metadata becomes structural first.
- This plan does not solve graph path ambiguity. Graph paths need their own migration to `GraphPath`/`LocalPath`.
- This plan does not force `profile` into every model immediately. It keeps `SourceRef` compatible and documents `profile` as future concrete source structure.
- This plan keeps MCP/client compatibility by accepting old string inputs and continuing to display derived names.
