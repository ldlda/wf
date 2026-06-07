# Content Access Stateful Runtime Routing Implementation Plan

> **Historical:** This plan has been implemented. The `StatefulMcpRuntime` protocol
> is in `wf_sources_mcp.sdk`, upstream transport prefers it for content reads,
> and `WfMcpService` wires the configured runtime pool as both `tool_executor`
> and `stateful_runtime`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route broker content reads (`read_resource`, `render_prompt`) through a stateful MCP runtime when one is configured, while preserving one-shot adapter fallback.

**Architecture:** Config-built services already pass `McpRuntimePool` as `tool_executor`; that runtime now supports `call_tool`, `read_resource`, and `get_prompt`. This slice makes the policy explicit with a `StatefulMcpRuntime` protocol instead of ad-hoc `hasattr` or string dispatch. Discovery/catalog refresh remains one-shot adapter based; content access prefers stateful runtime and falls back to the adapter only when no stateful runtime is configured.

**Tech Stack:** Python 3.14, MCP Python SDK, pytest/pytest-asyncio, ruff, basedpyright.

---

## File Structure

- Modify `src/wf_sources_mcp/sdk/protocols.py`
  - Add `StatefulMcpRuntime` protocol with `call_tool`, `read_resource`, `get_prompt`.
- Modify `src/wf_sources_mcp/sdk/__init__.py`
  - Export `StatefulMcpRuntime`.
- Modify `src/wf_mcp/sdk/base.py`
  - Re-export `StatefulMcpRuntime` through compatibility shim.
- Modify `src/wf_mcp/sdk/__init__.py`
  - Re-export `StatefulMcpRuntime` through old package.
- Modify `src/wf_mcp/broker/service/upstream_transport.py`
  - Add `stateful_runtime: StatefulMcpRuntime | None`.
  - Keep `tool_executor` compatibility but derive stateful runtime from it when possible.
  - Prefer stateful runtime in `read_resource` and `render_prompt`.
  - Keep adapter fallback.
- Modify `src/wf_mcp/broker/service/core.py`
  - Pass the configured runtime pool as both `tool_executor` and `stateful_runtime` where available.
- Modify `src/wf_mcp/broker/config.py`
  - If construction currently passes only `tool_executor=McpRuntimePool(...)`, update service construction if needed.
- Add/modify tests:
  - `tests/wf_sources_mcp/test_sdk_protocols.py`
  - `tests/wf_mcp/test_compat_imports.py`
  - `tests/wf_mcp/service/test_upstream_transport.py`
  - `tests/wf_mcp/service/test_content_access.py`

## Hard Boundaries

- Do not route catalog refresh/discovery listing through stateful runtime in this slice.
- Do not use `getattr(runtime, "read_resource")` dispatch.
- Do not remove adapter fallback.
- Do not add runtime raw method or notification support.
- Do not assume `list_resources` / `list_prompts` are stateless.

---

### Task 1: Add `StatefulMcpRuntime` Protocol

**Files:**
- Modify: `src/wf_sources_mcp/sdk/protocols.py`
- Modify: `src/wf_sources_mcp/sdk/__init__.py`
- Modify: `tests/wf_sources_mcp/test_sdk_protocols.py`

- [ ] **Step 1: Add protocol test**

Append to `tests/wf_sources_mcp/test_sdk_protocols.py`:

```python
def test_stateful_mcp_runtime_protocol_shape() -> None:
    from wf_sources_mcp.sdk import StatefulMcpRuntime, ToolExecutor

    assert StatefulMcpRuntime.__name__ == "StatefulMcpRuntime"
    assert ToolExecutor.__name__ == "ToolExecutor"
```

- [ ] **Step 2: Add the protocol**

In `src/wf_sources_mcp/sdk/protocols.py`, add after `ToolExecutor`:

```python
class StatefulMcpRuntime(ToolExecutor, Protocol):
    """Stateful execution/read boundary for configured MCP sources.

    Implementations keep source session state across calls. Discovery/catalog
    refresh may still use one-shot adapters by policy.
    """

    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]: ...

    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...
```

Update `__all__`:

```python
__all__ = [
    "BackendAdapter",
    "StatefulMcpRuntime",
    "ToolCallResult",
    "ToolExecutor",
]
```

- [ ] **Step 3: Export protocol from package root**

In `src/wf_sources_mcp/sdk/__init__.py`, import/export `StatefulMcpRuntime`:

```python
from .protocols import BackendAdapter, StatefulMcpRuntime, ToolCallResult, ToolExecutor
```

and include `"StatefulMcpRuntime"` in `__all__`.

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

In `src/wf_mcp/sdk/base.py`, re-export `StatefulMcpRuntime` with the existing protocol exports:

```python
from wf_sources_mcp.sdk import BackendAdapter, StatefulMcpRuntime, ToolCallResult

__all__ = ["BackendAdapter", "StatefulMcpRuntime", "ToolCallResult"]
```

In `src/wf_mcp/sdk/__init__.py`, update imports and `__all__`:

```python
from wf_sources_mcp.sdk import (
    BackendAdapter,
    McpSdkAdapter,
    StatefulMcpRuntime,
    ToolCallResult,
)

__all__ = ["BackendAdapter", "McpSdkAdapter", "StatefulMcpRuntime", "ToolCallResult"]
```

- [ ] **Step 2: Extend compatibility test**

In `tests/wf_mcp/test_compat_imports.py`, extend `test_wf_mcp_sdk_protocol_shims_reexport_wf_sources_mcp_sdk`:

```python
    from wf_mcp.sdk import StatefulMcpRuntime as CompatStatefulMcpRuntime
    from wf_mcp.sdk.base import StatefulMcpRuntime as CompatBaseStatefulMcpRuntime
    from wf_sources_mcp.sdk import StatefulMcpRuntime

    assert CompatStatefulMcpRuntime is StatefulMcpRuntime
    assert CompatBaseStatefulMcpRuntime is StatefulMcpRuntime
```

- [ ] **Step 3: Run compatibility test**

Run:

```bash
uv run pytest tests/wf_mcp/test_compat_imports.py -q
```

Expected: pass.

---

### Task 3: Add Stateful Runtime Routing to Upstream Transport

**Files:**
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `tests/wf_mcp/service/test_upstream_transport.py`

- [ ] **Step 1: Add fake stateful runtime and adapter tests**

Append to `tests/wf_mcp/service/test_upstream_transport.py`:

```python
class _StatefulRuntime:
    def __init__(self) -> None:
        self.resources: list[tuple[str, str]] = []
        self.prompts: list[tuple[str, str, dict[str, str] | None]] = []

    async def call_tool(self, connection, auth, tool_name, payload):
        raise AssertionError("not used by these tests")

    async def read_resource(self, connection, auth, uri: str):
        self.resources.append((connection.id, uri))
        return {"contents": [{"uri": uri, "text": "stateful resource"}]}

    async def get_prompt(
        self,
        connection,
        auth,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ):
        self.prompts.append((connection.id, prompt_name, arguments))
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": "stateful prompt"},
                }
            ]
        }


class _ExplodingContentAdapter(FakeAdapter):
    async def read_resource(self, connection, auth, uri):
        raise AssertionError("adapter read_resource should not be used")

    async def get_prompt(self, connection, auth, prompt_name, arguments=None):
        raise AssertionError("adapter get_prompt should not be used")
```

Add tests:

```python
async def test_upstream_transport_prefers_stateful_runtime_for_resource_reads(
    tmp_path: Path,
) -> None:
    events: list[McpEvent] = []
    runtime = _StatefulRuntime()
    transport = UpstreamTransportService(
        auth_store=FileStore(tmp_path),
        catalog_store=FileStore(tmp_path),
        event_sink=events.append,
        stateful_runtime=runtime,
    )
    transport.register_adapter("demo", _ExplodingContentAdapter())
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        metadata=_fake_transport_metadata(),
    )

    result = await transport.read_resource(
        connection,
        "demo.personal.resource.welcome",
        "fixture://docs/welcome",
    )

    assert result["contents"][0]["text"] == "stateful resource"
    assert runtime.resources == [("demo.personal", "fixture://docs/welcome")]
    assert [event.kind for event in events] == [
        "resource_read_started",
        "resource_read_completed",
    ]


async def test_upstream_transport_prefers_stateful_runtime_for_prompts(
    tmp_path: Path,
) -> None:
    events: list[McpEvent] = []
    runtime = _StatefulRuntime()
    transport = UpstreamTransportService(
        auth_store=FileStore(tmp_path),
        catalog_store=FileStore(tmp_path),
        event_sink=events.append,
        stateful_runtime=runtime,
    )
    transport.register_adapter("demo", _ExplodingContentAdapter())
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        metadata=_fake_transport_metadata(),
    )

    result = await transport.render_prompt(
        connection,
        "demo.personal.prompt.summarize",
        "prompt.summarize",
        {"text": "hello"},
    )

    assert result["messages"][0]["content"]["text"] == "stateful prompt"
    assert runtime.prompts == [
        ("demo.personal", "prompt.summarize", {"text": "hello"})
    ]
    assert [event.kind for event in events] == [
        "prompt_get_started",
        "prompt_get_completed",
    ]
```

- [ ] **Step 2: Add `stateful_runtime` field and import protocol**

In `src/wf_mcp/broker/service/upstream_transport.py`, change import:

```python
from wf_sources_mcp.sdk import BackendAdapter, StatefulMcpRuntime, ToolExecutor
```

Add field to `UpstreamTransportService`:

```python
    stateful_runtime: StatefulMcpRuntime | None = None
```

- [ ] **Step 3: Prefer stateful runtime for resource reads**

In `read_resource`, replace:

```python
        adapter = require_adapter(connection, self.adapters)
        auth = self.load_connection_auth(connection)
        # Compatibility boundary...
        source_connection = mcp_source_connection_from_connection_config(connection)
```

with:

```python
        auth = self.load_connection_auth(connection)
        # Compatibility boundary: broker callers still pass ConnectionConfig.
        source_connection = mcp_source_connection_from_connection_config(connection)
```

Then replace the execution line:

```python
        result = await adapter.read_resource(source_connection, auth, uri)
```

with:

```python
        if self.stateful_runtime is not None:
            result = await self.stateful_runtime.read_resource(
                source_connection,
                auth,
                uri,
            )
        else:
            adapter = require_adapter(connection, self.adapters)
            result = await adapter.read_resource(source_connection, auth, uri)
```

- [ ] **Step 4: Prefer stateful runtime for prompt gets**

In `render_prompt`, remove early adapter lookup and replace execution:

```python
        if self.stateful_runtime is not None:
            result = await self.stateful_runtime.get_prompt(
                source_connection,
                auth,
                local_name,
                arguments,
            )
        else:
            adapter = require_adapter(connection, self.adapters)
            result = await adapter.get_prompt(source_connection, auth, local_name, arguments)
```

Keep existing start/completed events unchanged.

- [ ] **Step 5: Run upstream transport tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py -q
```

Expected: pass.

---

### Task 4: Wire Configured Runtime as Stateful Runtime

**Files:**
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/config.py` if needed.
- Modify: `tests/wf_mcp/service/test_content_access.py`

- [ ] **Step 1: Wire service field**

In `src/wf_mcp/broker/service/core.py`, when constructing `UpstreamTransportService`, pass:

```python
            stateful_runtime=self.tool_executor
            if isinstance(self.tool_executor, object)
            else None,
```

Do not use that exact `isinstance(..., object)` if basedpyright dislikes it. Prefer a simple assignment after adding a `stateful_runtime` field to `WfMcpService` if needed:

```python
    stateful_runtime: StatefulMcpRuntime | None = None
```

Then:

```python
        stateful_runtime = self.stateful_runtime
        self.upstream = UpstreamTransportService(
            auth_store=auth_store,
            catalog_store=catalog_store,
            event_sink=self.events.record_event,
            tool_executor=self.tool_executor,
            stateful_runtime=stateful_runtime,
        )
```

For config-built services that construct `McpRuntimePool`, set both:

```python
    runtime_pool = McpRuntimePool(runtime_factory.create)
    service = WfMcpService(
        ...,
        tool_executor=runtime_pool,
        stateful_runtime=runtime_pool,
    )
```

If current `build_service_from_config` already constructs the pool inline, refactor to a local `runtime_pool` variable.

- [ ] **Step 2: Add content access service test with stateful runtime**

Append to `tests/wf_mcp/service/test_content_access.py`:

```python
class _StatefulRuntime:
    def __init__(self) -> None:
        self.resources: list[str] = []
        self.prompts: list[str] = []

    async def call_tool(self, connection, auth, tool_name, payload):
        raise AssertionError("not used")

    async def read_resource(self, connection, auth, uri: str):
        self.resources.append(uri)
        return {"contents": [{"uri": uri, "text": "stateful resource"}]}

    async def get_prompt(self, connection, auth, prompt_name, arguments=None):
        self.prompts.append(prompt_name)
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": "stateful prompt"},
                }
            ]
        }


async def test_content_access_uses_stateful_runtime_for_upstream_content() -> None:
    runtime = _StatefulRuntime()
    service = WfMcpService(
        store=FileStore(local_temp_root() / "content_stateful_runtime"),
        tool_executor=runtime,
        stateful_runtime=runtime,
    )
    service.register_connection(
        ConnectionConfig(
            id="demo.personal",
            server="demo",
            account="personal",
            metadata={"transport": "stdio", "command": "fake-mcp-server"},
        )
    )
    service.register_adapter("demo", FakeAdapter())
    await service.refresh_connection_catalog("demo.personal")

    resource = await service.content_access.read_resource(
        "demo.personal.resource.welcome"
    )
    prompt = await service.content_access.render_prompt(
        "demo.personal.prompt.summarize",
        arguments={"text": "hello"},
    )

    assert resource["contents"][0]["text"] == "stateful resource"
    assert prompt["messages"][0]["content"]["text"] == "stateful prompt"
    assert runtime.resources == ["fixture://resource/welcome"]
    assert runtime.prompts == ["prompt.summarize"]
```

Adjust expected URI if `FakeAdapter` catalog fixture uses a different resource URI; read it from the failure and keep the exact catalog URI.

- [ ] **Step 3: Run content tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_content_access.py tests/wf_mcp/service/test_upstream_transport.py -q
```

Expected: pass.

---

### Task 5: Docs and Plan Archive

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move after completion: `docs/superpowers/plans/2026-06-07-content-access-stateful-runtime-routing.md` to `docs/historical/superpowers/plans/2026-06-07-content-access-stateful-runtime-routing.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the MCP upstream source runtime cleanup bullets, add:

```markdown
   - Completed: broker content access now prefers a configured stateful MCP
     runtime for `read_resource` and `get_prompt`, with one-shot adapter fallback.
     Catalog refresh/discovery remains one-shot by policy.
```

- [ ] **Step 2: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, add after the prompt runtime item:

```markdown
13. Complete: broker content access now prefers configured `StatefulMcpRuntime`
    for resource and prompt reads, falling back to the one-shot adapter when no
    stateful runtime is configured. Catalog refresh/discovery remains one-shot.
```

Renumber following item if needed.

- [ ] **Step 3: Archive completed plan after implementation**

Run only after all code/tests pass:

```bash
git mv docs/superpowers/plans/2026-06-07-content-access-stateful-runtime-routing.md docs/historical/superpowers/plans/2026-06-07-content-access-stateful-runtime-routing.md
```

---

### Task 6: Final Verification

**Files:**
- All changed files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_content_access.py tests/wf_mcp/test_compat_imports.py -q
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
uv run basedpyright --level error tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_content_access.py tests/wf_sources_mcp/test_sdk_protocols.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 4: Run focused lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/sdk src/wf_mcp/sdk src/wf_mcp/broker/service/upstream_transport.py src/wf_mcp/broker/service/core.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_content_access.py
```

Expected: `All checks passed!`

- [ ] **Step 5: Check no discovery routing changed**

Run:

```bash
rg -n "stateful_runtime\\.(list_tools|list_resources|list_prompts)" src
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

- Spec coverage: The plan makes stateful-vs-one-shot routing explicit and only for content reads.
- Placeholder scan: No placeholder steps remain.
- Type consistency: `StatefulMcpRuntime` is a protocol satisfied by `McpRuntimePool`.
- Policy boundary: discovery/catalog refresh still uses one-shot adapter; no assumption that resource/prompt listing is stateless.

