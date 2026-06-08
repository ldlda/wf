# MCP Runtime Full Operation Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the persistent MCP runtime pool implement the same MCP operation surface as the one-shot backend adapter, then route broker operations through the persistent runtime whenever it is configured.

**Architecture:** `BackendAdapter` and `StatefulMcpRuntime` both represent "execute MCP operations for a configured source"; they should differ by session strategy, not by operation set. `McpSdkAdapter` remains the one-shot implementation. `McpRuntimePool` becomes the persistent implementation and should be preferred by `UpstreamTransportService` for tool calls, resource/prompt operations, catalog listings, raw methods, notifications, and liveness probes when available.

**Tech Stack:** Python 3.14, MCP SDK `ClientSession`, `McpSourceClient`, persistent owner-task queue, pytest-asyncio, ruff, basedpyright.

---

## Hard Boundaries

- Do not remove `McpSdkAdapter`; it remains the one-shot fallback.
- Do not remove `BackendAdapter` or `StatefulMcpRuntime` names in this slice.
- Do not change public JSON-RPC or CLI payload shapes.
- Do not change source registry or config file formats.
- Do not add e2e JSON-RPC session-reuse tests in this slice; that is the next QA slice.
- Do not expose raw `ClientSession` outside `wf_sources_mcp.runtime` internals.
- Do not dispatch owner-task operations via `getattr(client, operation)`; continue passing explicit callables.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Modify `src/wf_sources_mcp/sdk/protocols.py`: expand `StatefulMcpRuntime` to full operation surface or introduce a shared full-surface protocol.
- Modify `src/wf_sources_mcp/runtime/session.py`: add persistent session methods for `list_tools`, `get_connection_metadata`, `invoke_method`, and `send_notification`.
- Modify `src/wf_sources_mcp/runtime/factory.py`: route those new methods through `_SessionOwner.submit()`.
- Modify `src/wf_sources_mcp/runtime/pool.py`: expose full operation methods.
- Modify `src/wf_sources_mcp/client/source_client.py`: ensure all operations needed by runtime owner already exist and stay reusable.
- Modify `src/wf_mcp/broker/service/upstream_transport.py`: prefer `stateful_runtime` for all MCP operations that can use an existing session.
- Modify tests:
  - `tests/wf_sources_mcp/test_sdk_protocols.py`
  - `tests/wf_sources_mcp/test_runtime.py`
  - `tests/wf_mcp/service/test_upstream_transport.py`
- Modify docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

### Task 1: Expand the Runtime Protocol Surface

**Files:**
- Modify: `src/wf_sources_mcp/sdk/protocols.py`
- Modify: `tests/wf_sources_mcp/test_sdk_protocols.py`

- [ ] **Step 1: Add protocol tests first**

In `tests/wf_sources_mcp/test_sdk_protocols.py`, add or extend a static-shape test that assigns an object implementing all operations to both `BackendAdapter` and `StatefulMcpRuntime`.

The object should include:

- `get_connection_metadata`
- `list_tools`
- `list_resources`
- `list_prompts`
- `call_tool`
- `read_resource`
- `get_prompt`
- `invoke_method`
- `send_notification`

Use existing test fakes where possible.

- [ ] **Step 2: Update protocol definitions**

In `src/wf_sources_mcp/sdk/protocols.py`, prefer this shape:

```python
class McpSourceOperations(Protocol):
    async def list_tools(...): ...
    async def list_resources(...): ...
    async def list_prompts(...): ...
    async def get_connection_metadata(...): ...
    async def read_resource(...): ...
    async def get_prompt(...): ...
    async def invoke_method(...): ...
    async def send_notification(...): ...
    async def call_tool(...): ...


class BackendAdapter(McpSourceOperations, Protocol):
    """One-shot or adapter-style MCP operation executor."""


class StatefulMcpRuntime(McpSourceOperations, Protocol):
    """Persistent MCP operation executor for configured sources."""
```

Keep existing narrow aliases (`ToolRuntime`, `ResourceRuntime`, `PromptRuntime`, `ToolExecutor`) for compatibility.

Add `McpSourceOperations` to `__all__` and package exports in `src/wf_sources_mcp/sdk/__init__.py`.

- [ ] **Step 3: Run protocol tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_sdk_protocols.py -q
```

Expected: pass.

---

### Task 2: Add Full Operations to `PersistentMcpSession`

**Files:**
- Modify: `src/wf_sources_mcp/runtime/session.py`
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Add tests for session-level operations**

Extend fake client/session tests in `tests/wf_sources_mcp/test_runtime.py` to cover:

- `list_tools()`
- `get_connection_metadata()`
- `invoke_method()`
- `send_notification()`

For injected/fake `client` path, verify:

- list tools are converted to `DiscoveredTool`;
- metadata is local `{server, transport}`;
- invoke returns dumped payload;
- notification records that it was sent.

- [ ] **Step 2: Add callback types and methods**

In `src/wf_sources_mcp/runtime/session.py`, add callback types:

```python
RawToolLister = Callable[[], Awaitable[list[DiscoveredTool]]]
RawMetadataGetter = Callable[[], Awaitable[dict[str, Any]]]
RawMethodInvoker = Callable[[str, dict[str, Any] | None], Awaitable[dict[str, Any]]]
RawNotificationSender = Callable[[str, dict[str, Any] | None], Awaitable[None]]
```

Add corresponding dataclass fields.

Implement methods:

- `list_tools()`
- `get_connection_metadata()`
- `invoke_method(method, params=None)`
- `send_notification(method, params=None)`

Use callback first, then injected `client` fallback where applicable. Metadata can be computed locally from `self.connection` without client.

- [ ] **Step 3: Run runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: pass.

---

### Task 3: Route Full Operations Through the Owner Task

**Files:**
- Modify: `src/wf_sources_mcp/runtime/factory.py`
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Add owner-routing tests**

In `tests/wf_sources_mcp/test_runtime.py`, add or extend a test proving `PersistentSessionFactory` routes these operations through `_SessionOwner.submit()`:

- `list_tools`
- `invoke_method`
- `send_notification`

Existing tests already cover resources/prompts/tool calls. Keep all operations explicit; do not test implementation internals like queue item class unless existing patterns do.

- [ ] **Step 2: Wire callbacks in `PersistentSessionFactory.create()`**

In `create()`, pass:

```python
list_tools_callback=owner.list_tools
get_connection_metadata_callback=owner.get_connection_metadata
invoke_method_callback=owner.invoke_method
send_notification_callback=owner.send_notification
```

- [ ] **Step 3: Add `_SessionOwner` methods**

In `_SessionOwner`, add:

```python
async def list_tools(self) -> list[DiscoveredTool]:
    return await self.submit("list_tools", lambda client: client.list_tools())

async def get_connection_metadata(self) -> dict[str, Any]:
    return await self.submit(
        "get_connection_metadata",
        lambda client: client.get_connection_metadata(),
    )

async def invoke_method(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return await self.submit(
        "invoke_method",
        lambda client: client.invoke_method(method, params),
    )

async def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
    await self.submit(
        "send_notification",
        lambda client: client.send_notification(method, params),
    )
```

- [ ] **Step 4: Run runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: pass.

---

### Task 4: Add Full Operations to `McpRuntimePool`

**Files:**
- Modify: `src/wf_sources_mcp/runtime/pool.py`
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Add pool-level tests**

Add tests proving the pool reuses one session for:

- `list_tools`
- `invoke_method`
- `send_notification`

Also extend the public protocol/static-shape test so `McpRuntimePool` satisfies `StatefulMcpRuntime`.

- [ ] **Step 2: Implement pool methods**

Add methods to `McpRuntimePool`:

```python
async def list_tools(...)
async def get_connection_metadata(...)
async def invoke_method(...)
async def send_notification(...)
```

Each method should:

1. call `get_session(connection, auth)`;
2. delegate to the matching `PersistentMcpSession` method.

- [ ] **Step 3: Run runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py tests/wf_sources_mcp/test_sdk_protocols.py -q
```

Expected: pass.

---

### Task 5: Route Broker Upstream Operations Through Stateful Runtime

**Files:**
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `tests/wf_mcp/service/test_upstream_transport.py`

- [ ] **Step 1: Add routing tests**

Extend `_StatefulRuntime` fake in `tests/wf_mcp/service/test_upstream_transport.py` to implement the full operation surface.

Add tests proving that when `stateful_runtime` is configured:

- `invoke_method()` uses runtime, not adapter;
- `send_notification()` uses runtime, not adapter;
- `refresh_connection_catalog()` uses runtime for discovery/listing operations;
- `deployment_diagnostics()` uses runtime for live `list_tools()` checks.

Use an adapter fake that raises if called for the operation under test.

- [ ] **Step 2: Add a local operation selector helper**

In `UpstreamTransportService`, add a private helper:

```python
def _operations_for(self, connection: ConnectionConfig) -> StatefulMcpRuntime | BackendAdapter:
    if self.stateful_runtime is not None:
        return self.stateful_runtime
    return require_adapter(connection, self.adapters)
```

If basedpyright cannot narrow the union cleanly, keep explicit branches in each method instead of introducing a helper. Correctness is more important than DRY.

- [ ] **Step 3: Update `invoke_method()` and `send_notification()`**

Prefer `stateful_runtime` when present. Fall back to adapter when absent. Preserve event names and payloads.

- [ ] **Step 4: Update `refresh_connection_catalog()`**

For discovery/listing, prefer `stateful_runtime` when present:

```python
operations = self.stateful_runtime or require_adapter(connection, self.adapters)
capabilities = await discover_connection_capabilities(
    connection=source_connection,
    auth=auth,
    adapter=operations,
)
```

This requires `StatefulMcpRuntime` to satisfy the same protocol as `BackendAdapter`.

- [ ] **Step 5: Update `deployment_diagnostics()`**

Use `stateful_runtime.list_tools()` when present; otherwise adapter fallback.

- [ ] **Step 6: Run upstream transport tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_content_access.py tests/wf_mcp/service/test_catalog.py -q
```

Expected: pass.

---

### Task 6: Update Docs and Archive Plan

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-08-mcp-runtime-full-operation-surface.md` to `docs/historical/superpowers/plans/2026-06-08-mcp-runtime-full-operation-surface.md`

- [ ] **Step 1: Update roadmap**

Under the MCP runtime/source cleanup section, add:

```markdown
      Persistent MCP runtime now implements the full upstream MCP operation
      surface used by the one-shot adapter. Broker upstream operations prefer
      the shared runtime pool when configured, with one-shot adapters retained
      as fallback.
```

- [ ] **Step 2: Update long-lived boundary spec**

Add a completed numbered item:

```markdown
24. Complete: `McpRuntimePool` implements the full MCP operation surface
    (`list_tools`, resources, prompts, tools, raw methods, notifications, and
    local metadata). Broker upstream operations prefer the persistent runtime
    when configured and fall back to one-shot adapters.
```

Renumber pending items if needed.

- [ ] **Step 3: Archive the plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-mcp-runtime-full-operation-surface.md docs/historical/superpowers/plans/2026-06-08-mcp-runtime-full-operation-surface.md
```

Expected: plan moved under `docs/historical/...`.

---

### Task 7: Final Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py tests/wf_sources_mcp/test_sdk_protocols.py tests/wf_sources_mcp/test_sdk_adapter.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_content_access.py tests/wf_mcp/service/test_catalog.py -q
```

Expected: pass.

- [ ] **Step 2: Run env-gated everything-server test if `.env` has settings**

If `.env` contains `MCP_EVERYTHING_COMMAND` or `MCP_EVERYTHING_URL`, run:

```bash
uv run --env-file .env pytest tests/wf_mcp/test_sdk_adapter.py::test_mcp_sdk_adapter_can_probe_everything_server -q
```

Expected: pass or skip only for environment permission issues. Do not hide real failures.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/runtime src/wf_sources_mcp/sdk src/wf_mcp/broker/service/upstream_transport.py tests/wf_sources_mcp/test_runtime.py tests/wf_sources_mcp/test_sdk_protocols.py tests/wf_mcp/service/test_upstream_transport.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_sources_mcp/runtime src/wf_sources_mcp/sdk src/wf_mcp/broker/service/upstream_transport.py tests/wf_sources_mcp/test_runtime.py tests/wf_sources_mcp/test_sdk_protocols.py tests/wf_mcp/service/test_upstream_transport.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 5: Check whitespace**

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
- Confirmation that `McpRuntimePool` satisfies the full MCP operation protocol.
- Confirmation that `UpstreamTransportService` prefers stateful runtime for all MCP operations when configured.
- Confirmation that `McpSdkAdapter` remains the one-shot fallback.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
