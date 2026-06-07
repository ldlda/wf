# MCP Runtime Read Resource Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent MCP runtime support for `read_resource()` by routing it through the existing owner-task operation queue and `McpSourceClient`.

**Architecture:** This is the first non-tool runtime operation. It must stay a thin wrapper over `McpSourceClient.read_resource()` so raw MCP SDK types and transport ownership do not leak. `PersistentMcpSession` and `McpRuntimePool` gain `read_resource`; `get_prompt`, `invoke_method`, and `send_notification` remain out of scope.

**Tech Stack:** Python 3.14, MCP Python SDK, pytest/pytest-asyncio, ruff, basedpyright.

---

## File Structure

- Modify `src/wf_sources_mcp/runtime/factory.py`
  - Add `_SessionOwner.read_resource(uri)`.
  - Implement through `submit(operation="read_resource", run=lambda client: client.read_resource(uri))`.
- Modify `src/wf_sources_mcp/runtime/session.py`
  - Add `RawResourceReader` callback type.
  - Add `read_resource_callback` field.
  - Add `read_resource(uri)` method.
  - Keep fallback `client.read_resource()` serialization for injected/fake sessions.
- Modify `src/wf_sources_mcp/runtime/pool.py`
  - Add `McpRuntimePool.read_resource(connection, auth, uri)`.
- Modify tests:
  - `tests/wf_sources_mcp/test_runtime.py`
  - `tests/wf_mcp/test_stateful_runtime.py` only if type compatibility requires it.
- Update docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

## Hard Boundaries

- Do not add persistent runtime `get_prompt`, `invoke_method`, or `send_notification`.
- Do not expose raw `ClientSession` outside the owner task.
- Do not return raw MCP SDK result models from `read_resource`; return serialized `dict[str, Any]`.
- Do not alter `McpSourceClient.read_resource()` behavior.
- Do not dispatch by string; `operation="read_resource"` is metadata only.

---

### Task 1: Add Persistent Read Tests

**Files:**
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Extend fake client with resource reads**

In `tests/wf_sources_mcp/test_runtime.py`, import `AnyUrl`:

```python
from pydantic import AnyUrl
```

Update `_FakeFactory._create_with_stack()`'s `_FakeClient` class:

```python
        class _FakeClient:
            async def call_tool(
                self, tool_name: str, payload: dict[str, object]
            ) -> RawCallToolResult:
                return await factory._call_tool(tool_name, payload)

            async def read_resource(self, uri: AnyUrl):
                return type(
                    "ReadResourceResult",
                    (),
                    {
                        "model_dump": lambda _self, **_kwargs: {
                            "contents": [{"uri": str(uri), "text": "resource text"}]
                        }
                    },
                )()
```

- [ ] **Step 2: Add session-level persistent read test**

Append to `tests/wf_sources_mcp/test_runtime.py`:

```python
@pytest.mark.asyncio
async def test_persistent_session_factory_routes_resource_reads_through_owner() -> None:
    factory = _FakeFactory()
    connection = _connection()
    session = await factory.create(connection, None)

    await session.call_tool("echo", {"text": "one"})
    resource_payload = await session.read_resource("fixture://docs/welcome")
    await session.close()

    assert factory.created_connections == [connection]
    assert factory.calls == [("echo", {"text": "one"})]
    assert resource_payload == {
        "contents": [
            {"uri": "fixture://docs/welcome", "text": "resource text"},
        ]
    }
```

- [ ] **Step 3: Add pool-level persistent read test**

Append:

```python
@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_tool_and_resource_read() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    tool_result = await pool.call_tool(connection, None, "echo", {"text": "one"})
    resource_payload = await pool.read_resource(
        connection,
        None,
        "fixture://docs/welcome",
    )
    await pool.close_all()

    assert tool_result.output == {"echoed": "one"}
    assert resource_payload["contents"][0]["text"] == "resource text"
    assert factory.created_connections == [connection]
```

- [ ] **Step 4: Update public surface test**

Update `test_persistent_session_public_runtime_is_tool_call_only` to allow `read_resource` and still forbid the rest:

```python
def test_persistent_session_public_runtime_exposes_only_tool_and_resource_read() -> None:
    public_operations = {
        name
        for name in dir(PersistentMcpSession)
        if not name.startswith("_") and callable(getattr(PersistentMcpSession, name))
    }

    assert "call_tool" in public_operations
    assert "read_resource" in public_operations
    assert "get_prompt" not in public_operations
    assert "invoke_method" not in public_operations
    assert "send_notification" not in public_operations
```

- [ ] **Step 5: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: fail because `PersistentMcpSession.read_resource` and `McpRuntimePool.read_resource` do not exist yet.

---

### Task 2: Add `read_resource` to Persistent Session

**Files:**
- Modify: `src/wf_sources_mcp/runtime/session.py`

- [ ] **Step 1: Update imports and callback types**

Add `AnyUrl` import:

```python
from pydantic import AnyUrl
```

Add callback type:

```python
RawResourceReader = Callable[[str], Awaitable[dict[str, Any]]]
```

- [ ] **Step 2: Add callback field**

In `PersistentMcpSession`, add:

```python
    read_resource_callback: RawResourceReader | None = None
```

- [ ] **Step 3: Add `read_resource` method**

Add below `call_tool()`:

```python
    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read an MCP resource through the owner task or injected session."""
        if self.read_resource_callback is not None:
            return await self.read_resource_callback(uri)
        if self.client is not None:
            result = await self.client.read_resource(AnyUrl(uri))
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)
        raise RuntimeError("persistent MCP session has no resource read transport")
```

- [ ] **Step 4: Run source tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: still fail at factory/pool routing because callbacks are not wired yet.

---

### Task 3: Route `read_resource` Through Owner Queue

**Files:**
- Modify: `src/wf_sources_mcp/runtime/factory.py`

- [ ] **Step 1: Wire callback in `PersistentSessionFactory.create()`**

Update returned `PersistentMcpSession`:

```python
        return PersistentMcpSession(
            connection=connection,
            auth=auth,
            call_callback=owner.call_tool,
            read_resource_callback=owner.read_resource,
            close_callback=owner.close,
        )
```

- [ ] **Step 2: Add owner `read_resource()`**

Add below `_SessionOwner.call_tool()`:

```python
    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Submit a resource read through the generic owner-task operation queue."""
        return await self.submit(
            operation="read_resource",
            run=lambda client: client.read_resource(uri),
        )
```

- [ ] **Step 3: Run source tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: pool test still fails until pool method is added; direct session read should pass.

---

### Task 4: Add `read_resource` to Runtime Pool

**Files:**
- Modify: `src/wf_sources_mcp/runtime/pool.py`

- [ ] **Step 1: Add pool method**

Add below `call_tool()`:

```python
    async def read_resource(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        uri: str,
    ) -> dict[str, Any]:
        session = await self.get_session(connection, auth)
        return await session.read_resource(uri)
```

- [ ] **Step 2: Run runtime tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py tests/wf_mcp/test_stateful_runtime.py -q
```

Expected: pass.

---

### Task 5: Verify Surface and Update Docs

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move after completion: `docs/superpowers/plans/2026-06-07-mcp-runtime-read-resource.md` to `docs/historical/superpowers/plans/2026-06-07-mcp-runtime-read-resource.md`

- [ ] **Step 1: Verify forbidden runtime methods remain absent**

Run:

```bash
rg -n "def (list_tools|list_resources|list_prompts|get_prompt|invoke_method|send_notification)" src/wf_sources_mcp/runtime
```

Expected: no matches. `read_resource` is now allowed.

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, under the MCP upstream source runtime cleanup bullets, add:

```markdown
   - Completed: persistent MCP runtime can now route `read_resource` through
     the owner-task queue and `McpSourceClient`. This is intentionally a thin
     wrapper over the existing source-client facade; prompt/raw method runtime
     operations remain separate future slices.
```

- [ ] **Step 3: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, add after the runtime operation queue item:

```markdown
11. Complete: persistent MCP runtime can route `read_resource` through the
    owner-task queue and `McpSourceClient`. Runtime still does not expose
    `get_prompt`, raw method invocation, or notifications.
```

Renumber following item if needed.

- [ ] **Step 4: Archive completed plan after implementation**

Run only after all code/tests pass:

```bash
git mv docs/superpowers/plans/2026-06-07-mcp-runtime-read-resource.md docs/historical/superpowers/plans/2026-06-07-mcp-runtime-read-resource.md
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
uv run basedpyright --level error tests/wf_sources_mcp/test_runtime.py tests/wf_mcp/test_stateful_runtime.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 4: Run focused lint**

Run:

```bash
uv run ruff check src/wf_sources_mcp/runtime tests/wf_sources_mcp/test_runtime.py tests/wf_mcp/test_stateful_runtime.py
```

Expected: `All checks passed!`

- [ ] **Step 5: Confirm no forbidden runtime expansion**

Run:

```bash
rg -n "def (list_tools|list_resources|list_prompts|get_prompt|invoke_method|send_notification)" src/wf_sources_mcp/runtime
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

- Spec coverage: The plan adds persistent resource reads through the existing generic queue and source-client facade while keeping the surface intentionally narrow.
- Placeholder scan: No placeholder steps remain.
- Type consistency: `read_resource` returns `dict[str, Any]` everywhere.
- Hard boundary: no prompt/raw-method/notification runtime methods are added.

