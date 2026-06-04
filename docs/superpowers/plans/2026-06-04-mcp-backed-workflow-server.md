# MCP-Backed Workflow Server Construction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a concrete MCP-backed `WorkflowServer` composition so JSON-RPC/CLI can target a long-lived server with real MCP broker sources, admin data, and source-registry mutation.

**Architecture:** Keep `wf_server` transport-neutral and MCP-free. Add the MCP-specific constructor in `wf_mcp`, adapting an existing `WfMcpService` into the neutral `WorkflowServer` dataclass using `context_from_service`, `WorkflowApi`, `WorkflowAdminApi`, `WorkflowSourceAdminApi`, and `WorkflowSourceRegistryApi`. This proves remote RPC can use MCP-backed source registry/admin surfaces without making `wf_server` depend on `WfMcpService`.

**Tech Stack:** Python 3.14, dataclasses, Pydantic v2 models, `wf_api`, `wf_server`, `wf_mcp` broker services, `wf_transport_rpc_http`, pytest-asyncio, ruff, basedpyright.

---

## Current Context

Implemented pieces:

- `wf_server.context.WorkflowServer` is the neutral process-host shape.
- `wf_server.build_local_static_workflow_server()` builds a local/static server and intentionally leaves `source_registry_admin=None`.
- `wf_mcp.broker.config.build_service_from_config(config)` builds a `WfMcpService` with workflow stores, MCP adapters, source-registry startup merge, and configured connections.
- `wf_mcp.broker.service.workflow_operation_context.context_from_service(service)` adapts `WfMcpService` into a neutral `WorkflowOperationContext`.
- `wf_mcp.broker.service.source_registry_admin.SourceRegistryAdminProvider` provides desired-registry reads/mutations over `FileSourceRegistryStore`.
- `wf_transport_rpc_http.create_rpc_app(server)` registers workflow, source, source-registry, and admin JSON-RPC methods over any `WorkflowServer`.

Boundary rule:

- `wf_server` must not import `wf_mcp`.
- The MCP-backed constructor belongs in `wf_mcp` and returns a `wf_server.WorkflowServer`.

Out of scope:

- No new HTTP server process CLI.
- No hot reload/live remount after registry mutation.
- No auth redesign.
- No WebSocket/MCP transport sibling.
- No persisted run/resume process-restart implementation.

---

## File Structure

- Create `src/wf_mcp/broker/server.py`
  - MCP-specific adapter constructors returning `WorkflowServer`.
  - Wires `WorkflowApi`, source admin, admin, and desired source registry admin.
  - Keeps the dependency direction `wf_mcp -> wf_server`, not `wf_server -> wf_mcp`.
- Modify `src/wf_mcp/broker/__init__.py`
  - Re-export the constructor for callers/tests.
- Modify `src/wf_server/__init__.py`
  - No MCP import. Only add exports if current `WorkflowServerConfig` is not exported and tests need it.
- Test `tests/wf_mcp/test_mcp_workflow_server.py`
  - Direct construction tests for the MCP-backed server adapter.
- Test `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`
  - RPC tests proving source-registry read/mutation and admin connections work against the MCP-backed server.
- Modify `docs/current_roadmap.md`
  - Mark concrete MCP-backed `WorkflowServer` construction complete.
- Modify `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
  - Add implementation status for this slice.

---

### Task 1: Add MCP-Backed Server Adapter

**Files:**
- Create: `src/wf_mcp/broker/server.py`
- Modify: `src/wf_mcp/broker/__init__.py`
- Test: `tests/wf_mcp/test_mcp_workflow_server.py`

- [ ] **Step 1: Write direct construction tests**

Create `tests/wf_mcp/test_mcp_workflow_server.py`:

```python
from __future__ import annotations

import ast

from wf_mcp.broker.config import build_service_from_config
from wf_mcp.broker.server import (
    build_workflow_server_from_config,
    workflow_server_from_service,
)
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
)
from wf_server import WorkflowServer


def _registry_entry(source_id: str) -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry.model_validate(
        {
            "id": source_id,
            "kind": "mcp",
            "enabled": True,
            "provider": "demo",
            "account": "registry",
            "transport": {"kind": "stdio", "command": "demo-server"},
        }
    )


def test_wf_server_package_stays_mcp_free() -> None:
    path = "src/wf_server/context.py"
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("wf_mcp"):
                violations.append(f"{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("wf_mcp"):
                    violations.append(f"{node.lineno}: import {alias.name}")

    assert violations == []


def test_workflow_server_from_service_wires_neutral_surfaces(tmp_path) -> None:
    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[
            ConnectionConfig(id="demo.default", server="demo", account="default")
        ],
    )
    service = build_service_from_config(config)

    server = workflow_server_from_service(
        service,
        config=config,
        source_registry_store=FileSourceRegistryStore(config.store_root),
    )

    assert isinstance(server, WorkflowServer)
    assert server.config.store_root == config.store_root
    assert server.api.context is server.context
    assert server.source_registry_admin is not None
    assert server.admin.connections is service.connection_service
    assert server.admin.events is service.events


def test_build_workflow_server_from_config_exposes_registry_admin(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    FileSourceRegistryStore(config.store_root).save_registry(
        SourceRegistryFile(sources=[_registry_entry("demo.registry")])
    )

    server = build_workflow_server_from_config(config)

    assert server.source_registry_admin is not None
    assert "demo.registry" in server.context.specs.capability_sources
```

Run:

```bash
uv run pytest tests/wf_mcp/test_mcp_workflow_server.py -q
```

Expected: FAIL because `wf_mcp.broker.server` does not exist.

- [ ] **Step 2: Implement `src/wf_mcp/broker/server.py`**

Create `src/wf_mcp/broker/server.py`:

```python
from __future__ import annotations

from wf_api import (
    WorkflowAdminApi,
    WorkflowApi,
    WorkflowSourceAdminApi,
    WorkflowSourceRegistryApi,
    durable_workflow_api,
)
from wf_api.stores import WorkflowStores
from wf_server import WorkflowServer, WorkflowServerConfig

from .config import build_service_from_config
from .service import WfMcpService
from .service.source_registry_admin import SourceRegistryAdminProvider
from .service.workflow_operation_context import context_from_service
from ..models import BrokerConfig
from ..source_registry import FileSourceRegistryStore, SourceRegistryStore


def workflow_server_from_service(
    service: WfMcpService,
    *,
    config: BrokerConfig,
    source_registry_store: SourceRegistryStore,
) -> WorkflowServer:
    """Adapt an MCP broker service into the neutral WorkflowServer shape.

    This is intentionally in wf_mcp, not wf_server: MCP owns upstream source
    management, while wf_server stays transport-neutral and MCP-free.
    """
    context = context_from_service(service)
    api: WorkflowApi = durable_workflow_api(context)
    source_admin = WorkflowSourceAdminApi(context)
    admin = WorkflowAdminApi(
        connections=service.connection_service,
        events=service.events,
    )
    source_registry_admin = WorkflowSourceRegistryApi(
        provider=SourceRegistryAdminProvider(
            source_registry_store=source_registry_store,
            config_connections=config.connections,
        ),
        mutation_provider=SourceRegistryAdminProvider(
            source_registry_store=source_registry_store,
            config_connections=config.connections,
        ),
    )
    stores = WorkflowStores(
        artifact_store=service.artifact_store,
        draft_workspace_store=service.draft_workspace_store,
        run_store=service.run_store,
    )
    return WorkflowServer(
        config=WorkflowServerConfig(store_root=config.store_root),
        stores=stores,
        context=context,
        api=api,
        source_admin=source_admin,
        admin=admin,
        events=service.events,
        source_registry_admin=source_registry_admin,
    )


def build_workflow_server_from_config(config: BrokerConfig) -> WorkflowServer:
    """Build a neutral WorkflowServer backed by MCP broker runtime services."""
    service = build_service_from_config(config)
    return workflow_server_from_service(
        service,
        config=config,
        source_registry_store=FileSourceRegistryStore(config.store_root),
    )


__all__ = [
    "build_workflow_server_from_config",
    "workflow_server_from_service",
]
```

If basedpyright rejects `WorkflowStores(...)` because stores are optional on
`WfMcpService`, add explicit fail-fast guards before constructing it:

```python
if (
    service.artifact_store is None
    or service.draft_workspace_store is None
    or service.run_store is None
):
    raise ValueError("MCP-backed WorkflowServer requires workflow stores")
```

- [ ] **Step 3: Re-export the constructor**

Modify `src/wf_mcp/broker/__init__.py` to export:

```python
from .server import build_workflow_server_from_config, workflow_server_from_service

__all__ = [
    # keep existing exports here
    "build_workflow_server_from_config",
    "workflow_server_from_service",
]
```

Do not remove existing exports. If the file currently has no `__all__`, add only
the imports and let existing import behavior continue.

- [ ] **Step 4: Run direct construction tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_mcp_workflow_server.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/wf_mcp/broker/server.py src/wf_mcp/broker/__init__.py tests/wf_mcp/test_mcp_workflow_server.py
git commit -m "feat: build mcp backed workflow server"
```

---

### Task 2: Prove JSON-RPC Uses MCP-Backed Registry and Admin Surfaces

**Files:**
- Create: `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

- [ ] **Step 1: Write RPC integration tests**

Create `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`:

```python
from __future__ import annotations

import httpx

from wf_mcp.broker.server import build_workflow_server_from_config
from wf_mcp.models import BrokerConfig, ConnectionConfig
from wf_mcp.source_registry import (
    FileSourceRegistryStore,
    McpSourceRegistryEntry,
    SourceRegistryFile,
)
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app


def _registry_entry(source_id: str, *, enabled: bool = True) -> McpSourceRegistryEntry:
    return McpSourceRegistryEntry.model_validate(
        {
            "id": source_id,
            "kind": "mcp",
            "enabled": enabled,
            "provider": "demo",
            "account": "registry",
            "transport": {"kind": "stdio", "command": "demo-server"},
        }
    )


async def _rpc(client: httpx.AsyncClient, method: str, params: dict) -> dict:
    response = await client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": "test", "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


async def test_mcp_backed_rpc_lists_and_mutates_source_registry(tmp_path) -> None:
    config = BrokerConfig(store_root=tmp_path / "store", connections=[])
    FileSourceRegistryStore(config.store_root).save_registry(
        SourceRegistryFile(sources=[_registry_entry("demo.registry")])
    )
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(http_client)

        listed = await client.list_registry_entries(limit=10)
        disabled = await client.disable_registry_entry("demo.registry")
        inspected = await client.inspect_registry_entry("demo.registry")

    assert listed["entries"][0]["id"] == "demo.registry"
    assert disabled["entry"]["enabled"] is False
    assert inspected["entry"]["enabled"] is False


async def test_mcp_backed_rpc_reports_connections_and_events(tmp_path) -> None:
    config = BrokerConfig(
        store_root=tmp_path / "store",
        connections=[
            ConnectionConfig(
                id="demo.default",
                server="demo",
                account="default",
            )
        ],
    )
    server = build_workflow_server_from_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        connections = await _rpc(
            http_client, "workflow.admin.connections.list", {"limit": 20}
        )
        events = await _rpc(http_client, "workflow.admin.events.list", {"limit": 20})

    assert connections["result"]["connections"][0]["id"] == "demo.default"
    assert any(
        event["kind"] == "connection_registered"
        for event in events["result"]["events"]
    )
```

If `RpcWorkflowApiClient` method names differ, inspect
`src/wf_transport_rpc_http/client_source_registry.py` and use the exact names.
Do not change client method names in this slice unless the tests reveal a real
bug.

- [ ] **Step 2: Run RPC integration tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
```

Expected: PASS after Task 1.

- [ ] **Step 3: Commit**

```bash
git add tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
git commit -m "test: cover mcp backed workflow server rpc"
```

---

### Task 3: Add Server Construction Docs Status

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

- [ ] **Step 1: Update current roadmap**

In `docs/current_roadmap.md`, under **Durable API service shape**, replace the
remaining "concrete MCP-backed `WorkflowServer` construction remains future
work" language with:

```markdown
   - Completed: MCP-backed `WorkflowServer` construction is available through
      `wf_mcp.broker.server.build_workflow_server_from_config`. JSON-RPC can now
      expose real MCP-backed workflow, source-admin, admin, and desired source
      registry surfaces without making `wf_server` import `wf_mcp`.
```

Keep any longer-term note about shrinking/retiring old `wf_mcp` server entry
points; this slice does not retire them.

- [ ] **Step 2: Update long-lived API spec status**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`,
update the status paragraph near the top to mention this slice:

```markdown
Status: Slices 1-4 implemented. `wf_server` provides
`build_local_static_workflow_server`; `wf_mcp.broker.server` can adapt MCP
broker config/services into the neutral `WorkflowServer`; `wf_transport_rpc_http`
provides JSON-RPC methods and client support; `wf_cli` has target-aware context;
and `wf_config` owns neutral config models. WebSocket transport, auth,
streaming/progress, database backend, and live source hot reload remain future
work.
```

Under **First Slice** implementation status, add:

```markdown
- Slice 4 complete: `wf_mcp.broker.server.build_workflow_server_from_config()`
  returns a neutral `WorkflowServer` backed by MCP broker runtime services,
  including source registry admin and platform admin surfaces.
```

- [ ] **Step 3: Run link/status search**

Run:

```bash
rg -n "concrete MCP-backed `WorkflowServer` construction remains future work|Slices 1-3 implemented|MCP-backed `WorkflowServer`" docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
```

Expected:

- No stale "remains future work" claim for MCP-backed server construction.
- Status says Slices 1-4 implemented.
- The new constructor path is named.

- [ ] **Step 4: Commit**

```bash
git add docs/current_roadmap.md docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
git commit -m "docs: record mcp backed workflow server"
```

---

### Task 4: Final Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run focused test set**

Run:

```bash
uv run pytest tests/wf_mcp/test_mcp_workflow_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py tests/wf_server/test_local_static_server.py tests/wf_transport_rpc_http/test_source_registry_rpc.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint/type checks**

Run:

```bash
uv run ruff check src/wf_mcp/broker/server.py tests/wf_mcp/test_mcp_workflow_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
uv run basedpyright --level error src/wf_mcp/broker/server.py tests/wf_mcp/test_mcp_workflow_server.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py
git diff --check
```

Expected: all commands exit 0. CRLF warnings from Git are acceptable; whitespace
errors are not.

- [ ] **Step 3: Review package dependency direction**

Run:

```bash
rg -n "wf_mcp" src/wf_server
```

Expected: no matches.

- [ ] **Step 4: Final report**

Report:

- files created/modified
- verification output
- whether `wf_server` stayed MCP-free
- whether local/static source-registry unavailable behavior still passes
- any deviations from this plan

Do not run the full suite unless focused verification is green.

---

## Self-Review

- Spec coverage: covers the active roadmap gap "concrete MCP-backed `WorkflowServer` construction remains future work".
- Dependency direction: constructor lives in `wf_mcp`; `wf_server` remains MCP-free.
- Scope: no hot reload, auth redesign, process CLI, or persisted resume restart behavior.
- Testing: direct adapter tests plus JSON-RPC integration tests prove this is product-visible, not only internal wiring.
- Risk: `WorkflowServer.events` is currently typed as `InMemoryWorkflowEventRecorder`; if basedpyright rejects assigning `BrokerEventRecorder`, change that field type to `WorkflowEventRecorder` in `src/wf_server/context.py` and update no behavior. This is a type-only broadening and should be documented in the implementation report.
