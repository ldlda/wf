# MCP Runtime RPC Session Reuse E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic JSON-RPC integration test proving MCP-backed workflow runs reuse one persistent `McpRuntimePool` session for repeated operations against the same source.

**Architecture:** The test should build a real MCP-backed `WorkflowServer`, inject a recording `McpRuntimePool` backed by a fake persistent MCP client, expose it through `create_rpc_app`, then drive the workflow lifecycle via `RpcWorkflowApiClient`. The assertion should be semantic: two workflow runs against the same MCP source reuse one created session and see incrementing session-local state.

**Tech Stack:** Python 3.14, pytest-asyncio, httpx `ASGITransport`, JSON-RPC app/client, `WfMcpService`, `McpRuntimePool`, `PersistentSessionFactory`, MCP SDK result models.

---

## Hard Boundaries

- Do not use live `pnpx` / everything-server in this deterministic test.
- Do not assert directly on private `McpRuntimePool._sessions` if a recording factory/client can prove reuse.
- Do not add public production hooks only for this test.
- Do not change JSON-RPC method names or payload shapes.
- Do not remove one-shot adapter fallback behavior.
- Do not add a direct JSON-RPC `call_capability` method in this slice.
- Do not commit unless the caller explicitly asks for a commit.

## File Map

- Modify `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`: add recording runtime fake and one integration test.
- Optionally modify `docs/current_roadmap.md`: mark runtime RPC reuse proof complete.
- Optionally modify `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`: mark QA proof complete.
- Move this plan to `docs/historical/superpowers/plans/` after implementation is verified.

---

## Test Design

The test should prove this complete path:

```text
RpcWorkflowApiClient
  -> JSON-RPC app
  -> WorkflowServer.api.run_deployment()
  -> WfMcpService / WorkflowOperationContext
  -> generated NodeSpec
  -> UpstreamTransportService.tool_executor_for()
  -> McpRuntimePool
  -> one PersistentMcpSession
  -> fake MCP client session-local counter
```

Use a fake MCP client whose `call_tool("counter", ...)` increments `self.count`.

Expected behavior:

- First workflow run returns `{"count": 1}`.
- Second workflow run returns `{"count": 2}`.
- Recording session factory created exactly one session.
- Fake client recorded two tool calls.

If the path accidentally uses one-shot sessions, the count will reset and the test will fail.

---

### Task 1: Add Recording Runtime Fakes

**Files:**
- Modify: `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

- [ ] **Step 1: Add imports**

Add imports needed for fake runtime and server construction:

```python
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, cast

from mcp.client.session import ClientSession
from mcp.types import CallToolResult, ListPromptsResult, ListResourcesResult, ListToolsResult, TextContent, Tool

from wf_authoring import build_async_registry
from wf_mcp.broker.server import workflow_server_from_service
from wf_mcp.broker.service import WfMcpService
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.runtime import McpRuntimePool
from wf_sources_mcp.runtime.factory import PersistentSessionFactory
from wf_sources_mcp.storage import FileAuthStore, FileCatalogStore, FileStore
```

Adjust imports to match existing ordering and avoid duplicates. If `build_async_registry` is not needed, omit it.

- [ ] **Step 2: Add fake MCP client**

Add near the existing helpers:

```python
@dataclass(slots=True)
class _CountingMcpClient:
    count: int = 0
    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name="counter",
                    title="Counter",
                    description="Increment a session-local counter.",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]
        )

    async def call_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
    ) -> CallToolResult:
        self.tool_calls.append((tool_name, payload))
        if tool_name != "counter":
            raise KeyError(tool_name)
        self.count += 1
        return CallToolResult(
            content=[TextContent(type="text", text=str(self.count))],
            structuredContent={"count": self.count},
        )

    async def list_resources(self) -> ListResourcesResult:
        return ListResourcesResult(resources=[])

    async def list_prompts(self) -> ListPromptsResult:
        return ListPromptsResult(prompts=[])
```

Do not implement methods the test does not use unless basedpyright requires them for `ClientSession` casts.

- [ ] **Step 3: Add recording factory**

```python
class _RecordingSessionFactory(PersistentSessionFactory):
    def __init__(self) -> None:
        self.clients: list[_CountingMcpClient] = []
        self.created_connections: list[McpSourceConnection] = []

    async def _create_with_stack(
        self,
        stack: AsyncExitStack,
        connection: McpSourceConnection,
        auth,
    ) -> ClientSession:
        self.created_connections.append(connection)
        client = _CountingMcpClient()
        self.clients.append(client)
        return cast(ClientSession, client)
```

- [ ] **Step 4: Run typecheck for the test file**

Run:

```bash
uv run basedpyright --level error tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
```

Expected: no errors. If `ClientSession` cast is not enough, add minimal methods to `_CountingMcpClient` or use `# type: ignore[return-value]` only with a comment explaining the fake implements the subset used by the runtime owner.

---

### Task 2: Build an MCP-Backed WorkflowServer With Recording Runtime

**Files:**
- Modify: `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

- [ ] **Step 1: Add helper to build server and factory**

Add:

```python
def _runtime_reuse_server(tmp_path):
    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[
            ConnectionConfig(
                id="fixture.default",
                server="fixture",
                account="default",
                metadata={
                    "transport": "stdio",
                    "command": "fake-mcp-server",
                },
            )
        ],
    )
    factory = _RecordingSessionFactory()
    runtime_pool = McpRuntimePool(factory.create)
    service = WfMcpService(
        store=FileStore(tmp_path / "mcp-store"),
        auth_store=FileAuthStore(tmp_path / "auth-store"),
        catalog_store=FileCatalogStore(tmp_path / "catalog-store"),
        artifact_store=...,  # use the same file stores that build_service_from_config would use
        draft_workspace_store=...,
        run_store=...,
        tool_executor=runtime_pool,
        stateful_runtime=runtime_pool,
    )
    service.register_connection(config.connections[0])
    return workflow_server_from_service(
        service,
        config=config,
        source_registry_store=FileSourceRegistryStore(config.store_roots.source_registry_root),
    ), service, factory
```

Use existing store constructors already used in this test module or adjacent tests:

- `FileWorkflowArtifactStore`
- `FileDraftWorkspaceStore`
- `FileRunStore`

If `BrokerConfig.__post_init__` fills `store_roots`, use `config.store_roots.source_registry_root`. If basedpyright cannot narrow `store_roots`, assert it is not `None`.

- [ ] **Step 2: Refresh catalog before RPC lifecycle**

Inside the helper or the test, call:

```python
await service.refresh_connection_catalog("fixture.default")
```

This should use `stateful_runtime.list_tools()` and create the first persistent session. Do not register an adapter for `"fixture"`; that way the test fails if refresh tries the one-shot fallback.

- [ ] **Step 3: Verify catalog refresh uses one session**

After refresh:

```python
assert len(factory.clients) == 1
assert factory.created_connections[0].id == "fixture.default"
```

---

### Task 3: Drive Workflow Lifecycle Through JSON-RPC

**Files:**
- Modify: `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

- [ ] **Step 1: Add test skeleton**

Add:

```python
async def test_mcp_backed_rpc_workflow_reuses_runtime_session_across_runs(tmp_path) -> None:
    server, service, factory = _runtime_reuse_server(tmp_path)
    await service.refresh_connection_catalog("fixture.default")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_rpc_app(server)),
        base_url="http://test",
    ) as http_client:
        client = RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)
        ...
```

- [ ] **Step 2: Use RPC to create a draft from the discovered capability**

Call:

```python
created = await client.create_draft_workspace_from_capability(
    workspace_id="counter_ws",
    capability_name="fixture.default.counter",
    name="counter_workflow",
    title="Counter Workflow",
)
```

Assert:

```python
assert created["workspace_id"] == "counter_ws"
assert created["status"] == "valid"
```

If exact response keys differ, inspect existing draft RPC tests and assert stable public fields only.

- [ ] **Step 3: Use RPC to save an artifact**

Call:

```python
artifact = await client.create_artifact_from_workspace(
    workspace_id="counter_ws",
    artifact_id="counter_workflow",
    version=1,
    title="Counter Workflow",
    outcomes=["ok", "error"],
    kind="workflow",
)
```

Assert artifact ID/version from the response. If draft validation requires explicit outcomes from the capability, use the outcomes exposed by `wrap_discovered_tool` (`ok`, `error`).

- [ ] **Step 4: Use RPC to save a deployment**

Call:

```python
deployment = await client.save_deployment(
    {
        "id": "counter_workflow.default",
        "artifact_id": "counter_workflow",
        "artifact_version": 1,
        "bindings": [
            {"logical_source": "fixture.default", "concrete_source": "fixture.default"}
        ],
    }
)
```

If the artifact has no logical source binding because it was created directly from a concrete capability, use `bindings=[]`. Prefer following the artifact response's `required_logical_sources` if present.

- [ ] **Step 5: Run deployment twice through RPC**

Call:

```python
first = await client.run_deployment(
    deployment_id="counter_workflow.default",
    workflow_input={},
)
second = await client.run_deployment(
    deployment_id="counter_workflow.default",
    workflow_input={},
)
```

Assert:

```python
assert first["status"] == "completed"
assert second["status"] == "completed"
assert first["output"]["count"] == 1
assert second["output"]["count"] == 2
```

If output is nested under a generated field, inspect the actual result once and assert the stable output path.

- [ ] **Step 6: Assert runtime reuse**

After both runs:

```python
assert len(factory.clients) == 1
assert len(factory.created_connections) == 1
assert factory.clients[0].tool_calls == [
    ("counter", {}),
    ("counter", {}),
]
```

If refresh catalog creates one session and tool calls happen on the same client, this proves discovery + two runs all shared the same persistent session.

---

### Task 4: Fallback If Draft Synthesis Is Too Noisy

**Files:**
- Modify: `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

Only use this task if Task 3 gets blocked by draft synthesis details.

- [ ] **Step 1: Prepare artifact/deployment directly**

Use `server.api` directly to create the artifact/deployment after catalog refresh, then still run the deployment twice through `RpcWorkflowApiClient`.

This fallback still proves the product run path:

```text
JSON-RPC runs.start -> WorkflowApi -> generated NodeSpec -> McpRuntimePool
```

It does not prove draft/artifact RPC creation. That is acceptable if documented in the report.

- [ ] **Step 2: Keep the same runtime reuse assertions**

Do not weaken the session reuse assertions. The test must still prove one created client and two tool calls.

---

### Task 5: Docs and Plan Archive

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Move: `docs/superpowers/plans/2026-06-08-mcp-runtime-rpc-session-reuse-e2e.md` to `docs/historical/superpowers/plans/2026-06-08-mcp-runtime-rpc-session-reuse-e2e.md`

- [ ] **Step 1: Update roadmap**

Add:

```markdown
      JSON-RPC MCP-backed workflow runs now have deterministic session-reuse
      coverage: repeated runs against one source use one `McpRuntimePool`
      session and preserve session-local state.
```

- [ ] **Step 2: Update boundary spec**

Add a completed QA item after the full-operation-surface item:

```markdown
25. Complete: deterministic JSON-RPC integration coverage proves MCP-backed
    workflow runs reuse one persistent runtime session for repeated operations
    against the same source.
```

- [ ] **Step 3: Archive plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-08-mcp-runtime-rpc-session-reuse-e2e.md docs/historical/superpowers/plans/2026-06-08-mcp-runtime-rpc-session-reuse-e2e.md
```

---

### Task 6: Verification

**Files:**
- No code edits unless verification finds a real issue.

- [ ] **Step 1: Run new test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py::test_mcp_backed_rpc_workflow_reuses_runtime_session_across_runs -q
```

Expected: pass.

- [ ] **Step 2: Run broader RPC and runtime tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py tests/wf_sources_mcp/test_runtime.py tests/wf_mcp/service/test_upstream_transport.py -q
```

Expected: pass.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
```

Expected: source/test lint passes. If ruff does not support markdown without preview mode in this repo, run it on the Python test file only and report the markdown limitation.

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 5: Optional live smoke**

If `.env` has `MCP_EVERYTHING_COMMAND` or `MCP_EVERYTHING_URL`, run:

```bash
uv run --env-file .env pytest tests/wf_mcp/test_sdk_adapter.py::test_mcp_sdk_adapter_can_probe_everything_server -q
```

Expected: pass or skip only for environment permission issues.

- [ ] **Step 6: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings on Windows are acceptable.

---

## Expected Final Report

The implementer should report:

- Files modified and moved.
- Whether the test used full RPC draft/artifact/deployment setup or the direct setup fallback.
- Exact verification commands and outputs.
- Confirmation that repeated JSON-RPC workflow runs reuse one recording runtime session.
- Confirmation that the test does not use live external MCP servers.
- Any deviations from this plan.

Do not claim "full suite passed" unless the full suite was actually run.
