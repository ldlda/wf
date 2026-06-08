# MCP Tool Wrapper Event Seam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove direct `wf_mcp` event construction from `wrap_discovered_tool` so the wrapper can move to `wf_sources_mcp` in the next slice.

**Architecture:** Add a neutral `ToolWrapperEvent` DTO in `wf_sources_mcp.tool_events`. `wf_mcp.workflow.wrappers.wrap_discovered_tool` emits this neutral DTO. `wf_mcp.broker.discovery.specs_from_discovered_tools` adapts neutral wrapper events into broker-local `McpEvent` via `make_event`, preserving external event behavior.

**Tech Stack:** Python 3.14, dataclasses, `wf_authoring.NodeSpec`, `wf_sources_mcp` DTOs, pytest, ruff, basedpyright.

---

## Hard Boundaries

- Do not move `wrap_discovered_tool` in this slice.
- Do not move `specs_from_discovered_tools` in this slice.
- Do not change broker event kinds or payload shapes.
- Do not import `wf_mcp.events`, `wf_mcp.broker.events`, or `McpEvent` from `wf_mcp.workflow.wrappers`.
- Do not add any `wf_mcp` imports to `src/wf_sources_mcp/tool_events.py`.
- Preserve `wrap_discovered_tool(..., emit_event=...)` parameter name, but change its event object to neutral `ToolWrapperEvent`.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Create `src/wf_sources_mcp/tool_events.py`: neutral `ToolWrapperEvent`, `ToolWrapperEventSink`, and small factories.
- Modify `src/wf_sources_mcp/__init__.py`: export `ToolWrapperEvent`, `ToolWrapperEventSink`, `tool_call_started_event`, `tool_call_completed_event`.
- Modify `src/wf_mcp/workflow/wrappers.py`: emit neutral events instead of broker `McpEvent`.
- Modify `src/wf_mcp/broker/discovery.py`: adapt neutral events to broker-local `McpEvent`.
- Create `tests/wf_sources_mcp/test_tool_events.py`: canonical neutral event tests.
- Modify `tests/wf_mcp/test_workflow_wrappers.py`: add direct neutral event emission test.
- Modify `tests/wf_mcp/service/test_events.py`: keep existing broker event behavior passing.
- Modify `tests/wf_sources_mcp/test_import_direction_guard.py`: forbid old broker event imports inside `wf_sources_mcp`.
- Modify docs: `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Add Canonical Neutral Tool Event Tests

**Files:**
- Create: `tests/wf_sources_mcp/test_tool_events.py`

- [ ] **Step 1: Write tests for neutral event DTO/factories**

Create `tests/wf_sources_mcp/test_tool_events.py`:

```python
from __future__ import annotations

from wf_sources_mcp.tool_events import (
    ToolWrapperEvent,
    tool_call_completed_event,
    tool_call_started_event,
)


def test_tool_call_started_event_shape() -> None:
    event = tool_call_started_event(
        connection_id="demo.default",
        capability_id="demo.default.echo",
        input_payload={"message": "hello"},
    )

    assert event == ToolWrapperEvent(
        kind="tool_call_started",
        connection_id="demo.default",
        capability_id="demo.default.echo",
        payload={"input": {"message": "hello"}},
    )


def test_tool_call_completed_event_shape() -> None:
    event = tool_call_completed_event(
        connection_id="demo.default",
        capability_id="demo.default.echo",
        outcome="ok",
        meta={"duration_ms": 3},
    )

    assert event.kind == "tool_call_completed"
    assert event.connection_id == "demo.default"
    assert event.capability_id == "demo.default.echo"
    assert event.payload == {"outcome": "ok", "meta": {"duration_ms": 3}}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_tool_events.py -q
```

Expected: fail with `ModuleNotFoundError` or import error for `wf_sources_mcp.tool_events`.

---

### Task 2: Create `wf_sources_mcp.tool_events`

**Files:**
- Create: `src/wf_sources_mcp/tool_events.py`

- [ ] **Step 1: Add neutral event DTO and factories**

Create `src/wf_sources_mcp/tool_events.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolWrapperEvent:
    """Neutral tool-wrapper event before broker-specific event projection."""

    kind: str
    connection_id: str
    capability_id: str
    payload: dict[str, Any] = field(default_factory=dict)


ToolWrapperEventSink = Callable[[ToolWrapperEvent], None]


def tool_call_started_event(
    *,
    connection_id: str,
    capability_id: str,
    input_payload: dict[str, Any],
) -> ToolWrapperEvent:
    return ToolWrapperEvent(
        kind="tool_call_started",
        connection_id=connection_id,
        capability_id=capability_id,
        payload={"input": input_payload},
    )


def tool_call_completed_event(
    *,
    connection_id: str,
    capability_id: str,
    outcome: str,
    meta: dict[str, Any],
) -> ToolWrapperEvent:
    return ToolWrapperEvent(
        kind="tool_call_completed",
        connection_id=connection_id,
        capability_id=capability_id,
        payload={"outcome": outcome, "meta": meta},
    )


__all__ = [
    "ToolWrapperEvent",
    "ToolWrapperEventSink",
    "tool_call_completed_event",
    "tool_call_started_event",
]
```

- [ ] **Step 2: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_tool_events.py -q
```

Expected: pass.

---

### Task 3: Export Neutral Tool Event Symbols

**Files:**
- Modify: `src/wf_sources_mcp/__init__.py`
- Modify: `tests/wf_sources_mcp/test_tool_events.py`

- [ ] **Step 1: Add package-root exports**

Update `src/wf_sources_mcp/__init__.py` so this works:

```python
from wf_sources_mcp import (
    ToolWrapperEvent,
    ToolWrapperEventSink,
    tool_call_completed_event,
    tool_call_started_event,
)
```

If the package uses lazy `__getattr__`, add these names to `__all__` and route them to `.tool_events`:

```python
    if name in {
        "ToolWrapperEvent",
        "ToolWrapperEventSink",
        "tool_call_completed_event",
        "tool_call_started_event",
    }:
        from . import tool_events

        return getattr(tool_events, name)
```

- [ ] **Step 2: Add package-root export test**

Append to `tests/wf_sources_mcp/test_tool_events.py`:

```python
def test_tool_event_symbols_export_from_package_root() -> None:
    from wf_sources_mcp import ToolWrapperEvent as RootToolWrapperEvent
    from wf_sources_mcp import tool_call_started_event as root_started
    from wf_sources_mcp.tool_events import ToolWrapperEvent, tool_call_started_event

    assert RootToolWrapperEvent is ToolWrapperEvent
    assert root_started is tool_call_started_event
```

- [ ] **Step 3: Run canonical tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_tool_events.py -q
```

Expected: pass.

---

### Task 4: Make `wrap_discovered_tool` Emit Neutral Events

**Files:**
- Modify: `src/wf_mcp/workflow/wrappers.py`
- Modify: `tests/wf_mcp/test_workflow_wrappers.py`

- [ ] **Step 1: Replace broker event imports**

In `src/wf_mcp/workflow/wrappers.py`, remove:

```python
from wf_mcp.broker.events import McpEvent, make_event
```

Add:

```python
from wf_sources_mcp.tool_events import (
    ToolWrapperEventSink,
    tool_call_completed_event,
    tool_call_started_event,
)
```

- [ ] **Step 2: Change `emit_event` type**

Change:

```python
emit_event: Callable[[McpEvent], None] | None = None,
```

to:

```python
emit_event: ToolWrapperEventSink | None = None,
```

If `Callable` is no longer used in the file, remove `from collections.abc import Callable`.

- [ ] **Step 3: Emit neutral started event**

Replace:

```python
emit_event(
    make_event(
        "tool_call_started",
        connection_id=connection.id,
        capability_id=f"{connection.id}.{tool.name}",
        payload={"input": payload.model_dump(exclude_unset=True)},
    )
)
```

with:

```python
emit_event(
    tool_call_started_event(
        connection_id=connection.id,
        capability_id=f"{connection.id}.{tool.name}",
        input_payload=payload.model_dump(exclude_unset=True),
    )
)
```

- [ ] **Step 4: Emit neutral completed event**

Replace:

```python
emit_event(
    make_event(
        "tool_call_completed",
        connection_id=connection.id,
        capability_id=f"{connection.id}.{tool.name}",
        payload={
            "outcome": result.outcome,
            "meta": result.meta,
        },
    )
)
```

with:

```python
emit_event(
    tool_call_completed_event(
        connection_id=connection.id,
        capability_id=f"{connection.id}.{tool.name}",
        outcome=result.outcome,
        meta=result.meta,
    )
)
```

- [ ] **Step 5: Add direct wrapper neutral event test**

Append to `tests/wf_mcp/test_workflow_wrappers.py`:

```python
def test_discovered_tool_wrapper_emits_neutral_tool_events() -> None:
    events = []
    spec = wrap_discovered_tool(
        connection=McpSourceConnection(
            id="everything.default",
            provider="everything",
            account="default",
            transport=StdioSourceTransport(command="placeholder"),
        ),
        auth=None,
        executor=cast(ToolExecutor, TextContentAdapter()),
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

    async def run_call() -> None:
        await handler(
            {"message": "hello"},
            RuntimeContext(current_node_id="echo"),
        )

    asyncio.run(run_call())

    assert [event.kind for event in events] == [
        "tool_call_started",
        "tool_call_completed",
    ]
    assert events[0].connection_id == "everything.default"
    assert events[0].capability_id == "everything.default.echo"
    assert events[0].payload == {"input": {"message": "hello"}}
    assert events[1].payload["outcome"] == "ok"
```

- [ ] **Step 6: Run wrapper tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_workflow_wrappers.py -q
```

Expected: pass.

---

### Task 5: Adapt Neutral Events to Broker `McpEvent`

**Files:**
- Modify: `src/wf_mcp/broker/discovery.py`
- Run: existing broker event tests

- [ ] **Step 1: Import neutral event type and broker event factory**

In `src/wf_mcp/broker/discovery.py`, add:

```python
from wf_sources_mcp.tool_events import ToolWrapperEvent
```

Change:

```python
from .events import McpEvent
```

to:

```python
from .events import McpEvent, make_event
```

- [ ] **Step 2: Add adapter helper**

Add above `specs_from_discovered_tools`:

```python
def _project_tool_wrapper_event(event: ToolWrapperEvent) -> McpEvent:
    return make_event(
        event.kind,
        connection_id=event.connection_id,
        capability_id=event.capability_id,
        payload=event.payload,
    )
```

- [ ] **Step 3: Wrap `emit_event` when calling `wrap_discovered_tool`**

Inside `specs_from_discovered_tools`, before the list comprehension:

```python
def emit_tool_event(event: ToolWrapperEvent) -> None:
    if emit_event is not None:
        emit_event(_project_tool_wrapper_event(event))
```

Then change the `wrap_discovered_tool` call argument from:

```python
emit_event=emit_event,
```

to:

```python
emit_event=emit_tool_event if emit_event is not None else None,
```

- [ ] **Step 4: Run broker event behavior tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_events.py::test_service_records_tool_call_events -q
```

Expected: pass. This confirms public broker `McpEvent` behavior is preserved.

---

### Task 6: Add Import Guard for Broker Event Dependency

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add forbidden broker event import test**

Append to `tests/wf_sources_mcp/test_import_direction_guard.py`:

```python
def test_wf_sources_mcp_does_not_import_old_broker_event_modules() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "wf_sources_mcp"
    forbidden = {"wf_mcp.events", "wf_mcp.broker.events"}
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
        "wf_sources_mcp still imports old wf_mcp broker event modules:\n"
        + "\n".join(f"  {violation}" for violation in violations)
    )
```

- [ ] **Step 2: Run import guards**

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
- Move: `docs/superpowers/plans/2026-06-08-tool-wrapper-event-seam.md` to `docs/historical/superpowers/plans/2026-06-08-tool-wrapper-event-seam.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Under the `wf_sources_mcp` cleanup section, add:

```markdown
    - Completed: MCP tool wrapper event emission now uses neutral
      `wf_sources_mcp.tool_events` DTOs. Broker discovery projects those events
      into `McpEvent`, preparing `wrap_discovered_tool` for a package move.
```

- [ ] **Step 2: Update `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`**

Add a completed numbered item before the pending upstream transport/discovery/session services item:

```markdown
18. Complete: MCP tool wrapper event emission now uses neutral
    `wf_sources_mcp.tool_events` DTOs; `wf_mcp.broker.discovery` adapts them to
    broker-local `McpEvent`. `wrap_discovered_tool` remains in `wf_mcp` until
    the next move slice.
```

If numbering differs because new items landed meanwhile, keep the completed item before the broad pending item and renumber.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-tool-wrapper-event-seam.md docs/historical/superpowers/plans/2026-06-08-tool-wrapper-event-seam.md
```

Expected: `git status --short` shows an `R` rename for the plan.

---

### Task 8: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_tool_events.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_workflow_wrappers.py tests/wf_mcp/service/test_events.py::test_service_records_tool_call_events tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_upstream_transport.py -q
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
uv run ruff check src/wf_sources_mcp/tool_events.py src/wf_mcp/workflow/wrappers.py src/wf_mcp/broker/discovery.py tests/wf_sources_mcp/test_tool_events.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_workflow_wrappers.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp/tool_events.py src/wf_mcp/workflow/wrappers.py src/wf_mcp/broker/discovery.py tests/wf_sources_mcp/test_tool_events.py tests/wf_mcp/test_workflow_wrappers.py
```

Expected: `0 errors, 0 warnings, 0 notes`

- [ ] **Step 5: Check old wrapper event imports**

Run:

```bash
rg -n "wf_mcp\\.broker\\.events|wf_mcp\\.events|McpEvent|make_event|ToolWrapperEvent" src\\wf_mcp\\workflow src\\wf_sources_mcp src\\wf_mcp\\broker\\discovery.py tests
```

Expected:

- `src/wf_mcp/workflow/wrappers.py` must not import `McpEvent`, `make_event`, `wf_mcp.events`, or `wf_mcp.broker.events`.
- `src/wf_mcp/broker/discovery.py` may import `McpEvent`, `make_event`, and `ToolWrapperEvent`.
- `src/wf_sources_mcp` may define/use `ToolWrapperEvent` but must not import `wf_mcp.events` or `wf_mcp.broker.events`.

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
- Confirmation that `wf_mcp.workflow.wrappers` no longer imports broker event modules.
- Confirmation that broker tool-call event behavior still emits `McpEvent` with `tool_call_started` and `tool_call_completed`.
- Confirmation that `wrap_discovered_tool` still lives in `wf_mcp`.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
