# Move RawWorkflowPlan to wf_api.models

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `RawWorkflowPlan` from `wf_mcp.models` to canonical `wf_api.models`, keeping a compatibility shim in `wf_mcp.models`.

**Architecture:** `RawWorkflowPlan` is a standalone Pydantic model with no dependencies on other `wf_mcp.models` definitions. It depends only on `pydantic` and `wf_core` (Edge, InputBinding, Step). This makes it safe to move without entanglement. The `wf_mcp.models` module will re-export from `wf_api.models` as a shim.

**Tech Stack:** Python 3.14, Pydantic v2, pytest, ruff, basedpyright

---

### Task 1: Create `src/wf_api/models.py` with RawWorkflowPlan

**Files:**

- Create: `src/wf_api/models.py`

- [ ] **Step 1: Create the file with the model**

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from wf_core import Edge
from wf_core.models.steps import InputBinding, Step


class RawWorkflowPlan(BaseModel):
    """Raw authoring plan using the same graph step and edge models as core."""

    name: str
    input_schema: dict[str, Any]
    state_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: list[str] = Field(
        default_factory=lambda: ["ok"],
        description=(
            "Declared public workflow outcomes. Legacy plans without this field "
            "default to ok."
        ),
    )
    output: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Optional root workflow output bindings. Sources read graph paths "
            "such as state.result and targets write the public output payload."
        ),
    )
    start: str
    nodes: list[Step]
    edges: list[Edge]
```

- [ ] **Step 2: Verify the file was created correctly**

Run: `python -c "from wf_api.models import RawWorkflowPlan; print(RawWorkflowPlan.__name__)"`
Expected: `RawWorkflowPlan`

---

### Task 2: Replace `wf_mcp.models.RawWorkflowPlan` definition with shim

**Files:**

- Modify: `src/wf_mcp/models.py`

- [ ] **Step 1: Replace the RawWorkflowPlan class definition with a re-export**

Replace the `RawWorkflowPlan` class block (lines 45-68) with:

```python
# RawWorkflowPlan moved to wf_api.models; re-exported here for backward compat.
from wf_api.models import RawWorkflowPlan  # noqa: F401
```

Keep the original import block for pydantic, Edge, InputBinding, Step — they are still used indirectly via the re-export. Actually, after removing the class definition, `BaseModel`, `Field`, `Edge`, `InputBinding`, `Step` are no longer needed by this file. Remove those imports if no other class in the file uses them.

Check: The remaining classes in `wf_mcp/models.py` are `ConnectionConfig`, `AuthRecord`, `CatalogSnapshot`, `BrokerConfig`, `dump_catalog_snapshot`. These use `dataclass`, `field`, `Path`, `Any`, `CatalogNodeEntry`, `CatalogPromptEntry`, `CatalogResourceEntry`. They do NOT use `BaseModel`, `Field`, `Edge`, `InputBinding`, `Step`.

So remove: `from pydantic import BaseModel, Field`, `from wf_core import Edge`, `from wf_core.models.steps import InputBinding, Step`.

- [ ] **Step 2: Run ruff on the file**

Run: `uv run ruff check src/wf_mcp/models.py`
Expected: no errors

- [ ] **Step 3: Run basedpyright on the file**

Run: `uv run basedpyright --level error src/wf_mcp/models.py`
Expected: no errors

---

### Task 3: Update `wf_mcp/__init__.py` to import from shim

**Files:**

- Verify: `src/wf_mcp/__init__.py`

No change needed — `wf_mcp/__init__.py` already imports `RawWorkflowPlan` from `.models`, and the shim re-exports it. Verify this still works.

- [ ] **Step 1: Verify the import chain works**

Run: `python -c "from wf_mcp import RawWorkflowPlan; print(RawWorkflowPlan.__name__)"`
Expected: `RawWorkflowPlan`

---

### Task 4: Add focused tests

**Files:**

- Create: `tests/wf_api/test_raw_workflow_plan_extraction.py`

- [ ] **Step 1: Write the tests**

```python
from __future__ import annotations


def test_canonical_import_from_wf_api_models() -> None:
    from wf_api.models import RawWorkflowPlan

    assert RawWorkflowPlan.__name__ == "RawWorkflowPlan"


def test_compat_import_from_wf_mcp_models() -> None:
    from wf_mcp.models import RawWorkflowPlan as CompatPlan

    assert CompatPlan.__name__ == "RawWorkflowPlan"


def test_canonical_and_compat_are_identical() -> None:
    from wf_api.models import RawWorkflowPlan as Canonical
    from wf_mcp.models import RawWorkflowPlan as Compat

    assert Canonical is Compat
```

Note: The import direction rule is already covered by `tests/wf_api/test_import_direction.py::test_wf_api_has_no_wf_mcp_imports`. No need to duplicate.

- [ ] **Step 2: Run the new tests**

Run: `uv run pytest tests/wf_api/test_raw_workflow_plan_extraction.py -v`
Expected: all 3 PASS

---

### Task 5: Update test imports to use canonical path

**Files:**

- Modify: `tests/wf_mcp/service/conftest.py`
- Modify: `tests/wf_mcp/workflow_surface/test_runs.py`

- [ ] **Step 1: Update `tests/wf_mcp/service/conftest.py`**

Change line 8 from:

```python
from wf_mcp.models import AuthRecord, ConnectionConfig, RawWorkflowPlan
```

to:

```python
from wf_api.models import RawWorkflowPlan
from wf_mcp.models import AuthRecord, ConnectionConfig
```

- [ ] **Step 2: Update `tests/wf_mcp/workflow_surface/test_runs.py`**

Change line 32 from:

```python
from wf_mcp.models import RawWorkflowPlan
```

to:

```python
from wf_api.models import RawWorkflowPlan
```

- [ ] **Step 3: Run ruff on touched files**

Run: `uv run ruff check tests/wf_mcp/service/conftest.py tests/wf_mcp/workflow_surface/test_runs.py`
Expected: no errors

- [ ] **Step 4: Run basedpyright on touched files**

Run: `uv run basedpyright --level error tests/wf_mcp/service/conftest.py tests/wf_mcp/workflow_surface/test_runs.py`
Expected: no errors

---

### Task 6: Run full test suite and verify

- [ ] **Step 1: Run pytest**

Run: `uv run pytest -q`
Expected: all tests pass

- [ ] **Step 2: Run ruff on all touched files**

Run: `uv run ruff check src/wf_api/models.py src/wf_mcp/models.py src/wf_mcp/__init__.py tests/wf_api/test_raw_workflow_plan_extraction.py tests/wf_mcp/service/conftest.py tests/wf_mcp/workflow_surface/test_runs.py`
Expected: no errors

- [ ] **Step 3: Run basedpyright on touched files**

Run: `uv run basedpyright --level error src/wf_api/models.py src/wf_mcp/models.py`
Expected: no errors
