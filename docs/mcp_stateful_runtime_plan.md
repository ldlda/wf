# MCP Stateful Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make workflow execution safe for stateful MCP servers such as Playwright, and retire misleading broker-style raw tool calls that currently open fresh upstream sessions per call.

**Architecture:** Split "MCP discovery/catalog" from "MCP execution runtime." Catalog refresh can keep using short-lived SDK sessions, but workflow execution must use a persistent per-connection runtime so sequential workflow nodes hit the same upstream MCP server session. Public raw `call_tool` surfaces should be hidden or deleted after generated workflow node specs use the persistent runtime.

**Tech Stack:** Python 3.14, FastMCP, MCP Python SDK, `wf_core`, `wf_authoring`, `wf_mcp`, pytest, basedpyright, ruff.

## Implementation Status

- Tasks 1-3 are implemented: generated MCP workflow NodeSpecs now depend on
  the `ToolExecutor` protocol instead of directly baking in the one-shot SDK
  adapter.
- Tasks 4-7 are implemented: `McpRuntimePool`, `PersistentMcpSession`, and
  `PersistentSessionFactory` exist, and config-built services use the runtime
  pool for generated workflow node execution while discovery/catalog refreshes
  still use short-lived SDK adapter sessions.
- Unsafe raw public `call_tool` surfaces have been deleted. Remaining work starts
  at renaming the legacy `transparent_proxy` package to the clearer
  proxy/provider-layer package.

---

## Problem Statement

`wf_mcp` currently has a serious semantic mismatch:

- Stateless MCP tools, such as echo-style tools, work fine through one-shot calls.
- Stateful MCP servers, such as Playwright, keep browser/page state inside an upstream MCP process/session.
- `McpSdkAdapter.call_tool()` currently opens a fresh MCP session for every call.
- Generated workflow node specs and `wf.mcp.call_tool` both use that one-shot adapter path.

That means a workflow like:

```text
browser_navigate -> browser_snapshot -> browser_click -> browser_snapshot
```

can lose page state between steps even though the graph is correct.

This is not a `wf_core` graph problem. It is an MCP runtime lifecycle problem.

## Current Execution Paths

### Transparent Proxy Path

Used by directly exposed proxied MCP tools in MCP clients:

```text
MCP client
  -> wf-mcp FastMCP server
  -> mounted FastMCP proxy
  -> FastMCP Client(MCPConfigTransport)
  -> upstream MCP server
```

Relevant file:

- `src/wf_mcp/transparent_proxy/mounts.py`

Current behavior:

- Proxy mounts are cached by `ProxyMountRegistry`.
- The proxy/provider object survives reload for unchanged enabled connections.
- This path is better for manual/stateful upstream testing, but it is not the workflow execution path.

### Broker / Workflow Wrapper Path

Used by generated workflow node specs and `wf.mcp.call_tool`:

```text
workflow node
  -> NodeSpec wrapper
  -> BackendAdapter.call_tool(...)
  -> McpSdkAdapter._session(...)
  -> stdio_client(...)
  -> ClientSession(...)
  -> session.initialize()
  -> session.call_tool(...)
  -> session closes
```

Relevant files:

- `src/wf_mcp/workflow/wrappers.py`
- `src/wf_mcp/sdk/adapter.py`
- `src/wf_mcp/broker/service/core.py`
- `src/wf_mcp/broker/service/builtins.py`

Current behavior:

- Each adapter method call creates a new session.
- For stdio transports this can create a new upstream process.
- This is unacceptable for stateful MCP servers in workflows.

## Non-Goals

- Do not change `wf_core` graph semantics for this fix.
- Do not implement Playwright-specific hacks.
- Do not claim notification/subscription forwarding is solved.
- Do not delete all of `src/wf_mcp/broker` in this pass. That package still owns service/source/catalog/deployment infrastructure.
- Do not keep `src/wf_mcp/transparent_proxy` as a long-term package name. That
  name describes a retired public mode split, not the unified server's mounted
  upstream proxy/provider layer.
- Do not expose a bigger public broker surface while fixing this.

## Target Design

Introduce a persistent MCP runtime layer:

```text
McpConnectionRuntime
  owns one live upstream session/client for one connection

McpRuntimePool
  maps connection_id -> McpConnectionRuntime
  reuses runtime across workflow node calls
  reconnects on failure
  closes runtimes on explicit shutdown or config fingerprint change
```

Discovery remains allowed to use short-lived sessions:

```text
refresh_connection_catalog -> short-lived SDK session
```

Workflow execution must use the persistent runtime:

```text
workflow node -> generated NodeSpec -> persistent runtime pool -> same upstream session
```

Public raw `call_tool` surfaces should be removed from normal planner use. If kept temporarily, they must be explicitly marked debugging-only and stateless/stateful-unsafe.

## New Responsibilities

### `wf_mcp.runtime`

New package responsible for live upstream MCP execution sessions.

Proposed files:

- `src/wf_mcp/runtime/__init__.py`
- `src/wf_mcp/runtime/client.py`
- `src/wf_mcp/runtime/pool.py`
- `src/wf_mcp/runtime/errors.py`

This package should not know about workflow artifacts, draft workspaces, or admin MCP tools.

### `wf_mcp.sdk`

Keep protocol conversion and one-shot discovery helpers.

`McpSdkAdapter` may keep:

- `list_tools`
- `list_resources`
- `list_prompts`
- `read_resource`
- `get_prompt`
- `invoke_method`
- `send_notification`
- one-shot `call_tool` only if tests still need it, but it must not be the workflow execution default.

### `wf_mcp.workflow`

Generated NodeSpecs should depend on an execution callable/protocol, not directly on the one-shot adapter.

Target:

```python
class ToolExecutor(Protocol):
    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...
```

Both `McpSdkAdapter` and the persistent runtime pool can implement this protocol during migration.

### `wf_mcp.broker`

Keep for now:

- `WfMcpService`
- source inventory
- catalog snapshots
- connection registry
- artifact and draft workspace stores
- deployment execution
- events

Retire or hide:

- raw public `call_tool` tools
- `wf.mcp.call_tool` as planner-visible workflow helper
- legacy `call_broker_tool` from public broker mode tests

### `wf_mcp.transparent_proxy`

This package is also legacy-named. The code is still useful, but the name is
wrong for the current architecture.

Current useful contents:

- mounted upstream proxy runtime
- proxy mount registry and reload behavior
- source/config reload admin tools
- proxy tool inventory helpers
- safe-tool-name transform for hosts that reject dotted tool ids

Target package name:

```text
wf_mcp.proxy
```

Target shape:

```text
src/wf_mcp/proxy/
  __init__.py
  admin.py
  mounts.py
  runtime.py
  safe_names.py
  tools.py
```

Do this after the persistent workflow runtime seam exists. Otherwise two
separate lifecycle refactors land at once: workflow execution sessions and
mounted proxy/provider naming.

## Task 1: Add A Failing Persistent Runtime Test

**Files:**

- Create: `tests/wf_mcp/test_stateful_runtime.py`
- Modify only test fixtures if needed: `tests/wf_mcp/test_support.py`

- [ ] **Step 1: Create a fake stateful adapter/runtime fixture**

Add this test file:

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.sdk import ToolCallResult


@dataclass(slots=True)
class FakeStatefulSession:
    page_open: bool = False
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def call_tool(self, tool_name: str, payload: dict[str, Any]) -> ToolCallResult:
        self.calls.append((tool_name, payload))
        if tool_name == "browser_navigate":
            self.page_open = True
            return ToolCallResult(outcome="ok", output={"content": "opened"})
        if tool_name == "browser_snapshot":
            if not self.page_open:
                return ToolCallResult(
                    outcome="error",
                    output={"message": "No open pages available"},
                )
            return ToolCallResult(outcome="ok", output={"content": "snapshot"})
        return ToolCallResult(outcome="error", output={"message": "unknown tool"})
```

- [ ] **Step 2: Add the behavior test**

In the same file, add:

```python
def test_stateful_session_fixture_requires_reuse() -> None:
    async def run() -> None:
        first = FakeStatefulSession()
        second = FakeStatefulSession()

        await first.call_tool("browser_navigate", {})
        broken = await second.call_tool("browser_snapshot", {})
        working = await first.call_tool("browser_snapshot", {})

        assert broken.outcome == "error"
        assert broken.output["message"] == "No open pages available"
        assert working.outcome == "ok"
        assert working.output["content"] == "snapshot"

    asyncio.run(run())
```

- [ ] **Step 3: Run the test**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_stateful_runtime.py -q
```

Expected:

```text
1 passed
```

This test is a small executable explanation of the problem. It does not yet assert production behavior.

## Task 2: Introduce Runtime Protocols

**Files:**

- Create: `src/wf_mcp/runtime/__init__.py`
- Create: `src/wf_mcp/runtime/protocols.py`
- Test: `tests/wf_mcp/test_stateful_runtime.py`

- [ ] **Step 1: Add runtime protocols**

Create `src/wf_mcp/runtime/protocols.py`:

```python
from __future__ import annotations

from typing import Any, Protocol

from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.sdk import ToolCallResult


class ToolExecutor(Protocol):
    """Protocol for calling an upstream MCP tool.

    Implementations may be one-shot/stateless or persistent/stateful. Workflow
    execution should use a persistent implementation for stateful MCP servers.
    """

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...
```

Create `src/wf_mcp/runtime/__init__.py`:

```python
from .protocols import ToolExecutor

__all__ = ["ToolExecutor"]
```

- [ ] **Step 2: Assert `McpSdkAdapter` is still protocol-compatible**

Append to `tests/wf_mcp/test_stateful_runtime.py`:

```python
from typing import cast

from wf_mcp.runtime import ToolExecutor
from wf_mcp.sdk import McpSdkAdapter


def test_sdk_adapter_matches_tool_executor_protocol() -> None:
    executor = cast(ToolExecutor, McpSdkAdapter())
    assert executor is not None
```

- [ ] **Step 3: Run the focused test and typecheck**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_stateful_runtime.py -q
uv run basedpyright --level error
```

Expected:

```text
2 passed
0 errors
```

## Task 3: Inject ToolExecutor Into MCP Tool Wrappers

**Files:**

- Modify: `src/wf_mcp/workflow/wrappers.py`
- Modify: `src/wf_mcp/broker/discovery.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/test_workflow_wrappers.py`

- [ ] **Step 1: Change wrapper dependency name from adapter to executor**

In `src/wf_mcp/workflow/wrappers.py`, change the import:

```python
from ..runtime import ToolExecutor
```

and change the `wrap_discovered_tool` parameter:

```python
def wrap_discovered_tool(
    *,
    connection: ConnectionConfig,
    auth: AuthRecord | None,
    executor: ToolExecutor,
    tool: DiscoveredTool,
    emit_event: Callable[[McpEvent], None] | None = None,
) -> NodeSpec[BaseModel, BaseModel]:
```

Inside `invoke_tool`, call:

```python
result = await executor.call_tool(
    connection=connection,
    auth=auth,
    tool_name=tool.name,
    payload=payload.model_dump(exclude_unset=True),
)
```

- [ ] **Step 2: Update discovery call sites**

In `src/wf_mcp/broker/discovery.py`, where `wrap_discovered_tool(...)` is called, pass:

```python
executor=adapter
```

Do not change catalog refresh behavior yet. The adapter remains the temporary executor.

- [ ] **Step 3: Update tests**

In `tests/wf_mcp/test_workflow_wrappers.py`, replace:

```python
adapter=cast(BackendAdapter, adapter),
```

with:

```python
executor=cast(ToolExecutor, adapter),
```

and import:

```python
from wf_mcp.runtime import ToolExecutor
```

- [ ] **Step 4: Run wrapper tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_wrappers.py tests/wf_mcp/test_service.py::test_service_discovers_backend_tools_as_node_specs -q
uv run basedpyright --level error
```

Expected:

```text
passed
0 errors
```

This task creates the injection seam without changing runtime behavior.

## Task 4: Add Persistent MCP Runtime Skeleton

**Files:**

- Create: `src/wf_mcp/runtime/session.py`
- Create: `src/wf_mcp/runtime/pool.py`
- Test: `tests/wf_mcp/test_stateful_runtime.py`

- [ ] **Step 1: Add session wrapper skeleton**

Create `src/wf_mcp/runtime/session.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.sdk import ToolCallResult


@dataclass(slots=True)
class PersistentMcpSession:
    """Long-lived MCP execution handle for one configured connection.

    The first implementation can wrap a test fake. The production implementation
    will own MCP SDK read/write streams and a ClientSession.
    """

    connection: ConnectionConfig
    auth: AuthRecord | None
    client: Any

    async def call_tool(self, tool_name: str, payload: dict[str, Any]) -> ToolCallResult:
        return await self.client.call_tool(tool_name, payload)

    async def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close is not None:
            result = close()
            if hasattr(result, "__await__"):
                await result
```

- [ ] **Step 2: Add runtime pool**

Create `src/wf_mcp/runtime/pool.py`:

```python
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.sdk import ToolCallResult

from .session import PersistentMcpSession

SessionFactory = Callable[
    [ConnectionConfig, AuthRecord | None],
    PersistentMcpSession,
]


def connection_runtime_fingerprint(connection: ConnectionConfig) -> str:
    """Return the transport identity that decides runtime reuse."""
    return json.dumps(
        {
            "id": connection.id,
            "server": connection.server,
            "account": connection.account,
            "metadata": connection.metadata,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


@dataclass(slots=True)
class McpRuntimePool:
    """Cache one persistent MCP runtime per unchanged connection fingerprint."""

    session_factory: SessionFactory
    _sessions: dict[str, tuple[str, PersistentMcpSession]] = field(default_factory=dict)

    def get_session(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        fingerprint = connection_runtime_fingerprint(connection)
        current = self._sessions.get(connection.id)
        if current is not None and current[0] == fingerprint:
            return current[1]
        session = self.session_factory(connection, auth)
        self._sessions[connection.id] = (fingerprint, session)
        return session

    async def call_tool(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        session = self.get_session(connection, auth)
        return await session.call_tool(tool_name, payload)

    async def close_connection(self, connection_id: str) -> None:
        current = self._sessions.pop(connection_id, None)
        if current is not None:
            await current[1].close()
```

- [ ] **Step 3: Export pool types**

Update `src/wf_mcp/runtime/__init__.py`:

```python
from .pool import McpRuntimePool, connection_runtime_fingerprint
from .protocols import ToolExecutor
from .session import PersistentMcpSession

__all__ = [
    "McpRuntimePool",
    "PersistentMcpSession",
    "ToolExecutor",
    "connection_runtime_fingerprint",
]
```

- [ ] **Step 4: Test reuse with the fake stateful session**

Append to `tests/wf_mcp/test_stateful_runtime.py`:

```python
from wf_mcp.runtime import McpRuntimePool, PersistentMcpSession


def test_runtime_pool_reuses_stateful_session_for_same_connection() -> None:
    connection = ConnectionConfig(
        id="playwright.default",
        server="playwright",
        account="default",
        metadata={"transport": "stdio", "command": "pnpx", "args": ["@playwright/mcp"]},
    )

    def factory(connection: ConnectionConfig, auth: AuthRecord | None) -> PersistentMcpSession:
        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            client=FakeStatefulSession(),
        )

    async def run() -> None:
        pool = McpRuntimePool(factory)
        await pool.call_tool(connection, None, "browser_navigate", {})
        snapshot = await pool.call_tool(connection, None, "browser_snapshot", {})
        assert snapshot.outcome == "ok"
        assert snapshot.output["content"] == "snapshot"

    asyncio.run(run())
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_stateful_runtime.py -q
uv run basedpyright --level error
```

Expected:

```text
3 passed
0 errors
```

## Task 5: Wire Runtime Pool Into `WfMcpService`

**Files:**

- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/discovery.py`
- Test: `tests/wf_mcp/test_service.py`

- [ ] **Step 1: Add service field**

In `WfMcpService`, add:

```python
from ...runtime import McpRuntimePool, ToolExecutor
```

Add dataclass field:

```python
tool_executor: ToolExecutor | None = None
```

Add helper:

```python
def _tool_executor(self) -> ToolExecutor:
    """Return the execution path used by generated workflow node specs."""
    if self.tool_executor is not None:
        return self.tool_executor
    return require_adapter(self.adapters, "__missing__")  # temporary compile blocker
```

Do not keep the temporary compile blocker in final code. Replace it in Step 2.

- [ ] **Step 2: Use adapter as fallback executor during migration**

Replace `_tool_executor` with:

```python
def _tool_executor_for(self, connection: ConnectionConfig) -> ToolExecutor:
    """Return the executor for generated workflow nodes.

    A configured persistent executor wins. During migration, the existing
    one-shot adapter remains the fallback so discovery behavior stays stable.
    """
    if self.tool_executor is not None:
        return self.tool_executor
    return require_adapter(self.adapters, connection.server)
```

- [ ] **Step 3: Pass executor into discovered specs**

Where service discovery calls `specs_from_discovered_tools(...)`, thread through:

```python
executor=self._tool_executor_for(connection)
```

If `specs_from_discovered_tools` currently accepts `adapter`, change its
parameter to `executor: ToolExecutor` and pass that to `wrap_discovered_tool`.

- [ ] **Step 4: Add service test with fake executor**

Add to `tests/wf_mcp/test_service.py`:

```python
def test_generated_specs_use_injected_tool_executor() -> None:
    class RecordingExecutor:
        def __init__(self) -> None:
            self.payloads: list[dict[str, Any]] = []

        async def call_tool(self, connection, auth, tool_name, payload):
            self.payloads.append(payload)
            return ToolCallResult(outcome="ok", output={"echoed": payload["message"]})

    executor = RecordingExecutor()
    service = WfMcpService(
        store=FileStore(local_temp_root() / "injected_executor_store"),
        tool_executor=cast(ToolExecutor, executor),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", changed_echo_tool)
    spec = service._get_qualified_spec("demo.personal.echo_tool")
    handler = build_async_registry(spec)[spec.name]

    result = asyncio.run(
        handler({"message": "hello"}, RuntimeContext(current_node_id="echo"))
    )

    assert result["outcome"] == "ok"
    assert result["output"]["echoed"] == "hello"
```

Adjust imports in the test file:

```python
from typing import Any, cast
from wf_authoring import build_async_registry
from wf_core import RuntimeContext
from wf_mcp.runtime import ToolExecutor
from wf_mcp.sdk import ToolCallResult
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_service.py::test_generated_specs_use_injected_tool_executor -q
uv run basedpyright --level error
```

Expected:

```text
1 passed
0 errors
```

## Task 6: Implement Production Persistent SDK Session

**Files:**

- Modify: `src/wf_mcp/runtime/session.py`
- Create: `src/wf_mcp/runtime/factory.py`
- Test: `tests/wf_mcp/test_stateful_runtime.py`

- [ ] **Step 1: Create production factory boundary**

Create `src/wf_mcp/runtime/factory.py`:

```python
from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass, field

import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from wf_mcp.models import AuthRecord, ConnectionConfig

from .session import PersistentMcpSession


@dataclass(slots=True)
class PersistentSessionFactory:
    """Create initialized persistent MCP sessions for configured connections."""

    async_exit_stack: AsyncExitStack = field(default_factory=AsyncExitStack)

    async def create(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> PersistentMcpSession:
        transport = connection.metadata.get("transport", "stdio")
        if transport == "stdio":
            params = StdioServerParameters(
                command=connection.metadata["command"],
                args=list(connection.metadata.get("args", [])),
                env=connection.metadata.get("env"),
                cwd=connection.metadata.get("cwd"),
            )
            read_stream, write_stream = await self.async_exit_stack.enter_async_context(
                stdio_client(params)
            )
            session = await self.async_exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            return PersistentMcpSession(connection=connection, auth=auth, client=session)

        if transport == "streamable_http":
            http_client = await self.async_exit_stack.enter_async_context(
                httpx.AsyncClient()
            )
            read_stream, write_stream, _get_session_id = (
                await self.async_exit_stack.enter_async_context(
                    streamable_http_client(
                        connection.metadata["url"],
                        http_client=http_client,
                    )
                )
            )
            session = await self.async_exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            return PersistentMcpSession(connection=connection, auth=auth, client=session)

        raise ValueError(f"unsupported MCP transport {transport!r}")

    async def close(self) -> None:
        await self.async_exit_stack.aclose()
```

This factory intentionally owns an `AsyncExitStack`. That is the lifecycle
boundary missing from the one-shot adapter.

- [ ] **Step 2: Let runtime pool support async factories**

If Step 1 uses `async def create`, update `McpRuntimePool` to accept async factory
results:

```python
from collections.abc import Awaitable

SessionFactory = Callable[
    [ConnectionConfig, AuthRecord | None],
    PersistentMcpSession | Awaitable[PersistentMcpSession],
]
```

Make `get_session` async:

```python
async def get_session(...):
    created = self.session_factory(connection, auth)
    session = await created if hasattr(created, "__await__") else created
```

Update `call_tool` to:

```python
session = await self.get_session(connection, auth)
```

Update tests to await `get_session` only through `call_tool`.

- [ ] **Step 3: Export factory**

Update `src/wf_mcp/runtime/__init__.py`:

```python
from .factory import PersistentSessionFactory
```

and add it to `__all__`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_stateful_runtime.py -q
uv run basedpyright --level error
```

Expected:

```text
passed
0 errors
```

## Task 7: Use Persistent Runtime For Workflow Execution

**Files:**

- Modify: `src/wf_mcp/broker/config.py`
- Modify: `src/wf_mcp/server/core.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/test_server.py`

- [ ] **Step 1: Build runtime pool from config**

In `src/wf_mcp/broker/config.py`, after creating the service:

```python
from wf_mcp.runtime import McpRuntimePool, PersistentSessionFactory
```

Create:

```python
runtime_factory = PersistentSessionFactory()
service.tool_executor = McpRuntimePool(runtime_factory.create)
```

The service still registers `McpSdkAdapter()` for discovery.

- [ ] **Step 2: Document why discovery and execution differ**

Add this comment near the setup:

```python
# Discovery can use short-lived SDK sessions. Workflow execution needs a
# persistent runtime so stateful MCP servers such as Playwright keep page/session
# state across sequential workflow nodes.
```

- [ ] **Step 3: Add a non-live unit test**

In `tests/wf_mcp/test_server.py`, add a test that `build_service_from_config`
sets both:

```python
assert service.adapters["playwright"].__class__.__name__ == "McpSdkAdapter"
assert service.tool_executor is not None
```

Use a local config object rather than launching Playwright.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_server.py tests/wf_mcp/test_service.py tests/wf_mcp/test_stateful_runtime.py -q
uv run basedpyright --level error
```

Expected:

```text
passed
0 errors
```

## Task 8: Hide Or Delete Public Raw Call Tools

**Files:**

- Modify: `src/wf_mcp/admin_surface/tools.py`
- Modify: `src/wf_mcp/broker/service/builtins.py`
- Modify: `docs/wf_mcp_operator_manual.md`
- Modify: `docs/wf_mcp_troubleshooting.md`
- Test: `tests/wf_mcp/test_server.py`
- Test: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Remove planner visibility for `wf.mcp.call_tool`**

In `src/wf_mcp/broker/service/builtins.py`, remove `wf.mcp.call_tool` from
planner-visible built-in sources or mark its source visibility as:

```python
SourceVisibility(planner=False, mcp_client=False, admin_dashboard=True)
```

Prefer removal from planner-visible capability discovery. If kept, its
description must say:

```text
Debugging-only one-shot upstream MCP call. Not safe for stateful workflow steps.
```

- [ ] **Step 2: Hide `wf.admin.call_tool` in normal MCP tool lists**

In `src/wf_mcp/admin_surface/tools.py`, remove registration of `call_tool` or
guard it behind a future explicit debug flag.

If removing now breaks too many tests, first rename the tool description and
unpin it from search mode. It must not be a recommended workflow path.

- [ ] **Step 3: Update tests that expected broker raw call tools**

Tests likely to update:

- `tests/wf_mcp/test_broker_server.py`
- `tests/wf_mcp/test_server.py`
- `tests/wf_mcp/test_workflow_surface.py`

Replace expectations like:

```python
assert "call_broker_tool" in tool_names
```

with expectations for:

```python
assert "wf.workflow.call_capability" in tool_names
assert "wf.workflow.run_deployment" in tool_names
```

- [ ] **Step 4: Update docs**

In `docs/wf_mcp_operator_manual.md`, add:

```markdown
## Stateful MCP Servers

Stateful MCP servers, such as Playwright, should run through workflow
capabilities backed by the persistent MCP runtime. One-shot raw call helpers are
debugging-only and may not preserve upstream server state between calls.
```

In `docs/wf_mcp_troubleshooting.md`, add:

```markdown
If a browser workflow loses page state between steps, check whether it used a
raw call helper such as `wf.mcp.call_tool`. Use source-projected workflow
capabilities instead, and verify the service is using the persistent runtime
pool.
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp -q
uv run basedpyright --level error
```

Expected:

```text
passed
0 errors
```

## Task 9: Rename Broker Concepts In Docs Without Moving Code

**Files:**

- Modify: `docs/wf_mcp_architecture.md`
- Modify: `docs/wf_mcp_plan.md`
- Modify: `docs/project_map.md`

- [ ] **Step 1: Clarify package naming**

In `docs/wf_mcp_architecture.md`, replace the broker package row with:

```markdown
| `wf_mcp.broker` | Legacy-named service package. Currently coordinates sources, catalog snapshots, artifacts, deployments, and events. It should not grow new raw call behavior. Future cleanup should split this into service/discovery/catalog/runtime packages. |
```

- [ ] **Step 2: Mark broker raw-call language as historical**

In `docs/wf_mcp_plan.md`, wherever `call_broker_tool` is described as useful,
add:

```markdown
Historical note: raw broker call helpers were useful for early debugging, but
they are unsafe for stateful MCP servers because they can bypass the persistent
workflow runtime. New workflow authoring should use workflow capabilities and
deployments.
```

- [ ] **Step 3: Update project map**

In `docs/project_map.md`, describe:

```markdown
`WfMcpService` remains the central service today, but "broker" is a legacy name.
The runtime execution path should move to `wf_mcp.runtime`.
```

- [ ] **Step 4: Run docs grep**

Run:

```bash
rg -n "call_broker_tool|wf.mcp.call_tool|broker mode|raw call" docs
```

Expected:

Every remaining mention either:

- says historical/debugging-only, or
- points to the persistent runtime migration plan.

## Task 10: Rename `transparent_proxy` To `proxy`

**Files:**

- Move: `src/wf_mcp/transparent_proxy/admin.py` -> `src/wf_mcp/proxy/admin.py`
- Move: `src/wf_mcp/transparent_proxy/mounts.py` -> `src/wf_mcp/proxy/mounts.py`
- Move: `src/wf_mcp/transparent_proxy/runtime.py` -> `src/wf_mcp/proxy/runtime.py`
- Move: `src/wf_mcp/transparent_proxy/safe_names.py` -> `src/wf_mcp/proxy/safe_names.py`
- Move: `src/wf_mcp/transparent_proxy/tools.py` -> `src/wf_mcp/proxy/tools.py`
- Modify: `src/wf_mcp/server/core.py`
- Modify: `src/wf_mcp/cli.py`
- Modify: `docs/wf_mcp_architecture.md`
- Modify: tests under `tests/wf_mcp/`

- [ ] **Step 1: Move the package contents**

Create `src/wf_mcp/proxy/` and move the active implementation files:

```text
admin.py
mounts.py
runtime.py
safe_names.py
tools.py
```

Create `src/wf_mcp/proxy/__init__.py` exporting the runtime names currently
used by callers.

- [ ] **Step 2: Leave a temporary compatibility shim**

Replace `src/wf_mcp/transparent_proxy/__init__.py` with:

```python
from wf_mcp.proxy import *  # noqa: F403
```

Delete all other files from `src/wf_mcp/transparent_proxy/`.

This makes the old package visibly empty while giving downstream imports one
migration window.

- [ ] **Step 3: Update internal imports**

Replace internal imports of:

```text
wf_mcp.transparent_proxy
```

with:

```text
wf_mcp.proxy
```

Check with:

```bash
rg -n "transparent_proxy" src tests
```

Expected after this step:

```text
src/wf_mcp/transparent_proxy/__init__.py
```

is the only remaining source import location.

- [ ] **Step 4: Rename tests if practical**

Preferred rename:

```text
tests/wf_mcp/test_transparent_proxy.py -> tests/wf_mcp/test_proxy.py
```

If the file is too noisy, keep the filename for one pass but update test names
and imports first. The goal is no new test code using "transparent proxy" as the
current architecture term.

- [ ] **Step 5: Update docs**

In `docs/wf_mcp_architecture.md`, replace the package row with:

```markdown
| `wf_mcp.proxy` | Mount configured upstream MCP servers into the unified server. Owns proxy runtime, admin tools, safe tool-name transforms, and proxy inventory helpers. |
```

Add:

```markdown
`wf_mcp.transparent_proxy` is a compatibility shim only. Do not add new code
there.
```

- [ ] **Step 6: Run verification**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp -q
uv run basedpyright --level error
uvx ruff check src/wf_mcp tests/wf_mcp
```

Expected:

```text
passed
0 errors
ruff clean
```

## Task 11: Live Playwright Verification

**Files:**

- Modify if needed: `random shit/sonnet46-challenge-cont.md`
- No production code unless a focused bug is found.

- [ ] **Step 1: Restart `wf-mcp` with Playwright enabled**

Use config:

```json
{
  "id": "playwright.default",
  "server": "playwright",
  "account": "default",
  "enabled": true,
  "metadata": {
    "transport": "stdio",
    "command": "pnpx",
    "args": ["@playwright/mcp@latest"],
    "env": {}
  }
}
```

- [ ] **Step 2: Refresh catalog**

Call:

```text
wf.admin.refresh_connection_catalog(connection_id="playwright.default")
```

Expected:

`playwright.default.browser_navigate`, `playwright.default.browser_snapshot`,
and related browser tools appear in `wf.workflow.list_capabilities`.

- [ ] **Step 3: Run direct workflow deployment**

Run or rebuild a deployment using source-projected capabilities:

```text
playwright.default.browser_navigate
playwright.default.browser_snapshot
playwright.default.browser_click or browser_evaluate
playwright.default.browser_snapshot
```

Expected:

- Browser/page state persists across workflow steps.
- Snapshot tools receive `argument_keys: []` when no optional args are mapped.
- Workflow completes and output contains before/after snapshots.

- [ ] **Step 4: Record result**

Append to `random shit/sonnet46-challenge-cont.md`:

```markdown
## Persistent Runtime Retest

- Date:
- Config:
- Deployment:
- Result:
- Event trace summary:
- Remaining blocker:
```

## Migration Rule

Until this plan is implemented:

- Treat `wf.mcp.call_tool` as stateless/debugging-only.
- Prefer direct transparent proxy tools for manual upstream testing.
- Do not recommend broker raw calls for Playwright workflows.
- Do not delete `WfMcpService`; it still owns too much platform infrastructure.
- Do not add new code to `wf_mcp.transparent_proxy`; it should become a
  compatibility shim after the rename to `wf_mcp.proxy`.

After this plan is implemented:

- Generated workflow node specs should use persistent MCP runtime.
- Public raw call helpers should be hidden, removed, or clearly debug-only.
- `transparent_proxy/` should contain only a shim or be removed after one
  compatibility window.
- `broker/` can be renamed/split safely in a later structural cleanup.

## Verification Commands

Run after implementation:

```bash
uv run --with pytest pytest -q
uvx ruff check
uv run basedpyright --level error
```

Expected:

```text
all tests pass
ruff has no findings
basedpyright reports 0 errors
```

## Self-Review

Spec coverage:

- Explains stateless versus stateful MCP execution.
- Identifies why Playwright is broken.
- Keeps catalog/discovery separate from execution runtime.
- Avoids deleting `broker/` before its responsibilities move.
- Provides a deletion path for misleading raw `call_tool` surfaces.

Placeholder scan:

- No task depends on unspecified behavior.
- Every task names exact files and commands.

Risk:

- Production persistent MCP sessions need careful lifecycle handling on reload,
  config change, server shutdown, and upstream process crash.
- FastMCP proxy internals should not be reused for workflow runtime unless an
  official stable API exists.
