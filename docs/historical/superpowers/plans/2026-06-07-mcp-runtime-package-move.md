# MCP Runtime Package Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move persistent MCP runtime ownership from `wf_mcp.runtime` to `wf_sources_mcp.runtime` while preserving old imports as compatibility shims.

**Architecture:** The typed `McpSourceConnection` seam and shared `open_mcp_session()` now exist. This slice makes `wf_sources_mcp.runtime` canonical for persistent MCP sessions, pool reuse, and connection fingerprinting. `wf_mcp.runtime.*` should become thin re-export shims only; behavior should not change and persistent runtime remains tool-call-only.

**Tech Stack:** Python 3.14, dataclasses, asyncio actor/queue pattern, MCP Python SDK `ClientSession`, pytest, ruff, basedpyright.

---

## Current State

Canonical source-provider code already exists:

- `wf_sources_mcp.connections.McpSourceConnection`
- `wf_sources_mcp.client.open_mcp_session`
- `wf_sources_mcp.sdk.ToolCallResult`
- `wf_sources_mcp.sdk.converters.tool_result_to_call_result`

Old runtime files still live in `wf_mcp`:

- `src/wf_mcp/runtime/factory.py`
- `src/wf_mcp/runtime/session.py`
- `src/wf_mcp/runtime/pool.py`

The current `McpRuntimePool` has temporary compatibility glue:

```text
McpSourceConnection -> _legacy_connection_config() -> PersistentSessionFactory
```

After this plan, that back-conversion should disappear. The canonical runtime factory should accept `McpSourceConnection` directly.

---

## Non-Goals

- Do not broaden persistent runtime beyond `call_tool`.
- Do not add persistent `read_resource`, `get_prompt`, `invoke_method`, or `send_notification`.
- Do not move `McpSdkAdapter`.
- Do not touch MCP proxy/frontend transport.
- Do not change workflow runtime semantics.
- Do not change on-disk auth/catalog/source registry formats.

---

## Target File Structure

Create:

- `src/wf_sources_mcp/runtime/__init__.py`
- `src/wf_sources_mcp/runtime/session.py`
- `src/wf_sources_mcp/runtime/factory.py`
- `src/wf_sources_mcp/runtime/pool.py`
- `tests/wf_sources_mcp/test_runtime.py`

Modify:

- `src/wf_mcp/runtime/__init__.py` -> re-export shim
- `src/wf_mcp/runtime/session.py` -> re-export shim
- `src/wf_mcp/runtime/factory.py` -> re-export shim
- `src/wf_mcp/runtime/pool.py` -> re-export shim
- `src/wf_mcp/broker/config.py` -> canonical import from `wf_sources_mcp.runtime`
- any other production imports found by `rg 'wf_mcp\\.runtime' src`
- `tests/wf_mcp/test_compat_imports.py` -> shim identity tests
- `docs/current_roadmap.md`
- `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

---

## Task 1: Create Canonical Runtime Session

**Files:**
- Create: `src/wf_sources_mcp/runtime/session.py`
- Test: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Add session tests**

Create `tests/wf_sources_mcp/test_runtime.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from mcp.types import CallToolResult, TextContent

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.runtime import PersistentMcpSession
from wf_sources_mcp.transports import StdioSourceTransport


def _connection() -> McpSourceConnection:
    return McpSourceConnection(
        id="demo.personal",
        provider="demo",
        account="personal",
        transport=StdioSourceTransport(command="fake"),
    )


@pytest.mark.asyncio
async def test_persistent_session_call_callback_normalizes_tool_result() -> None:
    async def call_tool(tool_name: str, payload: dict[str, Any]) -> CallToolResult:
        assert tool_name == "echo"
        assert payload == {"text": "hi"}
        return CallToolResult(
            content=[TextContent(type="text", text="ok")],
            structuredContent={"echoed": "hi"},
        )

    session = PersistentMcpSession(
        connection=_connection(),
        auth=AuthRecord(connection_id="demo.personal", scheme="none"),
        call_callback=call_tool,
    )

    result = await session.call_tool("echo", {"text": "hi"})

    assert result.outcome == "ok"
    assert result.output == {"echoed": "hi"}


@pytest.mark.asyncio
async def test_persistent_session_raises_without_transport() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    with pytest.raises(RuntimeError, match="no tool call transport"):
        await session.call_tool("echo", {})
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: fail because `wf_sources_mcp.runtime` does not exist.

- [ ] **Step 3: Implement canonical session**

Create `src/wf_sources_mcp/runtime/session.py` by moving the implementation from `src/wf_mcp/runtime/session.py`, but change imports/types:

- Import `AuthRecord` from `wf_sources_mcp.auth`.
- Import `McpSourceConnection` from `wf_sources_mcp.connections`.
- Import `ToolCallResult` and `tool_result_to_call_result` from `wf_sources_mcp`.
- `PersistentMcpSession.connection` must be `McpSourceConnection`, not `ConnectionConfig`.

Keep:

- `RawToolCaller`
- `client` injection path
- `call_callback` path
- `close_callback`
- error message `"persistent MCP session has no tool call transport"`

- [ ] **Step 4: Run session tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
uv run basedpyright --level error src/wf_sources_mcp/runtime
```

Expected: pass.

---

## Task 2: Create Canonical Runtime Factory

**Files:**
- Create: `src/wf_sources_mcp/runtime/factory.py`
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Add factory owner-task tests**

Append to `tests/wf_sources_mcp/test_runtime.py`:

```python
from wf_sources_mcp.runtime.factory import PersistentSessionFactory


class _FakeFactory(PersistentSessionFactory):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.closed = False

    async def _call_tool(self, tool_name: str, payload: dict[str, object]):
        self.calls.append((tool_name, payload))
        return CallToolResult(
            content=[TextContent(type="text", text="ok")],
            structuredContent={"echoed": payload["text"]},
        )

    async def _close(self) -> None:
        self.closed = True

    async def _create_with_stack(self, stack, connection, auth):
        class _FakeClient:
            async def call_tool(self, tool_name, payload):
                return await self_factory._call_tool(tool_name, payload)

        self_factory = self
        return _FakeClient()


@pytest.mark.asyncio
async def test_persistent_session_factory_serializes_tool_calls() -> None:
    factory = _FakeFactory()
    session = await factory.create(_connection(), None)

    first = await session.call_tool("echo", {"text": "one"})
    second = await session.call_tool("echo", {"text": "two"})
    await session.close()

    assert first.output == {"echoed": "one"}
    assert second.output == {"echoed": "two"}
    assert factory.calls == [
        ("echo", {"text": "one"}),
        ("echo", {"text": "two"}),
    ]
```

- [ ] **Step 2: Implement factory**

Create `src/wf_sources_mcp/runtime/factory.py` by moving the implementation from `src/wf_mcp/runtime/factory.py`, but change types/imports:

- `PersistentSessionFactory.create(connection: McpSourceConnection, auth: AuthRecord | None)`.
- `_SessionOwner.connection: McpSourceConnection`.
- `_create_with_stack(stack, connection: McpSourceConnection, auth)` uses:

```python
session = await stack.enter_async_context(open_mcp_session(connection, auth))
return session
```

- Remove any `ConnectionConfig` import.
- Keep `_ToolCallRequest` and `_SessionOwner` private.
- Keep actor/queue behavior unchanged.

- [ ] **Step 3: Run factory tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
uv run basedpyright --level error src/wf_sources_mcp/runtime
```

Expected: pass.

---

## Task 3: Create Canonical Runtime Pool

**Files:**
- Create: `src/wf_sources_mcp/runtime/pool.py`
- Modify: `src/wf_sources_mcp/runtime/__init__.py`
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Add pool tests**

Append to `tests/wf_sources_mcp/test_runtime.py`:

```python
from wf_sources_mcp.runtime import McpRuntimePool, connection_runtime_fingerprint


@pytest.mark.asyncio
async def test_runtime_pool_reuses_unchanged_connection() -> None:
    created: list[McpSourceConnection] = []

    async def create_session(connection: McpSourceConnection, auth: AuthRecord | None):
        created.append(connection)
        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            call_callback=lambda tool_name, payload: CallToolResult(
                content=[TextContent(type="text", text="ok")],
                structuredContent={"echoed": payload["text"]},
            ),
        )

    pool = McpRuntimePool(session_factory=create_session)
    connection = _connection()

    await pool.call_tool(connection, None, "echo", {"text": "one"})
    await pool.call_tool(connection, None, "echo", {"text": "two"})

    assert created == [connection]


def test_runtime_fingerprint_changes_when_transport_changes() -> None:
    original = _connection()
    changed = McpSourceConnection(
        id="demo.personal",
        provider="demo",
        account="personal",
        transport=StdioSourceTransport(command="changed"),
    )

    assert connection_runtime_fingerprint(original) != connection_runtime_fingerprint(
        changed
    )
```

- [ ] **Step 2: Implement pool**

Create `src/wf_sources_mcp/runtime/pool.py` by moving the implementation from `src/wf_mcp/runtime/pool.py`, but make it canonical:

- `RuntimeConnection` should be `McpSourceConnection`.
- `SessionFactory` should accept `McpSourceConnection`, not `ConnectionConfig`.
- Remove `_legacy_connection_config`.
- Remove imports from `wf_mcp`.
- `connection_runtime_fingerprint` should accept `McpSourceConnection`.
- Keep reuse/close behavior unchanged.

Create `src/wf_sources_mcp/runtime/__init__.py`:

```python
from .factory import PersistentSessionFactory
from .pool import McpRuntimePool, connection_runtime_fingerprint
from .session import PersistentMcpSession

__all__ = [
    "McpRuntimePool",
    "PersistentMcpSession",
    "PersistentSessionFactory",
    "connection_runtime_fingerprint",
]
```

- [ ] **Step 3: Run runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
uv run basedpyright --level error src/wf_sources_mcp/runtime
```

Expected: pass.

---

## Task 4: Turn `wf_mcp.runtime` Into Compatibility Shims

**Files:**
- Replace: `src/wf_mcp/runtime/session.py`
- Replace: `src/wf_mcp/runtime/factory.py`
- Replace: `src/wf_mcp/runtime/pool.py`
- Modify: `src/wf_mcp/runtime/__init__.py`
- Test: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Add shim identity tests**

In `tests/wf_mcp/test_compat_imports.py`, add:

```python
def test_runtime_shims_reexport_wf_sources_mcp_runtime() -> None:
    from wf_mcp.runtime import (
        McpRuntimePool as OldMcpRuntimePool,
        PersistentMcpSession as OldPersistentMcpSession,
        PersistentSessionFactory as OldPersistentSessionFactory,
        connection_runtime_fingerprint as old_connection_runtime_fingerprint,
    )
    from wf_sources_mcp.runtime import (
        McpRuntimePool,
        PersistentMcpSession,
        PersistentSessionFactory,
        connection_runtime_fingerprint,
    )

    assert OldMcpRuntimePool is McpRuntimePool
    assert OldPersistentMcpSession is PersistentMcpSession
    assert OldPersistentSessionFactory is PersistentSessionFactory
    assert old_connection_runtime_fingerprint is connection_runtime_fingerprint
```

- [ ] **Step 2: Replace old runtime files with shims**

`src/wf_mcp/runtime/session.py`:

```python
"""Compatibility shim for the canonical MCP source runtime session."""

from wf_sources_mcp.runtime.session import PersistentMcpSession, RawToolCaller

__all__ = ["PersistentMcpSession", "RawToolCaller"]
```

`src/wf_mcp/runtime/factory.py`:

```python
"""Compatibility shim for the canonical MCP source runtime factory."""

from wf_sources_mcp.runtime.factory import PersistentSessionFactory

__all__ = ["PersistentSessionFactory"]
```

`src/wf_mcp/runtime/pool.py`:

```python
"""Compatibility shim for the canonical MCP source runtime pool."""

from wf_sources_mcp.runtime.pool import (
    McpRuntimePool,
    SessionFactory,
    connection_runtime_fingerprint,
)

__all__ = [
    "McpRuntimePool",
    "SessionFactory",
    "connection_runtime_fingerprint",
]
```

Keep `src/wf_mcp/runtime/protocols.py` as-is if it already shims `ToolExecutor`.

Update `src/wf_mcp/runtime/__init__.py` to re-export from `wf_sources_mcp.runtime` plus `ToolExecutor`:

```python
from wf_sources_mcp.runtime import (
    McpRuntimePool,
    PersistentMcpSession,
    PersistentSessionFactory,
    connection_runtime_fingerprint,
)

from .protocols import ToolExecutor

__all__ = [
    "McpRuntimePool",
    "PersistentMcpSession",
    "PersistentSessionFactory",
    "ToolExecutor",
    "connection_runtime_fingerprint",
]
```

- [ ] **Step 3: Run shim tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py tests/wf_sources_mcp/test_runtime.py -q
```

Expected: pass.

---

## Task 5: Update Production Imports To Canonical Runtime

**Files:**
- Modify: `src/wf_mcp/broker/config.py`
- Search all source files

- [ ] **Step 1: Find old runtime imports**

Run:

```bash
rg -n 'wf_mcp\.runtime|from \.\.runtime|from \.runtime' src tests
```

- [ ] **Step 2: Update production imports**

For production code outside shim files, import canonical runtime from `wf_sources_mcp.runtime`.

Likely file:

`src/wf_mcp/broker/config.py`

Replace:

```python
from wf_mcp.runtime import McpRuntimePool, PersistentSessionFactory
```

or relative equivalents with:

```python
from wf_sources_mcp.runtime import McpRuntimePool, PersistentSessionFactory
```

Do not update tests that intentionally verify compatibility shims.

- [ ] **Step 3: Run focused production tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/server/test_config.py::test_server_reuses_real_upstream_session_across_workflow_requests -q
uv run basedpyright --level error src
```

Expected: pass.

---

## Task 6: Preserve Existing Stateful Runtime Tests

**Files:**
- Modify: `tests/wf_mcp/test_stateful_runtime.py` only if required
- Test: `tests/wf_mcp/test_stateful_runtime.py`

- [ ] **Step 1: Run existing tests unchanged first**

Run:

```bash
uv run pytest tests/wf_mcp/test_stateful_runtime.py -q
```

Expected: should pass through shims. If it fails only because helper subclasses still type `ConnectionConfig`, update the tests to import canonical runtime but keep behavior assertions unchanged.

- [ ] **Step 2: Do not weaken behavior assertions**

The following behavior must remain tested:

- pool reuses unchanged connection fingerprint
- pool replaces changed connection fingerprint
- session owner serializes calls through one owner task
- closed sessions are closed via callback
- crashing factory surfaces errors to queued calls

If any of these tests need edits, preserve the same assertions and explain why in final report.

---

## Task 7: Documentation And Verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

- [ ] **Step 1: Update docs**

Roadmap/spec should say:

- persistent MCP runtime moved to `wf_sources_mcp.runtime`
- `wf_mcp.runtime.*` are compatibility shims
- runtime remains tool-call-only
- next slice is moving `McpSdkAdapter` to `wf_sources_mcp.sdk.adapter`

- [ ] **Step 2: Final verification**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/server/test_config.py::test_server_reuses_real_upstream_session_across_workflow_requests -q
uv run ruff check src tests
uv run basedpyright --level error src
git diff --check
```

Expected:

- focused tests pass
- ruff passes
- basedpyright has 0 errors
- no whitespace errors

If `ruff check src tests` finds unrelated pre-existing errors, do not fix unrelated files in this slice. Report exact files/errors and run `ruff check` on changed files instead.

---

## Final Report Requirements

The final report must state:

- runtime files moved or shimmed
- no behavior expansion beyond `call_tool`
- `wf_mcp.runtime` compatibility status
- whether any tests had to change and why
- exact verification commands and outputs

