# Core Path Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace loose core path/map strings with typed path objects and canonical list-of-struct node bindings while keeping deprecated shapes parse-compatible.

**Architecture:** Add immutable path value objects in `wf_core.paths`, then introduce canonical binding models in `wf_core.models.steps`. Runtime and validation move to the canonical bindings, while old `in_map`, `input_values`, `out_map`, and dict-shaped state fields are accepted only by model validators.

**Tech Stack:** Python 3.14, Pydantic v2, pytest, jsonschema, basedpyright, ruff.

**Current status as of 2026-05-20:** The implementation has moved past the
original checklist. Typed path values, canonical node bindings, canonical
runtime input/output handling, atomic state patches, canonical validation,
JSON-Schema-native state reducers, schema validation, and authoring canonical
emission are present in the tree. The remaining checklist item is the full
compatibility/regression pass in Task 9. If future code changes touch this area,
prefer adding focused tests to the existing `tests/core/test_*path*`,
`tests/core/test_*mapping*`, and `tests/authoring/test_builder.py` coverage
rather than reimplementing the earlier tasks.

---

## File Structure

- Modify `src/wf_core/paths.py`: own typed graph/state/local path objects and graph path resolution helpers.
- Modify `src/wf_core/local_paths.py`: keep compatibility wrappers over `LocalPath` plus local get/set helpers.
- Modify `src/wf_core/models/steps.py`: add `InputPathBinding`, `InputValueBinding`, `OutputBinding`, and canonical `NodeUse.input` / `NodeUse.output`.
- Modify `src/wf_core/models/conditions.py`: type condition path operands with `GraphSourcePath`.
- Modify `src/wf_core/models/schemas.py`: harden `SchemaRef` and add canonical state field declarations.
- Modify `src/wf_core/runtime/ops/nodes.py`: resolve canonical node input bindings.
- Modify `src/wf_core/runtime/ops/state.py`: apply canonical output bindings through an atomic state patch.
- Modify `src/wf_core/runtime/ops/schemas.py`: expose focused JSON Schema validation helpers.
- Modify `src/wf_core/validation/steps.py`: validate canonical bindings and typed paths.
- Modify `src/wf_authoring/dsl/paths.py`: emit core path objects while preserving ergonomic helpers.
- Modify `src/wf_authoring/dsl/conditions.py`: compile authoring expressions to core typed condition models.
- Add `tests/core/test_path_values.py`: path parsing, serialization, JSON Schema, and error tests.
- Add `tests/core/test_canonical_node_bindings.py`: canonical model parsing and deprecated compatibility tests.
- Add `tests/core/test_atomic_state_patches.py`: output binding, reducer, overlap, and atomicity tests.
- Update existing `tests/core/test_mapping_validation.py`, `tests/core/test_nested_mappings.py`, `tests/core/test_nested_state_paths.py`, and authoring tests as needed.

## Task 1: Add Typed Path Values

**Files:**

- Modify: `src/wf_core/paths.py`
- Modify: `src/wf_core/local_paths.py`
- Create: `tests/core/test_path_values.py`

- [ ] **Step 1: Write path value tests**

Add tests for parsing, string serialization, equality/hashability, invalid segments, root-only graph source reads, and no bare write state:

```python
import pytest
from pydantic import BaseModel, ValidationError

from wf_core.paths import GraphSourcePath, LocalPath, PathResolutionError, StatePath


def test_graph_source_path_accepts_root_and_nested_paths():
    assert str(GraphSourcePath.parse("state")) == "state"
    assert str(GraphSourcePath.parse("input.user")) == "input.user"
    assert str(GraphSourcePath.context("loop_item")) == "context.loop_item"


def test_state_path_rejects_bare_state_write_target():
    with pytest.raises(PathResolutionError, match="state path"):
        StatePath.parse("state")


def test_local_path_supports_root_marker():
    assert str(LocalPath.root()) == "."
    assert str(LocalPath.of("user.name")) == "user.name"


@pytest.mark.parametrize("raw", ["", "state.", "state.items.0", "state.user-name"])
def test_paths_reject_invalid_segments(raw: str):
    with pytest.raises(PathResolutionError):
        GraphSourcePath.parse(raw)


def test_path_objects_are_hashable():
    paths = {StatePath.of("person.name"), StatePath.of("person.name")}
    assert len(paths) == 1


def test_pydantic_accepts_path_strings_and_serializes_strings():
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    payload = Payload.model_validate(
        {"source": "input.user", "target": "state.person", "local": "user"}
    )
    assert payload.source == GraphSourcePath.input("user")
    assert payload.model_dump(mode="json")["target"] == "state.person"


def test_pydantic_rejects_bad_path_string():
    class Payload(BaseModel):
        source: GraphSourcePath

    with pytest.raises(ValidationError):
        Payload.model_validate({"source": "output.foo"})
```

- [ ] **Step 2: Run path tests to verify they fail**

Run: `uv run --with pytest pytest tests/core/test_path_values.py -q`

Expected: failures because `GraphSourcePath`, `StatePath`, and `LocalPath` classes do not exist or do not validate strictly.

- [ ] **Step 3: Implement path value classes**

In `src/wf_core/paths.py`, add frozen dataclasses and shared parsing helpers. Keep existing helper function names as compatibility wrappers where practical.

Implementation shape:

```python
from dataclasses import dataclass
import re
from typing import Any, ClassVar, Literal

SEGMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class LocalPath:
    """Node-local payload path. `.` means the whole local payload."""

    parts: tuple[str, ...]

    @classmethod
    def root(cls) -> "LocalPath":
        return cls(())

    @classmethod
    def of(cls, *fragments: str) -> "LocalPath":
        return cls(_parse_fragments(*fragments, allow_empty=False))

    @classmethod
    def parse(cls, raw: str) -> "LocalPath":
        if raw == ".":
            return cls.root()
        return cls.of(raw)

    def __str__(self) -> str:
        return "." if not self.parts else ".".join(self.parts)
```

Also add:

```python
GraphRoot = Literal["input", "state", "context"]


@dataclass(frozen=True)
class GraphSourcePath:
    """Readable workflow graph path rooted at input, state, or context."""

    root: GraphRoot
    parts: tuple[str, ...] = ()

    @classmethod
    def parse(cls, raw: str) -> "GraphSourcePath": ...

    @classmethod
    def input(cls, *fragments: str) -> "GraphSourcePath": ...

    @classmethod
    def state(cls, *fragments: str) -> "GraphSourcePath": ...

    @classmethod
    def context(cls, *fragments: str) -> "GraphSourcePath": ...
```

And:

```python
@dataclass(frozen=True)
class StatePath:
    """Writable workflow state path. Bare `state` is intentionally invalid."""

    parts: tuple[str, ...]

    @classmethod
    def parse(cls, raw: str) -> "StatePath":
        parsed = GraphSourcePath.parse(raw)
        if parsed.root != "state" or not parsed.parts:
            raise PathResolutionError("expected state path such as state.foo")
        return cls(parsed.parts)

    @classmethod
    def of(cls, *fragments: str) -> "StatePath": ...
```

Add Pydantic `__get_pydantic_core_schema__` and `__get_pydantic_json_schema__` hooks for each class so strings validate into objects and serialize back to strings.

- [ ] **Step 4: Update local path wrappers**

In `src/wf_core/local_paths.py`, keep public functions but delegate parsing to `LocalPath.parse`:

```python
def split_local_path(path: str | LocalPath) -> list[str]:
    """Split one node-local path, accepting the new typed path object."""
    parsed = path if isinstance(path, LocalPath) else LocalPath.parse(path)
    return list(parsed.parts)
```

Update `paths_overlap` and `has_overlapping_paths` to accept `str | LocalPath`.

- [ ] **Step 5: Run path tests**

Run: `uv run --with pytest pytest tests/core/test_path_values.py -q`

Expected: all tests in `test_path_values.py` pass.

## Task 2: Add Canonical Node Binding Models

**Files:**

- Modify: `src/wf_core/models/steps.py`
- Test: `tests/core/test_canonical_node_bindings.py`

- [ ] **Step 1: Write canonical binding tests**

Create `tests/core/test_canonical_node_bindings.py`:

```python
import pytest
from pydantic import ValidationError

from wf_core.models.steps import NodeUse
from wf_core.paths import GraphSourcePath, LocalPath, StatePath


def test_node_use_accepts_canonical_input_and_output_bindings():
    node = NodeUse.model_validate(
        {
            "id": "echo",
            "type": "node",
            "node": "echo",
            "input": [
                {"target": "message", "path": "input.message"},
                {"target": "mode", "value": None},
            ],
            "output": [{"source": "echoed", "target": "state.echoed"}],
        }
    )

    assert node.input[0].target == LocalPath.of("message")
    assert node.input[0].path == GraphSourcePath.input("message")
    assert node.input[1].value is None
    assert node.output[0].target == StatePath.of("echoed")


def test_node_use_converts_old_maps_to_canonical_bindings():
    node = NodeUse.model_validate(
        {
            "id": "echo",
            "type": "node",
            "node": "echo",
            "in_map": {"input.message": "message"},
            "input_values": {"mode": "fast"},
            "out_map": {"echoed": "state.echoed"},
        }
    )

    dumped = node.model_dump(mode="json")
    assert "in_map" not in dumped
    assert "input_values" not in dumped
    assert "out_map" not in dumped
    assert dumped["input"][0]["path"] == "input.message"
    assert dumped["input"][1]["value"] == "fast"
    assert dumped["output"][0]["target"] == "state.echoed"


def test_node_use_rejects_mixed_old_and_new_binding_styles():
    with pytest.raises(ValidationError):
        NodeUse.model_validate(
            {
                "id": "echo",
                "type": "node",
                "node": "echo",
                "input": [{"target": "message", "path": "input.message"}],
                "in_map": {"input.other": "other"},
            }
        )


def test_input_binding_rejects_path_and_value_together():
    with pytest.raises(ValidationError):
        NodeUse.model_validate(
            {
                "id": "bad",
                "type": "node",
                "node": "bad",
                "input": [
                    {"target": "message", "path": "input.message", "value": "x"}
                ],
            }
        )
```

- [ ] **Step 2: Run binding tests to verify they fail**

Run: `uv run --with pytest pytest tests/core/test_canonical_node_bindings.py -q`

Expected: failures because canonical binding fields do not exist yet.

- [ ] **Step 3: Implement binding models**

In `src/wf_core/models/steps.py`, add:

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator
from wf_core.paths import GraphSourcePath, LocalPath, StatePath


class InputPathBinding(BaseModel):
    """Map one graph source path into one node-local input path."""

    model_config = ConfigDict(extra="forbid")

    target: LocalPath
    path: GraphSourcePath


class InputValueBinding(BaseModel):
    """Map one static JSON-compatible value into one node-local input path."""

    model_config = ConfigDict(extra="forbid")

    target: LocalPath
    value: object


InputBinding = Annotated[
    InputPathBinding | InputValueBinding,
    Field(union_mode="left_to_right"),
]


class OutputBinding(BaseModel):
    """Map one node-local output path into one workflow state path."""

    model_config = ConfigDict(extra="forbid")

    source: LocalPath
    target: StatePath
```

Update `NodeUse`:

```python
class NodeUse(BaseModel):
    ...
    input: list[InputBinding] = Field(default_factory=list)
    output: list[OutputBinding] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_deprecated_maps(cls, data: object) -> object:
        ...
```

The validator should:

- If `input` or `output` is present, reject any of `in_map`, `input_values`, `out_map`.
- Convert `input_values` entries to `{"target": key, "value": value}` preserving order.
- Convert `in_map` entries to `{"target": destination, "path": source}` preserving order.
- Convert `out_map` entries to `{"source": source, "target": destination}` preserving order.
- Remove old keys from the normalized data.

- [ ] **Step 4: Run binding tests**

Run: `uv run --with pytest pytest tests/core/test_canonical_node_bindings.py -q`

Expected: all tests in `test_canonical_node_bindings.py` pass.

## Task 3: Move Runtime Node Input Resolution To Canonical Bindings

**Files:**

- Modify: `src/wf_core/runtime/ops/nodes.py`
- Test: `tests/core/test_nested_mappings.py`
- Test: `tests/core/test_canonical_node_bindings.py`

- [ ] **Step 1: Add runtime tests for canonical input binding behavior**

In `tests/core/test_nested_mappings.py`, add a test that builds the existing minimal workflow style but uses `input` / `output` instead of old maps:

```python
def test_canonical_bindings_resolve_input_values_and_paths():
    workflow = Workflow.model_validate(
        {
            "name": "canonical",
            "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}},
            "state_schema": {"fields": {"echoed": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"echoed": {"type": "string"}}},
            "start": "echo",
            "node_defs": [
                {
                    "name": "echo",
                    "input_schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}, "mode": {"type": "string"}},
                        "required": ["message", "mode"],
                    },
                    "output_schema": {"type": "object", "properties": {"echoed": {"type": "string"}}},
                    "outcomes": ["ok"],
                }
            ],
            "nodes": [
                {
                    "id": "echo",
                    "type": "node",
                    "node": "echo",
                    "input": [
                        {"target": "message", "path": "input.message"},
                        {"target": "mode", "value": "fast"},
                    ],
                    "output": [{"source": "echoed", "target": "state.echoed"}],
                }
            ],
            "edges": [{"from": "echo", "outcome": "ok", "to": "__end__"}],
        }
    )

    result = execute_workflow(
        workflow,
        {"message": "hi"},
        registry={"echo": lambda payload, _ctx: {"echoed": f"{payload['mode']}:{payload['message']}"}},
    )

    assert result.output["echoed"] == "fast:hi"
```

- [ ] **Step 2: Run the focused test to verify failure**

Run: `uv run --with pytest pytest tests/core/test_nested_mappings.py::test_canonical_bindings_resolve_input_values_and_paths -q`

Expected: failure because runtime still reads `node.input_values`, `node.in_map`, and `node.out_map`.

- [ ] **Step 3: Update `_resolve_node_execution`**

In `src/wf_core/runtime/ops/nodes.py`, import binding classes and use `node.input`.

Implementation shape:

```python
from wf_core.models.steps import InputPathBinding, InputValueBinding


for binding in node.input:
    if isinstance(binding, InputValueBinding):
        value = binding.value
    else:
        value = safe_resolve_path(
            str(binding.path),
            state=run.state,
            workflow_input=run.workflow_input,
            context=context_values,
        )
    set_local_value(resolved_input, binding.target, value)
```

`set_local_value` should accept `LocalPath` after Task 1.

- [ ] **Step 4: Run canonical runtime test**

Run: `uv run --with pytest pytest tests/core/test_nested_mappings.py::test_canonical_bindings_resolve_input_values_and_paths -q`

Expected: pass.

## Task 4: Move Runtime Output Writes To Canonical Bindings And Atomic Patches

**Files:**

- Modify: `src/wf_core/runtime/ops/state.py`
- Modify: `src/wf_core/runtime/ops/nodes.py`
- Test: `tests/core/test_atomic_state_patches.py`

- [ ] **Step 1: Write atomic patch tests**

Create `tests/core/test_atomic_state_patches.py`:

```python
import pytest

from wf_core.errors import WorkflowExecutionError
from wf_core.models.workflow import Workflow
from wf_core.runtime.ops.state import apply_output_bindings


def _workflow() -> Workflow:
    return Workflow.model_validate(
        {
            "name": "patch",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {
                "fields": {
                    "person": {"type": "object"},
                    "person.name": {"type": "string"},
                }
            },
            "output_schema": {"type": "object", "properties": {}},
            "start": "n",
            "nodes": [],
            "edges": [],
        }
    )


def test_output_bindings_commit_patch_atomically():
    workflow = _workflow()
    state = {"person": {"name": "old"}}

    with pytest.raises(WorkflowExecutionError):
        apply_output_bindings(
            workflow,
            [
                {"source": "person.name", "target": "state.person.name"},
                {"source": "missing", "target": "state.person.extra"},
            ],
            {"person": {"name": "new"}},
            state,
        )

    assert state["person"]["name"] == "old"


def test_output_bindings_reject_overlapping_write_targets():
    workflow = _workflow()
    state = {}

    with pytest.raises(WorkflowExecutionError, match="overlapping"):
        apply_output_bindings(
            workflow,
            [
                {"source": "person", "target": "state.person"},
                {"source": "person.name", "target": "state.person.name"},
            ],
            {"person": {"name": "Ada"}},
            state,
        )
```

- [ ] **Step 2: Run atomic patch tests to verify failure**

Run: `uv run --with pytest pytest tests/core/test_atomic_state_patches.py -q`

Expected: failure because `apply_output_bindings` does not exist.

- [ ] **Step 3: Implement `apply_output_bindings`**

In `src/wf_core/runtime/ops/state.py`, add a canonical function:

```python
from wf_core.models.steps import OutputBinding
from wf_core.paths import StatePath


def apply_output_bindings(
    workflow: Workflow,
    bindings: Sequence[OutputBinding],
    node_output: dict[str, Any],
    state: dict[str, Any],
    reducers: Mapping[str, ReducerDefinition] | None = None,
) -> dict[str, Any]:
    """Prepare and commit one atomic state patch from canonical output bindings."""
```

Function behavior:

- Validate no overlapping `binding.target`.
- Resolve every `binding.source` from `node_output` first.
- Build a prepared patch keyed by `StatePath`.
- Compute reducers into prepared merged values without mutating `state`.
- Commit all prepared values only after all prior steps succeed.
- Return JSON-friendly `dict[str, Any]` state changes using `str(path)` keys for now, until trace is separately migrated.

Keep `apply_output_map` as a compatibility wrapper that converts old map entries into `OutputBinding` and calls `apply_output_bindings`.

- [ ] **Step 4: Update node finalization**

In `src/wf_core/runtime/ops/nodes.py`, call `apply_output_bindings(workflow, node.output, result.output, run.state, reducers=reducers)` instead of `apply_output_map(...)`.

- [ ] **Step 5: Run state patch tests**

Run: `uv run --with pytest pytest tests/core/test_atomic_state_patches.py tests/core/test_nested_mappings.py -q`

Expected: pass.

## Task 5: Update Validation For Canonical Bindings

**Files:**

- Modify: `src/wf_core/validation/steps.py`
- Test: `tests/core/test_mapping_validation.py`
- Test: `tests/core/test_canonical_node_bindings.py`

- [ ] **Step 1: Add validation tests for canonical fields**

In `tests/core/test_mapping_validation.py`, add tests for invalid source paths, invalid destination paths, overlapping local input targets, and overlapping state output targets using canonical `input` / `output`.

Example:

```python
def test_validate_workflow_reports_overlapping_canonical_output_targets():
    workflow = workflow_with_node(
        node_use={
            "id": "n",
            "type": "node",
            "node": "n",
            "output": [
                {"source": "person", "target": "state.person"},
                {"source": "person.name", "target": "state.person.name"},
            ],
        }
    )

    report = workflow.validate_structure()

    assert any(issue.code == ValidationIssueCode.INVALID_DESTINATION_PATH for issue in report.issues)
```

Use the existing helper style in `tests/core/test_mapping_validation.py` rather than inventing a second full workflow factory if one already exists.

- [ ] **Step 2: Run mapping validation tests**

Run: `uv run --with pytest pytest tests/core/test_mapping_validation.py -q`

Expected: new canonical validation tests fail until validation reads `node.input` / `node.output`.

- [ ] **Step 3: Update `validate_node_use`**

In `src/wf_core/validation/steps.py`:

- Iterate `node.input`.
- For `InputValueBinding`, validate target local root against node input schema.
- For `InputPathBinding`, validate target and source graph path.
- Iterate `node.output`.
- Validate output source local root against node output schema.
- Validate destination `StatePath`.
- Use typed overlap helpers instead of raw map values.
- Keep issue paths readable, e.g. `nodes[0].input[1].target`.

- [ ] **Step 4: Run validation tests**

Run: `uv run --with pytest pytest tests/core/test_mapping_validation.py tests/core/test_canonical_node_bindings.py -q`

Expected: pass.

## Task 6: Add Canonical State Schema Fields

**Files:**

- Modify: `src/wf_core/models/schemas.py`
- Modify: `src/wf_core/runtime/ops/state.py`
- Modify: `src/wf_core/validation/steps.py`
- Test: `tests/core/test_nested_state_paths.py`
- Test: `tests/core/test_schema_validation.py`

- [ ] **Step 1: Write state schema canonical shape tests**

In `tests/core/test_nested_state_paths.py`, add:

```python
from wf_core.models.schemas import StateSchema
from wf_core.paths import StatePath


def test_state_schema_accepts_canonical_field_list():
    schema = StateSchema.model_validate(
        {
            "fields": [
                {"path": "state.person", "type": "object"},
                {"path": "state.person.name", "type": "string", "reducer": "wf.std.replace"},
            ]
        }
    )

    assert schema.fields[0].path == StatePath.of("person")
    assert schema.field_map()["person.name"].type == "string"


def test_state_schema_accepts_deprecated_dict_shape():
    schema = StateSchema.model_validate(
        {"fields": {"person.name": {"type": "string"}}}
    )

    assert schema.model_dump(mode="json")["fields"][0]["path"] == "state.person.name"
```

- [ ] **Step 2: Run state schema tests to verify failure**

Run: `uv run --with pytest pytest tests/core/test_nested_state_paths.py -q`

Expected: failure because `StateSchema.fields` is still a dict.

- [ ] **Step 3: Implement canonical `StateFieldDecl`**

In `src/wf_core/models/schemas.py`:

```python
class StateFieldDecl(BaseModel):
    """One declared state path plus validation and reducer metadata."""

    path: StatePath
    schema: SchemaRef = Field(default_factory=lambda: SchemaRef(type="object"))
    reducer: ReducerRef = Field(default_factory=lambda: ReducerRef(name="wf.std.replace"))
    trace: bool = True
    default: Any = None
```

Preserve compatibility for old `type` directly on the field:

- For old dict values like `{"type": "string"}`, convert to `{"schema": {"type": "string"}}`.
- For canonical values, allow either `schema` or simple `type` as input if that keeps existing tests stable.

Update `StateSchema`:

```python
class StateSchema(BaseModel):
    fields: list[StateFieldDecl] = Field(default_factory=list)

    def field_map(self) -> dict[str, StateFieldDecl]:
        return {".".join(field.path.parts): field for field in self.fields}
```

Add a model validator to accept old dict shape and normalize to list.

- [ ] **Step 4: Update callers of `workflow.state_schema.fields`**

Search: `rg 'state_schema\\.fields|\\.fields\\.get|set\\(workflow\\.state_schema\\.fields\\)' src tests`

Update code to use `workflow.state_schema.field_map()` when it needs lookup by rootless path.

Important updates:

- `src/wf_core/runtime/ops/state.py`
- `src/wf_core/validation/steps.py`
- any authoring or artifact code constructing state field maps.

- [ ] **Step 5: Run state schema tests**

Run: `uv run --with pytest pytest tests/core/test_nested_state_paths.py tests/core/test_schema_validation.py -q`

Expected: pass.

## Task 7: Harden SchemaRef With JSON Schema Validation

**Files:**

- Modify: `src/wf_core/models/schemas.py`
- Modify: `src/wf_core/runtime/ops/schemas.py`
- Test: `tests/core/test_schema_validation.py`

- [ ] **Step 1: Add schema validation tests**

In `tests/core/test_schema_validation.py`, add tests:

```python
import pytest
from pydantic import ValidationError

from wf_core.models.schemas import SchemaRef


def test_schema_ref_accepts_valid_json_schema_with_defs():
    schema = SchemaRef.model_validate(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "$defs": {"Name": {"type": "string"}},
            "properties": {"name": {"$ref": "#/$defs/Name"}},
        }
    )

    assert schema.model_extra["$defs"]["Name"]["type"] == "string"


def test_schema_ref_rejects_invalid_json_schema():
    with pytest.raises(ValidationError):
        SchemaRef.model_validate({"type": 123})
```

- [ ] **Step 2: Run schema tests to verify failure**

Run: `uv run --with pytest pytest tests/core/test_schema_validation.py -q`

Expected: invalid schema is currently accepted.

- [ ] **Step 3: Add `jsonschema` validation**

In `src/wf_core/models/schemas.py`, import:

```python
from jsonschema import SchemaError
from jsonschema.validators import Draft202012Validator, validator_for
from pydantic import model_validator
```

Add an after validator to `SchemaRef`:

```python
@model_validator(mode="after")
def _validate_json_schema(self) -> "SchemaRef":
    raw = self.model_dump(mode="python", exclude_none=True)
    validator_cls = validator_for(raw, default=Draft202012Validator)
    try:
        validator_cls.check_schema(raw)
    except SchemaError as exc:
        raise ValueError(f"invalid JSON Schema: {exc.message}") from exc
    return self
```

- [ ] **Step 4: Run schema tests**

Run: `uv run --with pytest pytest tests/core/test_schema_validation.py -q`

Expected: pass.

## Task 8: Update Authoring Helpers To Emit Canonical Bindings

**Files:**

- Modify: `src/wf_authoring/dsl/paths.py`
- Modify: `src/wf_authoring/dsl/conditions.py`
- Modify: `src/wf_authoring/builder/core.py`
- Test: `tests/authoring/test_builder.py`
- Test: `tests/authoring/test_conditions.py`
- Test: `tests/authoring/test_control_flow_examples.py`

- [ ] **Step 1: Add authoring tests for canonical dumps**

In `tests/authoring/test_builder.py`, add a test that builds a workflow and asserts the dumped node uses canonical `input` / `output`, not old maps:

```python
def test_builder_emits_canonical_node_bindings():
    workflow = (
        WorkflowBuilder("canonical")
        .schemas(
            input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
            state_schema={"fields": {"echoed": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"echoed": {"type": "string"}}},
        )
        .use(echo_node, id="echo", in_map={"input.message": "message"}, out_map={"echoed": "state.echoed"})
        .start_at("echo")
        .end("echo", "ok")
        .build()
    )

    dumped_node = workflow.model_dump(mode="json")["nodes"][0]
    assert "input" in dumped_node
    assert "output" in dumped_node
    assert "in_map" not in dumped_node
    assert "out_map" not in dumped_node
```

Adapt helper names to the current builder API in the file.

- [ ] **Step 2: Run authoring builder tests**

Run: `uv run --with pytest pytest tests/authoring/test_builder.py tests/authoring/test_conditions.py -q`

Expected: new canonical dump test may fail until builder emits or model normalizes canonical shapes.

- [ ] **Step 3: Update path/condition authoring wrappers**

In `src/wf_authoring/dsl/paths.py`, make ergonomic helpers return wrappers around core path values or values accepted by core models. Preserve existing public behavior where possible:

```python
def state_path(*parts: str) -> GraphPath:
    return GraphPath(str(GraphSourcePath.state(*parts)))
```

In `src/wf_authoring/dsl/conditions.py`, make `PathExpr` compile using `GraphSourcePath.parse` for `PathOperand`.

- [ ] **Step 4: Update builder to rely on canonical model normalization**

In `src/wf_authoring/builder/core.py`, either emit canonical binding dicts directly or keep passing old maps into `NodeUse.model_validate`. Prefer direct canonical emission where the builder already has enough structure.

Do not remove user-facing `in_map` / `out_map` builder parameters in this pass.

- [ ] **Step 5: Run authoring tests**

Run: `uv run --with pytest pytest tests/authoring -q`

Expected: authoring tests pass.

## Task 9: Full Compatibility And Regression Pass

**Files:**

- Modify docs/examples only if tests show stale serialized shapes.
- Test: full repo.

- [ ] **Step 1: Run core tests**

Run: `uv run --with pytest pytest tests/core tests/authoring tests/rewrite -q`

Expected: pass.

- [ ] **Step 2: Run artifact and MCP workflow-surface tests**

Run: `uv run --with pytest pytest tests/artifacts tests/wf_mcp/test_workflow_surface.py tests/wf_mcp/test_workflow_wrappers.py tests/wf_mcp/test_mcp_workflow_surface_example.py -q`

Expected: pass.

- [ ] **Step 3: Run full test suite**

Run: `uv run --with pytest pytest -q`

Expected: pass, allowing any existing intentionally skipped environment-dependent tests.

- [ ] **Step 4: Run static checks**

Run:

```bash
uvx ruff check
uv run basedpyright --level error
```

Expected: ruff passes and basedpyright reports 0 errors.

- [ ] **Step 5: Format touched files**

Run:

```bash
uvx ruff format src/wf_core src/wf_authoring tests/core tests/authoring
```

Expected: files format cleanly.

## Self-Review Notes

- Spec coverage: typed paths, canonical bindings, parse-only compatibility, null/missing semantics, dynamic traversal deferral, state patch atomicity, reducer behavior, JSON Schema validation, authoring updates, and tracing shape are covered. Full trace migration is intentionally not implemented beyond returning string-keyed `state_changes` for compatibility.
- Placeholder scan: this plan avoids `TBD` and names concrete files, tests, commands, and behavior.
- Type consistency: `LocalPath`, `GraphSourcePath`, `StatePath`, `InputPathBinding`, `InputValueBinding`, `OutputBinding`, and `StateFieldDecl` are introduced before later tasks use them.
