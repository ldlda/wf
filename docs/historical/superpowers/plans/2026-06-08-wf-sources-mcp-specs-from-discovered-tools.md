# MCP Specs From Discovered Tools Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move neutral `specs_from_discovered_tools` logic from `wf_mcp.broker.discovery` into `wf_sources_mcp.discovery`, leaving broker `McpEvent` projection in the compatibility adapter.

**Architecture:** `wf_sources_mcp.discovery.specs_from_discovered_tools` will accept `McpSourceConnection`, `AuthRecord`, `ToolExecutor`, `DiscoveredTool` list, and neutral `ToolWrapperEventSink`. `wf_mcp.broker.discovery.specs_from_discovered_tools` remains as the broker compatibility wrapper: it converts `ConnectionConfig` to `McpSourceConnection` and projects neutral `ToolWrapperEvent` into broker `McpEvent`.

**Tech Stack:** Python 3.14, `wf_authoring.NodeSpec`, `wf_sources_mcp` typed connection/auth/sdk/tool wrapper DTOs, pytest, ruff, basedpyright.

---

## Hard Boundaries

- Do not remove `wf_mcp.broker.discovery.specs_from_discovered_tools`; keep it as a compatibility adapter.
- Do not change broker event kinds or payload shapes.
- Do not change generated `NodeSpec` behavior.
- Do not import `wf_mcp` from `src/wf_sources_mcp/discovery.py`.
- Keep `discover_connection_capabilities` in `wf_sources_mcp.discovery`.
- Do not touch `UpstreamTransportService` behavior beyond imports if needed.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Modify `src/wf_sources_mcp/discovery.py`: add canonical `specs_from_discovered_tools`.
- Modify `src/wf_sources_mcp/__init__.py`: export `specs_from_discovered_tools`.
- Modify `src/wf_mcp/broker/discovery.py`: import canonical specs helper under an alias and keep the broker adapter.
- Create or modify `tests/wf_sources_mcp/test_discovery.py`: add canonical specs tests.
- Modify `tests/wf_mcp/test_compat_imports.py`: add/extend compatibility test for broker adapter if useful.
- Modify docs: `docs/current_roadmap.md` and `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`.
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Add Canonical Specs Tests

**Files:**
- Modify: `tests/wf_sources_mcp/test_discovery.py`

- [ ] **Step 1: Add imports needed for specs tests**

In `tests/wf_sources_mcp/test_discovery.py`, extend imports:

```python
from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_sources_mcp.discovery import (
    discover_connection_capabilities,
    specs_from_discovered_tools,
)
```

Keep existing imports for `AuthRecord`, `DiscoveredTool`, `McpSourceConnection`, `ToolCallResult`, and `BackendAdapter`.

- [ ] **Step 2: Add a recording executor fake**

Append after existing adapter fakes:

```python
class _RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        self.calls.append(
            {
                "connection": connection,
                "auth": auth,
                "tool_name": tool_name,
                "payload": payload,
            }
        )
        return ToolCallResult(
            outcome="ok",
            output={"content": [{"type": "text", "text": "Echo: hello"}]},
            meta={"duration_ms": 3},
        )
```

- [ ] **Step 3: Add canonical specs behavior test**

Append:

```python
async def test_specs_from_discovered_tools_wraps_tools_with_neutral_events() -> None:
    executor = _RecordingExecutor()
    events = []
    connection = _connection()
    specs = specs_from_discovered_tools(
        connection=connection,
        auth=None,
        executor=executor,
        tools=[
            DiscoveredTool(
                name="echo",
                title="Echo",
                description="Echo input",
                input_schema={
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"content": {"type": "array"}},
                },
            )
        ],
        emit_event=events.append,
    )
    handler = build_async_registry(*specs)["echo"]

    result = await handler(
        {"message": "hello"},
        RuntimeContext(current_node_id="echo"),
    )

    assert result["outcome"] == "ok"
    assert result["output"]["content"][0]["text"] == "Echo: hello"
    assert executor.calls[0]["connection"] is connection
    assert executor.calls[0]["tool_name"] == "echo"
    assert executor.calls[0]["payload"] == {"message": "hello"}
    assert [event.kind for event in events] == [
        "tool_call_started",
        "tool_call_completed",
    ]
    assert events[0].capability_id == "demo.default.echo"
    assert events[1].payload == {"outcome": "ok", "meta": {"duration_ms": 3}}
```

- [ ] **Step 4: Add package-root export assertion**

Append:

```python
def test_specs_from_discovered_tools_exports_from_package_root() -> None:
    from wf_sources_mcp import specs_from_discovered_tools as root_specs_from_tools
    from wf_sources_mcp.discovery import specs_from_discovered_tools

    assert root_specs_from_tools is specs_from_discovered_tools
```

- [ ] **Step 5: Run tests and verify failure before implementation**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_discovery.py -q
```

Expected: fail because `wf_sources_mcp.discovery.specs_from_discovered_tools` is not defined/exported yet.

---

### Task 2: Add Canonical `specs_from_discovered_tools`

**Files:**
- Modify: `src/wf_sources_mcp/discovery.py`

- [ ] **Step 1: Add imports**

In `src/wf_sources_mcp/discovery.py`, add:

```python
from wf_authoring import NodeSpec
from wf_sources_mcp.tool_events import ToolWrapperEventSink
from wf_sources_mcp.tool_wrappers import wrap_discovered_tool
from wf_sources_mcp.sdk import BackendAdapter, ToolExecutor
```

If `BackendAdapter` is already imported, merge the import:

```python
from wf_sources_mcp.sdk import BackendAdapter, ToolExecutor
```

- [ ] **Step 2: Add canonical function**

Append below `discover_connection_capabilities`:

```python
def specs_from_discovered_tools(
    *,
    connection: McpSourceConnection,
    auth: AuthRecord | None,
    executor: ToolExecutor,
    tools: list[DiscoveredTool],
    emit_event: ToolWrapperEventSink | None = None,
) -> list[NodeSpec[Any, Any]]:
    return [
        wrap_discovered_tool(
            connection=connection,
            auth=auth,
            executor=executor,
            tool=tool,
            emit_event=emit_event,
        )
        for tool in tools
    ]
```

- [ ] **Step 3: Update `__all__`**

Change:

```python
__all__ = ["DiscoveredConnectionCapabilities", "discover_connection_capabilities"]
```

to:

```python
__all__ = [
    "DiscoveredConnectionCapabilities",
    "discover_connection_capabilities",
    "specs_from_discovered_tools",
]
```

- [ ] **Step 4: Run canonical discovery tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_discovery.py -q
```

Expected: tests still fail only if package-root export is not wired yet. Direct module tests should pass.

---

### Task 3: Export `specs_from_discovered_tools` From Package Root

**Files:**
- Modify: `src/wf_sources_mcp/__init__.py`

- [ ] **Step 1: Add lazy export**

Add `"specs_from_discovered_tools"` to `__all__`.

In the existing discovery `__getattr__` branch, include this name:

```python
    if name in {
        "DiscoveredConnectionCapabilities",
        "discover_connection_capabilities",
        "specs_from_discovered_tools",
    }:
        from . import discovery

        return getattr(discovery, name)
```

- [ ] **Step 2: Run canonical discovery tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_discovery.py -q
```

Expected: all tests pass.

---

### Task 4: Make Broker Discovery a Compatibility Adapter

**Files:**
- Modify: `src/wf_mcp/broker/discovery.py`

- [ ] **Step 1: Import canonical specs helper under an alias**

Change imports:

```python
from wf_sources_mcp.discovery import (
    DiscoveredConnectionCapabilities,
    discover_connection_capabilities,
)
```

to:

```python
from wf_sources_mcp.discovery import (
    DiscoveredConnectionCapabilities,
    discover_connection_capabilities,
    specs_from_discovered_tools as source_specs_from_discovered_tools,
)
```

- [ ] **Step 2: Remove now-unneeded imports**

Remove:

```python
from wf_authoring import NodeSpec
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.tool_wrappers import wrap_discovered_tool
```

Keep:

```python
from typing import Any
from collections.abc import Callable
from wf_sources_mcp.connections import mcp_source_connection_from_connection_config
from wf_sources_mcp.sdk import ToolExecutor
from wf_sources_mcp.tool_events import ToolWrapperEvent
```

If basedpyright needs the return type annotation, keep `NodeSpec` and `DiscoveredTool`; otherwise prefer keeping the public signature unchanged:

```python
) -> list[NodeSpec[Any, Any]]:
```

In that case, keep `from wf_authoring import NodeSpec` and `from wf_sources_mcp.catalog import DiscoveredTool`.

- [ ] **Step 3: Replace function body to delegate to canonical helper**

Inside `specs_from_discovered_tools`, keep `source_connection` and `emit_tool_event`, then replace the list comprehension with:

```python
    return source_specs_from_discovered_tools(
        connection=source_connection,
        auth=auth,
        executor=executor,
        tools=tools,
        emit_event=emit_tool_event if emit_event is not None else None,
    )
```

- [ ] **Step 4: Run broker event behavior test**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_events.py::test_service_records_tool_call_events -q
```

Expected: pass.

---

### Task 5: Add Compatibility Test for Broker Adapter

**Files:**
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Add assertion that broker adapter remains distinct but callable**

Append:

```python
def test_wf_mcp_broker_discovery_keeps_specs_adapter() -> None:
    from wf_mcp.broker.discovery import specs_from_discovered_tools as broker_specs
    from wf_sources_mcp.discovery import specs_from_discovered_tools as source_specs

    assert broker_specs is not source_specs
    assert broker_specs.__name__ == "specs_from_discovered_tools"
```

This is intentionally not an identity test because the broker function adapts `ConnectionConfig` and broker `McpEvent`.

- [ ] **Step 2: Run compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py::test_wf_mcp_broker_discovery_keeps_specs_adapter -q
```

Expected: pass.

---

### Task 6: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-08-wf-sources-mcp-specs-from-discovered-tools.md` to `docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-specs-from-discovered-tools.md`

- [ ] **Step 1: Update `docs/current_roadmap.md`**

Under the `wf_sources_mcp` cleanup section, add:

```markdown
    - Completed: neutral `specs_from_discovered_tools` now lives in
      `wf_sources_mcp.discovery`. `wf_mcp.broker.discovery` remains as the
      broker adapter for `ConnectionConfig` and `McpEvent` projection.
```

- [ ] **Step 2: Update `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`**

Add a completed numbered item before the pending upstream transport/discovery/session services item:

```markdown
20. Complete: neutral `specs_from_discovered_tools` moved to
    `wf_sources_mcp.discovery`. `wf_mcp.broker.discovery` remains as the broker
    adapter for legacy `ConnectionConfig` input and `McpEvent` projection.
```

If numbering differs because new items landed meanwhile, keep the completed item before the broad pending item and renumber.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-wf-sources-mcp-specs-from-discovered-tools.md docs/historical/superpowers/plans/2026-06-08-wf-sources-mcp-specs-from-discovered-tools.md
```

Expected: `git status --short` shows an `R` rename for the plan.

---

### Task 7: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_discovery.py tests/wf_sources_mcp/test_tool_wrappers.py tests/wf_sources_mcp/test_import_direction_guard.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/service/test_events.py::test_service_records_tool_call_events tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_upstream_transport.py -q
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
uv run ruff check src/wf_sources_mcp/discovery.py src/wf_mcp/broker/discovery.py tests/wf_sources_mcp/test_discovery.py tests/wf_mcp/test_compat_imports.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp/discovery.py src/wf_mcp/broker/discovery.py tests/wf_sources_mcp/test_discovery.py tests/wf_mcp/test_compat_imports.py
```

Expected: `0 errors, 0 warnings, 0 notes`

- [ ] **Step 5: Check remaining broker discovery import usage**

Run:

```bash
rg -n "specs_from_discovered_tools|wf_mcp\\.broker\\.discovery|from \\.discovery import" src tests
```

Expected:

- `src/wf_sources_mcp/discovery.py` owns neutral `specs_from_discovered_tools`.
- `src/wf_mcp/broker/discovery.py` owns broker adapter `specs_from_discovered_tools`.
- `src/wf_mcp/broker/service/upstream_transport.py` may still import broker adapter.
- `src/wf_sources_mcp` must not import `wf_mcp.broker.discovery`.

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
- Confirmation that neutral `specs_from_discovered_tools` is canonical in `wf_sources_mcp.discovery`.
- Confirmation that `wf_mcp.broker.discovery.specs_from_discovered_tools` remains as a broker adapter.
- Confirmation that broker tool-call events still emit `McpEvent`.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
