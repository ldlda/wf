# Auth Admin Read Slice 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only auth admin surface that lists and inspects auth records without exposing secret payload values.

**Architecture:** Extend the existing neutral `WorkflowAdminApi` surface instead of creating a new top-level server field. Providers return safe auth summaries only: id, scheme, metadata, payload keys. MCP implements the provider from its existing store; JSON-RPC and CLI expose read-only methods. No save/delete/auth mutation and no provider-specific display promises in this slice.

**Tech Stack:** Python 3.14, dataclasses, protocols, Typer, JSON-RPC HTTP, pytest, ruff, basedpyright.

---

## Scope

Implement only:

- read-only auth summaries
- inspect one auth summary by auth ref
- JSON-RPC methods
- RPC client methods
- CLI commands under `wf admin auth`

Do not implement:

- secret payload output
- auth save/delete/update commands
- provider-specific display structs
- OAuth/secret-manager behavior
- changes to source registry mutation behavior

## Files

- Modify: `src/wf_api/admin.py`
  - add `WorkflowAdminAuthProvider`
  - add optional auth provider to `WorkflowAdminApi`
  - add `list_auth_records` / `inspect_auth_record`
- Modify: `src/wf_api/surface.py`
  - add auth methods to `WorkflowAdminSurface`
- Modify: `src/wf_api/__init__.py`
  - export `WorkflowAdminAuthProvider`
- Modify: `src/wf_mcp/storage/store.py`
  - add `list_auth_refs`
- Create: `src/wf_mcp/broker/service/auth_admin.py`
  - `McpAuthAdminProvider`
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
  - expose auth admin provider or list refs through store if needed
- Modify: `src/wf_mcp/broker/server.py`
  - wire `WorkflowAdminApi(..., auth=...)`
- Modify: `src/wf_server/context.py`
  - local/static admin uses no auth provider and reports unavailable
- Modify: `src/wf_transport_rpc_http/methods_admin.py`
  - register `workflow.admin.auth.list` / `.inspect`
- Modify: `src/wf_transport_rpc_http/models.py`
  - add `InspectAuthParams`
- Modify: `src/wf_transport_rpc_http/client_admin.py`
  - add client methods
- Modify: `src/wf_cli/commands/admin.py`
  - add auth sub-Typer
- Create: `src/wf_cli/commands/auth_admin.py`
  - `wf admin auth list` / `inspect`
- Tests:
  - `tests/wf_api/test_admin_api.py` or create if absent
  - `tests/wf_mcp/service/test_auth_admin.py`
  - `tests/wf_transport_rpc_http/test_admin_auth_rpc.py`
  - `tests/wf_cli/test_auth_admin.py`
- Docs:
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`

## Task 1: Neutral admin auth surface

**Files:**
- Modify: `src/wf_api/admin.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/__init__.py`
- Test: `tests/wf_api/test_admin_api.py`

- [ ] **Step 1: Add/extend wf_api admin tests**

If `tests/wf_api/test_admin_api.py` does not exist, create it with the imports
below. If it exists, append these tests.

```python
from __future__ import annotations

import pytest

from wf_api.admin import WorkflowAdminApi


class EmptyConnectionProvider:
    def list_connections(self):
        return []

    def get_connection_statuses(self):
        return []


class EmptyEventProvider:
    def list_events(self):
        return []


class AuthProvider:
    def list_auth_records(self):
        return [
            {
                "id": "github.work",
                "scheme": "bearer",
                "metadata": {"owner": "platform"},
                "payload_keys": ["token"],
            },
            {
                "id": "api.work",
                "scheme": "headers",
                "metadata": {},
                "payload_keys": ["headers"],
            },
        ]

    def inspect_auth_record(self, auth_ref: str):
        for record in self.list_auth_records():
            if record["id"] == auth_ref:
                return record
        raise KeyError(auth_ref)


def _api(auth=None) -> WorkflowAdminApi:
    return WorkflowAdminApi(
        connections=EmptyConnectionProvider(),
        events=EmptyEventProvider(),
        auth=auth,
    )


async def test_admin_lists_auth_records_sorted_without_payload_values() -> None:
    payload = await _api(AuthProvider()).list_auth_records()

    assert payload["total"] == 2
    assert [record["id"] for record in payload["auth_records"]] == [
        "api.work",
        "github.work",
    ]
    assert payload["auth_records"][0]["payload_keys"] == ["headers"]
    assert "payload" not in payload["auth_records"][0]


async def test_admin_inspects_auth_record_without_payload_values() -> None:
    payload = await _api(AuthProvider()).inspect_auth_record("github.work")

    assert payload == {
        "id": "github.work",
        "scheme": "bearer",
        "metadata": {"owner": "platform"},
        "payload_keys": ["token"],
    }


async def test_admin_auth_methods_report_unavailable_without_provider() -> None:
    with pytest.raises(RuntimeError, match="auth admin is not available"):
        await _api().list_auth_records()

    with pytest.raises(RuntimeError, match="auth admin is not available"):
        await _api().inspect_auth_record("github.work")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_api/test_admin_api.py -q
```

Expected: fails because `WorkflowAdminApi` does not accept `auth` and auth methods do not exist.

- [ ] **Step 3: Add provider protocol and API methods**

Modify `src/wf_api/admin.py`.

Add protocol:

```python
class WorkflowAdminAuthProvider(Protocol):
    """Provides read-only auth inventory without secret payload values."""

    def list_auth_records(self) -> Sequence[Mapping[str, Any] | object]: ...

    def inspect_auth_record(self, auth_ref: str) -> Mapping[str, Any] | object: ...
```

Change `WorkflowAdminApi.__init__` signature:

```python
    def __init__(
        self,
        *,
        connections: WorkflowAdminConnectionProvider,
        events: WorkflowAdminEventProvider,
        auth: WorkflowAdminAuthProvider | None = None,
    ) -> None:
        self.connections = connections
        self.events = events
        self.auth = auth
```

Add methods:

```python
    async def list_auth_records(self) -> dict[str, Any]:
        if self.auth is None:
            raise RuntimeError("auth admin is not available for this target")
        records = sorted(
            (_payload(item) for item in self.auth.list_auth_records()),
            key=lambda item: str(item.get("id", "")),
        )
        return {"auth_records": records, "total": len(records)}

    async def inspect_auth_record(self, auth_ref: str) -> dict[str, Any]:
        if self.auth is None:
            raise RuntimeError("auth admin is not available for this target")
        return _payload(self.auth.inspect_auth_record(auth_ref))
```

- [ ] **Step 4: Update surface protocol**

Modify `src/wf_api/surface.py`.

In `WorkflowAdminSurface`, add:

```python
    async def list_auth_records(self) -> dict[str, Any]: ...

    async def inspect_auth_record(self, auth_ref: str) -> dict[str, Any]: ...
```

If `Any` is not imported in that file, add:

```python
from typing import Any
```

- [ ] **Step 5: Export provider**

Modify `src/wf_api/__init__.py`.

Add to admin import:

```python
WorkflowAdminAuthProvider,
```

Add to `__all__`:

```python
"WorkflowAdminAuthProvider",
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_admin_api.py tests/wf_api/test_import_direction.py -q
uv run ruff check src/wf_api/admin.py src/wf_api/surface.py src/wf_api/__init__.py tests/wf_api/test_admin_api.py
uv run basedpyright --level error src/wf_api tests/wf_api/test_admin_api.py
```

Expected: all pass.

## Task 2: MCP auth admin provider

**Files:**
- Modify: `src/wf_mcp/storage/store.py`
- Create: `src/wf_mcp/broker/service/auth_admin.py`
- Test: `tests/wf_mcp/service/test_auth_admin.py`

- [ ] **Step 1: Add provider tests**

Create `tests/wf_mcp/service/test_auth_admin.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from wf_mcp.broker.service.auth_admin import McpAuthAdminProvider
from wf_mcp.models import AuthRecord
from wf_mcp.storage import FileStore


def _store(tmp_path: Path) -> FileStore:
    return FileStore(tmp_path)


def test_auth_admin_lists_safe_summaries_sorted(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "secret", "headers": {"Authorization": "Bearer secret"}},
        )
    )
    store.save_auth(
        AuthRecord(
            connection_id="api.work",
            scheme="headers",
            payload={"headers": {"X-API-Key": "secret"}},
        )
    )
    provider = McpAuthAdminProvider(store=store)

    records = provider.list_auth_records()

    assert records == [
        {
            "id": "api.work",
            "scheme": "headers",
            "metadata": {},
            "payload_keys": ["headers"],
        },
        {
            "id": "github.work",
            "scheme": "bearer",
            "metadata": {},
            "payload_keys": ["headers", "token"],
        },
    ]


def test_auth_admin_inspects_safe_summary(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "secret"},
        )
    )
    provider = McpAuthAdminProvider(store=store)

    assert provider.inspect_auth_record("github.work") == {
        "id": "github.work",
        "scheme": "bearer",
        "metadata": {},
        "payload_keys": ["token"],
    }


def test_auth_admin_inspect_unknown_raises_key_error(tmp_path: Path) -> None:
    provider = McpAuthAdminProvider(store=_store(tmp_path))

    with pytest.raises(KeyError, match="unknown auth record"):
        provider.inspect_auth_record("missing.auth")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_auth_admin.py -q
```

Expected: fails because `McpAuthAdminProvider` does not exist and `FileStore` cannot list auth refs.

- [ ] **Step 3: Add `list_auth_refs` to store**

Modify `src/wf_mcp/storage/store.py`.

Add to `class Store`:

```python
    def list_auth_refs(self) -> list[str]:
        raise NotImplementedError
```

Add to `class FileStore`:

```python
    def list_auth_refs(self) -> list[str]:
        """Return auth refs present in the local file auth store."""

        return sorted(path.stem for path in self.auth_dir.glob("*.json"))
```

- [ ] **Step 4: Create MCP auth admin provider**

Create `src/wf_mcp/broker/service/auth_admin.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wf_api import WorkflowAdminAuthProvider

from ...storage import Store


@dataclass(frozen=True, slots=True)
class McpAuthAdminProvider(WorkflowAdminAuthProvider):
    """Read-only auth inventory for MCP-backed workflow servers.

    Summaries intentionally expose payload keys, not payload values. Concrete
    auth variants can provide richer safe display later.
    """

    store: Store

    def list_auth_records(self) -> list[dict[str, Any]]:
        return [
            self.inspect_auth_record(auth_ref)
            for auth_ref in sorted(self.store.list_auth_refs())
        ]

    def inspect_auth_record(self, auth_ref: str) -> dict[str, Any]:
        record = self.store.load_auth(auth_ref)
        if record is None:
            raise KeyError(f"unknown auth record {auth_ref!r}")
        return {
            "id": record.connection_id,
            "scheme": record.scheme,
            "metadata": {},
            "payload_keys": sorted(str(key) for key in record.payload),
        }


__all__ = ["McpAuthAdminProvider"]
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_auth_admin.py tests/wf_mcp/test_store.py -q
uv run ruff check src/wf_mcp/storage/store.py src/wf_mcp/broker/service/auth_admin.py tests/wf_mcp/service/test_auth_admin.py
uv run basedpyright --level error src/wf_mcp/storage/store.py src/wf_mcp/broker/service/auth_admin.py tests/wf_mcp/service/test_auth_admin.py
```

Expected: all pass.

## Task 3: Wire MCP-backed server admin auth provider

**Files:**
- Modify: `src/wf_mcp/broker/server.py`
- Test: `tests/wf_mcp/test_mcp_workflow_server.py`

- [ ] **Step 1: Add server wiring test**

Append to `tests/wf_mcp/test_mcp_workflow_server.py`:

```python
async def test_workflow_server_from_service_exposes_auth_admin(tmp_path: Path) -> None:
    from wf_mcp.models import AuthRecord

    service = WfMcpService(store=FileStore(tmp_path))
    service.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "secret"},
        )
    )
    server = workflow_server_from_service(service)

    payload = await server.admin.list_auth_records()

    assert payload["auth_records"] == [
        {
            "id": "github.work",
            "scheme": "bearer",
            "metadata": {},
            "payload_keys": ["token"],
        }
    ]
```

If the file uses a helper for `WfMcpService`, follow its existing style but keep
`tmp_path`.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_mcp_workflow_server.py::test_workflow_server_from_service_exposes_auth_admin -q
```

Expected: fails because MCP-backed server does not wire an auth provider.

- [ ] **Step 3: Wire provider**

Modify `src/wf_mcp/broker/server.py`.

Add import:

```python
from .service.auth_admin import McpAuthAdminProvider
```

Find `WorkflowAdminApi(...)` construction in `workflow_server_from_service`.
Change it to pass:

```python
auth=McpAuthAdminProvider(store=service.store),
```

Do not add an auth provider to local/static server construction.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_mcp_workflow_server.py tests/wf_server/test_local_static_server.py -q
uv run ruff check src/wf_mcp/broker/server.py tests/wf_mcp/test_mcp_workflow_server.py
uv run basedpyright --level error src/wf_mcp/broker/server.py tests/wf_mcp/test_mcp_workflow_server.py
```

Expected: all pass. Local/static server should still report auth admin unavailable through `WorkflowAdminApi`.

## Task 4: JSON-RPC methods and client

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods_admin.py`
- Modify: `src/wf_transport_rpc_http/client_admin.py`
- Test: `tests/wf_transport_rpc_http/test_admin_auth_rpc.py`

- [ ] **Step 1: Add RPC tests**

Create `tests/wf_transport_rpc_http/test_admin_auth_rpc.py`:

```python
from __future__ import annotations

import pytest

from wf_mcp.broker import WfMcpService
from wf_mcp.broker.server import workflow_server_from_service
from wf_mcp.models import AuthRecord
from wf_mcp.storage import FileStore
from wf_transport_rpc_http.app import create_rpc_app
from wf_transport_rpc_http.client import RpcWorkflowApiClient


@pytest.mark.anyio
async def test_rpc_lists_auth_records(tmp_path):
    service = WfMcpService(store=FileStore(tmp_path))
    service.save_auth(AuthRecord(connection_id="github.work", scheme="bearer", payload={"token": "secret"}))
    app = create_rpc_app(workflow_server_from_service(service))
    client = RpcWorkflowApiClient.from_asgi_app(app, url="http://test/rpc")

    payload = await client.list_auth_records()

    assert payload["auth_records"] == [
        {
            "id": "github.work",
            "scheme": "bearer",
            "metadata": {},
            "payload_keys": ["token"],
        }
    ]


@pytest.mark.anyio
async def test_rpc_inspects_auth_record(tmp_path):
    service = WfMcpService(store=FileStore(tmp_path))
    service.save_auth(AuthRecord(connection_id="github.work", scheme="bearer", payload={"token": "secret"}))
    app = create_rpc_app(workflow_server_from_service(service))
    client = RpcWorkflowApiClient.from_asgi_app(app, url="http://test/rpc")

    payload = await client.inspect_auth_record("github.work")

    assert payload["id"] == "github.work"
    assert payload["payload_keys"] == ["token"]
    assert "payload" not in payload
```

If existing RPC tests use `async def` without `pytest.mark.anyio`, follow the
existing local style instead.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_admin_auth_rpc.py -q
```

Expected: fails because RPC methods/client methods do not exist.

- [ ] **Step 3: Add params model**

Modify `src/wf_transport_rpc_http/models.py`.

Add:

```python
class InspectAuthParams(RpcBaseModel):
    auth_ref: str = Field(min_length=1)
```

Use the same base model and `Field` import already used in this file.

- [ ] **Step 4: Register RPC methods**

Modify `src/wf_transport_rpc_http/methods_admin.py`.

Add import:

```python
from .models import AdminEmptyParams, InspectAuthParams
```

Add methods inside `register_methods`:

```python
    @entrypoint.method(name="workflow.admin.auth.list", errors=[WorkflowRpcError])
    async def workflow_admin_auth_list(
        params: AdminEmptyParams = Body(default_factory=AdminEmptyParams),
    ) -> dict[str, Any]:
        try:
            return await server.admin.list_auth_records()
        except (ValueError, KeyError, LookupError, FileNotFoundError, RuntimeError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(name="workflow.admin.auth.inspect", errors=[WorkflowRpcError])
    async def workflow_admin_auth_inspect(
        params: InspectAuthParams,
    ) -> dict[str, Any]:
        try:
            return await server.admin.inspect_auth_record(params.auth_ref)
        except (ValueError, KeyError, LookupError, FileNotFoundError, RuntimeError) as exc:
            raise_workflow_rpc_error(exc)
```

If ruff flags line length on the exception tuple, wrap it like existing methods.

- [ ] **Step 5: Add client methods**

Modify `src/wf_transport_rpc_http/client_admin.py`.

Add:

```python
    async def list_auth_records(self) -> dict[str, Any]:
        return await self._call("workflow.admin.auth.list", {})

    async def inspect_auth_record(self, auth_ref: str) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.auth.inspect",
            {"auth_ref": auth_ref},
        )
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_admin_auth_rpc.py -q
uv run ruff check src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods_admin.py src/wf_transport_rpc_http/client_admin.py tests/wf_transport_rpc_http/test_admin_auth_rpc.py
uv run basedpyright --level error src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods_admin.py src/wf_transport_rpc_http/client_admin.py tests/wf_transport_rpc_http/test_admin_auth_rpc.py
```

Expected: all pass.

## Task 5: CLI commands

**Files:**
- Create: `src/wf_cli/commands/auth_admin.py`
- Modify: `src/wf_cli/commands/admin.py`
- Test: `tests/wf_cli/test_auth_admin.py`

- [ ] **Step 1: Add CLI tests**

Create `tests/wf_cli/test_auth_admin.py`:

```python
from __future__ import annotations

from typer.testing import CliRunner

from wf_cli.app import app


class FakeAdmin:
    async def list_auth_records(self):
        return {
            "auth_records": [
                {
                    "id": "github.work",
                    "scheme": "bearer",
                    "metadata": {},
                    "payload_keys": ["token"],
                }
            ],
            "total": 1,
        }

    async def inspect_auth_record(self, auth_ref: str):
        return {
            "id": auth_ref,
            "scheme": "bearer",
            "metadata": {},
            "payload_keys": ["token"],
        }


class FakeContext:
    admin = FakeAdmin()
    verbose = False


def test_wf_admin_auth_list(monkeypatch) -> None:
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: FakeContext(),
    )

    result = CliRunner().invoke(app, ["admin", "auth", "list"])

    assert result.exit_code == 0
    assert "github.work" in result.stdout
    assert "secret" not in result.stdout


def test_wf_admin_auth_inspect(monkeypatch) -> None:
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda ctx: FakeContext(),
    )

    result = CliRunner().invoke(app, ["admin", "auth", "inspect", "github.work"])

    assert result.exit_code == 0
    assert "github.work" in result.stdout
    assert "payload_keys" in result.stdout
    assert "secret" not in result.stdout
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_auth_admin.py -q
```

Expected: fails because `wf admin auth` commands do not exist.

- [ ] **Step 3: Create CLI command module**

Create `src/wf_cli/commands/auth_admin.py`:

```python
from __future__ import annotations

from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_detail_payload, emit_list_payload
from wf_cli.remote_errors import run_cli_operation

app = typer.Typer(
    name="auth",
    help="Read auth record status without exposing secret payload values.",
    no_args_is_help=True,
)


@app.command("list")
def list_auth_records(
    ctx: typer.Context,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List auth records known to the target."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(context, context.admin.list_auth_records())
    emit_list_payload(
        payload,
        collection_key="auth_records",
        output_format=output_format,
        id_field="id",
        summary_fields=("scheme", "payload_keys"),
    )


@app.command("inspect")
def inspect_auth_record(
    ctx: typer.Context,
    auth_ref: Annotated[str, typer.Argument(help="Auth record id/ref.")],
) -> None:
    """Inspect one auth record summary without secret payload values."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.admin.inspect_auth_record(auth_ref),
    )
    emit_detail_payload(payload)
```

If `emit_detail_payload` has a different name in `wf_cli.formats`, inspect the
file and use the existing detail emitter.

- [ ] **Step 4: Register subcommand**

Modify `src/wf_cli/commands/admin.py`.

Change:

```python
from . import source_registry
```

to:

```python
from . import auth_admin, source_registry
```

Add after registry registration:

```python
app.add_typer(auth_admin.app, name="auth")
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/wf_cli/test_auth_admin.py -q
uv run ruff check src/wf_cli/commands/auth_admin.py src/wf_cli/commands/admin.py tests/wf_cli/test_auth_admin.py
uv run basedpyright --level error src/wf_cli/commands/auth_admin.py src/wf_cli/commands/admin.py tests/wf_cli/test_auth_admin.py
```

Expected: all pass.

## Task 6: Docs and final verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`

- [ ] **Step 1: Update spec status**

In `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`, update
the `## Status` section to:

```markdown
Slice 1 implements the neutral auth record/store protocol and MCP compatibility
bridge. Slice 2 surfaces missing explicit auth refs through live source
diagnostics and source registry apply summaries. Slice 3 exposes read-only auth
admin summaries without secret payload values. Auth mutation surfaces and
provider-specific auth unions are future slices.
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, under the auth/source secrets boundary bullet,
append:

```markdown
    Third implementation slice complete: read-only auth admin summaries are
    available through MCP-backed server admin, JSON-RPC, and CLI. Summaries show
    ids, schemes, metadata, and payload keys only; secret payload values remain
    hidden.
```

- [ ] **Step 3: Run final verification**

Run:

```bash
uv run pytest tests/wf_api/test_admin_api.py tests/wf_mcp/service/test_auth_admin.py tests/wf_mcp/test_mcp_workflow_server.py tests/wf_transport_rpc_http/test_admin_auth_rpc.py tests/wf_cli/test_auth_admin.py -q
uv run ruff check src/wf_api/admin.py src/wf_api/surface.py src/wf_api/__init__.py src/wf_mcp/storage/store.py src/wf_mcp/broker/service/auth_admin.py src/wf_mcp/broker/server.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods_admin.py src/wf_transport_rpc_http/client_admin.py src/wf_cli/commands/auth_admin.py src/wf_cli/commands/admin.py tests/wf_api/test_admin_api.py tests/wf_mcp/service/test_auth_admin.py tests/wf_transport_rpc_http/test_admin_auth_rpc.py tests/wf_cli/test_auth_admin.py
uv run basedpyright --level error src/wf_api src/wf_mcp/broker/service/auth_admin.py src/wf_mcp/storage/store.py src/wf_transport_rpc_http src/wf_cli/commands/auth_admin.py tests/wf_api/test_admin_api.py tests/wf_mcp/service/test_auth_admin.py tests/wf_transport_rpc_http/test_admin_auth_rpc.py tests/wf_cli/test_auth_admin.py
```

Expected: all pass.

- [ ] **Step 4: Final report**

Report:

- files changed
- verification output
- final auth summary shape
- confirmation that no secret payload values are returned
- deviations from this plan

