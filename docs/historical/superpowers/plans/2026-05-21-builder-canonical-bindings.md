# Builder Canonical Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `WorkflowBuilder.use()` and `WorkflowBuilder.use_ref()` expose canonical `input` / `output` binding lists, while keeping `in_map`, `input_values`, and `out_map` as deprecated Python sugar.

**Architecture:** `wf_core.NodeUse` already stores canonical binding structs: `InputPathBinding`, `InputValueBinding`, and `OutputBinding`. The builder should accept those same structs/dicts directly, normalize them through core models, and reject mixed canonical/deprecated arguments. Map sugar remains for pleasant Python authoring, but JSON/MCP-facing callers should use binding lists so structural path dicts live inside structs, not as unhashable mapping keys.

**Tech Stack:** Python 3.14, Pydantic models from `wf_core.models.steps`, `wf_authoring.WorkflowBuilder`, pytest, basedpyright, ruff.

---

## Why the Previous Plan Did Not Finish This

`2026-05-21-authoring-path-inputs.md` focused on path coercion:

- single-string TOML path parsing
- iterable/vararg literal segments
- typed `GraphPath`
- map normalization from `dict[str, str]` toward typed paths

That plan made `in_map`, `input_values`, and `out_map` safer, but it did not change the public builder API shape. So the current state is still incomplete:

```python
g.use(node, in_map=..., input_values=..., out_map=...)
```

exists, but:

```python
g.use(node, input=[...], output=[...])
```

does not.

That matters because structural path dicts cannot be Python dict keys. The JSON/MCP-friendly shape must be list-of-structs:

```json
{
  "input": [
    {
      "target": { "root": "local", "parts": ["payload.email"] },
      "path": { "root": "input", "parts": ["email.address"] }
    }
  ],
  "output": [
    {
      "source": { "root": "local", "parts": ["result.score"] },
      "target": { "root": "state", "parts": ["score"] }
    }
  ]
}
```

---

## Current State

Core already has the right canonical models in `src/wf_core/models/steps.py`:

```python
class InputPathBinding(BaseModel):
    target: LocalPath
    path: GraphSourcePath


class InputValueBinding(BaseModel):
    target: LocalPath
    value: object


class OutputBinding(BaseModel):
    source: LocalPath
    target: StatePath


class NodeUse(BaseModel):
    input: list[InputBinding] = Field(default_factory=list)
    output: list[OutputBinding] = Field(default_factory=list)
```

Builder currently has only deprecated/sugar arguments in `src/wf_authoring/builder/core.py`:

```python
def use(
    self,
    spec: NodeSpec[Any, Any],
    *,
    id: str | None = None,
    in_map: MapArg | None = None,
    input_values: Mapping[Any, Any] | None = None,
    out_map: MapArg | None = None,
    desc: str | None = None,
) -> NodeUse:
    ...
```

This is the API gap.

---

## Public Semantics

### Canonical Builder Inputs

Add `input` and `output` parameters:

```python
g.use(
    node,
    input=[
        {
            "target": {"root": "local", "parts": ["payload.email"]},
            "path": {"root": "input", "parts": ["email.address"]},
        },
        {
            "target": {"root": "local", "parts": ["static.limit"]},
            "value": 10,
        },
    ],
    output=[
        {
            "source": {"root": "local", "parts": ["result.score"]},
            "target": {"root": "state", "parts": ["score"]},
        },
    ],
)
```

Accepted item shapes:

- existing `InputPathBinding`
- existing `InputValueBinding`
- existing `OutputBinding`
- dicts that `InputPathBinding` / `InputValueBinding` / `OutputBinding` can validate

### Deprecated Sugar Inputs

Keep these for Python authors:

```python
g.use(node, in_map={state_path("text"): "payload.text"})
g.use(node, input_values={"limit": 10})
g.use(node, out_map={"result.score": state_path("score")})
```

But mark them as deprecated in docstrings and warn when explicitly used.

Auto-mapping still uses the same internal sugar when both canonical and deprecated args are absent.

### Mixing Rules

Reject ambiguous combinations:

- `input` cannot be mixed with `in_map`
- `input` cannot be mixed with `input_values`
- `output` cannot be mixed with `out_map`

Exact error examples:

```text
cannot mix canonical input with deprecated in_map/input_values
cannot mix canonical output with deprecated out_map
```

Use built-in `TypeError` for these authoring API misuse errors. This is similar
in spirit to Pydantic's user-error category: the caller supplied an invalid API
shape, not invalid workflow data.

### Structural Dict Key Rule

Do not support structural dicts as mapping keys. Python `dict` keys must be hashable, and adding `frozendict` support is not worth it.

If a user needs structural dict paths, they should use canonical binding lists:

```python
input=[{"target": {"root": "local", "parts": ["payload"]}, "path": {...}}]
```

Map sugar is for hashable Python authoring values only.

---

## File Structure

- Modify: `src/wf_authoring/builder/core.py`
  - Add `input` / `output` parameters to `use()` and `use_ref()`.
  - Add canonical/deprecated mixing checks.
  - Use canonical binding normalization when provided.
  - Warn when deprecated map-sugar args are explicitly used.

- Modify: `src/wf_authoring/builder/mapping.py`
  - Add `InputBindingArg`, `OutputBindingArg` aliases.
  - Add `normalize_input_bindings(...)`.
  - Add `normalize_output_bindings(...)`.
  - Keep map normalizers as deprecated/sugar internals.

- Modify: `docs/structural_refs.md`
  - Document canonical `input` / `output` list usage for structural path dicts.
  - State that structural dicts are not supported as map keys.

- Modify: `docs/authoring_sketch.md` or `docs/core_state_mapping_and_merge.md`
  - Replace older “builder uses in_map/out_map” framing with “builder accepts canonical lists; maps are sugar.”

- Test:
  - `tests/authoring/test_builder.py`
  - Maybe `tests/authoring/test_path_inputs.py` only if structural dict errors belong there.

---

## Task 1: Add Canonical Binding Normalizers

**Files:**

- Modify: `src/wf_authoring/builder/mapping.py`
- Test: `tests/authoring/test_builder.py`

- [ ] **Step 1: Write failing tests for canonical dict bindings**

Add to `tests/authoring/test_builder.py`:

```python
def test_builder_use_accepts_canonical_binding_dicts_with_structural_paths() -> None:
    builder = WorkflowBuilder(
        name="canonical_binding_dicts",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    step = builder.use(
        auto_bind_node,
        input=[
            {
                "target": {"root": "local", "parts": ["payload.text"]},
                "path": {"root": "input", "parts": ["text.with.dot"]},
            },
            {
                "target": {"root": "local", "parts": ["static.limit"]},
                "value": 3,
            },
        ],
        output=[
            {
                "source": {"root": "local", "parts": ["payload.text"]},
                "target": {"root": "state", "parts": ["text.with.dot"]},
            }
        ],
    )

    assert isinstance(step.input[0], InputPathBinding)
    assert step.input[0].path == GraphSourcePath("input", ("text.with.dot",))
    assert step.input[0].target == LocalPath(("payload.text",))
    assert isinstance(step.input[1], InputValueBinding)
    assert step.input[1].target == LocalPath(("static.limit",))
    assert step.input[1].value == 3
    assert step.output[0].source == LocalPath(("payload.text",))
    assert step.output[0].target == StatePath(("text.with.dot",))
```

Update imports:

```python
from wf_core.models.steps import InputPathBinding, InputValueBinding
```

- [ ] **Step 2: Run test to verify red**

```bash
uv run --with pytest pytest tests/authoring/test_builder.py::test_builder_use_accepts_canonical_binding_dicts_with_structural_paths -q
```

Expected: fails because `WorkflowBuilder.use()` has no `input` / `output` parameters.

- [ ] **Step 3: Add normalizer aliases and functions**

In `src/wf_authoring/builder/mapping.py`, add:

```python
from wf_core.models.steps import InputBinding, InputPathBinding, InputValueBinding, OutputBinding

InputBindingArg: TypeAlias = InputBinding | Mapping[str, object]
OutputBindingArg: TypeAlias = OutputBinding | Mapping[str, object]
```

Add:

```python
def normalize_input_bindings(bindings: Sequence[InputBindingArg] | None) -> list[InputBinding]:
    """Validate canonical input binding structs for WorkflowBuilder.use()."""
    if bindings is None:
        return []
    normalized: list[InputBinding] = []
    for binding in bindings:
        if isinstance(binding, InputPathBinding | InputValueBinding):
            normalized.append(binding)
            continue
        if not isinstance(binding, Mapping):
            raise TypeError(f"unsupported input binding {binding!r}")
        if "path" in binding:
            normalized.append(InputPathBinding.model_validate(binding))
        elif "value" in binding:
            normalized.append(InputValueBinding.model_validate(binding))
        else:
            raise ValueError("input binding must contain either 'path' or 'value'")
    return normalized
```

Add:

```python
def normalize_output_bindings(bindings: Sequence[OutputBindingArg] | None) -> list[OutputBinding]:
    """Validate canonical output binding structs for WorkflowBuilder.use()."""
    if bindings is None:
        return []
    normalized: list[OutputBinding] = []
    for binding in bindings:
        if isinstance(binding, OutputBinding):
            normalized.append(binding)
            continue
        if not isinstance(binding, Mapping):
            raise TypeError(f"unsupported output binding {binding!r}")
        normalized.append(OutputBinding.model_validate(binding))
    return normalized
```

- [ ] **Step 4: Run focused normalizer-related test**

```bash
uv run --with pytest pytest tests/authoring/test_builder.py::test_builder_use_accepts_canonical_binding_dicts_with_structural_paths -q
```

Expected: still fails until builder signatures are updated.

---

## Task 2: Add `input` / `output` to `use()`

**Files:**

- Modify: `src/wf_authoring/builder/core.py`
- Test: `tests/authoring/test_builder.py`

- [ ] **Step 1: Update imports**

In `src/wf_authoring/builder/core.py`, import new aliases/functions:

```python
from .mapping import (
    InputBindingArg,
    OutputBindingArg,
    normalize_input_bindings,
    normalize_output_bindings,
)
```

- [ ] **Step 2: Update `use()` signature**

Change:

```python
def use(
    self,
    spec: NodeSpec[Any, Any],
    *,
    id: str | None = None,
    in_map: MapArg | None = None,
    input_values: Mapping[Any, Any] | None = None,
    out_map: MapArg | None = None,
    desc: str | None = None,
) -> NodeUse:
```

to:

```python
def use(
    self,
    spec: NodeSpec[Any, Any],
    *,
    id: str | None = None,
    input: Sequence[InputBindingArg] | None = None,
    output: Sequence[OutputBindingArg] | None = None,
    in_map: MapArg | None = None,
    input_values: Mapping[Any, Any] | None = None,
    out_map: MapArg | None = None,
    desc: str | None = None,
) -> NodeUse:
```

Import `Sequence` from `collections.abc`.

- [ ] **Step 3: Add mixing guard helper**

Add near the canonical binding helpers:

```python
def _reject_mixed_binding_styles(
    *,
    input: object | None,
    output: object | None,
    in_map: object | None,
    input_values: object | None,
    out_map: object | None,
) -> None:
    """Keep canonical binding lists and deprecated map sugar from mixing."""
    if input is not None and (in_map is not None or input_values is not None):
        raise TypeError("cannot mix canonical input with deprecated in_map/input_values")
    if output is not None and out_map is not None:
        raise TypeError("cannot mix canonical output with deprecated out_map")
```

- [ ] **Step 4: Use canonical bindings when provided**

In `use()`:

```python
_reject_mixed_binding_styles(
    input=input,
    output=output,
    in_map=in_map,
    input_values=input_values,
    out_map=out_map,
)

if input is not None:
    node_input = normalize_input_bindings(input)
else:
    raw_in_map = auto_input_map(...) if in_map is None else in_map
    node_input = _canonical_input_bindings(
        normalize_input_mapping(raw_in_map),
        normalize_input_values(input_values),
    )

if output is not None:
    node_output = normalize_output_bindings(output)
else:
    raw_out_map = auto_output_map(...) if out_map is None else out_map
    node_output = _canonical_output_bindings(normalize_output_mapping(raw_out_map))
```

Then pass:

```python
input=node_input,
output=node_output,
```

- [ ] **Step 5: Run focused test**

```bash
uv run --with pytest pytest tests/authoring/test_builder.py::test_builder_use_accepts_canonical_binding_dicts_with_structural_paths -q
```

Expected: pass.

---

## Task 3: Add `input` / `output` to `use_ref()`

**Files:**

- Modify: `src/wf_authoring/builder/core.py`
- Test: `tests/authoring/test_builder.py`

- [ ] **Step 1: Write failing test**

Add:

```python
def test_builder_use_ref_accepts_canonical_binding_dicts() -> None:
    builder = WorkflowBuilder(
        name="external_ref_canonical_bindings",
        input_schema={},
        state_schema={"fields": {}},
        output_schema={},
    )

    step = builder.use_ref(
        "demo.echo",
        id="echo",
        input=[
            {
                "target": {"root": "local", "parts": ["text"]},
                "path": {"root": "input", "parts": ["text"]},
            }
        ],
        output=[
            {
                "source": {"root": "local", "parts": ["echoed"]},
                "target": {"root": "state", "parts": ["echoed"]},
            }
        ],
    )

    assert step.node == "demo.echo"
    assert isinstance(step.input[0], InputPathBinding)
    assert step.input[0].path == GraphSourcePath.input("text")
    assert step.output[0].target == StatePath.of("echoed")
```

- [ ] **Step 2: Update `use_ref()` signature**

Add:

```python
input: Sequence[InputBindingArg] | None = None,
output: Sequence[OutputBindingArg] | None = None,
```

before deprecated map args.

- [ ] **Step 3: Use same mixing guard and normalization**

`use_ref()` has no auto-map fallback, so logic is simpler:

```python
_reject_mixed_binding_styles(...)

node_input = (
    normalize_input_bindings(input)
    if input is not None
    else _canonical_input_bindings(
        normalize_input_mapping(in_map),
        normalize_input_values(input_values),
    )
)
node_output = (
    normalize_output_bindings(output)
    if output is not None
    else _canonical_output_bindings(normalize_output_mapping(out_map))
)
```

- [ ] **Step 4: Run focused test**

```bash
uv run --with pytest pytest tests/authoring/test_builder.py::test_builder_use_ref_accepts_canonical_binding_dicts -q
```

Expected: pass.

---

## Task 4: Deprecate Map Sugar Explicitly

**Files:**

- Modify: `src/wf_authoring/builder/core.py`
- Test: `tests/authoring/test_builder.py`

- [ ] **Step 1: Add warning helper**

Add:

```python
def _warn_deprecated_binding_sugar(
    *,
    in_map: object | None,
    input_values: object | None,
    out_map: object | None,
) -> None:
    """Warn when callers explicitly use map sugar instead of canonical bindings."""
    used = [
        name
        for name, value in (
            ("in_map", in_map),
            ("input_values", input_values),
            ("out_map", out_map),
        )
        if value is not None
    ]
    if not used:
        return
    warnings.warn(
        f"{', '.join(used)} are deprecated WorkflowBuilder sugar; use canonical "
        "input/output binding lists instead",
        DeprecationWarning,
        stacklevel=3,
    )
```

Auto-mapping when args are omitted must not warn.

- [ ] **Step 2: Add warning tests**

Add:

```python
def test_builder_warns_when_explicit_deprecated_maps_are_used() -> None:
    builder = WorkflowBuilder(
        name="deprecated_maps",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    with pytest.warns(DeprecationWarning, match="canonical input/output"):
        builder.use(
            auto_bind_node,
            in_map={"input.text": "text"},
            out_map={"text": "state.text"},
        )
```

Add:

```python
def test_builder_auto_mapping_does_not_warn() -> None:
    builder = WorkflowBuilder(
        name="auto_map_no_warning",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        builder.use(auto_bind_node)
```

Import `warnings` in the test file.

- [ ] **Step 3: Call warning helper**

In `use()` and `use_ref()`, after the mixing guard:

```python
_warn_deprecated_binding_sugar(
    in_map=in_map,
    input_values=input_values,
    out_map=out_map,
)
```

- [ ] **Step 4: Run focused warning tests**

```bash
uv run --with pytest pytest tests/authoring/test_builder.py::test_builder_warns_when_explicit_deprecated_maps_are_used tests/authoring/test_builder.py::test_builder_auto_mapping_does_not_warn -q
```

Expected: both pass.

---

## Task 5: Reject Mixed Styles and Dict Keys Clearly

**Files:**

- Modify: `src/wf_authoring/builder/core.py`
- Modify: `src/wf_authoring/builder/mapping.py`
- Test: `tests/authoring/test_builder.py`

- [ ] **Step 1: Add mixed-style tests**

Add:

```python
def test_builder_rejects_mixed_canonical_and_deprecated_input_styles() -> None:
    builder = WorkflowBuilder(
        name="mixed_input_styles",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    with pytest.raises(TypeError, match="cannot mix canonical input"):
        builder.use(
            auto_bind_node,
            input=[{"target": "text", "path": "input.text"}],
            in_map={"input.text": "text"},
        )
```

Add:

```python
def test_builder_rejects_mixed_canonical_and_deprecated_output_styles() -> None:
    builder = WorkflowBuilder(
        name="mixed_output_styles",
        input_schema=AutoBindInput,
        state_schema=AutoBindState,
        output_schema=AutoBindOutput,
    )

    with pytest.raises(TypeError, match="cannot mix canonical output"):
        builder.use(
            auto_bind_node,
            output=[{"source": "text", "target": "state.text"}],
            out_map={"text": "state.text"},
        )
```

- [ ] **Step 2: Add dict-key diagnostic test**

Python literal dicts cannot contain dict keys, so test the normalizer directly with a custom `Mapping` that yields a structural dict key:

```python
class _StructuralKeyMap:
    def items(self):
        return [
            (
                {"root": "input", "parts": ["email.address"]},
                "payload.email",
            )
        ]


def test_input_map_rejects_structural_dict_keys_with_clear_message() -> None:
    with pytest.raises(TypeError, match="structural path dicts cannot be map keys"):
        normalize_input_mapping(_StructuralKeyMap())
```

Import `normalize_input_mapping` from `wf_authoring.builder.mapping`.

- [ ] **Step 3: Implement dict-key guard**

In `normalize_input_mapping()`:

```python
def _reject_mapping_path_key(value: object, *, field_name: str) -> None:
    if isinstance(value, Mapping):
        raise TypeError(
            f"structural path dicts cannot be map keys in {field_name}; "
            "use canonical input/output binding lists instead"
        )
```

Call it on source keys for input maps and source keys for output maps before coercion.

Do not reject structural dict values, because values are allowed:

```python
out_map={"result": {"root": "state", "parts": ["score"]}}
```

- [ ] **Step 4: Run focused tests**

```bash
uv run --with pytest pytest tests/authoring/test_builder.py::test_builder_rejects_mixed_canonical_and_deprecated_input_styles tests/authoring/test_builder.py::test_builder_rejects_mixed_canonical_and_deprecated_output_styles tests/authoring/test_builder.py::test_input_map_rejects_structural_dict_keys_with_clear_message -q
```

Expected: all pass.

---

## Task 6: Docs

**Files:**

- Modify: `docs/structural_refs.md`
- Modify: `docs/authoring_sketch.md`
- Modify: `docs/core_state_mapping_and_merge.md`

- [ ] **Step 1: Update structural refs authoring example**

In `docs/structural_refs.md`, replace the current map-sugar-first example with canonical binding list example:

```python
g.use(
    node,
    input=[
        {
            "target": {"root": "local", "parts": ["payload.email"]},
            "path": {"root": "input", "parts": ["email.address"]},
        }
    ],
    output=[
        {
            "source": {"root": "local", "parts": ["result.score"]},
            "target": {"root": "state", "parts": ["score"]},
        }
    ],
)
```

Then state:

```text
`in_map`, `input_values`, and `out_map` remain deprecated Python sugar.
Structural path dicts are not valid map keys; use canonical binding lists when
working from JSON/MCP.
```

- [ ] **Step 2: Update authoring sketch**

In `docs/authoring_sketch.md`, update the API sketch from:

```python
use(node_spec, id=..., in_map=..., out_map=...)
```

to:

```python
use(node_spec, id=..., input=[...], output=[...])
```

Then mention:

```text
`in_map`, `input_values`, and `out_map` are compatibility sugar for Python
authors, not the preferred saved or MCP-facing shape.
```

- [ ] **Step 3: Update core mapping docs**

In `docs/core_state_mapping_and_merge.md`, ensure the docs say:

```text
The canonical public shape is list-of-binding structs. Deprecated map fields
are parse-only compatibility inputs at core level and Python sugar at builder
level.
```

---

## Task 7: Verification

**Files:**

- All touched files.

- [ ] **Step 1: Run focused authoring builder tests**

```bash
uv run --with pytest pytest tests/authoring/test_builder.py -q
```

Expected: pass.

- [ ] **Step 2: Run authoring tests**

```bash
uv run --with pytest pytest tests/authoring -q
```

Expected: pass.

- [ ] **Step 3: Run full tests**

```bash
uv run --with pytest pytest -q
```

Expected: pass.

- [ ] **Step 4: Run lint/type checks**

```bash
uvx ruff check src/wf_authoring tests/authoring
uvx ruff format --check src/wf_authoring tests/authoring docs/structural_refs.md docs/authoring_sketch.md docs/core_state_mapping_and_merge.md
uv run basedpyright --level error src/wf_authoring tests/authoring
```

Expected:

- ruff check passes
- format check passes or reports only markdown files if ruff does not handle them
- basedpyright reports `0 errors`

---

## Self-Review Checklist

- `g.use(input=[...], output=[...])` exists.
- `g.use_ref(input=[...], output=[...])` exists.
- `input_values` still exists, but emits `DeprecationWarning` when explicitly used.
- `in_map` and `out_map` still exist, but emit `DeprecationWarning` when explicitly used.
- Auto-mapping does not warn.
- Canonical list inputs support structural path dicts inside binding structs.
- Structural dicts as map keys are rejected with a clear message.
- Saved/core `NodeUse` output remains canonical `input` / `output`; deprecated map fields do not reappear in dumps.
