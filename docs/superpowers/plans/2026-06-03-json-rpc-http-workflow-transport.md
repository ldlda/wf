# JSON-RPC HTTP Workflow Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first remote workflow transport: JSON-RPC 2.0 over HTTP backed by `wf_server.WorkflowServer` and `wf_api.WorkflowApi`.

**Architecture:** Create a new `wf_transport_rpc_http` package that owns only JSON-RPC/HTTP concerns: app construction, request DTOs, error mapping, and a local/static server startup command. It must call `WorkflowServer.api` and must not import `wf_mcp` or `WorkflowSurfaceHandlers`. The CLI remote-target work is a later slice.

**Tech Stack:** Python 3.14, `fastapi-jsonrpc`, `uvicorn`, `httpx` ASGI tests, Pydantic v2, pytest, ruff, basedpyright.

---

## Source Notes

`fastapi-jsonrpc` 3.5.0 is current on PyPI as of 2026-06-03. Its documented shape is:

```python
import fastapi_jsonrpc as jsonrpc

app = jsonrpc.API()
entrypoint = jsonrpc.Entrypoint("/api/v1/jsonrpc")

@entrypoint.method(errors=[MyError])
def echo(data: str) -> str:
    return data

app.bind_entrypoint(entrypoint)
```

The package advertises FastAPI dependencies, async handlers, Pydantic models, OpenAPI/OpenRPC generation, typed errors, batch requests, and notifications. Its `MethodRoute` accepts a `name` parameter, so dotted JSON-RPC names such as `workflow.runs.start` should be registered directly instead of inventing underscore aliases.

If the library behavior differs during implementation, keep the package boundary and tests intact, then adapt only the decorator syntax.

---

## File Map

- Modify `pyproject.toml`
  - Add runtime dependencies: `fastapi-jsonrpc`, `uvicorn`.
- Create `src/wf_transport_rpc_http/__init__.py`
  - Export app factories and public DTOs.
- Create `src/wf_transport_rpc_http/models.py`
  - Pydantic request DTOs for the fixed JSON-RPC method set.
  - `TraceRangeParams` transport DTO that converts to `wf_api.TraceRange`.
- Create `src/wf_transport_rpc_http/errors.py`
  - Typed JSON-RPC error class for expected workflow operation failures.
  - Helper that maps known application exceptions to JSON-RPC errors without hiding unexpected bugs.
- Create `src/wf_transport_rpc_http/app.py`
  - Build `fastapi_jsonrpc.API` from an existing `WorkflowServer`.
  - Register fixed dotted method names under `/rpc`.
  - Add a non-RPC `GET /healthz` route for cheap process health checks.
- Create `src/wf_transport_rpc_http/cli.py`
  - Local/static server startup command for manual testing.
  - Reads store root from CLI option, constructs `build_local_static_workflow_server`, runs uvicorn.
- Modify `pyproject.toml`
  - Add script `wf-rpc-server = "wf_transport_rpc_http.cli:main"`.
- Create `tests/wf_transport_rpc_http/test_app.py`
  - In-process ASGI tests for health, capabilities, deployment run, inspect, bounded trace, and error behavior.
- Create `tests/wf_transport_rpc_http/test_import_direction.py`
  - AST guard: transport may import `wf_server`/`wf_api`, but not `wf_mcp`.
- Modify `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
  - Mark Slice 2 implementation status after code lands.
- Modify `docs/current_roadmap.md`
  - Add completion note and startup command.

Out of scope:

- No remote `wf` CLI targeting.
- No auth.
- No WebSocket/SSE/progress streaming.
- No source provider management.
- No upstream MCP source lifecycle.
- No dynamic JSON-RPC methods for saved workflows.
- No full trace in run responses.

---

## Public JSON-RPC Surface

Register these fixed method names:

```text
workflow.health
workflow.capabilities.list
workflow.capabilities.inspect
workflow.drafts.create_from_capability
workflow.drafts.patch
workflow.drafts.validate
workflow.artifacts.save
workflow.deployments.save
workflow.deployments.validate
workflow.runs.start
workflow.runs.inspect
workflow.runs.trace
workflow.runs.resume
```

Do not add a generic `workflow.call` or dynamic method lookup in this slice.

---

## Task 1: Add Dependency and Package Skeleton

**Files:**

- Modify: `pyproject.toml`
- Create: `src/wf_transport_rpc_http/__init__.py`
- Create: `tests/wf_transport_rpc_http/test_import_direction.py`

- [ ] **Step 1: Add dependencies**

Run:

```bash
uv add fastapi-jsonrpc uvicorn
```

Expected: `pyproject.toml` gains both dependencies and `uv.lock` updates.

If network access is blocked, request permission rather than manually editing `uv.lock`.

- [ ] **Step 2: Create import-direction test**

Create `tests/wf_transport_rpc_http/test_import_direction.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path


def test_wf_transport_rpc_http_imports_no_wfmcp_modules() -> None:
    root = Path("src/wf_transport_rpc_http")
    violations: list[str] = []

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "wf_mcp" or node.module.startswith("wf_mcp."):
                    violations.append(f"{path}:{node.lineno}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "wf_mcp" or alias.name.startswith("wf_mcp."):
                        violations.append(f"{path}:{node.lineno}: import {alias.name}")

    assert violations == []
```

- [ ] **Step 3: Create package skeleton**

Create `src/wf_transport_rpc_http/__init__.py`:

```python
from __future__ import annotations

__all__: list[str] = []
```

- [ ] **Step 4: Run focused test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_import_direction.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/wf_transport_rpc_http/__init__.py tests/wf_transport_rpc_http/test_import_direction.py
git commit -m "feat: add rpc http transport package"
```

---

## Task 2: Add Transport DTOs

**Files:**

- Create: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Create: `tests/wf_transport_rpc_http/test_models.py`

- [ ] **Step 1: Write DTO tests**

Create `tests/wf_transport_rpc_http/test_models.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from wf_transport_rpc_http.models import (
    InspectCapabilityParams,
    ListCapabilitiesParams,
    ReadRunTraceParams,
    StartRunParams,
    TraceRangeParams,
)


def test_trace_range_params_converts_to_api_trace_range() -> None:
    trace_range = TraceRangeParams(start=2, limit=5).to_api_trace_range()

    assert trace_range.start == 2
    assert trace_range.limit == 5


def test_trace_range_params_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        TraceRangeParams(start=-1, limit=5)

    with pytest.raises(ValidationError):
        TraceRangeParams(start=0, limit=0)

    with pytest.raises(ValidationError):
        TraceRangeParams(start=0, limit=101)


def test_capability_params_are_explicit_models() -> None:
    listed = ListCapabilitiesParams(query="echo", source_id="wf.std", limit=10)
    inspected = InspectCapabilityParams(qualified_name="wf.std.constant")

    assert listed.query == "echo"
    assert listed.source_id == "wf.std"
    assert listed.limit == 10
    assert inspected.qualified_name == "wf.std.constant"


def test_run_params_are_explicit_models() -> None:
    started = StartRunParams(
        deployment_id="demo.default",
        workflow_input={"message": "hello"},
        trace_range=TraceRangeParams(start=0, limit=3),
    )
    trace = ReadRunTraceParams(
        run_id="run_demo",
        trace_range=TraceRangeParams(start=0, limit=1),
    )

    assert started.deployment_id == "demo.default"
    assert started.workflow_input["message"] == "hello"
    assert started.trace_range is not None
    assert trace.run_id == "run_demo"
    assert trace.trace_range.limit == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_models.py -q
```

Expected: fail because `wf_transport_rpc_http.models` does not exist.

- [ ] **Step 3: Implement DTOs**

Create `src/wf_transport_rpc_http/models.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from wf_api.models import TraceRange


class RpcParamsModel(BaseModel):
    """Base transport DTO: reject misspelled JSON-RPC params early."""

    model_config = ConfigDict(extra="forbid")


class TraceRangeParams(RpcParamsModel):
    start: int = Field(default=0, ge=0, description="Zero-based trace offset.")
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum trace entries to return; full traces are never implicit.",
    )

    def to_api_trace_range(self) -> TraceRange:
        return TraceRange(start=self.start, limit=self.limit)


class HealthParams(RpcParamsModel):
    pass


class ListCapabilitiesParams(RpcParamsModel):
    query: str | None = Field(default=None)
    source_id: str | None = Field(default=None)
    cursor: str | None = Field(default=None)
    limit: int = Field(default=50, ge=1, le=200)


class InspectCapabilityParams(RpcParamsModel):
    qualified_name: str = Field(min_length=1)


class CreateDraftFromCapabilityParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    capability_name: str = Field(min_length=1)
    name: str | None = None
    title: str | None = None
    input_schema: dict[str, Any] | None = None
    state_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    input: list[Any] | None = None
    output: list[Any] | None = None
    input_map: dict[str, str] | None = None
    output_map: dict[str, str] | None = None
    error_message_source: Any | None = None


class PatchDraftParams(RpcParamsModel):
    draft: dict[str, Any]
    patch: list[dict[str, Any]]


class ValidateDraftParams(RpcParamsModel):
    draft: dict[str, Any]


class SaveArtifactParams(RpcParamsModel):
    artifact: dict[str, Any]


class SaveDeploymentParams(RpcParamsModel):
    deployment: dict[str, Any]


class ValidateDeploymentParams(RpcParamsModel):
    deployment_id: str = Field(min_length=1)
    live_check: bool = False


class StartRunParams(RpcParamsModel):
    deployment_id: str = Field(min_length=1)
    workflow_input: dict[str, Any] = Field(default_factory=dict)
    trace_range: TraceRangeParams | None = None


class InspectRunParams(RpcParamsModel):
    run_id: str = Field(min_length=1)


class ReadRunTraceParams(RpcParamsModel):
    run_id: str = Field(min_length=1)
    trace_range: TraceRangeParams


class ResumeRunParams(RpcParamsModel):
    run_id: str = Field(min_length=1)
    resume_payload: dict[str, Any] = Field(default_factory=dict)
    resume_outcome: str = Field(default="submitted", min_length=1)
    trace_range: TraceRangeParams | None = None
```

- [ ] **Step 4: Export DTOs**

Update `src/wf_transport_rpc_http/__init__.py`:

```python
from __future__ import annotations

from .models import (
    CreateDraftFromCapabilityParams,
    HealthParams,
    InspectCapabilityParams,
    InspectRunParams,
    ListCapabilitiesParams,
    PatchDraftParams,
    ReadRunTraceParams,
    ResumeRunParams,
    SaveArtifactParams,
    SaveDeploymentParams,
    StartRunParams,
    TraceRangeParams,
    ValidateDeploymentParams,
    ValidateDraftParams,
)

__all__ = [
    "CreateDraftFromCapabilityParams",
    "HealthParams",
    "InspectCapabilityParams",
    "InspectRunParams",
    "ListCapabilitiesParams",
    "PatchDraftParams",
    "ReadRunTraceParams",
    "ResumeRunParams",
    "SaveArtifactParams",
    "SaveDeploymentParams",
    "StartRunParams",
    "TraceRangeParams",
    "ValidateDeploymentParams",
    "ValidateDraftParams",
]
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_models.py tests/wf_transport_rpc_http/test_import_direction.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/wf_transport_rpc_http tests/wf_transport_rpc_http/test_models.py
git commit -m "feat: add workflow rpc transport params"
```

---

## Task 3: Add JSON-RPC App Factory and Health/Capability Methods

**Files:**

- Create: `src/wf_transport_rpc_http/errors.py`
- Create: `src/wf_transport_rpc_http/app.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Create: `tests/wf_transport_rpc_http/test_app.py`

- [ ] **Step 1: Write app tests for health and capabilities**

Create `tests/wf_transport_rpc_http/test_app.py`:

```python
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http.app import create_rpc_app


async def _rpc(client: httpx.AsyncClient, method: str, params: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": "test", "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


def test_rpc_health_and_capability_methods(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health_response = await client.get("/healthz")
            health = await _rpc(client, "workflow.health", {})
            listed = await _rpc(
                client,
                "workflow.capabilities.list",
                {"source_id": "wf.std", "limit": 10},
            )
            inspected = await _rpc(
                client,
                "workflow.capabilities.inspect",
                {"qualified_name": "wf.std.constant"},
            )

        assert health_response.status_code == 200
        assert health_response.json()["status"] == "ok"
        assert health["result"]["status"] == "ok"
        assert listed["result"]["items"]
        assert inspected["result"]["qualified_name"] == "wf.std.constant"

    asyncio.run(scenario())


def test_rpc_unknown_method_returns_json_rpc_error(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            payload = await _rpc(client, "workflow.nope", {})

        assert payload["error"]["code"] == -32601
        assert payload["error"]["message"] == "Method not found"

    asyncio.run(scenario())
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py -q
```

Expected: fail because `wf_transport_rpc_http.app` does not exist.

- [ ] **Step 3: Add transport error helper**

Create `src/wf_transport_rpc_http/errors.py`:

```python
from __future__ import annotations

from typing import NoReturn

import fastapi_jsonrpc as jsonrpc
from pydantic import BaseModel, ConfigDict


class WorkflowRpcError(jsonrpc.BaseError):
    """Expected workflow application error surfaced through JSON-RPC."""

    CODE = 5000
    MESSAGE = "Workflow operation failed"

    class DataModel(BaseModel):
        code: str
        message: str

        model_config = ConfigDict(extra="forbid")


def raise_workflow_rpc_error(exc: Exception) -> NoReturn:
    """Map expected application exceptions without swallowing programming bugs."""

    raise WorkflowRpcError(
        data={
            "code": exc.__class__.__name__,
            "message": str(exc),
        }
    ) from exc
```

- [ ] **Step 4: Implement app factory with first methods**

Create `src/wf_transport_rpc_http/app.py`:

```python
from __future__ import annotations

from typing import Any

import fastapi_jsonrpc as jsonrpc
from fastapi import Body

from wf_server import WorkflowServer

from .errors import WorkflowRpcError, raise_workflow_rpc_error
from .models import InspectCapabilityParams, ListCapabilitiesParams


def create_rpc_app(server: WorkflowServer) -> jsonrpc.API:
    """Build a JSON-RPC HTTP app over an existing WorkflowServer.

    Transport code owns only JSON-RPC envelope handling. Workflow semantics stay
    behind server.api, so this package remains swappable with WebSocket/MCP
    transports later.
    """

    app = jsonrpc.API()
    entrypoint = jsonrpc.Entrypoint("/rpc")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @entrypoint.method(name="workflow.health", errors=[WorkflowRpcError])
    async def workflow_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "store_root": str(server.config.store_root),
        }

    @entrypoint.method(name="workflow.capabilities.list", errors=[WorkflowRpcError])
    async def workflow_capabilities_list(
        params: ListCapabilitiesParams = Body(default_factory=ListCapabilitiesParams),
    ) -> dict[str, Any]:
        try:
            return await server.api.list_capabilities(
                query=params.query,
                source_id=params.source_id,
                cursor=params.cursor,
                limit=params.limit,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.capabilities.inspect", errors=[WorkflowRpcError])
    async def workflow_capabilities_inspect(
        params: InspectCapabilityParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_capability(
                qualified_name=params.qualified_name,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    app.bind_entrypoint(entrypoint)
    return app
```

If `fastapi-jsonrpc` does not accept `name=...` on `Entrypoint.method`, adapt to the equivalent supported registration mechanism while preserving the dotted method names in the tests.

- [ ] **Step 5: Export app factory and error**

Update `src/wf_transport_rpc_http/__init__.py` to include:

```python
from .app import create_rpc_app
from .errors import WorkflowRpcError
```

Add both names to `__all__`.

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_import_direction.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/wf_transport_rpc_http tests/wf_transport_rpc_http/test_app.py
git commit -m "feat: expose workflow capabilities over json rpc"
```

---

## Task 4: Add Draft, Artifact, and Deployment Methods

**Files:**

- Modify: `src/wf_transport_rpc_http/app.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`

- [ ] **Step 1: Add RPC test for draft/artifact/deployment lifecycle**

Append to `tests/wf_transport_rpc_http/test_app.py`:

```python
def test_rpc_draft_artifact_deployment_lifecycle(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            draft = await _rpc(
                client,
                "workflow.drafts.create_from_capability",
                {
                    "workspace_id": "constant_ws",
                    "capability_name": "wf.std.constant",
                    "name": "constant_workflow",
                    "title": "Constant Workflow",
                    "input_map": {},
                    "output_map": {"value": "state.result"},
                },
            )
            validate_draft = await _rpc(
                client,
                "workflow.drafts.validate",
                {"draft": draft["result"]["draft"]},
            )
            artifact = await _rpc(
                client,
                "workflow.artifacts.save",
                {
                    "artifact": {
                        "id": "constant_rpc",
                        "version": 1,
                        "kind": "wrapper",
                        "title": "Constant RPC",
                        "input_schema": {"type": "object", "properties": {}},
                        "output_schema": {
                            "type": "object",
                            "properties": {"result": {"type": "string"}},
                            "required": ["result"],
                        },
                        "outcomes": ["ok"],
                        "required_capabilities": {},
                        "source_bindings": {"wf.std": "wf.std"},
                        "plan": draft["result"]["draft"],
                    },
                },
            )
            deployment = await _rpc(
                client,
                "workflow.deployments.save",
                {
                    "deployment": {
                        "id": "constant_rpc.default",
                        "artifact_id": "constant_rpc",
                        "artifact_version": 1,
                        "bindings": [
                            {"logical_source": "wf.std", "concrete_source": "wf.std"}
                        ],
                    },
                },
            )
            validate_deployment = await _rpc(
                client,
                "workflow.deployments.validate",
                {"deployment_id": "constant_rpc.default"},
            )

        assert validate_draft["result"]["valid"] is True
        assert artifact["result"]["artifact_id"] == "constant_rpc"
        assert deployment["result"]["deployment_id"] == "constant_rpc.default"
        assert validate_deployment["result"]["status"] == "runnable"

    asyncio.run(scenario())
```

If `wf.std.constant` wrapper hints require a different minimal draft shape, adjust the test through the public RPC methods only. Do not reach into stores directly.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_draft_artifact_deployment_lifecycle -q
```

Expected: fail with method not found.

- [ ] **Step 3: Register draft/artifact/deployment methods**

Add imports in `src/wf_transport_rpc_http/app.py`:

```python
from .models import (
    CreateDraftFromCapabilityParams,
    InspectCapabilityParams,
    ListCapabilitiesParams,
    PatchDraftParams,
    SaveArtifactParams,
    SaveDeploymentParams,
    ValidateDeploymentParams,
    ValidateDraftParams,
)
```

Add methods before `app.bind_entrypoint(entrypoint)`:

```python
    @entrypoint.method(name="workflow.drafts.create_from_capability", errors=[WorkflowRpcError])
    async def workflow_drafts_create_from_capability(
        params: CreateDraftFromCapabilityParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.create_draft_workspace_from_capability(
                workspace_id=params.workspace_id,
                capability_name=params.capability_name,
                name=params.name,
                title=params.title,
                input_schema=params.input_schema,
                state_schema=params.state_schema,
                output_schema=params.output_schema,
                input=params.input,
                output=params.output,
                input_map=params.input_map,
                output_map=params.output_map,
                error_message_source=params.error_message_source,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.drafts.patch", errors=[WorkflowRpcError])
    async def workflow_drafts_patch(
        params: PatchDraftParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.patch_draft(draft=params.draft, patch=params.patch)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.drafts.validate", errors=[WorkflowRpcError])
    async def workflow_drafts_validate(
        params: ValidateDraftParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.validate_draft(draft=params.draft)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.artifacts.save", errors=[WorkflowRpcError])
    async def workflow_artifacts_save(
        params: SaveArtifactParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.save_artifact(params.artifact)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.save", errors=[WorkflowRpcError])
    async def workflow_deployments_save(
        params: SaveDeploymentParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.save_deployment(params.deployment)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.deployments.validate", errors=[WorkflowRpcError])
    async def workflow_deployments_validate(
        params: ValidateDeploymentParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.validate_deployment(
                deployment_id=params.deployment_id,
                live_check=params.live_check,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 4: Run focused lifecycle test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_draft_artifact_deployment_lifecycle -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_transport_rpc_http/app.py tests/wf_transport_rpc_http/test_app.py
git commit -m "feat: expose workflow authoring rpc methods"
```

---

## Task 5: Add Run, Inspect, Trace, and Resume Methods

**Files:**

- Modify: `src/wf_transport_rpc_http/app.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`

- [ ] **Step 1: Add helper plan to test file**

Add imports:

```python
from wf_api.models import RawWorkflowPlan
from wf_core import END
```

Add helper:

```python
def _constant_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "rpc_constant",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "reducer": "wf.std.replace"}
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
            "outcomes": ["ok"],
            "start": "constant",
            "nodes": [
                {
                    "id": "constant",
                    "type": "node",
                    "node": "wf.std.constant",
                    "input": [
                        {
                            "value": "hello over rpc",
                            "target": {"root": "local", "parts": ["value"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["value"]},
                            "target": {"root": "state", "parts": ["result"]},
                        }
                    ],
                }
            ],
            "edges": [{"from": "constant", "outcome": "ok", "to": END}],
            "output": [
                {
                    "path": {"root": "state", "parts": ["result"]},
                    "target": {"root": "local", "parts": ["result"]},
                }
            ],
        }
    )
```

- [ ] **Step 2: Add RPC run lifecycle test**

Append:

```python
def test_rpc_runs_deployment_and_reads_bounded_trace(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        await server.api.create_artifact_from_plan(
            artifact_id="rpc_constant",
            version=1,
            title="RPC Constant",
            plan=_constant_plan(),
            outcomes=["ok"],
            source_bindings={"wf.std": "wf.std"},
        )
        await server.api.save_deployment(
            {
                "id": "rpc_constant.default",
                "artifact_id": "rpc_constant",
                "artifact_version": 1,
                "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
            }
        )

        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            run = await _rpc(
                client,
                "workflow.runs.start",
                {
                    "deployment_id": "rpc_constant.default",
                    "workflow_input": {},
                    "trace_range": {"start": 0, "limit": 1},
                },
            )
            inspected = await _rpc(
                client,
                "workflow.runs.inspect",
                {"run_id": run["result"]["run_id"]},
            )
            trace = await _rpc(
                client,
                "workflow.runs.trace",
                {
                    "run_id": run["result"]["run_id"],
                    "trace_range": {"start": 0, "limit": 1},
                },
            )

        assert run["result"]["status"] == "completed"
        assert run["result"]["output"]["result"] == "hello over rpc"
        assert "trace" not in inspected["result"]
        assert inspected["result"]["trace_count"] >= 1
        assert trace["result"]["trace_start"] == 0
        assert trace["result"]["trace_limit"] == 1
        assert len(trace["result"]["trace"]) == 1

    asyncio.run(scenario())
```

- [ ] **Step 3: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_runs_deployment_and_reads_bounded_trace -q
```

Expected: fail with method not found.

- [ ] **Step 4: Register run methods**

Add imports in `src/wf_transport_rpc_http/app.py`:

```python
from .models import (
    ...
    InspectRunParams,
    ReadRunTraceParams,
    ResumeRunParams,
    StartRunParams,
)
```

Add methods before `app.bind_entrypoint(entrypoint)`:

```python
    @entrypoint.method(name="workflow.runs.start", errors=[WorkflowRpcError])
    async def workflow_runs_start(
        params: StartRunParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.run_deployment(
                deployment_id=params.deployment_id,
                workflow_input=params.workflow_input,
                trace_range=(
                    params.trace_range.to_api_trace_range()
                    if params.trace_range is not None
                    else None
                ),
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.inspect", errors=[WorkflowRpcError])
    async def workflow_runs_inspect(
        params: InspectRunParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.inspect_run(run_id=params.run_id)
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.trace", errors=[WorkflowRpcError])
    async def workflow_runs_trace(
        params: ReadRunTraceParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.read_run_trace(
                run_id=params.run_id,
                trace_range=params.trace_range.to_api_trace_range(),
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.runs.resume", errors=[WorkflowRpcError])
    async def workflow_runs_resume(
        params: ResumeRunParams = Body(...),
    ) -> dict[str, Any]:
        try:
            return await server.api.resume_run(
                run_id=params.run_id,
                resume_payload=params.resume_payload,
                resume_outcome=params.resume_outcome,
                trace_range=(
                    params.trace_range.to_api_trace_range()
                    if params.trace_range is not None
                    else None
                ),
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 5: Run run lifecycle test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_runs_deployment_and_reads_bounded_trace -q
```

Expected: pass.

- [ ] **Step 6: Run all transport tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/wf_transport_rpc_http/app.py tests/wf_transport_rpc_http/test_app.py
git commit -m "feat: expose workflow runs over json rpc"
```

---

## Task 6: Add Local Server CLI Entry Point

**Files:**

- Create: `src/wf_transport_rpc_http/cli.py`
- Modify: `pyproject.toml`
- Create: `tests/wf_transport_rpc_http/test_cli.py`

- [ ] **Step 1: Add CLI test**

Create `tests/wf_transport_rpc_http/test_cli.py`:

```python
from __future__ import annotations

from typer.testing import CliRunner

from wf_transport_rpc_http.cli import app


def test_rpc_server_cli_help_mentions_store_root() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--store-root" in result.output
    assert "--host" in result.output
    assert "--port" in result.output
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py -q
```

Expected: fail because `wf_transport_rpc_http.cli` does not exist.

- [ ] **Step 3: Implement CLI**

Create `src/wf_transport_rpc_http/cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import typer
import uvicorn

from wf_server import build_local_static_workflow_server

from .app import create_rpc_app

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def serve(
    store_root: Path = typer.Option(
        ...,
        "--store-root",
        help="Directory containing workflow artifact, draft, and run stores.",
    ),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port", min=1, max=65535),
) -> None:
    """Serve the local/static WorkflowApi over JSON-RPC HTTP."""
    server = build_local_static_workflow_server(store_root)
    rpc_app = create_rpc_app(server)
    uvicorn.run(rpc_app, host=host, port=port, access_log=False)


def main() -> None:
    app()
```

- [ ] **Step 4: Add script**

In `pyproject.toml`, add:

```toml
wf-rpc-server = "wf_transport_rpc_http.cli:main"
```

under `[project.scripts]`.

- [ ] **Step 5: Export app factories**

Update `src/wf_transport_rpc_http/__init__.py` to include:

```python
from .app import create_rpc_app
```

Ensure `create_rpc_app` is in `__all__`.

- [ ] **Step 6: Run CLI test**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/wf_transport_rpc_http/cli.py tests/wf_transport_rpc_http/test_cli.py
git commit -m "feat: add workflow rpc server command"
```

---

## Task 7: Documentation and Verification

**Files:**

- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update long-lived API spec status**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, under `### Slice 2: JSON-RPC HTTP Transport Adapter`, add:

```markdown
Implementation status:

- `wf_transport_rpc_http.create_rpc_app(server)` exposes a fixed JSON-RPC
  method set over an existing `wf_server.WorkflowServer`.
- `wf-rpc-server --store-root <path>` starts the local/static server over
  `/rpc`.
- This slice still does not include remote `wf` CLI targeting, auth,
  streaming/progress, or live upstream MCP source management.
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, add a concise note near the durable API/server roadmap section:

```markdown
- Completed: the first JSON-RPC-over-HTTP transport can expose the local/static
  `WorkflowServer` through fixed dotted methods. Remote CLI targeting remains
  the next transport-facing slice.
```

- [ ] **Step 3: Run focused verification**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http tests/wf_server tests/wf_api/test_import_direction.py -q
```

Expected: pass.

- [ ] **Step 4: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
```

Expected:

- pytest passes with the repository's existing skip/xfail count.
- ruff passes.
- basedpyright reports 0 errors. If it emits only the known file-enumeration warning, report that explicitly.

- [ ] **Step 5: Final review checklist**

Check:

```bash
rg -n "wf_mcp" src/wf_transport_rpc_http tests/wf_transport_rpc_http
rg -n "tools/list|dynamic.*method|saved workflow.*method" src/wf_transport_rpc_http docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md
```

Expected:

- No `wf_mcp` imports in transport package.
- No dynamic saved-workflow method registration.
- No MCP-style dynamic tool listing in the transport package.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md docs/current_roadmap.md
git commit -m "docs: record json rpc workflow transport"
```

---

## Self-Review Notes

Spec coverage:

- Fixed dotted method names: covered by Tasks 3-5.
- JSON-RPC 2.0 over HTTP: covered by `fastapi-jsonrpc` app in Task 3.
- No `wf_mcp` dependency: covered by import-direction test in Task 1.
- Explicit IDs and no hidden session state: all DTOs use explicit `deployment_id`, `run_id`, params.
- Bounded trace: `TraceRangeParams` enforces `limit <= 100`, `workflow.runs.trace` requires `trace_range`.
- No dynamic saved workflow methods: final review grep in Task 7.
- CLI remote targeting deferred: documented out of scope and roadmap note.

Known risk:

- The Task 4 draft/artifact/deployment test may need small payload corrections depending on exact current draft output shape. Keep the test public-method-only; do not bypass the RPC transport or stores to make it pass.

