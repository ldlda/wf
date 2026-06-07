# MCP Source Client Facade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a shared `McpSourceClient` facade around MCP SDK `ClientSession` operations, then make the one-shot `McpSdkAdapter` delegate to it without changing behavior.

**Architecture:** `open_mcp_session()` still owns transport opening and initialization. `McpSourceClient` owns MCP operation calls plus conversion/serialization from SDK models into workflow/source-provider DTOs. `McpSdkAdapter` remains one-shot but stops handling raw `ClientSession` operations directly; persistent runtime expansion is explicitly deferred.

**Tech Stack:** Python 3.14, MCP Python SDK, Pydantic, pytest/pytest-asyncio, ruff, basedpyright.

---

## File Structure

- Create `src/wf_sources_mcp/client/source_client.py`
  - `McpSourceClient` dataclass wrapping `ClientSession` and `McpSourceConnection`.
  - Methods mirror `BackendAdapter` operations except they do not accept `connection`/`auth`.
  - Converts tools/resources/prompts/tool results and serializes resource/prompt/raw method payloads.
- Modify `src/wf_sources_mcp/client/__init__.py`
  - Export `McpSourceClient`.
- Modify `src/wf_sources_mcp/sdk/adapter.py`
  - `_session()` becomes `_client()` and yields `McpSourceClient`.
  - Public methods delegate to client methods.
- Add `tests/wf_sources_mcp/test_source_client.py`
  - Direct facade tests for all operation families.
- Modify `tests/wf_sources_mcp/test_sdk_adapter.py`
  - Keep adapter tests; adjust only if needed for `_client()` naming.
- Update docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

## Hard Boundaries

- Do not change `BackendAdapter` signatures.
- Do not change `McpSdkAdapter` output shapes.
- Do not expand `PersistentMcpSession` beyond `call_tool` in this slice.
- Do not change `open_mcp_session()` transport behavior.
- Do not import `wf_mcp` from `src/wf_sources_mcp/**`.
- Do not manually call `__aexit__`; context-manager ownership stays with `async with`.

---

### Task 1: Add Direct Facade Tests

**Files:**
- Create: `tests/wf_sources_mcp/test_source_client.py`

- [ ] **Step 1: Create tests for the facade behavior**

Create `tests/wf_sources_mcp/test_source_client.py`:

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

from wf_sources_mcp.client import McpSourceClient
from wf_sources_mcp.connections import McpSourceConnection
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
        self.requests: list[ClientRequest] = []
        self.notifications: list[ClientNotification] = []

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


@pytest.mark.asyncio
async def test_source_client_lists_catalog_items_and_metadata() -> None:
    source_client = McpSourceClient(session=_FakeSession(), connection=_connection())

    tools = await source_client.list_tools()
    resources = await source_client.list_resources()
    prompts = await source_client.list_prompts()
    metadata = await source_client.get_connection_metadata()

    assert tools[0].name == "echo"
    assert resources[0].uri == "fixture://docs/welcome"
    assert prompts[0].name == "prompt.summarize"
    assert metadata == {"server": "demo", "transport": "stdio"}


@pytest.mark.asyncio
async def test_source_client_reads_resources_and_prompts_as_payloads() -> None:
    source_client = McpSourceClient(session=_FakeSession(), connection=_connection())

    resource_payload = await source_client.read_resource("fixture://docs/welcome")
    prompt_payload = await source_client.get_prompt(
        "prompt.summarize",
        {"text": "hello"},
    )

    assert resource_payload["contents"][0]["text"] == "hello"
    assert prompt_payload["messages"][0]["content"]["text"] == (
        "prompt.summarize:{'text': 'hello'}"
    )


@pytest.mark.asyncio
async def test_source_client_invokes_methods_and_notifications() -> None:
    session = _FakeSession()
    source_client = McpSourceClient(session=session, connection=_connection())

    result = await source_client.invoke_method("ping")
    await source_client.send_notification("notifications/initialized")

    assert result == {"ok": True}
    assert session.requests, "invoke_method should send a request"
    assert session.notifications, "send_notification should send a notification"


@pytest.mark.asyncio
async def test_source_client_call_tool_normalizes_result() -> None:
    source_client = McpSourceClient(session=_FakeSession(), connection=_connection())

    result = await source_client.call_tool("echo", {"text": "hello"})

    assert result.outcome == "ok"
    assert result.output == {
        "tool": "echo",
        "payload": {"text": "hello"},
    }
```

- [ ] **Step 2: Run tests to confirm missing class**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_source_client.py -q
```

Expected: fail with import error for `McpSourceClient`.

---

### Task 2: Implement `McpSourceClient`

**Files:**
- Create: `src/wf_sources_mcp/client/source_client.py`
- Modify: `src/wf_sources_mcp/client/__init__.py`

- [ ] **Step 1: Add the facade implementation**

Create `src/wf_sources_mcp/client/source_client.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp import ClientResult
from mcp.client.session import ClientSession
from mcp.types import (
    ClientNotification,
    ClientRequest,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
)
from pydantic import AnyUrl

from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.sdk.converters import (
    prompt_to_discovered,
    resource_to_discovered,
    tool_result_to_call_result,
    tool_to_discovered,
)
from wf_sources_mcp.sdk.protocols import ToolCallResult


@dataclass(slots=True)
class McpSourceClient:
    """Operation facade over an initialized MCP SDK ClientSession.

    This class owns SDK operation calls and conversion to wf_sources_mcp DTOs.
    It does not own transport lifetime. One-shot callers enter it through
    `open_mcp_session`; persistent runtime owners may wrap the session inside
    their owner task in a later slice.
    """

    session: ClientSession
    connection: McpSourceConnection

    async def list_tools(self) -> list[DiscoveredTool]:
        result: ListToolsResult = await self.session.list_tools()
        return [tool_to_discovered(tool) for tool in result.tools]

    async def list_resources(self) -> list[DiscoveredResource]:
        result: ListResourcesResult = await self.session.list_resources()
        return [resource_to_discovered(resource) for resource in result.resources]

    async def list_prompts(self) -> list[DiscoveredPrompt]:
        result: ListPromptsResult = await self.session.list_prompts()
        return [prompt_to_discovered(prompt) for prompt in result.prompts]

    async def get_connection_metadata(self) -> dict[str, Any]:
        transport = self.connection.transport
        return {
            "server": self.connection.provider,
            "transport": transport.kind if transport is not None else None,
        }

    async def read_resource(self, uri: str) -> dict[str, Any]:
        result = await self.session.read_resource(AnyUrl(uri))
        return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def get_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        result = await self.session.get_prompt(prompt_name, arguments)
        return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def invoke_method(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = await self.session.send_request(
            ClientRequest.model_validate({"method": method, "params": params}),
            ClientResult,
        )
        return result.model_dump(by_alias=True, mode="json", exclude_none=True)

    async def send_notification(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        await self.session.send_notification(
            ClientNotification.model_validate({"method": method, "params": params})
        )

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        result = await self.session.call_tool(tool_name, payload)
        return tool_result_to_call_result(result)


__all__ = ["McpSourceClient"]
```

- [ ] **Step 2: Export the facade from the client package**

Modify `src/wf_sources_mcp/client/__init__.py`:

```python
"""MCP source client helpers."""

from .source_client import McpSourceClient
from .transport import open_mcp_session

__all__ = ["McpSourceClient", "open_mcp_session"]
```

- [ ] **Step 3: Run direct facade tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_source_client.py -q
```

Expected: pass.

---

### Task 3: Delegate `McpSdkAdapter` to the Facade

**Files:**
- Modify: `src/wf_sources_mcp/sdk/adapter.py`
- Test: `tests/wf_sources_mcp/test_sdk_adapter.py`

- [ ] **Step 1: Replace raw session operation logic in adapter**

Replace `src/wf_sources_mcp/sdk/adapter.py` with:

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource, DiscoveredTool
from wf_sources_mcp.client import McpSourceClient, open_mcp_session
from wf_sources_mcp.connections import McpSourceConnection

from .protocols import BackendAdapter, ToolCallResult


class McpSdkAdapter(BackendAdapter):
    """One-shot MCP client adapter for upstream MCP source operations.

    This adapter intentionally opens a fresh SDK session per operation. It
    delegates all MCP operation/conversion details to `McpSourceClient` so the
    same operation facade can later be used inside persistent runtime owners.
    """

    @asynccontextmanager
    async def _client(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> AsyncIterator[McpSourceClient]:
        async with open_mcp_session(connection, auth) as session:
            yield McpSourceClient(session=session, connection=connection)

    async def list_tools(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        async with self._client(connection, auth) as client:
            return await client.list_tools()

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        async with self._client(connection, auth) as client:
            return await client.list_resources()

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        async with self._client(connection, auth) as client:
            return await client.list_prompts()

    async def get_connection_metadata(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> dict[str, Any]:
        async with self._client(connection, auth) as client:
            return await client.get_connection_metadata()

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        async with self._client(connection, auth) as client:
            return await client.read_resource(uri)

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        async with self._client(connection, auth) as client:
            return await client.get_prompt(prompt_name, arguments)

    async def invoke_method(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self._client(connection, auth) as client:
            return await client.invoke_method(method, params)

    async def send_notification(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        async with self._client(connection, auth) as client:
            await client.send_notification(method, params)

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        async with self._client(connection, auth) as client:
            return await client.call_tool(tool_name, payload)


__all__ = ["McpSdkAdapter"]
```

- [ ] **Step 2: Update adapter test fake hook name**

In `tests/wf_sources_mcp/test_sdk_adapter.py`, if the fake subclass overrides `_session`, change it to override `_client` instead:

```python
class _ClientContext:
    def __init__(self, client: McpSourceClient) -> None:
        self.client = client

    async def __aenter__(self) -> McpSourceClient:
        return self.client

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

    def _client(self, connection: McpSourceConnection, auth: object | None):
        assert connection.id == "demo.personal"
        assert auth is None
        return _ClientContext(
            McpSourceClient(session=self.fake_session, connection=connection)
        )
```

Also add this import near the top of the file:

```python
from wf_sources_mcp.client import McpSourceClient
```

- [ ] **Step 3: Run adapter and facade tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_source_client.py tests/wf_sources_mcp/test_sdk_adapter.py -q
```

Expected: pass.

---

### Task 4: Verify Persistent Runtime Is Not Expanded

**Files:**
- Modify only if needed: `src/wf_sources_mcp/runtime/session.py`
- Test: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Inspect runtime session remains tool-call-only**

Run:

```bash
rg -n "def (list_tools|list_resources|list_prompts|read_resource|get_prompt|invoke_method|send_notification)" src/wf_sources_mcp/runtime
```

Expected: no matches.

- [ ] **Step 2: Add or preserve code seam comment if needed**

If `src/wf_sources_mcp/runtime/session.py` does not already make the boundary clear, update the class docstring to include:

```python
    """Long-lived MCP execution handle for one configured connection.

    Production sessions use `call_callback` because MCP transports are entered
    inside an AnyIO cancel scope and must be called and closed by that same
    owner task. `client` remains available for simple injected/fake sessions in
    tests. `call_tool()` always normalizes SDK results for workflow nodes.

    This runtime intentionally exposes only tool calls for now. Shared
    non-tool operations live on `McpSourceClient`; routing them through the
    owner task is a separate runtime-expansion slice.
    """
```

- [ ] **Step 3: Run runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py tests/wf_mcp/test_stateful_runtime.py -q
```

Expected: pass.

---

### Task 5: Update Docs

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move after completion: `docs/superpowers/plans/2026-06-07-mcp-source-client-facade.md` to `docs/historical/superpowers/plans/2026-06-07-mcp-source-client-facade.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the MCP upstream source runtime cleanup bullets, add:

```markdown
   - Completed: shared `McpSourceClient` facade introduced in
     `wf_sources_mcp.client`. The one-shot SDK adapter delegates MCP operation
     calls and conversion through the facade; persistent runtime remains
     tool-call-only until a separate owner-task routing slice.
```

- [ ] **Step 2: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, in the numbered `wf_sources_mcp` implementation status list after the adapter move item, add:

```markdown
9. Complete: shared `McpSourceClient` facade introduced in
   `wf_sources_mcp.client`. `McpSdkAdapter` now delegates operation handling to
   this facade. Persistent runtime still exposes only `call_tool`; expanding it
   requires a separate owner-task request routing slice.
```

- [ ] **Step 3: Archive completed plan after implementation**

Run only after all code/tests pass:

```bash
git mv docs/superpowers/plans/2026-06-07-mcp-source-client-facade.md docs/historical/superpowers/plans/2026-06-07-mcp-source-client-facade.md
```

---

### Task 6: Final Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/test_compat_imports.py -q
```

Expected: pass. Report any environment-based skips exactly.

- [ ] **Step 2: Run source typecheck**

Run:

```bash
uv run basedpyright --level error src
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 3: Run focused lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp tests/wf_sources_mcp/test_source_client.py tests/wf_sources_mcp/test_sdk_adapter.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Check runtime non-expansion**

Run:

```bash
rg -n "def (list_tools|list_resources|list_prompts|read_resource|get_prompt|invoke_method|send_notification)" src/wf_sources_mcp/runtime
```

Expected: no matches.

- [ ] **Step 5: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings are acceptable on Windows.

---

## Self-Review

- Spec coverage: The plan creates the shared source-client facade, delegates one-shot adapter operations to it, preserves old runtime behavior, and documents the boundary.
- Placeholder scan: No placeholder steps remain. All code edits include concrete snippets.
- Type consistency: `McpSourceClient` wraps `ClientSession` plus `McpSourceConnection`; adapter public methods keep `BackendAdapter` signatures.
- Intentional non-goal: persistent runtime does not gain non-tool operations in this slice.

