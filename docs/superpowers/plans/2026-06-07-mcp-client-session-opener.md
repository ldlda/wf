# MCP Client Session Opener Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the clean source-provider MCP session opener in `wf_sources_mcp` and make one-shot adapter + persistent runtime borrow it, without moving runtime files yet.

**Architecture:** The previous slice introduced `McpSourceConnection`. This slice makes that seam useful by centralizing transport opening, auth injection, and `ClientSession.initialize()` in `wf_sources_mcp.client`. Existing `wf_mcp.sdk.adapter.McpSdkAdapter` and `wf_mcp.runtime.factory.PersistentSessionFactory` should call the shared opener instead of duplicating stdio/http setup.

**Tech Stack:** Python 3.14, MCP Python SDK, httpx, AnyIO/MCP async context managers, pytest, ruff, basedpyright.

---

## Design Intent

Do not make a prettier copy of `src/wf_mcp/runtime/factory.py`. Keep the good ideas and isolate them:

- keep the actor/owner-task pattern for persistent sessions
- keep runtime fingerprinting behavior
- centralize transport opening and auth
- keep `wf_mcp.runtime.*` in place for now
- make future movement to `wf_sources_mcp.runtime` mechanical

The desired flow:

```text
ConnectionConfig
  -> mcp_source_connection_from_connection_config()
  -> open_mcp_session(McpSourceConnection, AuthRecord | None)
  -> ClientSession

McpSdkAdapter: opens per operation
PersistentSessionFactory: opens once inside owner task
```

---

## Important Constraint

`StdioSourceTransport.cwd` exists because old persistent runtime supports `metadata["cwd"]`. The shared opener must preserve that field. Otherwise stdio servers that need a working directory regress.

---

## Task 1: Lock Down `cwd` Propagation

**Files:**
- Modify: `src/wf_sources_mcp/transports.py`
- Modify: `src/wf_sources_mcp/connections.py`
- Test: `tests/wf_sources_mcp/test_connections.py`

- [ ] Confirm `StdioSourceTransport` exposes `cwd: str | None = None`.
- [ ] Confirm legacy `ConnectionConfig` conversion carries `metadata["cwd"]` into `StdioSourceTransport.cwd`.
- [ ] Confirm tests assert cwd round-trips from legacy connection metadata.
- [ ] Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py tests/wf_sources_mcp/test_source_registry.py -q
uv run basedpyright --level error src/wf_sources_mcp
```

Expected: pass.

---

## Task 2: Create `wf_sources_mcp.client.transport`

**Files:**
- Create: `src/wf_sources_mcp/client/__init__.py`
- Create: `src/wf_sources_mcp/client/transport.py`
- Test: `tests/wf_sources_mcp/test_client_transport.py`

Implement:

```python
@asynccontextmanager
async def open_mcp_session(
    connection: McpSourceConnection,
    auth: AuthRecord | None,
) -> AsyncIterator[ClientSession]:
    ...
```

Behavior:

- for `StdioSourceTransport`:
  - merge `transport.env` with `mcp_auth_env(auth)`, auth wins on duplicate keys
  - pass `command`, `args`, `env`, and `cwd` to `StdioServerParameters`
  - enter `stdio_client`
  - enter `ClientSession`
  - call `await session.initialize()`
  - yield initialized session

- for `HttpSourceTransport`:
  - create `httpx.AsyncClient(headers=mcp_auth_headers(auth) or None)`
  - enter `streamable_http_client(str(transport.url), http_client=http_client)`
  - enter `ClientSession`
  - call `await session.initialize()`
  - yield initialized session

- unsupported transport:
  - raise `ValueError(f"unsupported MCP transport {transport.kind!r}")`

Testing guidance:

- Use monkeypatch/fakes for `stdio_client`, `streamable_http_client`, and `ClientSession`.
- Do not start real subprocesses.
- Assert stdio env merge and cwd propagation.
- Assert HTTP headers propagation.
- Assert initialize is called before yielding.

Verification:

```bash
uv run pytest tests/wf_sources_mcp/test_client_transport.py -q
uv run ruff check src/wf_sources_mcp tests/wf_sources_mcp
uv run basedpyright --level error src/wf_sources_mcp
```

---

## Task 3: Make `McpSdkAdapter` Use The Shared Opener

**Files:**
- Modify: `src/wf_mcp/sdk/adapter.py`
- Test: `tests/wf_mcp/test_sdk_adapter.py`

Replace the private `_session()` transport-opening logic with:

```python
from wf_sources_mcp.client import open_mcp_session
```

Then each operation should do:

```python
async with open_mcp_session(connection, auth) as session:
    ...
```

Do not move `McpSdkAdapter` yet. This slice only removes duplicated opening logic.

Verification:

```bash
uv run pytest tests/wf_mcp/test_sdk_adapter.py tests/wf_sources_mcp/test_client_transport.py -q
uv run basedpyright --level error src/wf_mcp/sdk src/wf_sources_mcp
```

---

## Task 4: Make `PersistentSessionFactory` Use The Shared Opener

**Files:**
- Modify: `src/wf_mcp/runtime/factory.py`
- Test: `tests/wf_mcp/test_stateful_runtime.py`

The factory still receives legacy `ConnectionConfig`. Convert inside `_create_with_stack()`:

```python
source_connection = mcp_source_connection_from_connection_config(connection)
```

Then use the shared opener while preserving `AsyncExitStack` ownership:

```python
session = await stack.enter_async_context(open_mcp_session(source_connection, auth))
return session
```

Do not remove `_SessionOwner`. The owner-task pattern is the important fix for AnyIO/MCP cancel-scope ownership.

Verification:

```bash
uv run pytest tests/wf_mcp/test_stateful_runtime.py -q
uv run basedpyright --level error src/wf_mcp/runtime src/wf_sources_mcp
```

---

## Task 5: Verify Boundary And Update Docs

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

Docs should say:

- shared MCP session opener exists in `wf_sources_mcp.client`
- one-shot adapter and persistent runtime both use it
- runtime files are still in `wf_mcp` for compatibility
- next slice can move `PersistentSessionFactory`, `PersistentMcpSession`, and `McpRuntimePool` to `wf_sources_mcp.runtime`

Final verification:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/service/test_upstream_transport.py -q
uv run ruff check src tests
uv run basedpyright --level error src
git diff --check
```

Expected:

- focused tests pass
- ruff passes
- basedpyright has 0 errors
- no whitespace errors

---

## Non-Goals

- Do not move runtime files yet.
- Do not move `McpSdkAdapter` yet.
- Do not introduce WebSocket/SSE support.
- Do not implement reconnect/backoff policy.
- Do not broaden persistent runtime beyond existing `call_tool` behavior in this slice.
- Do not change proxy/frontend MCP code.

---

## Future Slice

After this plan:

1. Move `PersistentSessionFactory`, `PersistentMcpSession`, and `McpRuntimePool` into `wf_sources_mcp.runtime`.
2. Keep `wf_mcp.runtime.*` shims.
3. Then move `McpSdkAdapter` into `wf_sources_mcp.sdk.adapter`.
4. Only after those moves, consider a broader `McpClientSession` abstraction for persistent `read_resource`, `get_prompt`, `invoke_method`, and `send_notification`.
