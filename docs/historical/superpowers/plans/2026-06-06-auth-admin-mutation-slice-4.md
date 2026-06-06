# Auth Admin Mutation Slice 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local/dev auth record save and delete through neutral admin, JSON-RPC, and `wf admin auth` CLI without exposing secret payload values in responses.

**Architecture:** Extend the existing neutral `WorkflowAdminApi` auth surface with mutation methods, then implement those methods in the MCP-backed file-store provider. JSON-RPC and CLI call the neutral admin surface; do not add new `wf-mcp` tools or old broker-only product behavior. This is a local/dev file-store slice only: no OAuth, no production secret manager, no provider-specific auth variants, and no secret payload values in response bodies.

**Tech Stack:** Python 3.14, dataclasses, Pydantic v2, Typer, JSON-RPC HTTP transport, pytest, ruff, basedpyright.

---

## Boundaries

- Do not add new behavior to the legacy `wf-mcp` script.
- Do not expose auth payload values in list, inspect, save, or delete responses.
- Do not support inline auth records in `wf_config` or source registry documents.
- Do not add OAuth/browser login, encryption, or secret-manager integration.
- Do not change the on-disk auth JSON shape in this slice.
- Do use `wf_api.auth.AuthRecord` as the neutral input shape for save/upsert.
- Do keep the current compatibility `wf_mcp.auth.AuthRecord(connection_id, scheme, payload)` file adapter.

## Files

- Modify `src/wf_api/admin.py`
  - Add mutation methods to `WorkflowAdminAuthProvider`.
  - Add `WorkflowAdminApi.save_auth_record(...)`.
  - Add `WorkflowAdminApi.delete_auth_record(...)`.
- Modify `src/wf_api/surface.py`
  - Add mutation methods to `WorkflowAdminSurface`.
- Modify `src/wf_mcp/storage/store.py`
  - Add `delete_auth(...)` and `delete_auth_record(...)` to `Store` / `FileStore`.
- Modify `src/wf_mcp/broker/service/auth_admin.py`
  - Implement save/delete using `Store.save_auth_record` and `Store.delete_auth_record`.
- Modify `src/wf_transport_rpc_http/models.py`
  - Add `SaveAuthParams` and `DeleteAuthParams`.
- Modify `src/wf_transport_rpc_http/methods_admin.py`
  - Register `workflow.admin.auth.save` and `workflow.admin.auth.delete`.
- Modify `src/wf_transport_rpc_http/client_admin.py`
  - Add `save_auth_record(...)` and `delete_auth_record(...)`.
- Modify `src/wf_cli/commands/auth_admin.py`
  - Add `wf admin auth save`.
  - Add `wf admin auth delete --confirm`.
- Modify docs:
  - `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`
  - `docs/current_roadmap.md`
  - `docs/wf_cli.md`
- Add/update tests:
  - `tests/wf_api/test_admin_api.py`
  - `tests/wf_mcp/service/test_auth_admin.py`
  - `tests/wf_mcp/test_auth.py` or `tests/wf_mcp/test_store.py`
  - `tests/wf_transport_rpc_http/test_admin_auth_rpc.py`
  - `tests/wf_cli/test_auth_admin.py`

---

### Task 1: Neutral Admin Auth Mutation Surface

**Files:**
- Modify: `src/wf_api/admin.py`
- Modify: `src/wf_api/surface.py`
- Test: `tests/wf_api/test_admin_api.py`

- [ ] **Step 1: Add failing neutral API tests**

Append these tests to `tests/wf_api/test_admin_api.py`. If a local fake provider already exists in the file, extend it instead of duplicating the whole class.

```python
from wf_api.auth import AuthRecord


class MutableAuthProvider(AuthProvider):
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def list_auth_records(self):
        return list(self.records.values())

    def inspect_auth_record(self, auth_ref: str):
        try:
            return self.records[auth_ref]
        except KeyError as exc:
            raise KeyError(auth_ref) from exc

    def save_auth_record(self, record: AuthRecord):
        self.records[record.id] = {
            "id": record.id,
            "scheme": record.scheme,
            "metadata": dict(record.metadata),
            "payload_keys": sorted(str(key) for key in record.payload),
        }
        return self.records[record.id]

    def delete_auth_record(self, auth_ref: str):
        if auth_ref not in self.records:
            raise KeyError(auth_ref)
        del self.records[auth_ref]
        return {"deleted": True, "id": auth_ref}


def test_admin_saves_auth_record_without_payload_values() -> None:
    provider = MutableAuthProvider()
    api = _api(provider)

    payload = asyncio.run(
        api.save_auth_record(
            auth_ref="drive.work",
            scheme="bearer",
            payload={"token": "secret"},
            metadata={"owner": "test"},
        )
    )

    assert payload == {
        "id": "drive.work",
        "scheme": "bearer",
        "metadata": {"owner": "test"},
        "payload_keys": ["token"],
    }
    assert "secret" not in str(payload)


def test_admin_deletes_auth_record() -> None:
    provider = MutableAuthProvider()
    api = _api(provider)
    asyncio.run(
        api.save_auth_record(
            auth_ref="drive.work",
            scheme="bearer",
            payload={"token": "secret"},
        )
    )

    payload = asyncio.run(api.delete_auth_record("drive.work"))

    assert payload == {"deleted": True, "id": "drive.work"}
    with pytest.raises(KeyError):
        provider.inspect_auth_record("drive.work")


def test_admin_auth_mutations_report_unavailable_without_provider() -> None:
    with pytest.raises(RuntimeError, match="auth admin is not available"):
        asyncio.run(
            _api().save_auth_record(
                auth_ref="drive.work",
                scheme="bearer",
                payload={"token": "secret"},
            )
        )

    with pytest.raises(RuntimeError, match="auth admin is not available"):
        asyncio.run(_api().delete_auth_record("drive.work"))
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
uv run pytest tests\wf_api\test_admin_api.py -q
```

Expected: fail because `WorkflowAdminApi.save_auth_record` and `delete_auth_record` do not exist.

- [ ] **Step 3: Implement neutral API methods**

In `src/wf_api/admin.py`, add:

```python
from wf_api.auth import AuthRecord
```

Extend `WorkflowAdminAuthProvider`:

```python
class WorkflowAdminAuthProvider(Protocol):
    """Provides auth inventory and local/dev auth mutation."""

    def list_auth_records(self) -> Sequence[Mapping[str, Any] | object]: ...

    def inspect_auth_record(self, auth_ref: str) -> Mapping[str, Any] | object: ...

    def save_auth_record(self, record: AuthRecord) -> Mapping[str, Any] | object: ...

    def delete_auth_record(self, auth_ref: str) -> Mapping[str, Any] | object: ...
```

Add methods to `WorkflowAdminApi`:

```python
    async def save_auth_record(
        self,
        *,
        auth_ref: str,
        scheme: str,
        payload: Mapping[str, object],
        metadata: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        if self.auth is None:
            raise RuntimeError("auth admin is not available for this target")
        record = AuthRecord(
            id=auth_ref,
            scheme=scheme,
            payload=dict(payload),
            metadata=dict(metadata or {}),
        )
        return _payload(self.auth.save_auth_record(record))

    async def delete_auth_record(self, auth_ref: str) -> dict[str, Any]:
        if self.auth is None:
            raise RuntimeError("auth admin is not available for this target")
        return _payload(self.auth.delete_auth_record(auth_ref))
```

In `src/wf_api/surface.py`, add these methods to `WorkflowAdminSurface`:

```python
    async def save_auth_record(
        self,
        *,
        auth_ref: str,
        scheme: str,
        payload: Mapping[str, object],
        metadata: Mapping[str, object] | None = None,
    ) -> dict[str, Any]: ...

    async def delete_auth_record(self, auth_ref: str) -> dict[str, Any]: ...
```

If `Mapping` is not imported in `surface.py`, import it from `collections.abc`.

- [ ] **Step 4: Run tests**

Run:

```powershell
uv run pytest tests\wf_api\test_admin_api.py -q
uv run ruff check src\wf_api\admin.py src\wf_api\surface.py tests\wf_api\test_admin_api.py
uv run basedpyright --level error src\wf_api\admin.py src\wf_api\surface.py tests\wf_api\test_admin_api.py
```

Expected: pass.

---

### Task 2: MCP File Store Save/Delete Provider

**Files:**
- Modify: `src/wf_mcp/storage/store.py`
- Modify: `src/wf_mcp/broker/service/auth_admin.py`
- Test: `tests/wf_mcp/test_store.py`
- Test: `tests/wf_mcp/service/test_auth_admin.py`

- [ ] **Step 1: Add failing store tests**

Append to `tests/wf_mcp/test_store.py`:

```python
def test_file_store_deletes_auth_record(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    record = AuthRecord(
        connection_id="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
    )
    store.save_auth(record)

    assert store.load_auth("drive.work") == record
    assert store.delete_auth("drive.work") is True
    assert store.load_auth("drive.work") is None
    assert store.delete_auth("drive.work") is False


def test_file_store_deletes_neutral_auth_record(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    store.save_auth_record(
        NeutralAuthRecord(
            id="drive.work",
            scheme="bearer",
            payload={"token": "secret"},
        )
    )

    assert store.delete_auth_record("drive.work") is True
    assert store.load_auth_record("drive.work") is None
```

Add imports if needed:

```python
from wf_api.auth import AuthRecord as NeutralAuthRecord
```

- [ ] **Step 2: Add failing provider tests**

Append to `tests/wf_mcp/service/test_auth_admin.py`:

```python
from wf_api.auth import AuthRecord as NeutralAuthRecord


def test_auth_admin_provider_saves_auth_without_returning_payload(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    provider = McpAuthAdminProvider(store)

    payload = provider.save_auth_record(
        NeutralAuthRecord(
            id="drive.work",
            scheme="bearer",
            payload={"token": "secret"},
            metadata={"owner": "test"},
        )
    )

    assert payload == {
        "id": "drive.work",
        "scheme": "bearer",
        "metadata": {},
        "payload_keys": ["token"],
    }
    assert "secret" not in str(payload)
    assert store.load_auth("drive.work") == AuthRecord(
        connection_id="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
    )


def test_auth_admin_provider_deletes_auth(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    provider = McpAuthAdminProvider(store)
    store.save_auth(AuthRecord(connection_id="drive.work", scheme="bearer"))

    payload = provider.delete_auth_record("drive.work")

    assert payload == {"deleted": True, "id": "drive.work"}
    assert store.load_auth("drive.work") is None


def test_auth_admin_provider_delete_unknown_auth_raises_key_error(tmp_path) -> None:
    provider = McpAuthAdminProvider(FileStore(tmp_path / "store"))

    with pytest.raises(KeyError, match="unknown auth record 'missing'"):
        provider.delete_auth_record("missing")
```

- [ ] **Step 3: Run failing tests**

Run:

```powershell
uv run pytest tests\wf_mcp\test_store.py tests\wf_mcp\service\test_auth_admin.py -q
```

Expected: fail because delete/save provider mutation methods are missing.

- [ ] **Step 4: Implement store delete methods**

In `src/wf_mcp/storage/store.py`, extend `Store`:

```python
    def delete_auth(self, connection_id: str) -> bool:
        raise NotImplementedError

    def delete_auth_record(self, auth_ref: str) -> bool:
        raise NotImplementedError
```

In `FileStore`, add:

```python
    def delete_auth(self, connection_id: str) -> bool:
        path = self._auth_path(connection_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def delete_auth_record(self, auth_ref: str) -> bool:
        """Delete neutral auth through the legacy MCP file shape."""
        return self.delete_auth(auth_ref)
```

- [ ] **Step 5: Implement provider methods**

In `src/wf_mcp/broker/service/auth_admin.py`, import neutral auth:

```python
from wf_api.auth import AuthRecord as NeutralAuthRecord
```

Add methods to `McpAuthAdminProvider`:

```python
    def save_auth_record(self, record: NeutralAuthRecord) -> dict[str, Any]:
        self.store.save_auth_record(record)
        return self.inspect_auth_record(record.id)

    def delete_auth_record(self, auth_ref: str) -> dict[str, Any]:
        deleted = self.store.delete_auth_record(auth_ref)
        if not deleted:
            raise KeyError(f"unknown auth record {auth_ref!r}")
        return {"deleted": True, "id": auth_ref}
```

- [ ] **Step 6: Run tests**

Run:

```powershell
uv run pytest tests\wf_mcp\test_store.py tests\wf_mcp\service\test_auth_admin.py -q
uv run ruff check src\wf_mcp\storage\store.py src\wf_mcp\broker\service\auth_admin.py tests\wf_mcp\test_store.py tests\wf_mcp\service\test_auth_admin.py
uv run basedpyright --level error src\wf_mcp\storage\store.py src\wf_mcp\broker\service\auth_admin.py tests\wf_mcp\test_store.py tests\wf_mcp\service\test_auth_admin.py
```

Expected: pass.

---

### Task 3: JSON-RPC Auth Mutation Methods

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods_admin.py`
- Modify: `src/wf_transport_rpc_http/client_admin.py`
- Test: `tests/wf_transport_rpc_http/test_admin_auth_rpc.py`

- [ ] **Step 1: Add failing RPC tests**

Append to `tests/wf_transport_rpc_http/test_admin_auth_rpc.py`:

```python
async def test_rpc_saves_auth_record_without_returning_payload(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    server = build_workflow_server_from_config(BrokerConfig(store_root=store.root))

    async with _client(server) as client:
        payload = await client.save_auth_record(
            auth_ref="drive.work",
            scheme="bearer",
            payload={"token": "secret"},
            metadata={"owner": "test"},
        )

    assert payload["id"] == "drive.work"
    assert payload["scheme"] == "bearer"
    assert payload["payload_keys"] == ["token"]
    assert "secret" not in str(payload)
    assert FileStore(store.root).load_auth("drive.work") == AuthRecord(
        connection_id="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
    )


async def test_rpc_deletes_auth_record(tmp_path) -> None:
    store = FileStore(tmp_path / "store")
    store.save_auth(AuthRecord(connection_id="drive.work", scheme="bearer"))
    server = build_workflow_server_from_config(BrokerConfig(store_root=store.root))

    async with _client(server) as client:
        payload = await client.delete_auth_record("drive.work")

    assert payload == {"deleted": True, "id": "drive.work"}
    assert FileStore(store.root).load_auth("drive.work") is None
```

Use the existing `_client(...)` helper in this test file. If it has a different name, adapt only the helper call.

- [ ] **Step 2: Run failing tests**

Run:

```powershell
uv run pytest tests\wf_transport_rpc_http\test_admin_auth_rpc.py -q
```

Expected: fail because RPC client/server mutation methods do not exist.

- [ ] **Step 3: Add RPC parameter models**

In `src/wf_transport_rpc_http/models.py`, add:

```python
class SaveAuthParams(RpcParamsModel):
    auth_ref: str = Field(min_length=1)
    scheme: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeleteAuthParams(RpcParamsModel):
    auth_ref: str = Field(min_length=1)
```

If `Any` is not imported in that file, import it from `typing`.

- [ ] **Step 4: Register RPC methods**

In `src/wf_transport_rpc_http/methods_admin.py`, import the new params:

```python
from .models import AdminEmptyParams, DeleteAuthParams, InspectAuthParams, SaveAuthParams
```

Add methods after `workflow.admin.auth.inspect`:

```python
    @entrypoint.method(
        name="workflow.admin.auth.save",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_auth_save(
        params: SaveAuthParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.admin.save_auth_record(
                auth_ref=params.auth_ref,
                scheme=params.scheme,
                payload=params.payload,
                metadata=params.metadata,
            )
        except (
            ValueError,
            KeyError,
            LookupError,
            FileNotFoundError,
            RuntimeError,
        ) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.admin.auth.delete",
        errors=[WorkflowRpcError],
    )
    async def workflow_admin_auth_delete(
        params: DeleteAuthParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.admin.delete_auth_record(params.auth_ref)
        except (
            ValueError,
            KeyError,
            LookupError,
            FileNotFoundError,
            RuntimeError,
        ) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 5: Add RPC client methods**

In `src/wf_transport_rpc_http/client_admin.py`, add:

```python
    async def save_auth_record(
        self,
        *,
        auth_ref: str,
        scheme: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.auth.save",
            {
                "auth_ref": auth_ref,
                "scheme": scheme,
                "payload": payload,
                "metadata": metadata or {},
            },
        )

    async def delete_auth_record(self, auth_ref: str) -> dict[str, Any]:
        return await self._call(
            "workflow.admin.auth.delete",
            {"auth_ref": auth_ref},
        )
```

- [ ] **Step 6: Run tests**

Run:

```powershell
uv run pytest tests\wf_transport_rpc_http\test_admin_auth_rpc.py -q
uv run ruff check src\wf_transport_rpc_http\models.py src\wf_transport_rpc_http\methods_admin.py src\wf_transport_rpc_http\client_admin.py tests\wf_transport_rpc_http\test_admin_auth_rpc.py
uv run basedpyright --level error src\wf_transport_rpc_http\models.py src\wf_transport_rpc_http\methods_admin.py src\wf_transport_rpc_http\client_admin.py tests\wf_transport_rpc_http\test_admin_auth_rpc.py
```

Expected: pass.

---

### Task 4: CLI Auth Save/Delete

**Files:**
- Modify: `src/wf_cli/commands/auth_admin.py`
- Test: `tests/wf_cli/test_auth_admin.py`

- [ ] **Step 1: Add failing CLI tests**

Append to `tests/wf_cli/test_auth_admin.py`:

```python
def test_wf_admin_auth_save(monkeypatch) -> None:
    mock_admin = MockAuthAdmin()
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda _ctx: SimpleNamespace(admin=mock_admin),
    )

    result = CliRunner().invoke(
        app,
        [
            "admin",
            "auth",
            "save",
            "drive.work",
            "--scheme",
            "bearer",
            "--payload",
            '{"token":"secret"}',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "drive.work"
    assert payload["payload_keys"] == ["token"]
    assert "secret" not in result.output
    mock_admin.save_auth_record.assert_called_once_with(
        auth_ref="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
        metadata=None,
    )


def test_wf_admin_auth_save_reads_payload_file(tmp_path, monkeypatch) -> None:
    mock_admin = MockAuthAdmin()
    payload_file = tmp_path / "auth.json"
    payload_file.write_text('{"token":"secret"}', encoding="utf-8")
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda _ctx: SimpleNamespace(admin=mock_admin),
    )

    result = CliRunner().invoke(
        app,
        [
            "admin",
            "auth",
            "save",
            "drive.work",
            "--scheme",
            "bearer",
            "--payload-file",
            str(payload_file),
        ],
    )

    assert result.exit_code == 0
    mock_admin.save_auth_record.assert_called_once_with(
        auth_ref="drive.work",
        scheme="bearer",
        payload={"token": "secret"},
        metadata=None,
    )


def test_wf_admin_auth_delete_requires_confirm(monkeypatch) -> None:
    mock_admin = MockAuthAdmin()
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda _ctx: SimpleNamespace(admin=mock_admin),
    )

    result = CliRunner().invoke(app, ["admin", "auth", "delete", "drive.work"])

    assert result.exit_code != 0
    assert "--confirm" in result.output
    mock_admin.delete_auth_record.assert_not_called()


def test_wf_admin_auth_delete(monkeypatch) -> None:
    mock_admin = MockAuthAdmin()
    monkeypatch.setattr(
        "wf_cli.commands.auth_admin.load_cli_context_from_typer",
        lambda _ctx: SimpleNamespace(admin=mock_admin),
    )

    result = CliRunner().invoke(
        app,
        ["admin", "auth", "delete", "drive.work", "--confirm"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {"deleted": True, "id": "drive.work"}
    mock_admin.delete_auth_record.assert_called_once_with("drive.work")
```

If the test file uses a different fake than `MockAuthAdmin`, extend the existing fake with `save_auth_record = MagicMock(...)` and `delete_auth_record = MagicMock(...)`.

- [ ] **Step 2: Run failing CLI tests**

Run:

```powershell
uv run pytest tests\wf_cli\test_auth_admin.py -q
```

Expected: fail because commands are missing.

- [ ] **Step 3: Implement JSON input helper locally**

In `src/wf_cli/commands/auth_admin.py`, add imports:

```python
import json
from pathlib import Path
```

Add helpers:

```python
def _read_json_object(
    inline: str | None,
    file_path: str | None,
    flag_names: str,
) -> dict[str, object]:
    if inline and file_path:
        raise typer.BadParameter(f"provide exactly one of {flag_names}")
    if inline:
        try:
            value = json.loads(inline)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise typer.BadParameter(f"{flag_names} must be a JSON object")
        return dict(value)
    if file_path:
        try:
            value = json.loads(Path(file_path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise typer.BadParameter(f"file not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"invalid JSON in file: {exc}") from exc
        if not isinstance(value, dict):
            raise typer.BadParameter(f"{flag_names} must be a JSON object")
        return dict(value)
    raise typer.BadParameter(f"{flag_names} is required")
```

- [ ] **Step 4: Add CLI commands**

In `src/wf_cli/commands/auth_admin.py`, add:

```python
@app.command("save")
def save_auth_record(
    ctx: typer.Context,
    auth_ref: Annotated[str, typer.Argument(help="Auth record id/ref.")],
    scheme: Annotated[str, typer.Option("--scheme", help="Auth scheme/kind.")],
    payload_json: Annotated[
        str | None,
        typer.Option("--payload", help="Secret payload JSON object."),
    ] = None,
    payload_file: Annotated[
        str | None,
        typer.Option("--payload-file", help="File containing secret payload JSON object."),
    ] = None,
    metadata_json: Annotated[
        str | None,
        typer.Option("--metadata", help="Non-secret metadata JSON object."),
    ] = None,
    metadata_file: Annotated[
        str | None,
        typer.Option("--metadata-file", help="File containing non-secret metadata JSON object."),
    ] = None,
) -> None:
    """Save or replace a local/dev auth record; response never includes payload values."""
    payload = _read_json_object(payload_json, payload_file, "--payload/--payload-file")
    metadata = (
        _read_json_object(metadata_json, metadata_file, "--metadata/--metadata-file")
        if metadata_json or metadata_file
        else None
    )
    context = load_cli_context_from_typer(ctx)
    result = run_cli_operation(
        context,
        context.admin.save_auth_record(
            auth_ref=auth_ref,
            scheme=scheme,
            payload=payload,
            metadata=metadata,
        ),
    )
    emit_json(result)


@app.command("delete")
def delete_auth_record(
    ctx: typer.Context,
    auth_ref: Annotated[str, typer.Argument(help="Auth record id/ref.")],
    confirm: Annotated[
        bool,
        typer.Option("--confirm", help="Required to delete an auth record."),
    ] = False,
) -> None:
    """Delete a local/dev auth record."""
    if not confirm:
        raise typer.BadParameter("--confirm is required to delete an auth record")
    context = load_cli_context_from_typer(ctx)
    result = run_cli_operation(context, context.admin.delete_auth_record(auth_ref))
    emit_json(result)
```

- [ ] **Step 5: Run CLI tests**

Run:

```powershell
uv run pytest tests\wf_cli\test_auth_admin.py -q
uv run ruff check src\wf_cli\commands\auth_admin.py tests\wf_cli\test_auth_admin.py
uv run basedpyright --level error src\wf_cli\commands\auth_admin.py tests\wf_cli\test_auth_admin.py
```

Expected: pass.

---

### Task 5: Docs and Final Verification

**Files:**
- Modify: `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/wf_cli.md`

- [ ] **Step 1: Update auth spec status**

In `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`, update the `## Status` paragraph to include:

```markdown
Slice 4 adds local/dev file-backed auth save/delete through neutral admin,
JSON-RPC, and CLI. Responses still expose only ids, schemes, metadata, and
payload keys; secret payload values remain write-only. OAuth, production secret
managers, and provider-specific auth variants remain future work.
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, under the auth/source secrets boundary bullet, add:

```markdown
Fourth implementation slice complete: local/dev auth records can be saved and
deleted through neutral admin, JSON-RPC, and `wf admin auth`. This is still not
a production secret manager or OAuth flow; payload values are accepted only as
write inputs and never returned.
```

- [ ] **Step 3: Update CLI docs**

In `docs/wf_cli.md`, add an auth section near admin/source registry commands:

```markdown
### Local/dev auth records

Auth payload values are write-only. `list`, `inspect`, `save`, and `delete`
responses show ids, schemes, metadata, and payload keys only.

```powershell
wf admin auth save drive.work --scheme bearer --payload-file drive-auth.json
wf admin auth list
wf admin auth inspect drive.work
wf admin auth delete drive.work --confirm
```

Use source `auth_ref` values to point sources at these records. Do not commit
payload files containing real secrets.
```
```

- [ ] **Step 4: Run final focused suite**

Run:

```powershell
uv run pytest tests\wf_api\test_admin_api.py tests\wf_mcp\test_store.py tests\wf_mcp\service\test_auth_admin.py tests\wf_transport_rpc_http\test_admin_auth_rpc.py tests\wf_cli\test_auth_admin.py -q
uv run ruff check src\wf_api\admin.py src\wf_api\surface.py src\wf_mcp\storage\store.py src\wf_mcp\broker\service\auth_admin.py src\wf_transport_rpc_http\models.py src\wf_transport_rpc_http\methods_admin.py src\wf_transport_rpc_http\client_admin.py src\wf_cli\commands\auth_admin.py tests\wf_api\test_admin_api.py tests\wf_mcp\test_store.py tests\wf_mcp\service\test_auth_admin.py tests\wf_transport_rpc_http\test_admin_auth_rpc.py tests\wf_cli\test_auth_admin.py
uv run basedpyright --level error src\wf_api src\wf_mcp\storage\store.py src\wf_mcp\broker\service\auth_admin.py src\wf_transport_rpc_http src\wf_cli\commands\auth_admin.py tests\wf_api\test_admin_api.py tests\wf_mcp\test_store.py tests\wf_mcp\service\test_auth_admin.py tests\wf_transport_rpc_http\test_admin_auth_rpc.py tests\wf_cli\test_auth_admin.py
```

Expected: pass.

- [ ] **Step 5: Run broader smoke**

Run:

```powershell
uv run pytest tests\wf_mcp tests\wf_transport_rpc_http tests\wf_cli\test_auth_admin.py -q
```

Expected: pass with the existing skipped/xfail counts only.

- [ ] **Step 6: Review security invariant**

Run:

```powershell
rg -n "\"payload\"|secret|token" src\wf_api\admin.py src\wf_mcp\broker\service\auth_admin.py src\wf_transport_rpc_http\methods_admin.py src\wf_cli\commands\auth_admin.py tests\wf_api\test_admin_api.py tests\wf_mcp\service\test_auth_admin.py tests\wf_transport_rpc_http\test_admin_auth_rpc.py tests\wf_cli\test_auth_admin.py
```

Expected:

- Payload appears only as input construction or persisted store calls.
- Response assertions use `payload_keys`.
- Tests assert secret values are not present in output.

---

## Self-Review

- Spec coverage: this plan implements local/dev auth save/delete, keeps read responses secret-free, and leaves OAuth/secret managers/provider unions future.
- Placeholder scan: no TBD/TODO placeholders are present.
- Type consistency: public API method names are `save_auth_record` and `delete_auth_record` across `wf_api`, JSON-RPC client, and CLI. RPC method names are `workflow.admin.auth.save` and `workflow.admin.auth.delete`.
- Scope check: this plan does not touch legacy `wf-mcp` tools; it routes through neutral admin surfaces and JSON-RPC/CLI.
