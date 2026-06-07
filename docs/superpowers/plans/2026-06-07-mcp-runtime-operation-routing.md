# MCP Runtime Operation Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the persistent MCP runtime's hardcoded tool-call request queue with a generic owner-task operation queue that executes explicit callables against `McpSourceClient`, while keeping the public runtime surface tool-call-only.

**Architecture:** The raw MCP SDK `ClientSession` must stay inside the owner task because MCP/AnyIO transports are task/cancel-scope sensitive. `_SessionOwner` should create one `McpSourceClient` inside that task and execute queued callables against it. Request metadata (`operation`, `connection_id`, `sequence`, `submitted_at`) is for diagnostics/future tracing only; execution must never use string dispatch such as `getattr(client, operation)`.

**Tech Stack:** Python 3.14, MCP Python SDK, pytest/pytest-asyncio, ruff, basedpyright.

---

## File Structure

- Modify `src/wf_sources_mcp/runtime/factory.py`
  - Replace `_ToolCallRequest` with generic `_ClientOperationRequest[T]`.
  - Add sequence/submission metadata.
  - Add `_SessionOwner.submit()` helper.
  - Wrap the owned SDK session in `McpSourceClient`.
  - Implement `call_tool()` through `submit(..., run=lambda client: client.call_tool(...))`.
- Modify `src/wf_sources_mcp/runtime/session.py`
  - Change `RawToolCaller` to return canonical `ToolCallResult` instead of raw SDK `CallToolResult`.
  - Remove duplicate conversion in the callback path.
  - Keep fallback `client=` conversion for existing tests/fakes.
- Modify tests:
  - `tests/wf_sources_mcp/test_runtime.py`
  - `tests/wf_mcp/test_stateful_runtime.py`
- Update docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

## Hard Boundaries

- Do not add public runtime methods for `read_resource`, `get_prompt`, `invoke_method`, or `send_notification`.
- Do not execute queued operations by string lookup. `operation` is metadata only.
- Do not expose raw `ClientSession` outside the owner task.
- Do not manually call `__aexit__`; keep `AsyncExitStack` and `async with`.
- Do not change `McpRuntimePool.call_tool()` signature or output shape.

---

### Task 1: Add Runtime Routing Metadata Tests

**Files:**
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Extend the fake factory to capture client-operation routing**

In `tests/wf_sources_mcp/test_runtime.py`, update `_FakeFactory` to track created connections and keep its existing call tracking:

```python
class _FakeFactory(PersistentSessionFactory):
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.created_connections: list[McpSourceConnection] = []

    async def _call_tool(
        self, tool_name: str, payload: dict[str, object]
    ) -> CallToolResult:
        self.calls.append((tool_name, payload))
        return CallToolResult(
            content=[TextContent(type="text", text="ok")],
            structuredContent={"echoed": payload["text"]},
        )

    async def _create_with_stack(
        self,
        stack: AsyncExitStack,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> ClientSession:
        self.created_connections.append(connection)
        factory = self

        class _FakeClient:
            async def call_tool(
                self, tool_name: str, payload: dict[str, object]
            ) -> CallToolResult:
                return await factory._call_tool(tool_name, payload)

        return _FakeClient()  # type: ignore[return-value]
```

- [ ] **Step 2: Strengthen the serialization test**

Update `test_persistent_session_factory_serializes_tool_calls`:

```python
@pytest.mark.asyncio
async def test_persistent_session_factory_serializes_tool_calls() -> None:
    factory = _FakeFactory()
    connection = _connection()
    session = await factory.create(connection, None)

    first = await session.call_tool("echo", {"text": "one"})
    second = await session.call_tool("echo", {"text": "two"})
    await session.close()

    assert first.output == {"echoed": "one"}
    assert second.output == {"echoed": "two"}
    assert factory.created_connections == [connection]
    assert factory.calls == [
        ("echo", {"text": "one"}),
        ("echo", {"text": "two"}),
    ]
```

- [ ] **Step 3: Add a test proving public runtime is still tool-call-only**

Append:

```python
def test_persistent_session_public_runtime_is_tool_call_only() -> None:
    public_operations = {
        name
        for name in dir(PersistentMcpSession)
        if not name.startswith("_") and callable(getattr(PersistentMcpSession, name))
    }

    assert "call_tool" in public_operations
    assert "read_resource" not in public_operations
    assert "get_prompt" not in public_operations
    assert "invoke_method" not in public_operations
    assert "send_notification" not in public_operations
```

- [ ] **Step 4: Run the focused runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: pass before implementation. This task locks intended behavior and gives a regression target.

---

### Task 2: Refactor Owner Queue to Generic Client Operations

**Files:**
- Modify: `src/wf_sources_mcp/runtime/factory.py`

- [ ] **Step 1: Update imports**

At the top of `src/wf_sources_mcp/runtime/factory.py`, replace the current imports with the needed generic/callable imports:

```python
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from itertools import count
from typing import Generic, TypeVar

from mcp.client.session import ClientSession

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.client import McpSourceClient, open_mcp_session
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import ToolCallResult

from .session import PersistentMcpSession

T = TypeVar("T")
ClientOperation = Callable[[McpSourceClient], Awaitable[T]]
```

- [ ] **Step 2: Replace `_ToolCallRequest` with metadata-rich generic request**

Replace `_ToolCallRequest` with:

```python
@dataclass(slots=True)
class _ClientOperationRequest(Generic[T]):
    """One explicit operation submitted to the MCP transport owner task.

    `operation` is metadata for diagnostics/tracing only. Execution uses `run`;
    do not dispatch with `getattr(client, operation)`.
    """

    operation: str
    connection_id: str
    sequence: int
    submitted_at: float
    run: ClientOperation[T]
    result: asyncio.Future[T]
```

- [ ] **Step 3: Update `_SessionOwner` fields**

Change `_requests` and add `_sequence`:

```python
    _requests: asyncio.Queue[_ClientOperationRequest[object] | None] = field(
        default_factory=asyncio.Queue
    )
    _sequence: count = field(default_factory=lambda: count(1))
    _task: asyncio.Task[None] | None = None
```

- [ ] **Step 4: Add generic submit helper**

Inside `_SessionOwner`, replace the body of `call_tool` later, but first add this helper before `call_tool`:

```python
    async def submit(
        self,
        operation: str,
        run: ClientOperation[T],
    ) -> T:
        """Submit an explicit client operation to the MCP owner task."""
        task = self._task
        if task is None:
            raise RuntimeError("persistent MCP session is not started")
        if task.done():
            await task
            raise RuntimeError("persistent MCP session stopped unexpectedly")

        result: asyncio.Future[T] = asyncio.get_running_loop().create_future()
        await self._requests.put(
            _ClientOperationRequest(
                operation=operation,
                connection_id=self.connection.id,
                sequence=next(self._sequence),
                submitted_at=time.monotonic(),
                run=run,
                result=result,
            )
        )
        done, _pending = await asyncio.wait(
            {result, task}, return_when=asyncio.FIRST_COMPLETED
        )
        if result in done:
            return result.result()
        await task
        raise RuntimeError("persistent MCP session stopped unexpectedly")
```

- [ ] **Step 5: Implement `call_tool` through explicit operation callable**

Replace `_SessionOwner.call_tool` with:

```python
    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, object],
    ) -> ToolCallResult:
        """Submit a tool call through the generic owner-task operation queue."""
        return await self.submit(
            operation="call_tool",
            run=lambda client: client.call_tool(tool_name, payload),
        )
```

- [ ] **Step 6: Wrap SDK session with `McpSourceClient` in owner loop**

In `_run`, after `_create_with_stack`, create the facade and execute request callables:

```python
                session = await self.factory._create_with_stack(
                    stack, self.connection, self.auth
                )
                client = McpSourceClient(session=session, connection=self.connection)
                ready.set_result(None)
                while True:
                    request = await self._requests.get()
                    if request is None:
                        return
                    try:
                        response = await request.run(client)
                    except Exception as exc:
                        request.result.set_exception(exc)
                    else:
                        request.result.set_result(response)
```

- [ ] **Step 7: Preserve failure fanout**

Keep the existing `except BaseException as exc` block, but it should now work with `_ClientOperationRequest[object]`:

```python
            while not self._requests.empty():
                pending = self._requests.get_nowait()
                if pending is not None and not pending.result.done():
                    pending.result.set_exception(exc)
            raise
```

- [ ] **Step 8: Run source runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: pass.

---

### Task 3: Make `PersistentMcpSession` Callback Return Canonical Result

**Files:**
- Modify: `src/wf_sources_mcp/runtime/session.py`
- Modify: `tests/wf_sources_mcp/test_runtime.py` if needed.

- [ ] **Step 1: Update callback type**

In `src/wf_sources_mcp/runtime/session.py`, remove the raw SDK `CallToolResult` import and change `RawToolCaller`:

```python
RawToolCaller = Callable[[str, dict[str, Any]], Awaitable[ToolCallResult]]
```

- [ ] **Step 2: Update callback path in `call_tool`**

Replace `call_tool()` implementation with:

```python
    async def call_tool(
        self, tool_name: str, payload: dict[str, Any]
    ) -> ToolCallResult:
        if self.call_callback is not None:
            return await self.call_callback(tool_name, payload)
        if self.client is not None:
            result = await self.client.call_tool(tool_name, payload)
            return tool_result_to_call_result(result)
        raise RuntimeError("persistent MCP session has no tool call transport")
```

- [ ] **Step 3: Update direct callback test**

In `tests/wf_sources_mcp/test_runtime.py`, update `test_persistent_session_call_callback_normalizes_tool_result` because callback now returns canonical `ToolCallResult`:

```python
@pytest.mark.asyncio
async def test_persistent_session_call_callback_returns_canonical_result() -> None:
    async def call_tool(tool_name: str, payload: dict[str, Any]) -> ToolCallResult:
        assert tool_name == "echo"
        assert payload == {"text": "hi"}
        return ToolCallResult(outcome="ok", output={"echoed": "hi"})

    session = PersistentMcpSession(
        connection=_connection(),
        auth=AuthRecord(connection_id="demo.personal", scheme="none"),
        call_callback=call_tool,
    )

    result = await session.call_tool("echo", {"text": "hi"})

    assert result.outcome == "ok"
    assert result.output == {"echoed": "hi"}
```

Use an import alias if both SDK raw `CallToolResult` and canonical `ToolCallResult` are needed in the same test file:

```python
from mcp.types import CallToolResult as RawCallToolResult
from wf_sources_mcp.sdk import ToolCallResult
```

- [ ] **Step 4: Run runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py tests/wf_mcp/test_stateful_runtime.py -q
```

Expected: pass.

---

### Task 4: Verify No Runtime Surface Expansion

**Files:**
- Test: `tests/wf_sources_mcp/test_runtime.py`
- Docs: no code changes unless prior task missed docstring boundary.

- [ ] **Step 1: Run method grep**

Run:

```bash
rg -n "def (list_tools|list_resources|list_prompts|read_resource|get_prompt|invoke_method|send_notification)" src/wf_sources_mcp/runtime
```

Expected: no matches.

- [ ] **Step 2: Run compatibility and stateful tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/test_compat_imports.py -q
```

Expected: pass.

---

### Task 5: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move after completion: `docs/superpowers/plans/2026-06-07-mcp-runtime-operation-routing.md` to `docs/historical/superpowers/plans/2026-06-07-mcp-runtime-operation-routing.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the MCP upstream source runtime cleanup bullets, add:

```markdown
   - Completed: persistent MCP runtime owner now uses a generic explicit
     operation queue with request metadata and `McpSourceClient` execution.
     Public runtime remains tool-call-only; `operation` strings are diagnostics
     labels, not dispatch.
```

- [ ] **Step 2: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, in the numbered `wf_sources_mcp` implementation status list after the source-client facade item, add:

```markdown
10. Complete: persistent MCP runtime owner now routes explicit callables through
    a generic operation queue with request metadata. The runtime still exposes
    only `call_tool`; non-tool methods require a separate public-surface slice.
```

Renumber the old following item if needed.

- [ ] **Step 3: Archive completed plan after implementation**

Run only after all code/tests pass:

```bash
git mv docs/superpowers/plans/2026-06-07-mcp-runtime-operation-routing.md docs/historical/superpowers/plans/2026-06-07-mcp-runtime-operation-routing.md
```

---

### Task 6: Final Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/test_compat_imports.py -q
```

Expected: pass. Report skips exactly.

- [ ] **Step 2: Run source typecheck**

Run:

```bash
uv run basedpyright --level error src
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 3: Run focused test typecheck**

Run:

```bash
uv run basedpyright --level error tests/wf_sources_mcp/test_runtime.py tests/wf_mcp/test_stateful_runtime.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 4: Run focused lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/runtime tests/wf_sources_mcp/test_runtime.py tests/wf_mcp/test_stateful_runtime.py
```

Expected: `All checks passed!`

- [ ] **Step 5: Confirm runtime non-expansion**

Run:

```bash
rg -n "def (list_tools|list_resources|list_prompts|read_resource|get_prompt|invoke_method|send_notification)" src/wf_sources_mcp/runtime
```

Expected: no matches.

- [ ] **Step 6: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings are acceptable on Windows.

---

## Self-Review

- Spec coverage: The plan replaces hardcoded tool-call requests with generic explicit callable requests, preserves owner-task transport ownership, adds metadata, and keeps the public runtime surface unchanged.
- Placeholder scan: No placeholder steps remain. Code snippets use exact paths and current symbols.
- Type consistency: queued operations return canonical `ToolCallResult` for `call_tool`; raw SDK `CallToolResult` remains only in fake/SDK-session paths.
- Explicit dispatch rule: `operation` is metadata only. The plan never uses `getattr(client, operation)`.

