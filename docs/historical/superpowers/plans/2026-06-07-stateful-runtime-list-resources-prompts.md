# Stateful Runtime List Resources Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the stateful MCP runtime's safe client surface by adding persistent `list_resources()` and `list_prompts()`, and split runtime protocols into tool/resource/prompt slices.

**Architecture:** `McpSourceClient` already wraps initialized MCP client operations for tools, resources, and prompts. `McpRuntimePool` should be able to route the same safe resource/prompt listing operations through its owner-task queue so session-scoped listings can observe runtime state. Protocols should describe the slices explicitly: tool execution, resource operations, prompt operations, and their combined stateful runtime.

**Tech Stack:** Python 3.14, MCP Python SDK, pytest/pytest-asyncio, ruff, basedpyright.

---

## File Structure

- Modify `src/wf_sources_mcp/sdk/protocols.py`
  - Add `ToolRuntime`, `ResourceRuntime`, `PromptRuntime`.
  - Make `StatefulMcpRuntime(ToolRuntime, ResourceRuntime, PromptRuntime, Protocol)`.
  - Keep `ToolExecutor` as a compatibility alias/subprotocol for workflow node execution.
- Modify `src/wf_sources_mcp/sdk/__init__.py`
  - Export new protocol slices.
- Modify compatibility shims:
  - `src/wf_mcp/sdk/base.py`
  - `src/wf_mcp/sdk/__init__.py`
- Modify runtime:
  - `src/wf_sources_mcp/runtime/session.py`
  - `src/wf_sources_mcp/runtime/factory.py`
  - `src/wf_sources_mcp/runtime/pool.py`
- Modify tests:
  - `tests/wf_sources_mcp/test_sdk_protocols.py`
  - `tests/wf_sources_mcp/test_runtime.py`
  - `tests/wf_mcp/test_compat_imports.py`
- Update docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

## Hard Boundaries

- Do not add raw `invoke_method` or `send_notification`.
- Do not add runtime `list_tools` in this slice.
- Do not use runtime `isinstance` checks or `@runtime_checkable` protocols.
- Do not route catalog refresh/discovery through stateful runtime in this slice.
- Do not assume resource/prompt listings are stateless; these new methods exist because they can be session-scoped.

---

### Task 1: Split Protocol Slices

**Files:**
- Modify: `src/wf_sources_mcp/sdk/protocols.py`
- Modify: `src/wf_sources_mcp/sdk/__init__.py`
- Modify: `tests/wf_sources_mcp/test_sdk_protocols.py`

- [ ] **Step 1: Add protocol shape tests**

Append to `tests/wf_sources_mcp/test_sdk_protocols.py`:

```python
def test_stateful_runtime_protocol_slices_export() -> None:
    from wf_sources_mcp.sdk import (
        PromptRuntime,
        ResourceRuntime,
        StatefulMcpRuntime,
        ToolExecutor,
        ToolRuntime,
    )

    assert ToolRuntime.__name__ == "ToolRuntime"
    assert ResourceRuntime.__name__ == "ResourceRuntime"
    assert PromptRuntime.__name__ == "PromptRuntime"
    assert ToolExecutor.__name__ == "ToolExecutor"
    assert StatefulMcpRuntime.__name__ == "StatefulMcpRuntime"
```

- [ ] **Step 2: Add protocol slices**

In `src/wf_sources_mcp/sdk/protocols.py`, replace the current `ToolExecutor` / `StatefulMcpRuntime` section with:

```python
class ToolRuntime(Protocol):
    """Runtime boundary for executing MCP tools from workflow nodes."""

    async def call_tool(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        tool_name: str,
        payload: dict[str, Any],
    ) -> ToolCallResult: ...


class ToolExecutor(ToolRuntime, Protocol):
    """Compatibility name for workflow-node tool execution."""


class ResourceRuntime(Protocol):
    """Stateful resource operations for configured MCP sources."""

    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]: ...

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]: ...


class PromptRuntime(Protocol):
    """Stateful prompt operations for configured MCP sources."""

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]: ...

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...


class StatefulMcpRuntime(ToolRuntime, ResourceRuntime, PromptRuntime, Protocol):
    """Stateful execution/read/list boundary for configured MCP sources.

    Implementations keep source session state across calls. Catalog refresh may
    still use one-shot adapters by policy.
    """
```

Update `__all__`:

```python
__all__ = [
    "BackendAdapter",
    "PromptRuntime",
    "ResourceRuntime",
    "StatefulMcpRuntime",
    "ToolCallResult",
    "ToolExecutor",
    "ToolRuntime",
]
```

- [ ] **Step 3: Export slices from package root**

In `src/wf_sources_mcp/sdk/__init__.py`, import/export the new symbols:

```python
from .protocols import (
    BackendAdapter,
    PromptRuntime,
    ResourceRuntime,
    StatefulMcpRuntime,
    ToolCallResult,
    ToolExecutor,
    ToolRuntime,
)
```

Include `"PromptRuntime"`, `"ResourceRuntime"`, and `"ToolRuntime"` in `__all__`.

- [ ] **Step 4: Run protocol tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_sdk_protocols.py -q
```

Expected: pass.

---

### Task 2: Preserve Compatibility Exports

**Files:**
- Modify: `src/wf_mcp/sdk/base.py`
- Modify: `src/wf_mcp/sdk/__init__.py`
- Modify: `tests/wf_mcp/test_compat_imports.py`

- [ ] **Step 1: Update compatibility shims**

In `src/wf_mcp/sdk/base.py`, re-export all protocol slices:

```python
from wf_sources_mcp.sdk import (
    BackendAdapter,
    PromptRuntime,
    ResourceRuntime,
    StatefulMcpRuntime,
    ToolCallResult,
    ToolRuntime,
)

__all__ = [
    "BackendAdapter",
    "PromptRuntime",
    "ResourceRuntime",
    "StatefulMcpRuntime",
    "ToolCallResult",
    "ToolRuntime",
]
```

In `src/wf_mcp/sdk/__init__.py`, update imports/exports similarly while keeping `McpSdkAdapter`:

```python
from wf_sources_mcp.sdk import (
    BackendAdapter,
    McpSdkAdapter,
    PromptRuntime,
    ResourceRuntime,
    StatefulMcpRuntime,
    ToolCallResult,
    ToolRuntime,
)

__all__ = [
    "BackendAdapter",
    "McpSdkAdapter",
    "PromptRuntime",
    "ResourceRuntime",
    "StatefulMcpRuntime",
    "ToolCallResult",
    "ToolRuntime",
]
```

- [ ] **Step 2: Extend compatibility test**

In `tests/wf_mcp/test_compat_imports.py`, extend `test_wf_mcp_sdk_protocol_shims_reexport_wf_sources_mcp_sdk`:

```python
    from wf_mcp.sdk import PromptRuntime as CompatPromptRuntime
    from wf_mcp.sdk import ResourceRuntime as CompatResourceRuntime
    from wf_mcp.sdk import ToolRuntime as CompatToolRuntime
    from wf_mcp.sdk.base import PromptRuntime as CompatBasePromptRuntime
    from wf_mcp.sdk.base import ResourceRuntime as CompatBaseResourceRuntime
    from wf_mcp.sdk.base import ToolRuntime as CompatBaseToolRuntime
    from wf_sources_mcp.sdk import PromptRuntime, ResourceRuntime, ToolRuntime

    assert CompatPromptRuntime is PromptRuntime
    assert CompatResourceRuntime is ResourceRuntime
    assert CompatToolRuntime is ToolRuntime
    assert CompatBasePromptRuntime is PromptRuntime
    assert CompatBaseResourceRuntime is ResourceRuntime
    assert CompatBaseToolRuntime is ToolRuntime
```

- [ ] **Step 3: Run compatibility test**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py -q
```

Expected: pass.

---

### Task 3: Add Persistent Resource/Prompt Listing Methods

**Files:**
- Modify: `src/wf_sources_mcp/runtime/session.py`
- Modify: `src/wf_sources_mcp/runtime/factory.py`
- Modify: `src/wf_sources_mcp/runtime/pool.py`
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Extend fake client with list methods**

In `tests/wf_sources_mcp/test_runtime.py`, add imports:

```python
from mcp.types import ListPromptsResult, ListResourcesResult, Prompt, Resource
```

Update `_FakeClient` inside `_FakeFactory._create_with_stack()`:

```python
            async def list_resources(self) -> ListResourcesResult:
                return ListResourcesResult(
                    resources=[
                        Resource(
                            uri=AnyUrl("fixture://docs/runtime"),
                            name="resource.runtime",
                            title="Runtime Resource",
                            description="Runtime-scoped resource.",
                            mimeType="text/plain",
                        )
                    ]
                )

            async def list_prompts(self) -> ListPromptsResult:
                return ListPromptsResult(
                    prompts=[
                        Prompt(
                            name="prompt.runtime",
                            title="Runtime Prompt",
                            description="Runtime-scoped prompt.",
                            arguments=[],
                        )
                    ]
                )
```

- [ ] **Step 2: Add runtime tests**

Append to `tests/wf_sources_mcp/test_runtime.py`:

```python
@pytest.mark.asyncio
async def test_persistent_session_factory_routes_resource_and_prompt_lists() -> None:
    factory = _FakeFactory()
    session = await factory.create(_connection(), None)

    resources = await session.list_resources()
    prompts = await session.list_prompts()
    await session.close()

    assert resources[0].name == "resource.runtime"
    assert resources[0].uri == "fixture://docs/runtime"
    assert prompts[0].name == "prompt.runtime"


@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_resource_and_prompt_lists() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    resources = await pool.list_resources(connection, None)
    prompts = await pool.list_prompts(connection, None)
    await pool.close_all()

    assert resources[0].name == "resource.runtime"
    assert prompts[0].name == "prompt.runtime"
    assert factory.created_connections == [connection]
```

Update public surface test:

```python
    assert "list_resources" in public_operations
    assert "list_prompts" in public_operations
    assert "invoke_method" not in public_operations
    assert "send_notification" not in public_operations
```

- [ ] **Step 3: Add session callback types and methods**

In `src/wf_sources_mcp/runtime/session.py`, import DTOs:

```python
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource
```

Add callback types:

```python
RawResourceLister = Callable[[], Awaitable[list[DiscoveredResource]]]
RawPromptLister = Callable[[], Awaitable[list[DiscoveredPrompt]]]
```

Add fields:

```python
    list_resources_callback: RawResourceLister | None = None
    list_prompts_callback: RawPromptLister | None = None
```

Add methods:

```python
    async def list_resources(self) -> list[DiscoveredResource]:
        """List MCP resources through the owner task or injected session."""
        if self.list_resources_callback is not None:
            return await self.list_resources_callback()
        if self.client is not None:
            from wf_sources_mcp.sdk.converters import resource_to_discovered

            result = await self.client.list_resources()
            return [resource_to_discovered(resource) for resource in result.resources]
        raise RuntimeError("persistent MCP session has no resource list transport")

    async def list_prompts(self) -> list[DiscoveredPrompt]:
        """List MCP prompts through the owner task or injected session."""
        if self.list_prompts_callback is not None:
            return await self.list_prompts_callback()
        if self.client is not None:
            from wf_sources_mcp.sdk.converters import prompt_to_discovered

            result = await self.client.list_prompts()
            return [prompt_to_discovered(prompt) for prompt in result.prompts]
        raise RuntimeError("persistent MCP session has no prompt list transport")
```

- [ ] **Step 4: Wire owner methods**

In `src/wf_sources_mcp/runtime/factory.py`, add callbacks in `PersistentSessionFactory.create()`:

```python
            list_resources_callback=owner.list_resources,
            list_prompts_callback=owner.list_prompts,
```

Add owner methods:

```python
    async def list_resources(self) -> list[DiscoveredResource]:
        """Submit resource listing through the generic owner-task operation queue."""
        return await self.submit(
            operation="list_resources",
            run=lambda client: client.list_resources(),
        )

    async def list_prompts(self) -> list[DiscoveredPrompt]:
        """Submit prompt listing through the generic owner-task operation queue."""
        return await self.submit(
            operation="list_prompts",
            run=lambda client: client.list_prompts(),
        )
```

Import DTOs:

```python
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource
```

- [ ] **Step 5: Add pool methods**

In `src/wf_sources_mcp/runtime/pool.py`, import DTOs:

```python
from wf_sources_mcp.catalog import DiscoveredPrompt, DiscoveredResource
```

Add below `get_prompt()`:

```python
    async def list_resources(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredResource]:
        session = await self.get_session(connection, auth)
        return await session.list_resources()

    async def list_prompts(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
    ) -> list[DiscoveredPrompt]:
        session = await self.get_session(connection, auth)
        return await session.list_prompts()
```

- [ ] **Step 6: Run runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: pass.

---

### Task 4: Static Protocol Conformance Tests

**Files:**
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Add assignment-based type conformance test**

Append:

```python
def test_runtime_pool_satisfies_stateful_protocol_static_shape() -> None:
    from wf_sources_mcp.sdk import (
        PromptRuntime,
        ResourceRuntime,
        StatefulMcpRuntime,
        ToolRuntime,
    )

    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)

    tool_runtime: ToolRuntime = pool
    resource_runtime: ResourceRuntime = pool
    prompt_runtime: PromptRuntime = pool
    stateful_runtime: StatefulMcpRuntime = pool

    assert tool_runtime is pool
    assert resource_runtime is pool
    assert prompt_runtime is pool
    assert stateful_runtime is pool
```

This is a static typecheck target. Do not add `isinstance` runtime checks.

- [ ] **Step 2: Run focused typecheck**

Run:

```bash
uv run basedpyright --level error tests/wf_sources_mcp/test_runtime.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

---

### Task 5: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move after completion: `docs/superpowers/plans/2026-06-07-stateful-runtime-list-resources-prompts.md` to `docs/historical/superpowers/plans/2026-06-07-stateful-runtime-list-resources-prompts.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the MCP upstream source runtime cleanup bullets, add:

```markdown
   - Completed: stateful MCP runtime now has protocol slices for tools,
     resources, and prompts, and can route session-scoped `list_resources` and
     `list_prompts` through the owner task. Catalog refresh still uses one-shot
     adapter policy.
```

- [ ] **Step 2: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, add after the content-access routing item:

```markdown
14. Complete: stateful MCP runtime protocols split into tool/resource/prompt
    slices. Runtime can route `list_resources` and `list_prompts` through the
    owner task for session-scoped listings; catalog refresh remains one-shot.
```

Renumber following item if needed.

- [ ] **Step 3: Archive completed plan after implementation**

Run only after all code/tests pass:

```bash
git mv docs/superpowers/plans/2026-06-07-stateful-runtime-list-resources-prompts.md docs/historical/superpowers/plans/2026-06-07-stateful-runtime-list-resources-prompts.md
```

---

### Task 6: Final Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_compat_imports.py -q
```

Expected: pass.

- [ ] **Step 2: Run source typecheck**

Run:

```bash
uv run basedpyright --level error src
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 3: Run focused test typecheck**

Run:

```bash
uv run basedpyright --level error tests/wf_sources_mcp/test_runtime.py tests/wf_sources_mcp/test_sdk_protocols.py tests/wf_mcp/test_compat_imports.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 4: Run focused lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/sdk src/wf_sources_mcp/runtime src/wf_mcp/sdk tests/wf_sources_mcp/test_runtime.py tests/wf_sources_mcp/test_sdk_protocols.py tests/wf_mcp/test_compat_imports.py
```

Expected: `All checks passed!`

- [ ] **Step 5: Check raw runtime methods remain absent**

Run:

```bash
rg -n "def (invoke_method|send_notification)" src/wf_sources_mcp/runtime
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

- Spec coverage: The plan adds session-scoped resource/prompt listings and splits protocols by capability without expanding raw MCP method support.
- Placeholder scan: No placeholder steps remain.
- Type consistency: resource/prompt list methods return `list[DiscoveredResource]` and `list[DiscoveredPrompt]`.
- Policy boundary: catalog refresh/discovery policy remains separate and one-shot.

