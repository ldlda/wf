# Workflow Config and RPC CLI Target Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

### Target Selection Precedence

1. `--url` CLI override selects an RPC HTTP target.
2. `--local` CLI override selects the in-process local target.
3. Config file `client.target` selects the configured target.
4. Missing target config defaults to local.

CLI overrides intentionally win over config so one-off diagnostics can point at
a different server without editing the config file.

**Goal:** Add neutral workflow config models and let selected `wf` CLI commands target either local execution or the JSON-RPC HTTP server.

**Architecture:** Introduce `wf_config` as the protocol-neutral config package. Keep existing `wf_mcp.config.json` loading for compatibility, but add a new `wf.json`-style shape with `client.target`, `server.store`, `server.transports`, and bootstrap `server.sources`. Put the JSON-RPC client adapter in `wf_transport_rpc_http.client`; CLI context chooses local `WorkflowApi` or remote RPC adapter based on config plus CLI overrides.

**Tech Stack:** Python 3.14, Pydantic v2 discriminated unions, Typer, httpx, pytest, ruff, basedpyright.

---

## Scope

This is the first config/remote CLI slice.

In scope:

- Neutral config models and loader.
- Filesystem store config only.
- `client.target.kind = "local"` and `client.target.kind = "rpc_http"`.
- `server.transports.kind = "rpc_http"` for `wf-rpc-server`.
- `server.sources.kind = "stdlib"` only.
- CLI overrides: `--local`, `--url`, `--timeout`.
- Remote CLI support for:
  - `wf cap list`
  - `wf cap inspect`
  - `wf run start`
  - `wf run inspect`
  - `wf run trace`

Out of scope:

- Remote draft/artifact/deployment CLI commands.
- Store-backed source registry.
- MCP source config migration.
- `/mcp` hosting.
- Auth.
- SQL store.
- WebSocket/progress streaming.

---

## File Map

- Create `src/wf_config/__init__.py`
  - Public exports for config models and loader.
- Create `src/wf_config/models.py`
  - Pydantic tagged unions for target, store, transport, and source config.
- Create `src/wf_config/loader.py`
  - Load neutral config from JSON, resolve relative filesystem paths relative to config file.
  - Compatibility helper for old MCP config can stay in CLI context rather than here.
- Create `tests/wf_config/test_models.py`
  - Unit tests for discriminated unions, duplicate source ids, relative store paths.
- Create `src/wf_transport_rpc_http/client.py`
  - `RpcWorkflowApiClient` with the subset of `WorkflowApi` methods needed by CLI.
- Create `tests/wf_transport_rpc_http/test_client.py`
  - ASGI-backed client tests against `create_rpc_app`.
- Modify `src/wf_cli/context.py`
  - Add target selection and return either local `WorkflowApi` or `RpcWorkflowApiClient`.
  - Keep old `wf_mcp.config.json` compatibility path.
- Modify `src/wf_cli/app.py`
  - Add root options `--local`, `--url`, `--timeout`.
- Modify `src/wf_cli/commands/caps.py`
  - No behavior change expected; it should keep using `context.handlers`.
- Modify `src/wf_cli/commands/runs.py`
  - No behavior change expected; it should keep using `context.handlers`.
- Modify `src/wf_transport_rpc_http/cli.py`
  - Accept `--config`; read `server.store` and first `rpc_http` transport when supplied.
  - Keep existing direct `--store-root`, `--host`, `--port` flags as overrides.
- Create or modify `tests/wf_cli/test_remote_target.py`
  - Validate remote target routing for cap/run commands.
- Modify `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`
  - Mark first implementation status after code lands.
- Modify `docs/current_roadmap.md`
  - Add completion note for neutral config + remote CLI target slice.

---

## Target Interface Shape

`CliContext.handlers` currently contains `WorkflowApi`. After this slice it may contain either:

```python
WorkflowApi | RpcWorkflowApiClient
```

The remote client only needs to implement the methods used by the first remote CLI slice:

```python
async def list_capabilities(...)
async def inspect_capability(...)
async def run_deployment(...)
async def inspect_run(...)
async def read_run_trace(...)
```

Do not make a fake full `WorkflowApi` implementation in this slice. Add methods only when commands use them.

---

## Task 1: Add Neutral Config Models

**Files:**

- Create: `src/wf_config/__init__.py`
- Create: `src/wf_config/models.py`
- Create: `tests/wf_config/test_models.py`

- [ ] **Step 1: Write failing config model tests**

Create `tests/wf_config/test_models.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from wf_config import (
    FilesystemStoreConfig,
    LocalTargetConfig,
    RpcHttpTargetConfig,
    RpcHttpTransportConfig,
    StdlibSourceConfig,
    WorkflowConfigFile,
)


def test_workflow_config_parses_local_target_and_filesystem_store() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "client": {"target": {"kind": "local"}},
            "server": {
                "store": {"kind": "filesystem", "root": ".wf_store"},
                "sources": [{"kind": "stdlib", "id": "wf.std"}],
            },
        }
    )

    assert isinstance(config.client.target, LocalTargetConfig)
    assert isinstance(config.server.store, FilesystemStoreConfig)
    assert config.server.store.root.as_posix() == ".wf_store"
    assert isinstance(config.server.sources[0], StdlibSourceConfig)
    assert config.server.sources[0].id == "wf.std"


def test_workflow_config_parses_rpc_http_target_and_transport() -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "client": {
                "target": {
                    "kind": "rpc_http",
                    "url": "http://127.0.0.1:8765/rpc",
                    "timeout_seconds": 12,
                }
            },
            "server": {
                "transports": [
                    {
                        "kind": "rpc_http",
                        "host": "0.0.0.0",
                        "port": 9999,
                        "path": "/rpc",
                    }
                ]
            },
        }
    )

    assert isinstance(config.client.target, RpcHttpTargetConfig)
    assert config.client.target.url == "http://127.0.0.1:8765/rpc"
    assert config.client.target.timeout_seconds == 12
    assert isinstance(config.server.transports[0], RpcHttpTransportConfig)
    assert config.server.transports[0].host == "0.0.0.0"
    assert config.server.transports[0].port == 9999


def test_workflow_config_rejects_duplicate_source_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate source id"):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "server": {
                    "sources": [
                        {"kind": "stdlib", "id": "wf.std"},
                        {"kind": "stdlib", "id": "wf.std"},
                    ]
                },
            }
        )


def test_workflow_config_rejects_unknown_target_kind() -> None:
    with pytest.raises(ValidationError):
        WorkflowConfigFile.model_validate(
            {
                "version": 1,
                "client": {"target": {"kind": "mcp"}},
            }
        )
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_config/test_models.py -q
```

Expected: fail because `wf_config` does not exist.

- [ ] **Step 3: Implement models**

Create `src/wf_config/models.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkflowConfigModel(BaseModel):
    """Base config model: reject typos so config mistakes fail fast."""

    model_config = ConfigDict(extra="forbid")


class LocalTargetConfig(WorkflowConfigModel):
    kind: Literal["local"] = "local"


class RpcHttpTargetConfig(WorkflowConfigModel):
    kind: Literal["rpc_http"]
    url: str
    timeout_seconds: float = Field(default=30.0, gt=0)


TargetConfig = Annotated[
    LocalTargetConfig | RpcHttpTargetConfig,
    Field(discriminator="kind"),
]


class ClientConfig(WorkflowConfigModel):
    target: TargetConfig = Field(default_factory=LocalTargetConfig)


class FilesystemStoreConfig(WorkflowConfigModel):
    kind: Literal["filesystem"] = "filesystem"
    root: Path = Path(".wf_store")


StoreConfig = Annotated[
    FilesystemStoreConfig,
    Field(discriminator="kind"),
]


class RpcHttpTransportConfig(WorkflowConfigModel):
    kind: Literal["rpc_http"]
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    path: str = "/rpc"

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("transport path must start with '/'")
        return value


ServerTransportConfig = Annotated[
    RpcHttpTransportConfig,
    Field(discriminator="kind"),
]


class StdlibSourceConfig(WorkflowConfigModel):
    kind: Literal["stdlib"]
    id: str = Field(min_length=1)


SourceConfig = Annotated[
    StdlibSourceConfig,
    Field(discriminator="kind"),
]


class ServerConfig(WorkflowConfigModel):
    store: StoreConfig = Field(default_factory=FilesystemStoreConfig)
    transports: list[ServerTransportConfig] = Field(default_factory=list)
    sources: list[SourceConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> ServerConfig:
        seen: set[str] = set()
        for source in self.sources:
            if source.id in seen:
                raise ValueError(f"duplicate source id {source.id!r}")
            seen.add(source.id)
        return self


class WorkflowConfigFile(WorkflowConfigModel):
    version: Literal[1] = 1
    client: ClientConfig = Field(default_factory=ClientConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
```

Create `src/wf_config/__init__.py`:

```python
from __future__ import annotations

from .models import (
    ClientConfig,
    FilesystemStoreConfig,
    LocalTargetConfig,
    RpcHttpTargetConfig,
    RpcHttpTransportConfig,
    ServerConfig,
    StdlibSourceConfig,
    WorkflowConfigFile,
)

__all__ = [
    "ClientConfig",
    "FilesystemStoreConfig",
    "LocalTargetConfig",
    "RpcHttpTargetConfig",
    "RpcHttpTransportConfig",
    "ServerConfig",
    "StdlibSourceConfig",
    "WorkflowConfigFile",
]
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_config/test_models.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_config tests/wf_config/test_models.py
git commit -m "feat: add neutral workflow config models"
```

---

## Task 2: Add Config Loader and Relative Path Resolution

**Files:**

- Create: `src/wf_config/loader.py`
- Modify: `src/wf_config/__init__.py`
- Modify: `tests/wf_config/test_models.py`

- [ ] **Step 1: Add loader tests**

Append to `tests/wf_config/test_models.py`:

```python
import json

from wf_config import load_workflow_config


def test_load_workflow_config_resolves_filesystem_store_relative_to_config(
    tmp_path,
) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_workflow_config(config_path)

    assert config.server.store.root == (tmp_path / ".wf_store").resolve()


def test_load_workflow_config_preserves_absolute_filesystem_store(tmp_path) -> None:
    absolute_root = (tmp_path / "absolute-store").resolve()
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": str(absolute_root)},
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_workflow_config(config_path)

    assert config.server.store.root == absolute_root
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_config/test_models.py::test_load_workflow_config_resolves_filesystem_store_relative_to_config -q
```

Expected: fail because `load_workflow_config` does not exist.

- [ ] **Step 3: Implement loader**

Create `src/wf_config/loader.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from .models import FilesystemStoreConfig, WorkflowConfigFile


def load_workflow_config(path: str | Path) -> WorkflowConfigFile:
    """Load neutral workflow config and resolve local filesystem paths.

    Relative filesystem store roots are config-file relative so `wf --config`
    behaves the same regardless of the caller's current working directory.
    """

    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    config = WorkflowConfigFile.model_validate(data)
    store = config.server.store
    if isinstance(store, FilesystemStoreConfig) and not store.root.is_absolute():
        config = config.model_copy(
            update={
                "server": config.server.model_copy(
                    update={
                        "store": store.model_copy(
                            update={"root": (config_path.parent / store.root).resolve()}
                        )
                    }
                )
            }
        )
    return config
```

- [ ] **Step 4: Export loader**

Update `src/wf_config/__init__.py`:

```python
from .loader import load_workflow_config
```

Add `"load_workflow_config"` to `__all__`.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/wf_config/test_models.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/wf_config tests/wf_config/test_models.py
git commit -m "feat: load neutral workflow config"
```

---

## Task 3: Add JSON-RPC Workflow API Client

**Files:**

- Create: `src/wf_transport_rpc_http/client.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Create: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Write client tests**

Create `tests/wf_transport_rpc_http/test_client.py`:

```python
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from wf_api.models import RawWorkflowPlan, TraceRange
from wf_core import END
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app


def _constant_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "client_constant",
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
                            "value": "hello from rpc client",
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


def test_rpc_workflow_client_lists_and_inspects_capabilities(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http_client:
            client = RpcWorkflowApiClient(
                url="http://test/rpc",
                timeout_seconds=5,
                http_client=http_client,
            )
            listed = await client.list_capabilities(source_id="wf.std", limit=5)
            inspected = await client.inspect_capability(
                qualified_name="wf.std.constant"
            )

        assert listed["capabilities"]
        assert inspected["name"] == "wf.std.constant"

    asyncio.run(scenario())


def test_rpc_workflow_client_runs_and_reads_trace(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        await server.api.create_artifact_from_plan(
            artifact_id="client_constant",
            version=1,
            title="Client Constant",
            plan=_constant_plan(),
            outcomes=["ok"],
            source_bindings={"wf.std": "wf.std"},
        )
        await server.api.save_deployment(
            {
                "id": "client_constant.default",
                "artifact_id": "client_constant",
                "artifact_version": 1,
                "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
            }
        )
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http_client:
            client = RpcWorkflowApiClient(
                url="http://test/rpc",
                timeout_seconds=5,
                http_client=http_client,
            )
            run = await client.run_deployment(
                deployment_id="client_constant.default",
                workflow_input={},
                trace_range=TraceRange(start=0, limit=1),
            )
            inspected = await client.inspect_run(run_id=run["run_id"])
            trace = await client.read_run_trace(
                run_id=run["run_id"],
                trace_range=TraceRange(start=0, limit=1),
            )

        assert run["status"] == "completed"
        assert run["output"]["result"] == "hello from rpc client"
        assert inspected["trace_count"] >= 1
        assert len(trace["trace"]) == 1

    asyncio.run(scenario())


def test_rpc_workflow_client_raises_for_rpc_error(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http_client:
            client = RpcWorkflowApiClient(
                url="http://test/rpc",
                timeout_seconds=5,
                http_client=http_client,
            )
            try:
                await client.inspect_capability(qualified_name="missing.capability")
            except RuntimeError as exc:
                message = str(exc)
            else:
                raise AssertionError("expected RuntimeError")

        assert "Workflow operation failed" in message
        assert "missing.capability" in message

    asyncio.run(scenario())
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_client.py -q
```

Expected: fail because `RpcWorkflowApiClient` does not exist.

- [ ] **Step 3: Implement client**

Create `src/wf_transport_rpc_http/client.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from wf_api.models import TraceRange


@dataclass(slots=True)
class RpcWorkflowApiClient:
    """Small WorkflowApi-compatible adapter for JSON-RPC HTTP targets.

    This is intentionally not a full WorkflowApi clone. It implements only the
    methods used by the first remote CLI slice.
    """

    url: str
    timeout_seconds: float = 30.0
    http_client: httpx.AsyncClient | None = None

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": uuid4().hex,
            "method": method,
            "params": params,
        }
        if self.http_client is None:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.url, json=request)
        else:
            response = await self.http_client.post(self.url, json=request)
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            error = payload["error"]
            message = error.get("message", "JSON-RPC error")
            data = error.get("data")
            if isinstance(data, dict) and data.get("message"):
                message = f"{message}: {data['message']}"
            raise RuntimeError(message)
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("JSON-RPC response result must be an object")
        return result

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.capabilities.list",
            {
                "query": query,
                "source_id": source_id,
                "cursor": cursor,
                "limit": limit,
            },
        )

    async def inspect_capability(self, *, qualified_name: str) -> dict[str, Any]:
        return await self._call(
            "workflow.capabilities.inspect",
            {"qualified_name": qualified_name},
        )

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.runs.start",
            {
                "deployment_id": deployment_id,
                "workflow_input": workflow_input,
                "trace_range": _trace_range_payload(trace_range),
            },
        )

    async def inspect_run(self, *, run_id: str) -> dict[str, Any]:
        return await self._call("workflow.runs.inspect", {"run_id": run_id})

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRange,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.runs.trace",
            {
                "run_id": run_id,
                "trace_range": _trace_range_payload(trace_range),
            },
        )


def _trace_range_payload(trace_range: TraceRange | None) -> dict[str, int] | None:
    if trace_range is None:
        return None
    return {"start": trace_range.start, "limit": trace_range.limit}
```

- [ ] **Step 4: Export client**

Update `src/wf_transport_rpc_http/__init__.py`:

```python
from .client import RpcWorkflowApiClient
```

Add `"RpcWorkflowApiClient"` to `__all__`.

- [ ] **Step 5: Run client tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_client.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/wf_transport_rpc_http tests/wf_transport_rpc_http/test_client.py
git commit -m "feat: add workflow rpc http client"
```

---

## Task 4: Route CLI Context by Neutral Target Config

**Files:**

- Modify: `src/wf_cli/context.py`
- Modify: `src/wf_cli/app.py`
- Create: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add remote target tests**

Create `tests/wf_cli/test_remote_target.py`:

```python
from __future__ import annotations

import json

from wf_cli.context import load_cli_context
from wf_transport_rpc_http import RpcWorkflowApiClient


def test_load_cli_context_uses_rpc_client_for_rpc_http_target(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                        "timeout_seconds": 9,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path)

    assert isinstance(context.handlers, RpcWorkflowApiClient)
    assert context.handlers.url == "http://127.0.0.1:8765/rpc"
    assert context.handlers.timeout_seconds == 9
    assert context.service is None


def test_load_cli_context_local_override_beats_rpc_config(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "client": {
                    "target": {
                        "kind": "rpc_http",
                        "url": "http://127.0.0.1:8765/rpc",
                    }
                },
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                },
            }
        ),
        encoding="utf-8",
    )

    context = load_cli_context(config_path, force_local=True)

    assert not isinstance(context.handlers, RpcWorkflowApiClient)
    assert context.service is None
    assert context.config_path == config_path
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py -q
```

Expected: fail because `load_cli_context` does not understand neutral config/remote targets.

- [ ] **Step 3: Update CLI context**

Modify `src/wf_cli/context.py`.

Replace `CliContext` with:

```python
@dataclass(frozen=True)
class CliContext:
    """Protocol-neutral CLI handle over local or remote workflow operations."""

    config_path: Path
    service: WfMcpService | None
    handlers: WorkflowApi | RpcWorkflowApiClient
```

Add imports:

```python
from wf_config import FilesystemStoreConfig, LocalTargetConfig, RpcHttpTargetConfig, load_workflow_config
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient
```

Change `load_cli_context` signature:

```python
def load_cli_context(
    config_path: str | Path,
    *,
    force_local: bool = False,
    rpc_url: str | None = None,
    rpc_timeout_seconds: float | None = None,
) -> CliContext:
```

Implement this logic:

```python
    resolved_config_path = Path(config_path)
    if resolved_config_path.name == "wf_mcp.config.json":
        config = load_broker_config(resolved_config_path)
        service = build_service_from_config(config)
        return CliContext(
            config_path=resolved_config_path,
            service=service,
            handlers=WorkflowApi(context_from_service(service)),
        )

    config = load_workflow_config(resolved_config_path)
    target = config.client.target
    if rpc_url is not None:
        timeout = rpc_timeout_seconds if rpc_timeout_seconds is not None else 30.0
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=RpcWorkflowApiClient(url=rpc_url, timeout_seconds=timeout),
        )
    if force_local or isinstance(target, LocalTargetConfig):
        store = config.server.store
        if not isinstance(store, FilesystemStoreConfig):
            raise ValueError("local CLI target currently requires filesystem store")
        server = build_local_static_workflow_server(store.root)
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=server.api,
        )
    if isinstance(target, RpcHttpTargetConfig):
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=RpcWorkflowApiClient(
                url=target.url,
                timeout_seconds=(
                    rpc_timeout_seconds
                    if rpc_timeout_seconds is not None
                    else target.timeout_seconds
                ),
            ),
        )
    raise ValueError(f"unsupported workflow target {target!r}")
```

Keep `config_path_from_context` for compatibility.

- [ ] **Step 4: Add root CLI override plumbing**

Modify `src/wf_cli/app.py` root callback to accept:

```python
    local: Annotated[
        bool,
        typer.Option("--local", help="Force same-process local workflow target."),
    ] = False,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override workflow JSON-RPC target URL."),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", min=0.1, help="Override RPC timeout seconds."),
    ] = None,
```

Set:

```python
ctx.obj = {
    "config_path": config,
    "force_local": local,
    "rpc_url": url,
    "rpc_timeout_seconds": timeout,
}
```

Add helper functions in `src/wf_cli/context.py`:

```python
def force_local_from_context(ctx: typer.Context) -> bool:
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    return bool(obj.get("force_local", False))


def rpc_url_from_context(ctx: typer.Context) -> str | None:
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    value = obj.get("rpc_url")
    return value if isinstance(value, str) else None


def rpc_timeout_from_context(ctx: typer.Context) -> float | None:
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    value = obj.get("rpc_timeout_seconds")
    return value if isinstance(value, float | int) else None


def load_cli_context_from_typer(ctx: typer.Context) -> CliContext:
    return load_cli_context(
        config_path_from_context(ctx),
        force_local=force_local_from_context(ctx),
        rpc_url=rpc_url_from_context(ctx),
        rpc_timeout_seconds=rpc_timeout_from_context(ctx),
    )
```

Do not update every command manually yet; Task 5 does the selected commands.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py tests/wf_cli/test_context.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/wf_cli/context.py src/wf_cli/app.py tests/wf_cli/test_remote_target.py
git commit -m "feat: select workflow cli target from config"
```

---

## Task 5: Wire Selected CLI Commands Through Target-Aware Context

**Files:**

- Modify: `src/wf_cli/commands/caps.py`
- Modify: `src/wf_cli/commands/runs.py`
- Modify: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add CLI remote cap/run tests**

Append to `tests/wf_cli/test_remote_target.py`:

```python
import asyncio

import httpx
from typer.testing import CliRunner

from wf_api.models import RawWorkflowPlan
from wf_cli.app import app
from wf_core import END
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import create_rpc_app


def _constant_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "remote_cli_constant",
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
                            "value": "hello remote cli",
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


def test_wf_cap_commands_use_rpc_url_override(monkeypatch, tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        rpc_app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=rpc_app)
        client = httpx.AsyncClient(transport=transport, base_url="http://test")
        monkeypatch.setattr(
            "wf_transport_rpc_http.client.httpx.AsyncClient",
            lambda *args, **kwargs: client,
        )
        config_path = tmp_path / "wf.json"
        config_path.write_text('{"version": 1}', encoding="utf-8")

        result = CliRunner().invoke(
            app,
            [
                "--config",
                str(config_path),
                "--url",
                "http://test/rpc",
                "cap",
                "inspect",
                "wf.std.constant",
            ],
        )
        await client.aclose()
        assert result.exit_code == 0, result.output
        assert '"name": "wf.std.constant"' in result.output

    asyncio.run(scenario())
```

This test uses monkeypatching because Typer commands own `asyncio.run`; keep it focused to prove the context path, not the whole HTTP stack.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_cap_commands_use_rpc_url_override -q
```

Expected: fail because commands still call `load_cli_context(config_path_from_context(ctx))`.

- [ ] **Step 3: Update selected commands**

In `src/wf_cli/commands/caps.py`, replace:

```python
from wf_cli.context import config_path_from_context, load_cli_context
```

with:

```python
from wf_cli.context import load_cli_context_from_typer
```

Replace both:

```python
context = load_cli_context(config_path_from_context(ctx))
```

with:

```python
context = load_cli_context_from_typer(ctx)
```

In `src/wf_cli/commands/runs.py`, do the same replacement.

- [ ] **Step 4: Run focused CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py tests/wf_cli/test_run_deploy.py tests/wf_cli/test_discovery_lifecycle.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_cli/commands/caps.py src/wf_cli/commands/runs.py tests/wf_cli/test_remote_target.py
git commit -m "feat: route cap and run cli commands to rpc targets"
```

---

## Task 6: Read Server Config in wf-rpc-server

**Files:**

- Modify: `src/wf_transport_rpc_http/cli.py`
- Modify: `tests/wf_transport_rpc_http/test_cli.py`

- [ ] **Step 1: Add CLI config test**

Append to `tests/wf_transport_rpc_http/test_cli.py`:

```python
import json


def test_rpc_server_cli_accepts_config_file(tmp_path) -> None:
    config_path = tmp_path / "wf.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "server": {
                    "store": {"kind": "filesystem", "root": ".wf_store"},
                    "transports": [
                        {
                            "kind": "rpc_http",
                            "host": "127.0.0.1",
                            "port": 9999,
                            "path": "/rpc",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["--config", str(config_path), "--help"])

    assert result.exit_code == 0
    assert "--config" in result.output
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py -q
```

Expected: fail because `--config` does not exist.

- [ ] **Step 3: Update CLI options**

Modify `src/wf_transport_rpc_http/cli.py`:

- Add imports:

```python
from wf_config import FilesystemStoreConfig, RpcHttpTransportConfig, load_workflow_config
```

- Change options:

```python
    config: Path | None = typer.Option(
        None,
        "--config",
        help="Path to neutral workflow config JSON.",
    ),
    store_root: Path | None = typer.Option(
        None,
        "--store-root",
        help="Override filesystem workflow store root.",
    ),
```

- Resolve values:

```python
    resolved_store_root = store_root
    resolved_host = host
    resolved_port = port
    if config is not None:
        workflow_config = load_workflow_config(config)
        store = workflow_config.server.store
        if not isinstance(store, FilesystemStoreConfig):
            raise typer.BadParameter("wf-rpc-server currently requires filesystem store")
        resolved_store_root = resolved_store_root or store.root
        rpc_transport = next(
            (
                transport
                for transport in workflow_config.server.transports
                if isinstance(transport, RpcHttpTransportConfig)
            ),
            None,
        )
        if rpc_transport is not None:
            resolved_host = host or rpc_transport.host
            resolved_port = port or rpc_transport.port
    if resolved_store_root is None:
        raise typer.BadParameter("--store-root is required when --config is not supplied")
```

To make host/port overrides work, change defaults to `None`:

```python
host: str | None = typer.Option(None, "--host")
port: int | None = typer.Option(None, "--port", min=1, max=65535)
```

Pass defaults to uvicorn:

```python
uvicorn.run(
    rpc_app,
    host=resolved_host or "127.0.0.1",
    port=resolved_port or 8765,
    access_log=False,
)
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_cli.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_transport_rpc_http/cli.py tests/wf_transport_rpc_http/test_cli.py
git commit -m "feat: load rpc server config"
```

---

## Task 7: Documentation and Verification

**Files:**

- Modify: `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update spec implementation status**

In `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`, add:

```markdown
## Implementation Status

First slice implemented:

- neutral `wf_config` models and loader
- filesystem server store config
- stdlib source bootstrap config
- local and JSON-RPC client targets
- `wf` root overrides for `--local`, `--url`, and `--timeout`
- remote JSON-RPC client support for capability and run CLI commands
- `wf-rpc-server --config` support for server store and RPC HTTP transport

Still future:

- store-backed mutable source registry
- MCP/OpenAPI source config
- `/mcp` hosting from neutral server config
- remote draft/artifact/deployment CLI commands
- auth and SQL stores
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, add:

```markdown
- Completed: workflow config now distinguishes client targets from server
  hosting config, and selected `wf` commands can target JSON-RPC HTTP with
  explicit CLI overrides.
```

- [ ] **Step 3: Run focused verification**

Run:

```bash
uv run pytest tests/wf_config tests/wf_transport_rpc_http tests/wf_cli/test_remote_target.py tests/wf_cli/test_run_deploy.py tests/wf_cli/test_discovery_lifecycle.py -q
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

- pytest passes with existing skip/xfail count.
- ruff passes.
- basedpyright has 0 errors. If the known file enumeration warning appears with exit code 1 but 0 errors, report it explicitly.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md docs/current_roadmap.md
git commit -m "docs: record workflow config target slice"
```

---

## Self-Review Notes

Spec coverage:

- `client.target` default and overrides: Tasks 1, 4, 5.
- `server.store` as tagged union: Tasks 1, 2, 6.
- `server.transports` for RPC HTTP: Tasks 1, 6.
- `server.sources` tagged union with stdlib only: Task 1.
- Store-backed source registry deferred: docs in Task 7.
- No MCP CLI target: enforced by model union in Task 1.
- Remote CLI subset only: Tasks 3-5.

Known risks:

- `wf_transport_rpc_http.client` monkeypatching in CLI tests is awkward because Typer commands call `asyncio.run`. Keep this test narrow; do not overbuild a test framework in this slice.
- `wf_cli.context` still keeps old MCP config compatibility. That dependency should shrink later, but removing it here would make the slice too broad.

