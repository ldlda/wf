# MCP Schema Model Helpers Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MCP JSON-schema-to-Pydantic model helper logic from `wf_mcp.workflow.wrappers` into `wf_sources_mcp.schema_models` so broker catalog hydration no longer imports private wrapper helpers.

**Architecture:** `wf_sources_mcp.schema_models` owns the tolerant JSON Schema subset compiler used for generated MCP tool NodeSpecs. `wf_mcp.workflow.wrappers` keeps `wrap_discovered_tool` and event emission for now, but imports the canonical model helper. `SourceCatalogService` also imports the canonical helper directly.

**Tech Stack:** Python 3.14, Pydantic v2 `create_model`, `wf_authoring.NodeSpec`, pytest, ruff, basedpyright.

---

## Hard Boundaries

- Do not move `wrap_discovered_tool` in this slice.
- Do not move `specs_from_discovered_tools` in this slice.
- Do not change event emission or `McpEvent` usage.
- Do not change generated payload behavior: unset optional fields must still be omitted via `model_dump(exclude_unset=True)` at call sites.
- Do not add any `wf_mcp` imports to `src/wf_sources_mcp/schema_models.py`.
- Preserve compatibility for tests/imports that still reach private wrapper helpers where practical.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Create `src/wf_sources_mcp/schema_models.py`: canonical `_python_type_from_schema`, `_optional_type`, `_field_default`, and public `model_from_schema`.
- Modify `src/wf_sources_mcp/__init__.py`: export `model_from_schema` lazily or directly.
- Modify `src/wf_mcp/workflow/wrappers.py`: import `model_from_schema`; keep `_model_from_schema` as a compatibility alias if tests or code still use it.
- Modify `src/wf_mcp/broker/service/source_catalog.py`: import `model_from_schema` from `wf_sources_mcp.schema_models`.
- Create `tests/wf_sources_mcp/test_schema_models.py`: canonical helper tests.
- Modify `tests/wf_mcp/test_workflow_wrappers.py`: only if needed; existing wrapper behavior tests should keep passing.
- Modify `tests/wf_sources_mcp/test_import_direction_guard.py`: forbid importing `wf_mcp.workflow.wrappers` inside `wf_sources_mcp`.
- Modify docs: `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Add Canonical Schema Model Tests

**Files:**
- Create: `tests/wf_sources_mcp/test_schema_models.py`

- [ ] **Step 1: Write canonical behavior tests**

Create `tests/wf_sources_mcp/test_schema_models.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wf_sources_mcp.schema_models import model_from_schema


def test_model_from_schema_maps_basic_json_schema_types() -> None:
    model = model_from_schema(
        "ToolInput",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Display name"},
                "count": {"type": "integer"},
                "ratio": {"type": "number"},
                "enabled": {"type": "boolean"},
                "metadata": {"type": "object"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "count"],
        },
    )

    payload = model.model_validate(
        {
            "name": "demo",
            "count": 2,
            "ratio": 1.5,
            "enabled": True,
            "metadata": {"a": "b"},
            "tags": ["one"],
        }
    )

    assert isinstance(payload, BaseModel)
    assert payload.model_dump(exclude_unset=True) == {
        "name": "demo",
        "count": 2,
        "ratio": 1.5,
        "enabled": True,
        "metadata": {"a": "b"},
        "tags": ["one"],
    }


def test_model_from_schema_omits_unset_optional_fields() -> None:
    model = model_from_schema(
        "OptionalInput",
        {
            "type": "object",
            "properties": {
                "required_name": {"type": "string"},
                "optional_depth": {"type": "integer"},
            },
            "required": ["required_name"],
        },
    )

    payload = model.model_validate({"required_name": "root"})

    assert payload.model_dump(exclude_unset=True) == {"required_name": "root"}


def test_model_from_schema_preserves_explicit_defaults() -> None:
    model = model_from_schema(
        "DefaultInput",
        {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "query": {"type": "string"},
            },
        },
    )

    payload = model.model_validate({})

    assert payload.model_dump() == {"limit": 10, "query": None}
    assert payload.model_dump(exclude_unset=True) == {}


def test_model_from_schema_allows_extra_fields_and_tolerates_unknown_shapes() -> None:
    model = model_from_schema(
        "LooseInput",
        {
            "type": "object",
            "properties": {
                "enum_value": {"enum": ["a", "b"]},
                "union_value": {"type": ["string", "integer"]},
                "unknown_value": {"x-custom": True},
            },
        },
    )

    payload = model.model_validate(
        {
            "enum_value": "a",
            "union_value": 123,
            "unknown_value": {"nested": True},
            "extra": "kept",
        }
    )

    dumped: dict[str, Any] = payload.model_dump(exclude_unset=True)
    assert dumped["enum_value"] == "a"
    assert dumped["union_value"] == 123
    assert dumped["unknown_value"] == {"nested": True}
    assert dumped["extra"] == "kept"
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_schema_models.py -q
```

Expected: fail with `ModuleNotFoundError` or import error for `wf_sources_mcp.schema_models`.

---

### Task 2: Create Canonical `wf_sources_mcp.schema_models`

**Files:**
- Create: `src/wf_sources_mcp/schema_models.py`

- [ ] **Step 1: Add canonical helper implementation**

Create `src/wf_sources_mcp/schema_models.py` by moving the helper logic from `src/wf_mcp/workflow/wrappers.py`:

```python
from __future__ import annotations

from types import NoneType, UnionType
from typing import Any, Union, cast, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, create_model

_JSON_TYPE_MAP: dict[str, object] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict[str, Any],
}


def _python_type_from_schema(schema: object) -> object:
    """Map the supported MCP JSON Schema subset into a Pydantic annotation.

    This is intentionally not a full JSON Schema compiler. Unsupported shapes
    become `Any` so discovery remains tolerant while the original schema
    contract stays available on generated NodeSpecs.
    """
    if not isinstance(schema, dict):
        return Any

    if "enum" in schema:
        return Any

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null_types = [item for item in schema_type if item != "null"]
        if len(non_null_types) == 1:
            return _optional_type(
                _python_type_from_schema({**schema, "type": non_null_types[0]})
            )
        return Any

    if schema_type == "array":
        item_type = _python_type_from_schema(schema.get("items", {}))
        return list[item_type] if isinstance(item_type, type) else list[Any]

    if not isinstance(schema_type, str):
        return Any
    return _JSON_TYPE_MAP.get(schema_type, Any)


def _optional_type(annotation: object) -> object:
    """Return an optional version of a supported runtime annotation."""
    if annotation is Any:
        return Any
    origin = get_origin(annotation)
    if origin in {Union, UnionType} and NoneType in get_args(annotation):
        return annotation
    return annotation | None if isinstance(annotation, type) else Any


def _field_default(
    field_name: str,
    property_schema: object,
    required: set[str],
) -> object:
    """Return the Pydantic default for one MCP tool input property."""
    if isinstance(property_schema, dict) and "default" in property_schema:
        return property_schema["default"]
    return ... if field_name in required else None


def model_from_schema(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """Create a loose Pydantic adapter model for an MCP JSON Schema object.

    Input should be object-like JSON Schema with `properties` and optional
    `required`. The returned model is the Python-call boundary for generated
    NodeSpecs; the original JSON Schema remains the public contract.
    """
    properties = cast(dict[str, Any], schema.get("properties", {}))
    required = set(cast(list[str], schema.get("required", [])))
    field_defs: dict[str, tuple[object, object]] = {}

    for field_name, property_schema in properties.items():
        annotation = _python_type_from_schema(property_schema)
        default = _field_default(field_name, property_schema, required)
        description = (
            property_schema.get("description")
            if isinstance(property_schema, dict)
            else None
        )
        field_defs[field_name] = (
            annotation,
            Field(default=default, description=description),
        )

    raw_field_defs = cast(dict[str, Any], field_defs)
    model = create_model(
        name,
        __config__=ConfigDict(extra="allow"),
        **raw_field_defs,
    )
    return cast(type[BaseModel], model)


__all__ = ["model_from_schema"]
```

- [ ] **Step 2: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_schema_models.py -q
```

Expected: all tests pass.

---

### Task 3: Export `model_from_schema` From `wf_sources_mcp`

**Files:**
- Modify: `src/wf_sources_mcp/__init__.py`

- [ ] **Step 1: Add package-root export**

Update `src/wf_sources_mcp/__init__.py` so this works:

```python
from wf_sources_mcp import model_from_schema
```

If the package uses lazy `__getattr__`, add `"model_from_schema"` to `__all__` and route it to `.schema_models`:

```python
    if name == "model_from_schema":
        from . import schema_models

        return schema_models.model_from_schema
```

If direct imports are safe, use:

```python
from .schema_models import model_from_schema
```

- [ ] **Step 2: Add root export test**

Append to `tests/wf_sources_mcp/test_schema_models.py`:

```python
def test_model_from_schema_exports_from_package_root() -> None:
    from wf_sources_mcp import model_from_schema as root_model_from_schema
    from wf_sources_mcp.schema_models import model_from_schema

    assert root_model_from_schema is model_from_schema
```

- [ ] **Step 3: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_schema_models.py -q
```

Expected: all tests pass.

---

### Task 4: Update `wf_mcp.workflow.wrappers` to Use Canonical Helper

**Files:**
- Modify: `src/wf_mcp/workflow/wrappers.py`

- [ ] **Step 1: Replace local helper implementation**

In `src/wf_mcp/workflow/wrappers.py`:

- Remove imports used only by helper internals:

```python
from types import NoneType, UnionType
from typing import Union, cast, get_args, get_origin
from pydantic import ConfigDict, Field, create_model
```

- Keep imports needed by `wrap_discovered_tool`:

```python
from collections.abc import Callable
from typing import Any
from pydantic import BaseModel
```

- Add:

```python
from wf_sources_mcp.schema_models import model_from_schema
```

- Delete `_JSON_TYPE_MAP`, `_python_type_from_schema`, `_optional_type`, `_field_default`, and the old `_model_from_schema` implementation.

- Add a compatibility alias after imports:

```python
_model_from_schema = model_from_schema
```

Keep this alias because some old tests/imports may still reference `wf_mcp.workflow.wrappers._model_from_schema`.

- [ ] **Step 2: Update wrapper calls**

Change:

```python
input_model = _model_from_schema(
```

to:

```python
input_model = model_from_schema(
```

Change:

```python
output_model = _model_from_schema(
```

to:

```python
output_model = model_from_schema(
```

- [ ] **Step 3: Run wrapper tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_wrappers.py tests/wf_mcp/test_stateful_runtime.py -q
```

Expected: pass.

---

### Task 5: Update Source Catalog Hydration Import

**Files:**
- Modify: `src/wf_mcp/broker/service/source_catalog.py`

- [ ] **Step 1: Replace private wrapper helper import**

Change:

```python
from ...workflow.wrappers import _model_from_schema
```

to:

```python
from wf_sources_mcp.schema_models import model_from_schema
```

- [ ] **Step 2: Update hydration calls**

Change:

```python
input_model = _model_from_schema(f"{model_prefix}_Input", entry.input_schema)
```

to:

```python
input_model = model_from_schema(f"{model_prefix}_Input", entry.input_schema)
```

Change:

```python
output_model = _model_from_schema(f"{model_prefix}_Output", output_schema)
```

to:

```python
output_model = model_from_schema(f"{model_prefix}_Output", output_schema)
```

- [ ] **Step 3: Run source catalog tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_adapters.py -q
```

Expected: pass.

---

### Task 6: Add Import Guard for Old Wrapper Helper Dependency

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add forbidden old wrapper import test**

Append to `tests/wf_sources_mcp/test_import_direction_guard.py`:

```python
def test_wf_sources_mcp_does_not_import_old_workflow_wrapper_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.workflow", "wf_mcp.workflow.wrappers"}
    violations: list[str] = []

    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root.parent)
        module = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden:
                violations.append(f"{module}:{node.lineno}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden:
                        violations.append(f"{module}:{node.lineno}: import {alias.name}")

    assert violations == [], (
        "wf_sources_mcp still imports old wf_mcp workflow wrapper module:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
```

- [ ] **Step 2: Run import guard**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: pass.

---

### Task 7: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-08-wf-sources-mcp-schema-models.md` to `docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-schema-models.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Under the `wf_sources_mcp` cleanup section, add:

```markdown
    - Completed: MCP JSON-schema-to-Pydantic model helper now lives in
      `wf_sources_mcp.schema_models`. `wf_mcp.workflow.wrappers` still owns
      tool wrapper event emission, but no longer owns the shared schema compiler.
```

- [ ] **Step 2: Update `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`**

Add a completed numbered item before the pending upstream transport/discovery/session services item:

```markdown
17. Complete: MCP JSON-schema-to-Pydantic model helper moved to
    `wf_sources_mcp.schema_models`. This removes the broker catalog hydration
    dependency on private `wf_mcp.workflow.wrappers` helpers; eventful tool
    wrapping remains in `wf_mcp` for the next seam.
```

If numbering differs because new items landed meanwhile, keep the completed item before the broad pending item and renumber.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-wf-sources-mcp-schema-models.md docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-schema-models.md
```

Expected: `git status --short` shows an `R` rename for the plan.

---

### Task 8: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_schema_models.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_workflow_wrappers.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_adapters.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run source-provider tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp -q
```

Expected: all `wf_sources_mcp` tests pass.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/schema_models.py src/wf_mcp/workflow/wrappers.py src/wf_mcp/broker/service/source_catalog.py tests/wf_sources_mcp/test_schema_models.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_workflow_wrappers.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp/schema_models.py src/wf_mcp/workflow/wrappers.py src/wf_mcp/broker/service/source_catalog.py tests/wf_sources_mcp/test_schema_models.py
```

Expected: `0 errors, 0 warnings, 0 notes`

- [ ] **Step 5: Check old private helper usage**

Run:

```bash
rg -n "_model_from_schema|_python_type_from_schema|_field_default|_optional_type|wf_mcp\.workflow\.wrappers" src tests
```

Expected:

- `src/wf_mcp/workflow/wrappers.py` may contain `_model_from_schema = model_from_schema` compatibility alias.
- `tests` may import `wrap_discovered_tool` from `wf_mcp.workflow`.
- `src/wf_mcp/broker/service/source_catalog.py` must not import `_model_from_schema`.
- `src/wf_sources_mcp` must not import `wf_mcp.workflow` or `wf_mcp.workflow.wrappers`.

- [ ] **Step 6: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings on Windows are acceptable.

---

## Expected Final Report

The implementer should report:

- Files created, modified, and moved.
- Exact verification commands and pass/fail output.
- Confirmation that `source_catalog.py` no longer imports `_model_from_schema` from `wf_mcp.workflow.wrappers`.
- Confirmation that `wrap_discovered_tool` still lives in `wf_mcp`.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
