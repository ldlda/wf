# MCP SDK Adapter Package Move Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the concrete one-shot MCP SDK adapter from `wf_mcp.sdk.adapter` to canonical ownership in `wf_sources_mcp.sdk.adapter` while preserving old imports as compatibility shims.

**Architecture:** `wf_sources_mcp` owns MCP-as-upstream-source code: source DTOs, auth, catalog DTOs, SDK protocols/converters, session opener, persistent runtime, and now the concrete one-shot adapter. `wf_mcp` remains a compatibility/broker/frontend package and should re-export `McpSdkAdapter` without owning its implementation. This slice must not change runtime behavior or expand persistent sessions beyond tool calls.

**Tech Stack:** Python 3.14, MCP Python SDK, Pydantic, pytest/pytest-asyncio, ruff, basedpyright.

---

## File Structure

- Create `src/wf_sources_mcp/sdk/adapter.py`
  - Canonical `McpSdkAdapter` implementation.
  - Uses `wf_sources_mcp.client.open_mcp_session`.
  - Uses `wf_sources_mcp.sdk.converters`.
  - Imports no `wf_mcp` modules.
- Modify `src/wf_sources_mcp/sdk/__init__.py`
  - Export `McpSdkAdapter`.
- Replace `src/wf_mcp/sdk/adapter.py`
  - Compatibility shim re-exporting `McpSdkAdapter`.
- Modify `src/wf_mcp/sdk/__init__.py`
  - Import `McpSdkAdapter` from `wf_sources_mcp.sdk`.
- Modify production imports that construct real adapters:
  - `src/wf_mcp/broker/config.py`
  - `src/wf_mcp/broker/server.py`
  - `src/wf_mcp/server/core.py`
- Add canonical tests:
  - `tests/wf_sources_mcp/test_sdk_adapter.py`
- Extend compatibility/import tests:
  - `tests/wf_mcp/test_compat_imports.py`
  - `tests/wf_sources_mcp/test_import_direction_guard.py`
- Update docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

## Hard Boundaries

- Do not add persistent runtime support for `read_resource`, `get_prompt`, `invoke_method`, or `send_notification` in this slice.
- Do not change `BackendAdapter` method signatures.
- Do not change `McpSdkAdapter` behavior or output payloads.
- Do not remove old import paths.
- Do not modify generated MCP protocol models or frontend MCP tool schemas.
- Do not import `wf_mcp` from any `src/wf_sources_mcp/**` file.

---

### Task 1: Add Canonical Adapter Test

**Files:**
- Create: `tests/wf_sources_mcp/test_sdk_adapter.py`

- [ ] **Step 1: Create the canonical adapter test file**

Create `tests/wf_sources_mcp/test_sdk_adapter.py`:

```python
from __future__ import annotations

from typing import Any

import pytest
from mcp import ClientResult
from mcp.types import (
    CallToolResult,
    ClientNotification,
    ClientRequest,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    Prompt,
    Resource,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk import BackendAdapter, McpSdkAdapter
from wf_sources_mcp.transports import StdioSourceTransport


def _connection() -> McpSourceConnection:
    return McpSourceConnection(
        id="demo.personal",
        provider="demo",
        account="personal",
        transport=StdioSourceTransport(command="fake"),
    )


class _FakeSession:
    def __init__(self) -> None:
        self.notifications: list[ClientNotification] = []
        self.requests: list[ClientRequest] = []

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name="echo",
                    title="Echo",
                    description="Echo text.",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]
        )

    async def list_resources(self) -> ListResourcesResult:
        return ListResourcesResult(
            resources=[
                Resource(
                    uri=AnyUrl("fixture://docs/welcome"),
                    name="resource.welcome",
                    title="Welcome",
                    description="Welcome resource.",
                    mimeType="text/plain",
                )
            ]
        )

    async def list_prompts(self) -> ListPromptsResult:
        return ListPromptsResult(
            prompts=[
                Prompt(
                    name="prompt.summarize",
                    title="Summarize",
                    description="Summarize input.",
                    arguments=[],
                )
            ]
        )

    async def read_resource(self, uri: AnyUrl) -> Any:
        return type(
            "ReadResourceResult",
            (),
            {
                "model_dump": lambda _self, **_kwargs: {
                    "contents": [{"uri": str(uri), "text": "hello"}]
                }
            },
        )()

    async def get_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> Any:
        return type(
            "GetPromptResult",
            (),
            {
                "model_dump": lambda _self, **_kwargs: {
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": f"{prompt_name}:{arguments or {}}",
                            },
                        }
                    ]
                }
            },
        )()

    async def send_request(
        self,
        request: ClientRequest,
        result_type: type[ClientResult],
    ) -> Any:
        assert result_type is ClientResult
        self.requests.append(request)
        return type(
            "ClientResultModel",
            (),
            {"model_dump": lambda _self, **_kwargs: {"ok": True}},
        )()

    async def send_notification(self, notification: ClientNotification) -> None:
        self.notifications.append(notification)

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
    ) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text="ok")],
            structuredContent={"tool": tool_name, "payload": payload},
        )


class _SessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> _FakeSession:
        return self.session

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None


class _FakeAdapter(McpSdkAdapter):
    def __init__(self, session: _FakeSession) -> None:
        self.fake_session = session

    def _session(self, connection: McpSourceConnection, auth: object | None):
        assert connection.id == "demo.personal"
        assert auth is None
        return _SessionContext(self.fake_session)


def test_mcp_sdk_adapter_implements_backend_protocol() -> None:
    adapter: BackendAdapter = McpSdkAdapter()

    assert adapter.__class__.__name__ == "McpSdkAdapter"


@pytest.mark.asyncio
async def test_mcp_sdk_adapter_uses_session_for_all_backend_methods() -> None:
    session = _FakeSession()
    adapter = _FakeAdapter(session)
    connection = _connection()

    tools = await adapter.list_tools(connection, None)
    resources = await adapter.list_resources(connection, None)
    prompts = await adapter.list_prompts(connection, None)
    metadata = await adapter.get_connection_metadata(connection, None)
    resource_payload = await adapter.read_resource(
        connection,
        None,
        "fixture://docs/welcome",
    )
    prompt_payload = await adapter.get_prompt(
        connection,
        None,
        "prompt.summarize",
        {"text": "hello"},
    )
    method_payload = await adapter.invoke_method(
        connection,
        None,
        "fixture/ping",
        {"value": 1},
    )
    await adapter.send_notification(connection, None, "fixture/notify", {"ok": True})
    tool_result = await adapter.call_tool(connection, None, "echo", {"text": "hello"})

    assert tools[0].name == "echo"
    assert resources[0].uri == "fixture://docs/welcome"
    assert prompts[0].name == "prompt.summarize"
    assert metadata == {"server": "demo", "transport": "stdio"}
    assert resource_payload["contents"][0]["text"] == "hello"
    assert prompt_payload["messages"][0]["content"]["text"] == (
        "prompt.summarize:{'text': 'hello'}"
    )
    assert method_payload == {"ok": True}
    assert session.requests[0].method == "fixture/ping"
    assert session.notifications[0].method == "fixture/notify"
    assert tool_result.outcome == "ok"
    assert tool_result.output == {
        "tool": "echo",
        "payload": {"text": "hello"},
    }
```

- [ ] **Step 2: Run the canonical test and confirm it fails**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_sdk_adapter.py -q
```

Expected: fail with an import error because `wf_sources_mcp.sdk.McpSdkAdapter` does not exist yet.

---

### Task 2: Move Adapter Implementation to `wf_sources_mcp`

**Files:**
- Create: `src/wf_sources_mcp/sdk/adapter.py`
- Modify: `src/wf_sources_mcp/sdk/__init__.py`

- [ ] **Step 1: Create canonical adapter module**

Create `src/wf_sources_mcp/sdk/adapter.py` by moving the implementation from `src/wf_mcp/sdk/adapter.py`, adjusted to canonical imports:

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientResult
from mcp.types import (
    ClientNotification,
    ClientRequest,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
)
from pydantic import AnyUrl

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.client import open_mcp_session
from wf_sources_mcp.connections import McpSourceConnection

from .converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
)
from .protocols import BackendAdapter, ToolCallResult


class McpSdkAdapter(BackendAdapter):
    """One-shot MCP client adapter for upstream MCP source operations.

    This adapter intentionally opens a fresh SDK session per operation. Stateful
    workflow tool execution is handled by `wf_sources_mcp.runtime`; discovery
    and admin operations use this simpler one-shot path.
    """

    @asynccontextmanager
    async def _session(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ):
        async with open_mcp_session(connection, auth) as session:
            yield session

    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        async with self._session(connection, auth) as session:
            result: ListToolsResult = await session.list_tools()
            return [tool_to_discovered(tool) for tool in result.tools]

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        async with self._session(connection, auth) as session:
            result: ListResourcesResult = await session.list_resources()
            return [resource_to_discovered(resource) for resource in result.resources]

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        async with self._session(connection, auth) as session:
            result: ListPromptsResult = await session.list_prompts()
            return [prompt_to_discovered(prompt) for prompt in result.prompts]

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        transport = connection.transport
        return {
            "server": connection.provider,
            "transport": transport.kind if transport is not None else None,
        }

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        async with self._session(connection, auth) as session:
            result = await session.read_resource(AnyUrl(uri))
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        async with self._session(connection, auth) as session:
            result = await session.get_prompt(prompt_name, arguments)
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._session(connection, auth) as session:
            result = await session.send_request(
                ClientRequest.model_validate({"method": method, "params": params}),
                ClientResult,
            )
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        async with self._session(connection, auth) as session:
            await session.send_notification(
                ClientNotification.model_validate({"method": method, "params": params})
            )

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        async with self._session(connection, auth) as session:
            result = await session.call_tool(tool_name, payload)
            return tool_result_to_call_result(result)


__all__ = ["McpSdkAdapter"]
```

- [ ] **Step 2: Export adapter from package root**

Modify `src/wf_sources_mcp/sdk/__init__.py`:

```python
from __future__ import annotations

from .adapter import McpSdkAdapter
from .converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
    workflow_output_schema_from_mcp_tool_schema,
)
from .protocols import BackendAdapter, ToolCallResult, ToolExecutor

__all__ = [
    "BackendAdapter",
    "McpSdkAdapter",
    "ToolCallResult",
    "ToolExecutor",
    "prompt_to_discovered",
    "resource_to_discovered",
    "tool_result_to_call_result",
    "tool_to_discovered",
    "workflow_output_schema_from_mcp_tool_schema",
]
```

- [ ] **Step 3: Run canonical adapter test**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_sdk_adapter.py -q
```

Expected: pass.

---

### Task 3: Turn Old Adapter Module Into Shim

**Files:**
- Modify: `src/wf_mcp/sdk/adapter.py`
- Modify: `src/wf_mcp/sdk/__init__.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Replace old adapter module with shim**

Replace `src/wf_mcp/sdk/adapter.py` with:

```python
"""Compatibility shim for the canonical MCP SDK adapter."""

from wf_sources_mcp.sdk.adapter import McpSdkAdapter

__all__ = ["McpSdkAdapter"]
```

- [ ] **Step 2: Update old SDK package exports**

Replace `src/wf_mcp/sdk/__init__.py` with:

```python
from wf_sources_mcp.sdk import BackendAdapter, McpSdkAdapter, ToolCallResult

__all__ = ["BackendAdapter", "McpSdkAdapter", "ToolCallResult"]
```

- [ ] **Step 3: Add shim identity test**

Append to `tests/wf_mcp/test_compat_imports.py`:

```python

def test_wf_mcp_sdk_adapter_shim_reexports_wf_sources_mcp_adapter() -> None:
    from wf_mcp.sdk import McpSdkAdapter as CompatPackageAdapter
    from wf_mcp.sdk.adapter import McpSdkAdapter as CompatModuleAdapter
    from wf_sources_mcp.sdk import McpSdkAdapter
    from wf_sources_mcp.sdk.adapter import McpSdkAdapter as CanonicalModuleAdapter

    assert CompatPackageAdapter is McpSdkAdapter
    assert CompatModuleAdapter is McpSdkAdapter
    assert CanonicalModuleAdapter is McpSdkAdapter
```

- [ ] **Step 4: Run compatibility tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py -q
```

Expected: pass.

---

### Task 4: Update Production Construction Imports

**Files:**
- Modify: `src/wf_mcp/broker/config.py`
- Modify: `src/wf_mcp/broker/server.py`
- Modify: `src/wf_mcp/server/core.py`

- [ ] **Step 1: Update broker config import**

In `src/wf_mcp/broker/config.py`, replace:

```python
from ..sdk import McpSdkAdapter
```

with:

```python
from wf_sources_mcp.sdk import McpSdkAdapter
```

- [ ] **Step 2: Update broker server import**

In `src/wf_mcp/broker/server.py`, replace:

```python
from ..sdk.adapter import McpSdkAdapter
```

with:

```python
from wf_sources_mcp.sdk import McpSdkAdapter
```

- [ ] **Step 3: Update legacy server core import**

In `src/wf_mcp/server/core.py`, replace:

```python
from ..sdk import McpSdkAdapter
```

with:

```python
from wf_sources_mcp.sdk import McpSdkAdapter
```

- [ ] **Step 4: Run focused construction tests**

Run:

```bash
uv run pytest tests/wf_mcp/server/test_config.py tests/wf_mcp/test_broker_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
```

Expected: pass.

---

### Task 5: Strengthen Import Direction Guard

**Files:**
- Modify: `tests/wf_sources_mcp/test_import_direction_guard.py`

- [ ] **Step 1: Add old adapter module to forbidden imports**

In `test_wf_sources_mcp_does_not_import_old_sdk_protocol_modules`, extend the `forbidden` set:

```python
    forbidden = {
        "wf_mcp.sdk",
        "wf_mcp.sdk.adapter",
        "wf_mcp.sdk.base",
        "wf_mcp.runtime",
        "wf_mcp.runtime.protocols",
    }
```

- [ ] **Step 2: Run import direction tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_import_direction_guard.py -q
```

Expected: pass.

---

### Task 6: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move after completion: `docs/superpowers/plans/2026-06-07-mcp-sdk-adapter-package-move.md` to `docs/historical/superpowers/plans/2026-06-07-mcp-sdk-adapter-package-move.md`

- [ ] **Step 1: Update roadmap status**

In `docs/current_roadmap.md`, under the MCP upstream source runtime cleanup bullets near the existing runtime move status, add:

```markdown
   - Completed: one-shot MCP SDK adapter moved to `wf_sources_mcp.sdk.adapter`.
     `McpSdkAdapter` is now canonical in `wf_sources_mcp`; `wf_mcp.sdk.*`
     remains a compatibility shim for old imports. Persistent runtime is still
     tool-call-only.
```

- [ ] **Step 2: Update long-lived API boundary status**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, in the numbered `wf_sources_mcp` implementation status list after item 7, add:

```markdown
8. Complete: one-shot MCP SDK adapter moved to
   `wf_sources_mcp.sdk.adapter`, with `wf_mcp.sdk.adapter` retained as a
   compatibility shim. This does not expand persistent runtime; the next
   design slice should unify one-shot and persistent client operation handling
   behind a shared source-client facade.
```

- [ ] **Step 3: Archive completed plan after implementation**

Run only after all code/tests pass:

```bash
git mv docs/superpowers/plans/2026-06-07-mcp-sdk-adapter-package-move.md docs/historical/superpowers/plans/2026-06-07-mcp-sdk-adapter-package-move.md
```

---

### Task 7: Final Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/test_compat_imports.py tests/wf_mcp/server/test_config.py tests/wf_mcp/test_broker_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
```

Expected: pass. If a live stdio/server test is skipped because the environment blocks subprocess MCP transports, report the skip exactly.

- [ ] **Step 2: Run source typecheck**

Run:

```bash
uv run basedpyright --level error src
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 3: Run focused lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp src/wf_mcp/sdk src/wf_mcp/broker/config.py src/wf_mcp/broker/server.py src/wf_mcp/server/core.py tests/wf_sources_mcp/test_sdk_adapter.py tests/wf_mcp/test_compat_imports.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Check old canonical imports**

Run:

```bash
rg -n "from wf_mcp\.sdk\.adapter|from wf_mcp\.sdk import McpSdkAdapter|import wf_mcp\.sdk" src tests
```

Expected: only compatibility tests or intentionally old-public-path tests should remain. Production construction paths should import from `wf_sources_mcp.sdk`.

- [ ] **Step 5: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings are acceptable on Windows.

---

## Self-Review

- Spec coverage: This plan moves canonical `McpSdkAdapter` ownership to `wf_sources_mcp`, preserves compatibility shims, updates production constructors, strengthens import guards, and updates docs.
- Placeholder scan: No placeholder steps remain. All code edits include concrete snippets.
- Type consistency: All adapter signatures use current `BackendAdapter` types: `McpSourceConnection`, `AuthRecord | None`, `ToolCallResult`.
- Intentional non-goal: persistent runtime remains tool-call-only. Shared one-shot/persistent client-operation facade is a future design slice, not part of this move.
