# Stateful Runtime E2E Gap Audit

**Date:** 2026-06-08
**Auditor:** opencode
**Goal:** Design smallest e2e test proving JSON-RPC/CLI-backed workflow server uses shared `McpRuntimePool` instead of one-shot `McpSdkAdapter` sessions.

---

## 1. Current Call Chain for Tool/Resource/Prompt Operations

### Tool Calls (Workflow Node Execution)

```
JSON-RPC request
  → RpcWorkflowApiClient.call_capability()
    → WorkflowServer.api.call_capability()
      → SourceCatalogService.get_qualified_spec(qualified_name)
        → spec.fn(payload)  # NodeSpec function
          → tool_executor_for(connection).call_tool(...)
            → UpstreamTransportService.tool_executor_for()
              → self.tool_executor (McpRuntimePool) or require_adapter()
                → McpRuntimePool.call_tool()
                  → get_session()  # fingerprint-based reuse
                    → PersistentMcpSession.call_tool()
                      → _SessionOwner.submit()  # owner-task queue
```

**Key files:**

- `src/wf_transport_rpc_http/methods_capabilities.py` - RPC entry point
- `src/wf_mcp/broker/service/workflow_operation_context.py:78-86` - context_from_service
- `src/wf_mcp/broker/service/source_catalog.py:257-298` - spec_from_snapshot_entry (hydrated specs)
- `src/wf_mcp/broker/service/upstream_transport.py:86-95` - tool_executor_for()
- `src/wf_sources_mcp/runtime/pool.py:50-55` - McpRuntimePool.call_tool()
- `src/wf_sources_mcp/runtime/pool.py:36-48` - McpRuntimePool.get_session()
- `src/wf_sources_mcp/runtime/factory.py:82-160` - _SessionOwner (owner-task queue)

### Resource Reads

```
ContentAccessService.read_resource(qualified_name)
  → SourceCatalogService.get_resource(qualified_name)
  → ConnectionService.get(connection_id)
  → UpstreamTransportService.read_resource(connection, qualified_name, uri)
    → self.stateful_runtime.read_resource(...)  # preferred
    → adapter.read_resource(...)                 # fallback
```

**Key files:**

- `src/wf_mcp/broker/service/content_access.py:30-52` - read_resource()
- `src/wf_mcp/broker/service/upstream_transport.py:97-126` - read_resource()

### Prompt Renders

```
ContentAccessService.render_prompt(qualified_name, arguments)
  → SourceCatalogService.get_prompt(qualified_name)
  → ConnectionService.get(connection_id)
  → UpstreamTransportService.render_prompt(connection, qualified_name, local_name, arguments)
    → self.stateful_runtime.get_prompt(...)  # preferred
    → adapter.get_prompt(...)                 # fallback
```

**Key files:**

- `src/wf_mcp/broker/service/content_access.py:54-82` - render_prompt()
- `src/wf_mcp/broker/service/upstream_transport.py:128-163` - render_prompt()

---

## 2. Where Stateful Runtime Is Used vs One-Shot Adapter Fallback

### Stateful Runtime Usage (McpRuntimePool)

| Operation | Where | Condition |
|-----------|-------|-----------|
| Tool calls (workflow nodes) | `source_catalog.py:279` via `tool_executor_for()` | `tool_executor is not None` |
| Resource reads | `upstream_transport.py:117-121` | `stateful_runtime is not None` |
| Prompt renders | `upstream_transport.py:151-157` | `stateful_runtime is not None` |
| Catalog refresh specs | `upstream_transport.py:258` via `tool_executor_for()` | `tool_executor is not None` |

### One-Shot Adapter Fallback (McpSdkAdapter)

| Operation | Where | Condition |
|-----------|-------|-----------|
| Discovery (list_tools/resources/prompts) | `upstream_transport.py:256-258` | Always uses `require_adapter()` |
| Live source checks | `upstream_transport.py:292-298` | Always uses `require_adapter()` |
| Raw method invocation | `upstream_transport.py:165-178` | Always uses `require_adapter()` |
| Notifications | `upstream_transport.py:180-197` | Always uses `require_adapter()` |
| Resource reads (no pool) | `upstream_transport.py:123-124` | `stateful_runtime is None` |
| Prompt renders (no pool) | `upstream_transport.py:159-160` | `stateful_runtime is None` |

### Configuration Wiring

```python
# src/wf_mcp/broker/config.py:182-186
service = WfMcpService(
    ...
    tool_executor=runtime_pool,      # McpRuntimePool
    stateful_runtime=runtime_pool,   # McpRuntimePool (same instance)
)
```

---

## 3. Smallest Reliable Test Design

### Test Objective

Prove that two sequential `call_capability` RPC requests through the JSON-RPC server share the same underlying MCP session, rather than opening a new session per request.

### Test Implementation

```python
# tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py

async def test_rpc_workflow_shares_mcp_runtime_session_across_tool_calls(tmp_path) -> None:
    """Prove JSON-RPC-backed workflow server uses shared McpRuntimePool."""
    # 1. Build server from config (wires McpRuntimePool)
    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[
            ConnectionConfig(
                id="fixture.personal",
                server="fixture",
                account="personal",
                metadata={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [fixture_server_path()],
                },
            )
        ],
    )
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)
    
    # 2. Track session creation via pool's internal state
    pool = server.context.specs  # Access through context
    # ... or access via service.upstream.tool_executor
    
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc",
            http_client=http_client,
        )
        
        # 3. First tool call - creates session
        first = await client.call_capability(
            qualified_name="fixture.personal.echo_tool",
            payload={"text": "one"},
        )
        
        # 4. Second tool call - should reuse session
        second = await client.call_capability(
            qualified_name="fixture.personal.echo_tool",
            payload={"text": "two"},
        )
    
    # 5. Verify same session was used (pool has exactly 1 session)
    assert first["outcome"] == "ok"
    assert second["outcome"] == "ok"
    assert len(pool._sessions) == 1  # Key assertion
```

### Alternative: Session Counter Approach

If pool internals aren't accessible, use a recording factory:

```python
async def test_rpc_server_uses_shared_runtime_pool(tmp_path) -> None:
    session_creations = 0
    
    class CountingSessionFactory:
        async def create(self, connection, auth):
            nonlocal session_creations
            session_creations += 1
            # ... create real session
    
    # Inject counting factory into pool
    # ... then verify session_creations == 1 after multiple tool calls
```

---

## 4. Blockers and Fake/Test Hooks Needed

### Blockers

1. **Pool internals not directly accessible from RPC test**
   - `WorkflowServer` wraps `WfMcpService` via `context_from_service()`
   - Pool is buried in `service.upstream.tool_executor`
   - Need to extract pool reference for assertion

2. **Existing test is close but not JSON-RPC**
   - `test_server_reuses_real_upstream_session_across_workflow_requests()` in `tests/wf_mcp/server/test_config.py:121-147` tests via MCP client, not JSON-RPC
   - Needs adaptation for RPC transport

### Fake/Test Hooks Needed

1. **Session creation counter** (preferred)
   - Add optional `on_session_created` callback to `McpRuntimePool`
   - Or expose `_sessions` for test inspection

2. **Recording factory** (alternative)
   - Create `RecordingSessionFactory` that counts invocations
   - Inject into pool during test setup

3. **Pool reference accessor**
   - Add `get_pool()` method to `WfMcpService` or expose via property
   - Or access via `service.upstream.tool_executor`

---

## 5. Exact Files/Tests Likely to Change

### Files to Modify

| File | Change |
|------|--------|
| `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py` | Add new e2e test |
| `src/wf_sources_mcp/runtime/pool.py` | Add optional session counter (minimal) |

### Tests to Add/Modify

| Test | Status | Purpose |
|------|--------|---------|
| `test_rpc_workflow_shares_mcp_runtime_session_across_tool_calls` | **NEW** | Prove JSON-RPC uses shared pool |
| `test_server_reuses_real_upstream_session_across_workflow_requests` | Existing | Already tests MCP client path |

### Files to Inspect (No Changes)

- `src/wf_mcp/broker/config.py:182-186` - Pool wiring (already correct)
- `src/wf_mcp/broker/service/upstream_transport.py:86-95` - tool_executor_for (already routes to pool)
- `src/wf_sources_mcp/runtime/pool.py:36-48` - get_session (fingerprint-based reuse)
- `src/wf_mcp/broker/service/source_catalog.py:279` - Hydrated spec tool call routing

---

## 6. Verification Commands

```bash
# Run existing related tests
uv run pytest tests/wf_mcp/server/test_config.py::test_server_reuses_real_upstream_session_across_workflow_requests -q
uv run pytest tests/wf_mcp/test_stateful_runtime.py -q
uv run pytest tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q

# After adding new test
uv run pytest tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py::test_rpc_workflow_shares_mcp_runtime_session_across_tool_calls -q

# Type checking
uv run basedpyright --level error
uv run ruff check
uv run ruff format
```

---

## 7. Summary

**Current State:** The wiring is correct. `McpRuntimePool` is configured as both `tool_executor` and `stateful_runtime` in config-built services. The pool's `get_session()` method reuses sessions based on connection fingerprint.

**Gap:** No JSON-RPC-specific test proves this reuse. Existing tests cover MCP client path and unit-level pool behavior, but not the full RPC transport stack.

**Smallest Fix:** Add one e2e test in `test_mcp_backed_server_rpc.py` that:

1. Builds server from config
2. Makes two `call_capability` RPC requests
3. Asserts pool has exactly 1 session (not 2)

**Estimated Effort:** ~30 lines of test code + optional pool counter hook.
