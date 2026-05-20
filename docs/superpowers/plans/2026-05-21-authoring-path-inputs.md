# Authoring Path Inputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `wf_authoring` understand structural, string, iterable, and vararg path inputs consistently across DSL helpers and `WorkflowBuilder.use()`.

**Architecture:** Keep `wf_core` path objects as the canonical runtime model. Add one authoring coercion layer that turns ergonomic inputs into `GraphSourcePath`, `StatePath`, and `LocalPath`. Single-string helper calls parse TOML dotted-key expressions; varargs and iterables are literal path parts. Builder maps should normalize into typed path objects instead of string-to-string maps so the authoring layer stops being another dotted-string boundary.

**Tech Stack:** Python 3.14, stdlib `tomllib`, `wf_core.paths`, `wf_authoring.dsl`, `WorkflowBuilder`, pytest.

---

## Current State

The core now supports structural path objects:

```json
{"root": "state", "parts": ["person.name", "three and four"]}
```

But `wf_authoring` still stores paths as strings:

- `wf_authoring.dsl.paths.GraphPath.value: str`
- `wf_authoring.dsl.mapping.PathArg = str | GraphPath`
- `WorkflowBuilder.use(..., in_map=..., out_map=...)` normalizes maps to `dict[str, str]`
- builder internals call `LocalPath.parse(...)`, `GraphSourcePath.parse(...)`, and `StatePath.parse(...)`

That means authoring helpers still risk ambiguity:

```python
state("person.name")
```

Today this is dotted shorthand. To express a literal field named `person.name`, users need structural/literal segment input.

---

## Semantics

### Single String Argument

Parse as TOML dotted-key expression:

```python
state("person.name")
# parts: ["person", "name"]

state('"person.name"')
# parts: ["person.name"]

state('person."three and four"')
# parts: ["person", "three and four"]
```

### Varargs

Treat each argument as a literal path segment:

```python
state("person.name", "email address")
# parts: ["person.name", "email address"]

state_path("oh", "my", "days")
# parts: ["oh", "my", "days"]
```

### Iterable Input

Treat iterable items as literal path segments:

```python
state(("person.name",))
# parts: ["person.name"]

input_path(["user", "email"])
# parts: ["user", "email"]
```

### Existing Path Objects

Pass through path objects without reparsing:

```python
state_path(StatePath(("person.name",)))
input_path(GraphSourcePath.input("user"))
```

### Structural Path Dicts

Accept structural core path dicts at authoring boundaries when data is already
model-shaped:

```python
state_path({"root": "state", "parts": ["person.name"]})
input_path({"root": "input", "parts": ["user", "email"]})
```

This keeps MCP / JSON-facing callers from converting canonical objects back
into display strings just to pass through `wf_authoring`.

---

## File Structure

- Create: `src/wf_authoring/dsl/path_inputs.py`
  - Own `PathInput` type alias.
  - Own TOML key-expression parser using `tomllib`.
  - Own coercion functions for graph/local/state paths.

- Modify: `src/wf_authoring/dsl/paths.py`
  - Make `GraphPath` wrap `GraphSourcePath`, not a string.
  - Update `graph_path`, `input_path`, `state_path`, `context_path`.

- Modify: `src/wf_authoring/dsl/conditions.py`
  - Use typed `GraphSourcePath` directly from `GraphPath` / `PathExpr`.
  - Update `state(...)`, `input(...)`, and `context(...)` to accept `PathInput`.

- Modify: `src/wf_authoring/dsl/mapping.py`
  - Expand `PathArg` to include structural/core path objects and iterable parts.
  - Keep `bind_fields` / `bind_state` APIs stable, but normalize through the new coercers.

- Modify: `src/wf_authoring/builder/mapping.py`
  - Normalize `MapArg` to typed paths, not strings.
  - Keep legacy string map support.

- Modify: `src/wf_authoring/builder/core.py`
  - Change `_canonical_input_bindings` / `_canonical_output_bindings` to accept typed path mappings.
  - Stop reparsing paths from strings when already typed.

- Test:
  - `tests/authoring/test_path_inputs.py`
  - `tests/authoring/test_builder.py`
  - `tests/authoring/test_conditions.py`

---

## Task 1: Add Path Input Coercion Module

**Files:**
- Create: `src/wf_authoring/dsl/path_inputs.py`
- Test: `tests/authoring/test_path_inputs.py`

- [ ] **Step 1: Write failing tests**

```python
from wf_authoring.dsl.path_inputs import (
    coerce_graph_path,
    coerce_local_path,
    coerce_state_path,
)
from wf_core.paths import GraphSourcePath, LocalPath, StatePath


def test_single_string_path_input_uses_toml_dotted_key_syntax() -> None:
    assert coerce_state_path("person.name") == StatePath(("person", "name"))
    assert coerce_state_path('"person.name"') == StatePath(("person.name",))
    assert coerce_state_path('person."three and four"') == StatePath(
        ("person", "three and four")
    )


def test_vararg_path_input_treats_parts_as_literal_segments() -> None:
    assert coerce_state_path("person.name", "email address") == StatePath(
        ("person.name", "email address")
    )


def test_iterable_path_input_treats_items_as_literal_segments() -> None:
    assert coerce_local_path(("payload.text",)) == LocalPath(("payload.text",))


def test_existing_path_objects_pass_through() -> None:
    source = GraphSourcePath("state", ("person.name",))
    assert coerce_graph_path(source) is source


def test_structural_path_dicts_validate_through_core_models() -> None:
    assert coerce_graph_path({"root": "state", "parts": ["person.name"]}) == (
        GraphSourcePath("state", ("person.name",))
    )
```

- [ ] **Step 2: Run tests to verify red**

```bash
uv run --with pytest pytest tests/authoring/test_path_inputs.py -q
```

Expected: fails because module does not exist.

- [ ] **Step 3: Implement parser using `tomllib`**

Implement:

```python
import tomllib
from collections.abc import Iterable, Mapping
from typing import TypeAlias

from wf_core.paths import GraphSourcePath, LocalPath, StatePath

PathInput: TypeAlias = (
    str
    | Iterable[str]
    | Mapping[str, object]
    | GraphSourcePath
    | StatePath
    | LocalPath
)
```

Parser approach:

```python
def _parse_toml_key_expr(expr: str) -> tuple[str, ...]:
    parsed = tomllib.loads(f"{expr} = true")
    ...
```

Walk the nested dict until the leaf value is `True`; each nested key is one path segment.

Rules:

- one `str` argument parses as TOML key expression
- multiple `str` arguments are literal segments
- one iterable argument is literal segments
- existing path object passes through when compatible
- structural dicts validate through the matching core path model
- invalid TOML raises `ValueError` with message mentioning TOML key expression

- [ ] **Step 4: Run tests to verify green**

```bash
uv run --with pytest pytest tests/authoring/test_path_inputs.py -q
```

Expected: all tests pass.

---

## Task 2: Make DSL Path Helpers Typed

**Files:**
- Modify: `src/wf_authoring/dsl/paths.py`
- Modify: `src/wf_authoring/dsl/conditions.py`
- Test: `tests/authoring/test_path_inputs.py`
- Test: `tests/authoring/test_conditions.py`

- [ ] **Step 1: Write failing helper tests**

Add:

```python
from wf_authoring import state, state_path
from wf_core.paths import GraphSourcePath


def test_state_path_helper_supports_toml_strings_and_literal_varargs() -> None:
    assert state_path('"person.name"').path == GraphSourcePath(
        "state", ("person.name",)
    )
    assert state_path("person.name", "email address").path == GraphSourcePath(
        "state", ("person.name", "email address")
    )


def test_state_expr_helper_uses_same_path_input_rules() -> None:
    condition = state('"person.name"').eq("Ada").to_condition()

    assert condition.left.path == GraphSourcePath("state", ("person.name",))
```

- [ ] **Step 2: Run tests to verify red**

```bash
uv run --with pytest pytest tests/authoring/test_path_inputs.py tests/authoring/test_conditions.py -q
```

Expected: old helpers either split incorrectly or do not accept these signatures.

- [ ] **Step 3: Update `GraphPath`**

Change:

```python
@dataclass(frozen=True, slots=True)
class GraphPath:
    path: GraphSourcePath

    @property
    def value(self) -> str:
        return str(self.path)
```

Keep `.value` as compatibility display output.

- [ ] **Step 4: Update helper signatures**

```python
def input_path(first: PathInput, *parts: str) -> GraphPath: ...
def state_path(first: PathInput, *parts: str) -> GraphPath: ...
def context_path(first: PathInput, *parts: str) -> GraphPath: ...
```

Use coercers from `path_inputs.py`.

- [ ] **Step 5: Update conditions**

Make `PathExpr` store `GraphSourcePath`, while keeping `.path` display property if needed:

```python
@dataclass(frozen=True, slots=True)
class PathExpr:
    source: GraphSourcePath

    @property
    def path(self) -> str:
        return str(self.source)
```

Use `PathOperand(path=self.source)` instead of reparsing strings.

- [ ] **Step 6: Run tests**

```bash
uv run --with pytest pytest tests/authoring/test_path_inputs.py tests/authoring/test_conditions.py -q
```

Expected: all pass.

---

## Task 3: Make Builder Maps Accept Typed Path Inputs

**Files:**
- Modify: `src/wf_authoring/builder/mapping.py`
- Modify: `src/wf_authoring/builder/core.py`
- Modify: `src/wf_authoring/dsl/mapping.py`
- Test: `tests/authoring/test_builder.py`

- [ ] **Step 1: Write failing builder tests**

Add:

```python
from wf_authoring import input_path, state_path
from wf_core.paths import GraphSourcePath, LocalPath, StatePath


def test_builder_use_accepts_typed_paths_and_literal_iterable_paths() -> None:
    builder = WorkflowBuilder(...)
    step = builder.use(
        auto_bind_node,
        in_map={input_path('"text.with.dot"'): ("payload.text",)},
        out_map={("payload.text",): state_path("state field")},
    )

    assert step.input[0].path == GraphSourcePath("input", ("text.with.dot",))
    assert step.input[0].target == LocalPath(("payload.text",))
    assert step.output[0].source == LocalPath(("payload.text",))
    assert step.output[0].target == StatePath(("state field",))
```

Use existing builder test fixtures in `tests/authoring/test_builder.py`.

- [ ] **Step 2: Run tests to verify red**

```bash
uv run --with pytest pytest tests/authoring/test_builder.py -q
```

Expected: tuple/typed map values fail.

- [ ] **Step 3: Update map normalization**

In `builder/mapping.py`, introduce typed mapping aliases:

```python
InputMap = dict[GraphSourcePath, LocalPath]
OutputMap = dict[LocalPath, StatePath]
```

Add:

```python
normalize_input_mapping(mapping: MapArg | None) -> InputMap
normalize_output_mapping(mapping: MapArg | None) -> OutputMap
```

Rules:

- input map key = graph source path
- input map value = local path
- output map key = local path
- output map value = state path

Legacy strings still parse through the new coercers.

- [ ] **Step 4: Update builder core**

Change `_canonical_input_bindings`:

```python
def _canonical_input_bindings(
    in_map: Mapping[GraphSourcePath, LocalPath],
    input_values: Mapping[LocalPath, Any],
) -> list[InputBinding]:
```

Change `_canonical_output_bindings`:

```python
def _canonical_output_bindings(
    out_map: Mapping[LocalPath, StatePath],
) -> list[OutputBinding]:
```

`InputValueBinding.target` should also accept typed/local path input.

- [ ] **Step 5: Update DSL mapping helpers**

`bind_fields(**mapping)` and `bind_state(**mapping)` can keep returning dicts, but values should be normalized display/typed consistently. Prefer returning typed path maps if that does not break tests; otherwise keep their public shape and let builder normalize.

- [ ] **Step 6: Run tests**

```bash
uv run --with pytest pytest tests/authoring/test_builder.py tests/authoring/test_demo_workflow.py tests/authoring/test_ops.py -q
```

Expected: all pass.

---

## Task 3.5: Foreach Boundary Check

**Files:**
- Inspect: `src/wf_authoring/builder/core.py`
- Inspect: `src/wf_core/models/steps.py` or current foreach model location

`WorkflowBuilder.foreach(over=...)` also accepts path-like input today, but the
core foreach model may still store the source path as a string. Do not let this
block `WorkflowBuilder.use()` map normalization.

- [ ] **Step 1: Inspect foreach field type**

If core foreach already accepts `GraphSourcePath`, normalize `over` through the
new graph-path coercer and add one focused test.

If core foreach still accepts only strings, keep the existing string
serialization path and leave a short comment at the call site:

```text
foreach path input should move to typed GraphSourcePath when the core foreach
model is upgraded.
```

- [ ] **Step 2: Avoid partial semantic claims**

Do not document foreach as fully structural until the core field is structural.

---

## Task 4: Docs and Examples

**Files:**
- Modify: `docs/structural_refs.md`
- Modify or create an authoring docs/example if one already exists.

- [ ] **Step 1: Add authoring examples**

Add:

```python
state("person.name")          # TOML/dotted expression
state('"person.name"')        # literal dotted field
state("person.name", "email") # literal segments
state(("person.name",))       # literal iterable
```

- [ ] **Step 2: Mention builder maps**

Add:

```python
g.use(
    node,
    in_map={input_path('"email.address"'): ("payload.email",)},
    out_map={("result.score",): state_path("score")},
)
```

---

## Task 5: Verification

- [ ] **Step 1: Run focused authoring tests**

```bash
uv run --with pytest pytest tests/authoring -q
```

- [ ] **Step 2: Run full tests**

```bash
uv run --with pytest pytest -q
```

- [ ] **Step 3: Run checks**

```bash
uvx ruff check src/wf_authoring src/wf_core/paths.py tests/authoring
uv run basedpyright --level error src/wf_authoring src/wf_core/paths.py tests/authoring
```

---

## Self-Review Notes

- Do not roll a custom TOML parser. Use stdlib `tomllib`.
- Canonical saved JSON remains structural `root` / `parts`.
- Single strings are ergonomic expressions. Varargs and iterables are literal segments.
- Keep `.value` / `str(...)` as display compatibility only.
- `WorkflowBuilder.use()` should stop being a string-to-string path boundary.
- If Pydantic path models are not hashable enough for dict keys, normalize maps
  into explicit binding-pair lists internally instead of falling back to display
  strings.
