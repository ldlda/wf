# MCP Runtime Get Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent MCP runtime support for `get_prompt()` by routing it through the existing owner-task operation queue and `McpSourceClient`.

**Architecture:** This is the second safe non-tool runtime operation after `read_resource`. It stays a thin wrapper over `McpSourceClient.get_prompt()` and returns serialized `dict[str, Any]`. Raw method invocation, notifications, and discovery lists remain separate future decisions.

**Tech Stack:** Python 3.14, MCP Python SDK, pytest/pytest-asyncio, ruff, basedpyright.

---

## File Structure

- Modify `src/wf_sources_mcp/runtime/factory.py`
  - Add `_SessionOwner.get_prompt(prompt_name, arguments=None)`.
  - Implement through `submit(operation="get_prompt", run=lambda client: client.get_prompt(prompt_name, arguments))`.
- Modify `src/wf_sources_mcp/runtime/session.py`
  - Add `RawPromptGetter` callback type.
  - Add `get_prompt_callback` field.
  - Add `get_prompt(prompt_name, arguments=None)` method.
  - Keep fallback `client.get_prompt()` serialization for injected/fake sessions.
- Modify `src/wf_sources_mcp/runtime/pool.py`
  - Add `McpRuntimePool.get_prompt(connection, auth, prompt_name, arguments=None)`.
- Modify tests:
  - `tests/wf_sources_mcp/test_runtime.py`
  - `tests/wf_mcp/test_stateful_runtime.py` only if type compatibility requires it.
- Update docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

## Hard Boundaries

- Do not add persistent runtime `invoke_method`, `send_notification`, or discovery list methods.
- Do not expose raw `ClientSession` outside the owner task.
- Do not return raw MCP SDK result models from `get_prompt`; return serialized `dict[str, Any]`.
- Do not alter `McpSourceClient.get_prompt()` behavior.
- Do not dispatch by string; `operation="get_prompt"` is metadata only.

---

### Task 1: Add Persistent Prompt Tests

**Files:**
- Modify: `tests/wf_sources_mcp/test_runtime.py`

- [ ] **Step 1: Extend fake client with prompt gets**

In `tests/wf_sources_mcp/test_runtime.py`, update `_FakeFactory._create_with_stack()`'s `_FakeClient` class to include:

```python
            async def get_prompt(
                self,
                prompt_name: str,
                arguments: dict[str, str] | None = None,
            ):
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
```

- [ ] **Step 2: Add error-path test**

Append to `tests/wf_sources_mcp/test_runtime.py`:

```python
@pytest.mark.asyncio
async def test_persistent_session_raises_without_prompt_transport() -> None:
    session = PersistentMcpSession(connection=_connection(), auth=None)

    with pytest.raises(RuntimeError, match="no prompt transport"):
        await session.get_prompt("prompt.summarize")
```

- [ ] **Step 3: Add session-level persistent prompt test**

Append:

```python
@pytest.mark.asyncio
async def test_persistent_session_factory_routes_prompts_through_owner() -> None:
    factory = _FakeFactory()
    connection = _connection()
    session = await factory.create(connection, None)

    await session.call_tool("echo", {"text": "one"})
    await session.read_resource("fixture://docs/welcome")
    prompt_payload = await session.get_prompt(
        "prompt.summarize",
        {"text": "hello"},
    )
    await session.close()

    assert factory.created_connections == [connection]
    assert factory.calls == [("echo", {"text": "one"})]
    assert prompt_payload["messages"][0]["content"]["text"] == (
        "prompt.summarize:{'text': 'hello'}"
    )
```

- [ ] **Step 4: Add pool-level persistent prompt test**

Append:

```python
@pytest.mark.asyncio
async def test_runtime_pool_reuses_session_for_tool_resource_and_prompt() -> None:
    factory = _FakeFactory()
    pool = McpRuntimePool(factory.create)
    connection = _connection()

    tool_result = await pool.call_tool(connection, None, "echo", {"text": "one"})
    resource_payload = await pool.read_resource(
        connection,
        None,
        "fixture://docs/welcome",
    )
    prompt_payload = await pool.get_prompt(
        connection,
        None,
        "prompt.summarize",
        {"text": "hello"},
    )
    await pool.close_all()

    assert tool_result.output == {"echoed": "one"}
    assert resource_payload["contents"][0]["text"] == "resource text"
    assert prompt_payload["messages"][0]["content"]["text"] == (
        "prompt.summarize:{'text': 'hello'}"
    )
    assert factory.created_connections == [connection]
```

- [ ] **Step 5: Update public surface test**

Update `test_persistent_session_public_runtime_exposes_only_tool_and_resource_read` to allow `get_prompt` and still forbid the rest:

```python
def test_persistent_session_public_runtime_exposes_safe_read_operations() -> None:
    public_operations = {
        name
        for name in dir(PersistentMcpSession)
        if not name.startswith("_") and callable(getattr(PersistentMcpSession, name))
    }

    assert "call_tool" in public_operations
    assert "read_resource" in public_operations
    assert "get_prompt" in public_operations
    assert "invoke_method" not in public_operations
    assert "send_notification" not in public_operations
```

- [ ] **Step 6: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: fail because `PersistentMcpSession.get_prompt` and `McpRuntimePool.get_prompt` do not exist yet.

---

### Task 2: Add `get_prompt` to Persistent Session

**Files:**
- Modify: `src/wf_sources_mcp/runtime/session.py`

- [ ] **Step 1: Add callback type**

Add near existing callback types:

```python
RawPromptGetter = Callable[
    [str, dict[str, str] | None],
    Awaitable[dict[str, Any]],
]
```

- [ ] **Step 2: Add callback field**

In `PersistentMcpSession`, add:

```python
    get_prompt_callback: RawPromptGetter | None = None
```

- [ ] **Step 3: Add `get_prompt` method**

Add below `read_resource()`:

```python
    async def get_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Get an MCP prompt through the owner task or injected session."""
        if self.get_prompt_callback is not None:
            return await self.get_prompt_callback(prompt_name, arguments)
        if self.client is not None:
            result = await self.client.get_prompt(prompt_name, arguments)
            return result.model_dump(by_alias=True, mode="json", exclude_none=True)
        raise RuntimeError("persistent MCP session has no prompt transport")
```

- [ ] **Step 4: Run source tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: still fail at factory/pool routing until callbacks are wired.

---

### Task 3: Route `get_prompt` Through Owner Queue

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
            get_prompt_callback=owner.get_prompt,
            close_callback=owner.close,
        )
```

- [ ] **Step 2: Add owner `get_prompt()`**

Add below `_SessionOwner.read_resource()`:

```python
    async def get_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Submit a prompt get through the generic owner-task operation queue."""
        return await self.submit(
            operation="get_prompt",
            run=lambda client: client.get_prompt(prompt_name, arguments),
        )
```

- [ ] **Step 3: Run source tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_runtime.py -q
```

Expected: pool test still fails until pool method is added; direct session prompt should pass.

---

### Task 4: Add `get_prompt` to Runtime Pool

**Files:**
- Modify: `src/wf_sources_mcp/runtime/pool.py`

- [ ] **Step 1: Add pool method**

Add below `read_resource()`:

```python
    async def get_prompt(
        self,
        connection: McpSourceConnection,
        auth: AuthRecord | None,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        session = await self.get_session(connection, auth)
        return await session.get_prompt(prompt_name, arguments)
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
- Move after completion: `docs/superpowers/plans/2026-06-07-mcp-runtime-get-prompt.md` to `docs/historical/superpowers/plans/2026-06-07-mcp-runtime-get-prompt.md`

- [ ] **Step 1: Verify forbidden runtime methods remain absent**

Run:

```bash
rg -n "def (list_tools|list_resources|list_prompts|invoke_method|send_notification)" src/wf_sources_mcp/runtime
```

Expected: no matches. `read_resource` and `get_prompt` are now allowed.

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, under the MCP upstream source runtime cleanup bullets, add:

```markdown
   - Completed: persistent MCP runtime can now route `get_prompt` through
     the owner-task queue and `McpSourceClient`. This keeps prompt reads
     stateful without adding raw method invocation or notification support.
```

- [ ] **Step 3: Update long-lived API boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, add after the `read_resource` runtime item:

```markdown
12. Complete: persistent MCP runtime can route `get_prompt` through the
    owner-task queue and `McpSourceClient`. Runtime still does not expose raw
    method invocation, notifications, or discovery list operations.
```

Renumber following item if needed.

- [ ] **Step 4: Archive completed plan after implementation**

Run only after all code/tests pass:

```bash
git mv docs/superpowers/plans/2026-06-07-mcp-runtime-get-prompt.md docs/historical/superpowers/plans/2026-06-07-mcp-runtime-get-prompt.md
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
rg -n "def (list_tools|list_resources|list_prompts|invoke_method|send_notification)" src/wf_sources_mcp/runtime
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

- Spec coverage: The plan adds persistent prompt gets through the existing generic queue and source-client facade while keeping the surface narrow.
- Placeholder scan: No placeholder steps remain.
- Type consistency: `get_prompt` returns `dict[str, Any]` everywhere and accepts `dict[str, str] | None` arguments.
- Hard boundary: no raw method, notification, or discovery-list runtime methods are added.

