# MCP Tool Wrapper Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `wrap_discovered_tool` from `wf_mcp.workflow.wrappers` into canonical `wf_sources_mcp.tool_wrappers` now that event emission is neutral.

**Architecture:** `wf_sources_mcp.tool_wrappers` will own generated MCP tool `NodeSpec` creation. `wf_mcp.workflow.wrappers` becomes a compatibility shim re-exporting the canonical function and `_model_from_schema` alias. Broker discovery imports the canonical wrapper directly, then projects neutral tool events to broker `McpEvent` as it already does.

**Tech Stack:** Python 3.14, `wf_authoring.NodeSpec`, `wf_core.RuntimeContext`, Pydantic v2, `wf_sources_mcp` typed connection/auth/sdk DTOs, pytest, ruff, basedpyright.

---

## Hard Boundaries

- Do not move `specs_from_discovered_tools` in this slice.
- Do not change broker event kinds or payload shapes.
- Do not change generated `NodeSpec` names, schemas, outcomes, or payload behavior.
- Do not import `wf_mcp` from `src/wf_sources_mcp/tool_wrappers.py`.
- Keep `wf_mcp.workflow.wrap_discovered_tool` import-compatible via a shim.
- Keep `_model_from_schema` compatibility alias in `wf_mcp.workflow.wrappers` for now.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Create `src/wf_sources_mcp/tool_wrappers.py`: canonical `wrap_discovered_tool`.
- Modify `src/wf_sources_mcp/__init__.py`: export `wrap_discovered_tool` lazily or directly.
- Replace `src/wf_mcp/workflow/wrappers.py`: compatibility shim re-exporting `wrap_discovered_tool` and `_model_from_schema`.
- Keep `src/wf_mcp/workflow/__init__.py`: can continue importing from `.wrappers`, now a shim.
- Modify `src/wf_mcp/broker/discovery.py`: import `wrap_discovered_tool` from `wf_sources_mcp.tool_wrappers`.
- Create `tests/wf_sources_mcp/test_tool_wrappers.py`: canonical wrapper behavior tests.
- Modify `tests/wf_mcp/test_compat_imports.py`: shim identity test.
- Modify `tests/wf_mcp/test_workflow_wrappers.py`: either leave as compat-path tests or reduce if duplicated; do not delete coverage in this slice unless canonical tests are equal-or-stronger.
- Modify `tests/wf_sources_mcp/test_import_direction_guard.py`: add guard forbidding `wf_mcp.workflow` imports if not already sufficient.
- Modify docs: `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Add Canonical Tool Wrapper Tests

**Files:**
- Create: `tests/wf_sources_mcp/test_tool_wrappers.py`

- [ ] **Step 1: Write canonical wrapper behavior tests**

Create `tests/wf_sources_mcp/test_tool_wrappers.py`:

```python
from __future__ import annotations

from typing import Any, cast

import pytest

from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import ToolCallResult, ToolExecutor
from wf_sources_mcp.tool_wrappers import wrap_discovered_tool
from wf_sources_mcp.transports import StdioSourceTransport


def _connection() -> McpSourceConnection:
    return McpSourceConnection(
        id="everything.default",
        provider="everything",
        account="default",
        transport=StdioSourceTransport(command="placeholder"),
    )


class RecordingExecutor:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        self.payloads.append(payload)
        return ToolCallResult(outcome="ok", output={})


class TextContentExecutor:
    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        message = payload.get("message", "")
        return ToolCallResult(
            outcome="ok",
            output={
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo: {message}",
                    }
                ],
            },
        )


@pytest.mark.asyncio
async def test_wrap_discovered_tool_omits_unset_optional_arguments() -> None:
    executor = RecordingExecutor()
    spec = wrap_discovered_tool(
        connection=_connection(),
        auth=None,
        executor=cast(ToolExecutor, executor),
        tool=DiscoveredTool(
            name="browser_snapshot",
            title=None,
            description=None,
            input_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "depth": {"type": "integer"},
                },
            },
            output_schema={"type": "object", "properties": {}},
        ),
    )
    handler = build_async_registry(spec)[spec.name]

    await handler({}, RuntimeContext(current_node_id="snapshot"))
    await handler({"target": "main"}, RuntimeContext(current_node_id="snapshot"))

    assert executor.payloads == [{}, {"target": "main"}]


@pytest.mark.asyncio
async def test_wrap_discovered_tool_preserves_raw_mcp_content_output() -> None:
    spec = wrap_discovered_tool(
        connection=_connection(),
        auth=None,
        executor=cast(ToolExecutor, TextContentExecutor()),
        tool=DiscoveredTool(
            name="echo",
            title="Echo",
            description=None,
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            output_schema={
                "type": "object",
                "properties": {"content": {"type": "array"}},
            },
        ),
    )
    handler = build_async_registry(spec)[spec.name]

    result = await handler(
        {"message": "hello"},
        RuntimeContext(current_node_id="echo"),
    )

    assert result["outcome"] == "ok"
    assert "text" not in result["output"]
    assert result["output"]["content"][0]["type"] == "text"
    assert result["output"]["content"][0]["text"] == "Echo: hello"


@pytest.mark.asyncio
async def test_wrap_discovered_tool_emits_neutral_tool_events() -> None:
    events = []
    spec = wrap_discovered_tool(
        connection=_connection(),
        auth=None,
        executor=cast(ToolExecutor, TextContentExecutor()),
        tool=DiscoveredTool(
            name="echo",
            title="Echo",
            description=None,
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            output_schema={
                "type": "object",
                "properties": {"content": {"type": "array"}},
            },
        ),
        emit_event=events.append,
    )
    handler = build_async_registry(spec)[spec.name]

    await handler({"message": "hello"}, RuntimeContext(current_node_id="echo"))

    assert [event.kind for event in events] == [
        "tool_call_started",
        "tool_call_completed",
    ]
    assert events[0].connection_id == "everything.default"
    assert events[0].capability_id == "everything.default.echo"
    assert events[0].payload == {"input": {"message": "hello"}}
    assert events[1].payload["outcome"] == "ok"
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_tool_wrappers.py -q
```

Expected: fail with `ModuleNotFoundError` or import error for `wf_sources_mcp.tool_wrappers`.

---

### Task 2: Create Canonical `wf_sources_mcp.tool_wrappers`

**Files:**
- Create: `src/wf_sources_mcp/tool_wrappers.py`

- [ ] **Step 1: Move wrapper implementation**

Create `src/wf_sources_mcp/tool_wrappers.py` with the current implementation from `src/wf_mcp/workflow/wrappers.py`, excluding `_model_from_schema` compatibility alias:

```python
from __future__ import annotations

from pydantic import BaseModel

from wf_authoring import NodeReturn, NodeSpec
from wf_core import RuntimeContext
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.schema_models import model_from_schema
from wf_sources_mcp.sdk import ToolExecutor
from wf_sources_mcp.tool_events import (
    ToolWrapperEventSink,
    tool_call_completed_event,
    tool_call_started_event,
)


def wrap_discovered_tool(
    *,
    connection: McpSourceConnection,
    auth: AuthRecord | None,
    executor: ToolExecutor,
    tool: DiscoveredTool,
    emit_event: ToolWrapperEventSink | None = None,
) -> NodeSpec[BaseModel, BaseModel]:
    input_model = model_from_schema(
        f"{connection.id}_{tool.name}_Input",
        tool.input_schema,
    )
    output_model = model_from_schema(
        f"{connection.id}_{tool.name}_Output",
        tool.output_schema,
    )

    async def invoke_tool(
        payload: BaseModel,
        ctx: RuntimeContext,
    ) -> NodeReturn[BaseModel]:
        if emit_event is not None:
            emit_event(
                tool_call_started_event(
                    connection_id=connection.id,
                    capability_id=f"{connection.id}.{tool.name}",
                    input_payload=payload.model_dump(exclude_unset=True),
                )
            )
        result = await executor.call_tool(
            connection=connection,
            auth=auth,
            tool_name=tool.name,
            # Pydantic fills absent optional fields with None, but strict MCP
            # servers such as Playwright distinguish omitted from explicit null.
            payload=payload.model_dump(exclude_unset=True),
        )
        if emit_event is not None:
            emit_event(
                tool_call_completed_event(
                    connection_id=connection.id,
                    capability_id=f"{connection.id}.{tool.name}",
                    outcome=result.outcome,
                    meta=result.meta,
                )
            )
        return NodeReturn(
            outcome=result.outcome,
            output=output_model.model_validate(result.output),
        )

    return NodeSpec(
        name=tool.name,
        input_model=input_model,
        output_model=output_model,
        outcomes=tool.outcomes,
        fn=invoke_tool,
        description=tool.description,
        is_async=True,
        input_schema_contract=tool.input_schema,
        output_schema_contract=tool.output_schema,
    )


__all__ = ["wrap_discovered_tool"]
```

- [ ] **Step 2: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_tool_wrappers.py -q
```

Expected: pass.

---

### Task 3: Export `wrap_discovered_tool` From `wf_sources_mcp`

**Files:**
- Modify: `src/wf_sources_mcp/__init__.py`
- Modify: `tests/wf_sources_mcp/test_tool_wrappers.py`

- [ ] **Step 1: Add package-root export**

Update `src/wf_sources_mcp/__init__.py` so this works:

```python
from wf_sources_mcp import wrap_discovered_tool
```

If the package uses lazy `__getattr__`, add `"wrap_discovered_tool"` to `__all__` and route it to `.tool_wrappers`:

```python
    if name == "wrap_discovered_tool":
        from . import tool_wrappers

        return tool_wrappers.wrap_discovered_tool
```

- [ ] **Step 2: Add package-root export test**

Append to `tests/wf_sources_mcp/test_tool_wrappers.py`:

```python
def test_wrap_discovered_tool_exports_from_package_root() -> None:
    from wf_sources_mcp import wrap_discovered_tool as root_wrap_discovered_tool
    from wf_sources_mcp.tool_wrappers import wrap_discovered_tool

    assert root_wrap_discovered_tool is wrap_discovered_tool
```

- [ ] **Step 3: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_tool_wrappers.py -q
```

Expected: pass.

---

### Task 4: Replace `wf_mcp.workflow.wrappers` With Compatibility Shim

**Files:**
- Modify: `src/wf_mcp/workflow/wrappers.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Replace wrapper module with shim**

Replace `src/wf_mcp/workflow/wrappers.py` with:

```python
"""Compatibility shim for MCP source tool wrapper generation.

Canonical implementation lives in `wf_sources_mcp.tool_wrappers`.
"""

from __future__ import annotations

from wf_sources_mcp.schema_models import model_from_schema
from wf_sources_mcp.tool_wrappers import wrap_discovered_tool

_model_from_schema = model_from_schema

__all__ = ["_model_from_schema", "wrap_discovered_tool"]
```

- [ ] **Step 2: Add shim identity test**

Append to `tests/wf_mcp/test_compat_imports.py`:

```python
def test_wf_mcp_workflow_wrapper_shim_reexports_wf_sources_mcp_tool_wrapper() -> None:
    from wf_mcp.workflow import wrap_discovered_tool as compat_package_wrap
    from wf_mcp.workflow.wrappers import wrap_discovered_tool as compat_module_wrap
    from wf_sources_mcp.tool_wrappers import wrap_discovered_tool

    assert compat_package_wrap is wrap_discovered_tool
    assert compat_module_wrap is wrap_discovered_tool
```

- [ ] **Step 3: Run compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py::test_wf_mcp_workflow_wrapper_shim_reexports_wf_sources_mcp_tool_wrapper -q
```

Expected: pass.

---

### Task 5: Update Broker Discovery to Canonical Import

**Files:**
- Modify: `src/wf_mcp/broker/discovery.py`

- [ ] **Step 1: Replace wrapper import**

Change:

```python
from ..workflow import wrap_discovered_tool
```

to:

```python
from wf_sources_mcp.tool_wrappers import wrap_discovered_tool
```

- [ ] **Step 2: Run broker discovery/event tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_events.py::test_service_records_tool_call_events tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py -q
```

Expected: pass.

---

### Task 6: Keep Old Wrapper Tests Passing or Move Imports to Canonical

**Files:**
- Modify: `tests/wf_mcp/test_workflow_wrappers.py` only if needed.

- [ ] **Step 1: Run old wrapper tests through compatibility path**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_wrappers.py -q
```

Expected: pass. These tests may continue importing `wrap_discovered_tool` from `wf_mcp.workflow` because that validates the shim path.

- [ ] **Step 2: Only if type/lint complains, update imports**

If basedpyright or ruff complains, change test imports to canonical `wf_sources_mcp` types where practical, but keep at least one compatibility test in `tests/wf_mcp/test_compat_imports.py`.

Do not delete `tests/wf_mcp/test_workflow_wrappers.py` in this slice.

---

### Task 7: Strengthen Import-Direction Guard

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Ensure old workflow wrapper import guard exists**

Confirm this test exists from the previous seam:

```python
def test_wf_sources_mcp_does_not_import_old_workflow_wrapper_module() -> None:
    ...
```

If it does not exist, add it with forbidden modules:

```python
forbidden = {"wf_mcp.workflow", "wf_mcp.workflow.wrappers"}
```

- [ ] **Step 2: Run import guards**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: pass.

---

### Task 8: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-08-wf-sources-mcp-tool-wrappers.md` to `docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-tool-wrappers.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Under the `wf_sources_mcp` cleanup section, add:

```markdown
    - Completed: MCP discovered-tool wrapper generation (`wrap_discovered_tool`)
      now lives in `wf_sources_mcp.tool_wrappers`. `wf_mcp.workflow` remains a
      compatibility shim; broker discovery imports the canonical wrapper.
```

- [ ] **Step 2: Update `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`**

Add a completed numbered item before the pending upstream transport/discovery/session services item:

```markdown
19. Complete: MCP discovered-tool wrapper generation (`wrap_discovered_tool`)
    moved to `wf_sources_mcp.tool_wrappers`, with `wf_mcp.workflow` retained as
    a compatibility shim. `specs_from_discovered_tools` remains in `wf_mcp`
    as the broker event projection adapter.
```

If numbering differs because new items landed meanwhile, keep the completed item before the broad pending item and renumber.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-wf-sources-mcp-tool-wrappers.md docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-tool-wrappers.md
```

Expected: `git status --short` shows an `R` rename for the plan.

---

### Task 9: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_tool_wrappers.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_workflow_wrappers.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/service/test_events.py::test_service_records_tool_call_events tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_upstream_transport.py -q
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
uv run ruff check src/wf_sources_mcp/tool_wrappers.py src/wf_mcp/workflow/wrappers.py src/wf_mcp/broker/discovery.py tests/wf_sources_mcp/test_tool_wrappers.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/test_workflow_wrappers.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp/tool_wrappers.py src/wf_mcp/workflow/wrappers.py src/wf_mcp/broker/discovery.py tests/wf_sources_mcp/test_tool_wrappers.py tests/wf_mcp/test_workflow_wrappers.py
```

Expected: `0 errors, 0 warnings, 0 notes`

- [ ] **Step 5: Check old wrapper import usage**

Run:

```bash
rg -n "wf_mcp\\.workflow|from \\.workflow import|from \\.wrappers import|wrap_discovered_tool" src tests
```

Expected:

- `src/wf_mcp/workflow/*` may contain shim exports.
- `tests/wf_mcp/test_workflow_wrappers.py` may use the compatibility import.
- `tests/wf_mcp/test_compat_imports.py` may assert shim identity.
- `src/wf_mcp/broker/discovery.py` must import from `wf_sources_mcp.tool_wrappers`.
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
- Confirmation that `wrap_discovered_tool` is canonical in `wf_sources_mcp.tool_wrappers`.
- Confirmation that `wf_mcp.workflow` and `wf_mcp.workflow.wrappers` are compatibility shims.
- Confirmation that `specs_from_discovered_tools` still lives in `wf_mcp.broker.discovery`.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
