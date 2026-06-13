# Source Auth Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source-level auth and health diagnostics so users can tell whether a source is configured, authenticated, catalogued, and safe to call before running `wf cap call`.

**Architecture:** Keep `wf_api` neutral by adding an optional source diagnostics provider to `WorkflowSourceAdminApi`. Implement MCP-specific checks in `wf_mcp.broker.service.source_diagnostics`, wire that provider into MCP-backed `WorkflowServer`, and expose diagnostics over JSON-RPC and CLI via `wf source diagnose`. `source inspect` should include a compact `diagnostics` block when a provider exists, but local/static servers must keep working without MCP imports.

**Tech Stack:** Python 3.14, dataclasses/protocols, Pydantic JSON-RPC params, Typer CLI, pytest-asyncio, existing `AuthRecord`/`StoredAuthRecord` and MCP broker services.

---

## File Structure

- Modify `src/wf_api/source_admin.py`: add `WorkflowSourceDiagnosticsProvider` protocol, optional `diagnostics` provider, `diagnose_source()`, and optional diagnostics in `inspect_source()`.
- Modify `src/wf_api/surface.py`: add `diagnose_source()` to `WorkflowSourceAdminSurface`.
- Create `src/wf_mcp/broker/service/source_diagnostics.py`: MCP-specific diagnostics provider.
- Modify `src/wf_mcp/broker/server.py`: wire diagnostics provider when building MCP-backed server.
- Modify `src/wf_transport_rpc_http/models.py`: add `DiagnoseSourceParams`.
- Modify `src/wf_transport_rpc_http/methods/sources.py`: register `workflow.sources.diagnose`.
- Modify `src/wf_transport_rpc_http/client/sources.py`: add `diagnose_source()`.
- Modify `src/wf_cli/commands/sources.py`: add `wf source diagnose <source_id>`.
- Add/modify tests:
  - `tests/wf_api/test_source_admin_api.py`
  - `tests/wf_mcp/service/test_source_diagnostics.py`
  - `tests/wf_mcp/test_mcp_workflow_server.py`
  - `tests/wf_transport_rpc_http/test_app.py`
  - `tests/wf_transport_rpc_http/test_client.py`
  - `tests/wf_cli/test_remote_target.py`
- Modify docs:
  - `docs/wf_cli.md`
  - `docs/current_roadmap.md`

---

### Task 1: Neutral Source Diagnostics API

**Files:**
- Modify: `src/wf_api/source_admin.py`
- Modify: `src/wf_api/surface.py`
- Test: `tests/wf_api/test_source_admin_api.py`

- [ ] **Step 1: Write neutral API tests**

Create `tests/wf_api/test_source_admin_api.py` if it does not exist. Add:

```python
from __future__ import annotations

import pytest

from wf_api.operation_context import WorkflowOperationContext
from wf_api.source_admin import WorkflowSourceAdminApi
from wf_api.stores import memory_workflow_stores
from wf_platform import CapabilityBuckets, CapabilitySource


class _Specs:
    def __init__(self) -> None:
        self.capability_sources = {
            "demo.source": CapabilitySource(
                id="demo.source",
                kind="connection",
                capabilities=CapabilityBuckets(),
                description="Demo source",
            )
        }

    def get_qualified_spec(self, qualified_name: str):
        raise KeyError(qualified_name)


class _Diagnostics:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def diagnose_source(self, source_id: str) -> dict[str, object]:
        self.calls.append(source_id)
        return {
            "source_id": source_id,
            "status": "ok",
            "auth": {"record_present": True},
            "diagnostics": [],
        }


def _api(*, diagnostics: object | None = None) -> WorkflowSourceAdminApi:
    stores = memory_workflow_stores()
    context = WorkflowOperationContext(
        artifact_store=stores.artifact_store,
        draft_workspace_store=stores.draft_workspace_store,
        run_store=stores.run_store,
        events=None,
        specs=_Specs(),
        runtime=None,
        live_sources=None,
    )
    return WorkflowSourceAdminApi(context, diagnostics=diagnostics)


@pytest.mark.asyncio
async def test_inspect_source_includes_optional_diagnostics() -> None:
    provider = _Diagnostics()
    payload = await _api(diagnostics=provider).inspect_source(
        source_id="demo.source"
    )

    assert payload["id"] == "demo.source"
    assert payload["diagnostics"]["source_id"] == "demo.source"
    assert provider.calls == ["demo.source"]


@pytest.mark.asyncio
async def test_inspect_source_omits_diagnostics_without_provider() -> None:
    payload = await _api().inspect_source(source_id="demo.source")

    assert payload["id"] == "demo.source"
    assert "diagnostics" not in payload


@pytest.mark.asyncio
async def test_diagnose_source_uses_provider() -> None:
    payload = await _api(diagnostics=_Diagnostics()).diagnose_source(
        source_id="demo.source"
    )

    assert payload["status"] == "ok"
    assert payload["auth"]["record_present"] is True


@pytest.mark.asyncio
async def test_diagnose_source_without_provider_returns_basic_status() -> None:
    payload = await _api().diagnose_source(source_id="demo.source")

    assert payload == {
        "source_id": "demo.source",
        "status": "unknown",
        "diagnostics": [],
        "message": "No source diagnostics provider is configured.",
    }
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_api/test_source_admin_api.py -q
```

Expected: fails because `WorkflowSourceAdminApi.__init__()` has no `diagnostics` argument and `diagnose_source()` does not exist.

- [ ] **Step 3: Implement neutral protocol and API**

In `src/wf_api/source_admin.py`, add:

```python
from typing import Any, Protocol
```

Then add above `WorkflowSourceAdminApi`:

```python
class WorkflowSourceDiagnosticsProvider(Protocol):
    """Optional source-specific diagnostics provider.

    Implementations may know about transport/auth/catalog details. The neutral
    API only forwards source ids and serializes returned dictionaries.
    """

    def diagnose_source(self, source_id: str) -> dict[str, Any]: ...
```

Change the constructor:

```python
def __init__(
    self,
    context: WorkflowOperationContext,
    *,
    diagnostics: WorkflowSourceDiagnosticsProvider | None = None,
) -> None:
    self.context = context
    self.diagnostics = diagnostics
```

Change `inspect_source()` to:

```python
async def inspect_source(self, *, source_id: str) -> dict[str, Any]:
    try:
        source = self.context.specs.capability_sources[source_id]
    except KeyError as exc:
        raise KeyError(f"unknown source {source_id!r}") from exc
    payload = source.as_inventory().model_dump(mode="json")
    if self.diagnostics is not None:
        payload["diagnostics"] = self.diagnostics.diagnose_source(source_id)
    return payload
```

Add:

```python
async def diagnose_source(self, *, source_id: str) -> dict[str, Any]:
    try:
        self.context.specs.capability_sources[source_id]
    except KeyError as exc:
        raise KeyError(f"unknown source {source_id!r}") from exc
    if self.diagnostics is None:
        return {
            "source_id": source_id,
            "status": "unknown",
            "diagnostics": [],
            "message": "No source diagnostics provider is configured.",
        }
    return self.diagnostics.diagnose_source(source_id)
```

In `src/wf_api/surface.py`, add to `WorkflowSourceAdminSurface`:

```python
async def diagnose_source(self, *, source_id: str) -> dict[str, Any]: ...
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_api/test_source_admin_api.py -q
uv run basedpyright --level error src/wf_api/source_admin.py src/wf_api/surface.py tests/wf_api/test_source_admin_api.py
```

Expected: tests pass and typecheck has 0 errors.

Commit:

```bash
git add src/wf_api/source_admin.py src/wf_api/surface.py tests/wf_api/test_source_admin_api.py
git commit -m "feat: add neutral source diagnostics api"
```

---

### Task 2: MCP Source Diagnostics Provider

**Files:**
- Create: `src/wf_mcp/broker/service/source_diagnostics.py`
- Modify: `src/wf_mcp/broker/server.py`
- Test: `tests/wf_mcp/service/test_source_diagnostics.py`
- Test: `tests/wf_mcp/test_mcp_workflow_server.py`

- [ ] **Step 1: Write provider tests**

Create `tests/wf_mcp/service/test_source_diagnostics.py`:

```python
from __future__ import annotations

from wf_api.auth import AuthRecord
from wf_mcp.broker.service.source_diagnostics import SourceDiagnosticsProvider
from wf_mcp.connections import ConnectionRegistry
from wf_mcp.models import ConnectionConfig
from wf_sources_mcp.catalog import CatalogSnapshot
from wf_sources_mcp.storage import FileAuthStore, FileCatalogStore


def _connection(**metadata: object) -> ConnectionConfig:
    return ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        enabled=True,
        metadata={"transport": "http", "url": "https://example.test/mcp", **metadata},
    )


def _provider(tmp_path, connection: ConnectionConfig) -> SourceDiagnosticsProvider:
    registry = ConnectionRegistry()
    registry.register(connection)
    return SourceDiagnosticsProvider(
        connection_lookup=registry.get,
        auth_store=FileAuthStore(tmp_path / "auth"),
        catalog_store=FileCatalogStore(tmp_path / "catalog"),
    )


def test_source_diagnostics_reports_present_auth(tmp_path) -> None:
    connection = _connection(auth_ref="demo.creds")
    provider = _provider(tmp_path, connection)
    provider.auth_store.save_auth(
        AuthRecord(
            connection_id="demo.creds",
            scheme="oauth_refresh_token",
            payload={
                "client_id": "client",
                "client_secret": "secret",
                "refresh_token": "refresh",
                "token_url": "https://oauth2.example.test/token",
            },
        )
    )

    payload = provider.diagnose_source("demo.personal")

    assert payload["source_id"] == "demo.personal"
    assert payload["status"] == "ok"
    assert payload["auth"]["auth_ref"] == "demo.creds"
    assert payload["auth"]["record_present"] is True
    assert payload["auth"]["scheme"] == "oauth_refresh_token"
    assert payload["auth"]["transport_supported"] is True
    assert payload["diagnostics"] == []


def test_source_diagnostics_reports_missing_auth(tmp_path) -> None:
    payload = _provider(
        tmp_path,
        _connection(auth_ref="missing.creds"),
    ).diagnose_source("demo.personal")

    assert payload["status"] == "error"
    assert payload["auth"]["record_present"] is False
    assert payload["diagnostics"][0]["code"] == "auth_not_found"


def test_source_diagnostics_reports_unsupported_transport_auth(tmp_path) -> None:
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        metadata={"transport": "stdio", "command": "demo", "auth_ref": "demo.creds"},
    )
    provider = _provider(tmp_path, connection)
    provider.auth_store.save_auth(
        AuthRecord(
            connection_id="demo.creds",
            scheme="oauth_refresh_token",
            payload={
                "client_id": "client",
                "client_secret": "secret",
                "refresh_token": "refresh",
                "token_url": "https://oauth2.example.test/token",
            },
        )
    )

    payload = provider.diagnose_source("demo.personal")

    assert payload["status"] == "error"
    assert payload["auth"]["transport_supported"] is False
    assert payload["diagnostics"][0]["code"] == "auth_scheme_not_supported"


def test_source_diagnostics_reports_catalog_snapshot(tmp_path) -> None:
    provider = _provider(tmp_path, _connection())
    provider.catalog_store.save_catalog(
        CatalogSnapshot(
            connection_id="demo.personal",
            fetched_at_epoch_ms=123,
            max_age_seconds=60,
        )
    )

    payload = provider.diagnose_source("demo.personal")

    assert payload["catalog"] == {
        "has_snapshot": True,
        "fetched_at_epoch_ms": 123,
        "max_age_seconds": 60,
        "node_count": 0,
        "resource_count": 0,
        "prompt_count": 0,
    }
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_source_diagnostics.py -q
```

Expected: fails because `source_diagnostics.py` does not exist.

- [ ] **Step 3: Implement provider**

Create `src/wf_mcp/broker/service/source_diagnostics.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from wf_api.auth import AuthRecord
from wf_core import DependencyDiagnostic, DiagnosticSeverity
from wf_sources_mcp.auth import connection_auth_diagnostic
from wf_sources_mcp.storage import AuthStore, CatalogStore

from ...models import ConnectionConfig

ConnectionLookup = Callable[[str], ConnectionConfig]


def _auth_ref(connection: ConnectionConfig) -> str | None:
    value = connection.metadata.get("auth_ref")
    return value if isinstance(value, str) and value else None


def _transport_kind(connection: ConnectionConfig) -> str | None:
    value = connection.metadata.get("transport")
    return value if isinstance(value, str) and value else None


def _auth_scheme_supported(
    *,
    transport_kind: str | None,
    auth: AuthRecord | None,
) -> bool:
    if auth is None:
        return True
    if transport_kind == "stdio":
        return auth.scheme == "env"
    if transport_kind == "http":
        return auth.scheme in {"bearer", "headers", "oauth_refresh_token"}
    return False


def _unsupported_auth_diagnostic(
    *,
    source_id: str,
    auth_ref: str,
    scheme: str,
    transport_kind: str | None,
) -> dict[str, Any]:
    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="auth_scheme_not_supported",
        logical_ref=auth_ref,
        bound_source=source_id,
        message=(
            f"Source {source_id!r} uses {transport_kind or 'unknown'} transport, "
            f"but auth record {auth_ref!r} has unsupported scheme {scheme!r}."
        ),
        repair_hint=(
            "Use env auth for stdio MCP sources, or bearer/headers/"
            "oauth_refresh_token auth for HTTP MCP sources."
        ),
    ).model_dump(mode="json")


@dataclass(slots=True)
class SourceDiagnosticsProvider:
    """MCP broker diagnostics for source auth, transport, and catalog state."""

    connection_lookup: ConnectionLookup
    auth_store: AuthStore
    catalog_store: CatalogStore

    def diagnose_source(self, source_id: str) -> dict[str, Any]:
        connection = self.connection_lookup(source_id)
        auth_ref = _auth_ref(connection)
        auth = self.auth_store.load_auth(auth_ref) if auth_ref else None
        transport_kind = _transport_kind(connection)
        snapshot = self.catalog_store.load_catalog(source_id)
        diagnostics: list[dict[str, Any]] = []

        missing_auth = connection_auth_diagnostic(
            connection,
            load_auth_ref=self.auth_store.load_auth,
        )
        if missing_auth is not None:
            diagnostics.append(missing_auth.model_dump(mode="json"))

        transport_supported = _auth_scheme_supported(
            transport_kind=transport_kind,
            auth=auth,
        )
        if auth_ref and auth is not None and not transport_supported:
            diagnostics.append(
                _unsupported_auth_diagnostic(
                    source_id=source_id,
                    auth_ref=auth_ref,
                    scheme=auth.scheme,
                    transport_kind=transport_kind,
                )
            )

        return {
            "source_id": source_id,
            "status": "error" if diagnostics else "ok",
            "enabled": connection.enabled,
            "transport": {
                "kind": transport_kind,
                "configured": transport_kind is not None,
            },
            "auth": {
                "auth_ref": auth_ref,
                "record_present": auth is not None if auth_ref else None,
                "scheme": None if auth is None else auth.scheme,
                "transport_supported": transport_supported,
            },
            "catalog": {
                "has_snapshot": snapshot is not None,
                "fetched_at_epoch_ms": None
                if snapshot is None
                else snapshot.fetched_at_epoch_ms,
                "max_age_seconds": None if snapshot is None else snapshot.max_age_seconds,
                "node_count": 0 if snapshot is None else len(snapshot.nodes),
                "resource_count": 0 if snapshot is None else len(snapshot.resources),
                "prompt_count": 0 if snapshot is None else len(snapshot.prompts),
            },
            "diagnostics": diagnostics,
        }
```

- [ ] **Step 4: Wire provider into MCP-backed server**

In `src/wf_mcp/broker/server.py`, import:

```python
from .service.source_diagnostics import SourceDiagnosticsProvider
```

Inside `workflow_server_from_service()`, construct:

```python
source_diagnostics = SourceDiagnosticsProvider(
    connection_lookup=service.connections.get,
    auth_store=service.auth_store,
    catalog_store=service.catalog_store,
)
```

Change:

```python
source_admin = WorkflowSourceAdminApi(context)
```

to:

```python
source_admin = WorkflowSourceAdminApi(
    context,
    diagnostics=source_diagnostics,
)
```

If the function does not currently name `source_admin`, apply the same change where `WorkflowSourceAdminApi` is constructed.

- [ ] **Step 5: Add server wiring test**

In `tests/wf_mcp/test_mcp_workflow_server.py`, add:

```python
async def test_workflow_server_source_admin_reports_mcp_diagnostics(tmp_path) -> None:
    service = _service(tmp_path)
    payload = await service.workflow_server.source_admin.diagnose_source(
        source_id="demo.personal"
    )

    assert payload["source_id"] == "demo.personal"
    assert "auth" in payload
    assert "catalog" in payload
```

If the local helper is named differently, use the existing helper that builds a `WfMcpService`/`WorkflowServer` with `demo.personal`; keep the assertions above.

- [ ] **Step 6: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_source_diagnostics.py tests/wf_mcp/test_mcp_workflow_server.py -q
uv run basedpyright --level error src/wf_mcp/broker/service/source_diagnostics.py src/wf_mcp/broker/server.py tests/wf_mcp/service/test_source_diagnostics.py tests/wf_mcp/test_mcp_workflow_server.py
```

Expected: tests pass and typecheck has 0 errors.

Commit:

```bash
git add src/wf_mcp/broker/service/source_diagnostics.py src/wf_mcp/broker/server.py tests/wf_mcp/service/test_source_diagnostics.py tests/wf_mcp/test_mcp_workflow_server.py
git commit -m "feat: add mcp source diagnostics provider"
```

---

### Task 3: JSON-RPC Source Diagnose Method

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/sources.py`
- Modify: `src/wf_transport_rpc_http/client/sources.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add RPC tests**

In `tests/wf_transport_rpc_http/test_app.py`, add:

```python
async def test_rpc_diagnoses_source(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path)
    client = TestClient(create_app(server))

    response = client.post(
        "/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "workflow.sources.diagnose",
            "params": {"source_id": "wf.std"},
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["result"]["source_id"] == "wf.std"
    assert payload["result"]["status"] == "unknown"
```

In `tests/wf_transport_rpc_http/test_client.py`, add:

```python
async def test_rpc_client_diagnoses_source(tmp_path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class Client(RpcSourceAdminClientMixin):
        async def _call(self, method: str, params: dict[str, object]):
            calls.append((method, params))
            return {"source_id": params["source_id"], "status": "ok"}

    payload = await Client().diagnose_source(source_id="demo.personal")

    assert payload == {"source_id": "demo.personal", "status": "ok"}
    assert calls == [
        ("workflow.sources.diagnose", {"source_id": "demo.personal"})
    ]
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_diagnoses_source tests/wf_transport_rpc_http/test_client.py::test_rpc_client_diagnoses_source -q
```

Expected: fails because model/method/client are missing.

- [ ] **Step 3: Implement RPC model/method/client**

In `src/wf_transport_rpc_http/models.py`, add:

```python
class DiagnoseSourceParams(RpcParamsModel):
    source_id: str = Field(min_length=1)
```

In `src/wf_transport_rpc_http/methods/sources.py`, import `DiagnoseSourceParams` and add:

```python
@entrypoint.method(name="workflow.sources.diagnose", errors=[WorkflowRpcError])
async def workflow_sources_diagnose(
    params: DiagnoseSourceParams = RpcParams(),
) -> dict[str, Any]:
    try:
        return await server.source_admin.diagnose_source(
            source_id=params.source_id
        )
    except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
        raise_workflow_rpc_error(exc)
```

In `src/wf_transport_rpc_http/client/sources.py`, add:

```python
async def diagnose_source(self: RpcCaller, *, source_id: str) -> dict[str, Any]:
    return await self._call(
        "workflow.sources.diagnose",
        {"source_id": source_id},
    )
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_diagnoses_source tests/wf_transport_rpc_http/test_client.py::test_rpc_client_diagnoses_source -q
uv run basedpyright --level error src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/sources.py src/wf_transport_rpc_http/client/sources.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
```

Expected: tests pass and typecheck has 0 errors.

Commit:

```bash
git add src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/sources.py src/wf_transport_rpc_http/client/sources.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
git commit -m "feat: expose source diagnostics over rpc"
```

---

### Task 4: CLI Source Diagnose Command

**Files:**
- Modify: `src/wf_cli/commands/sources.py`
- Test: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Write CLI tests**

In `tests/wf_cli/test_remote_target.py`, add:

```python
def test_wf_source_diagnose_uses_rpc_url_override(monkeypatch, tmp_path) -> None:
    captured: dict[str, str] = {}

    class FakeSourceAdmin:
        async def diagnose_source(self, *, source_id: str) -> dict[str, object]:
            captured["source_id"] = source_id
            return {
                "source_id": source_id,
                "status": "ok",
                "auth": {
                    "auth_ref": "demo.creds",
                    "record_present": True,
                    "scheme": "bearer",
                    "transport_supported": True,
                },
                "diagnostics": [],
            }

    class FakeContext:
        source_admin = FakeSourceAdmin()

    monkeypatch.setattr(
        "wf_cli.commands.sources.load_cli_context_from_typer",
        lambda ctx: FakeContext(),
    )

    result = runner.invoke(
        app,
        ["--url", "http://127.0.0.1:8765/rpc", "source", "diagnose", "demo.personal"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert captured == {"source_id": "demo.personal"}
    assert payload["status"] == "ok"
    assert payload["auth"]["scheme"] == "bearer"
```

If the file already has a `runner` or `app` helper, use the existing helper names.

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_source_diagnose_uses_rpc_url_override -q
```

Expected: fails because `wf source diagnose` is not registered.

- [ ] **Step 3: Implement CLI command**

In `src/wf_cli/commands/sources.py`, add:

```python
@app.command("diagnose")
def diagnose_source(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Workflow source id.")],
) -> None:
    """Diagnose source transport, auth, and catalog state."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.source_admin.diagnose_source(source_id=source_id),
    )
    emit_json(payload)
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_source_diagnose_uses_rpc_url_override -q
uv run basedpyright --level error src/wf_cli/commands/sources.py tests/wf_cli/test_remote_target.py
```

Expected: tests pass and typecheck has 0 errors.

Commit:

```bash
git add src/wf_cli/commands/sources.py tests/wf_cli/test_remote_target.py
git commit -m "feat: add source diagnose cli"
```

---

### Task 5: Docs And Final Verification

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update CLI docs**

In `docs/wf_cli.md`, add a source diagnostics subsection near the source commands:

```markdown
### Diagnose A Source

Use `wf source diagnose <source_id>` to inspect source health before calling
capabilities:

```bash
wf --config wf.config.json source diagnose gdrive.personal
```

The output reports transport kind, auth reference, whether the auth record
exists, whether the auth scheme is compatible with the transport, catalog
snapshot counts, and non-secret diagnostics. Secret payload values are never
printed.
```
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, add a completed item under the current source/auth roadmap section:

```markdown
- Completed source auth diagnostics: `wf source diagnose <source_id>` now reports
  transport/auth/catalog state without exposing secret payloads.
```

- [ ] **Step 3: Run focused verification**

Run:

```bash
uv run pytest tests/wf_api/test_source_admin_api.py tests/wf_mcp/service/test_source_diagnostics.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py -q
uv run ruff check src/wf_api/source_admin.py src/wf_api/surface.py src/wf_mcp/broker/service/source_diagnostics.py src/wf_mcp/broker/server.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/sources.py src/wf_transport_rpc_http/client/sources.py src/wf_cli/commands/sources.py tests/wf_api/test_source_admin_api.py tests/wf_mcp/service/test_source_diagnostics.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py
uv run basedpyright --level error src/wf_api/source_admin.py src/wf_api/surface.py src/wf_mcp/broker/service/source_diagnostics.py src/wf_mcp/broker/server.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/sources.py src/wf_transport_rpc_http/client/sources.py src/wf_cli/commands/sources.py tests/wf_api/test_source_admin_api.py tests/wf_mcp/service/test_source_diagnostics.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py
```

Expected:

- Focused tests pass.
- Ruff reports `All checks passed!`.
- Basedpyright reports `0 errors`.

- [ ] **Step 4: Commit docs**

```bash
git add docs/wf_cli.md docs/current_roadmap.md
git commit -m "docs: document source diagnostics"
```

---

## Self-Review

- Spec coverage: plan adds neutral API, MCP diagnostics provider, RPC/client method, CLI command, docs, and tests. It explicitly avoids secret payload output.
- Placeholder scan: no `TBD`, `TODO`, or "similar to" placeholders remain.
- Type consistency: method name is `diagnose_source` across API, surface, RPC client, CLI, and tests. RPC method name is `workflow.sources.diagnose`. Payload uses `diagnostics` for the diagnostic list and `auth`/`catalog` for structured summaries.

