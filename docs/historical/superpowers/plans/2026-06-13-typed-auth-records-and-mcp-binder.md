# Typed Auth Records And MCP Binder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace stringly runtime MCP auth interpretation with typed auth records plus a source-owned MCP auth binder, while preserving current auth file compatibility.

**Architecture:** `wf_api.auth` owns durable typed auth record models and compatibility parsing. `wf_sources_mcp.auth` owns MCP-specific binding from typed records to HTTP headers/`httpx.Auth` or stdio env. `open_mcp_session()` performs the small MCP client glue from bound auth into `httpx.AsyncClient` or `StdioServerParameters`.

**Tech Stack:** Python 3.14, dataclasses/Pydantic already in repo, pytest, basedpyright, ruff, httpx, MCP Python SDK.

---

## File Structure

- Modify `src/wf_api/auth.py`: add typed auth variants, stored record wrapper, compatibility parse/serialize helpers.
- Modify `src/wf_sources_mcp/auth.py`: add `BoundMcpHttpAuth`, `BoundMcpStdioAuth`, `McpAuthBinder`, and compatibility bridge from neutral records.
- Modify `src/wf_sources_mcp/client/transport.py`: use `McpAuthBinder` in `open_mcp_session()`.
- Modify `src/wf_sources_mcp/storage/store.py`: read old and new auth JSON shapes; write new shape through neutral record save path if practical.
- Modify `src/wf_mcp/broker/service/auth_admin.py` only if summary shape needs `kind` aliasing.
- Add/modify tests:
  - `tests/wf_api/test_auth.py`
  - `tests/wf_sources_mcp/test_auth.py`
  - `tests/wf_sources_mcp/test_client_transport.py`
  - `tests/wf_mcp/service/test_auth_admin.py`

## Task 1: Typed Neutral Auth Models

**Files:**
- Modify: `src/wf_api/auth.py`
- Test: `tests/wf_api/test_auth.py`

- [ ] **Step 1: Add failing tests for typed auth parsing and compatibility**

Append tests:

```python
import pytest

from wf_api.auth import (
    BearerAuth,
    EnvAuth,
    HeaderAuth,
    OAuthRefreshTokenAuth,
    OpaqueAuth,
    StoredAuthRecord,
    auth_record_from_compat,
)


def test_stored_auth_record_accepts_bearer_variant() -> None:
    record = StoredAuthRecord(
        id="google.drive.personal",
        auth=BearerAuth(access_token="access-token"),
        metadata={"provider": "google"},
    )

    assert record.id == "google.drive.personal"
    assert record.auth.kind == "bearer"
    assert record.metadata["provider"] == "google"


def test_stored_auth_record_accepts_oauth_refresh_token_variant() -> None:
    record = StoredAuthRecord(
        id="google.drive.personal",
        auth=OAuthRefreshTokenAuth(
            client_id="client-id",
            client_secret="client-secret",
            refresh_token="refresh-token",
            token_url="https://oauth2.googleapis.com/token",
            scopes=("https://www.googleapis.com/auth/drive.readonly",),
        ),
    )

    assert record.auth.kind == "oauth_refresh_token"
    assert str(record.auth.token_url) == "https://oauth2.googleapis.com/token"
    assert record.auth.scopes == ("https://www.googleapis.com/auth/drive.readonly",)


def test_auth_record_from_compat_maps_existing_scheme_payload_shape() -> None:
    record = auth_record_from_compat(
        id="demo.default",
        scheme="bearer",
        payload={"token": "abc"},
        metadata={"source": "test"},
    )

    assert isinstance(record.auth, BearerAuth)
    assert record.auth.access_token == "abc"
    assert record.metadata["source"] == "test"


def test_auth_record_from_compat_preserves_unknown_as_opaque() -> None:
    record = auth_record_from_compat(
        id="demo.default",
        scheme="custom",
        payload={"x": "y"},
        metadata={},
    )

    assert isinstance(record.auth, OpaqueAuth)
    assert record.auth.scheme == "custom"
    assert record.auth.payload == {"x": "y"}


def test_typed_auth_rejects_missing_bearer_token() -> None:
    with pytest.raises(ValueError, match="bearer token"):
        auth_record_from_compat(
            id="demo.default",
            scheme="bearer",
            payload={},
            metadata={},
        )
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_api/test_auth.py -q
```

Expected: fails because typed auth classes/helpers do not exist.

- [ ] **Step 3: Implement typed auth models and compatibility parser**

In `src/wf_api/auth.py`, keep existing `AuthRecord` for compatibility but add:

```python
from typing import Annotated, Any, Literal

from pydantic import AnyUrl, BaseModel, Field


class BearerAuth(BaseModel):
    kind: Literal["bearer"] = "bearer"
    access_token: str


class HeaderAuth(BaseModel):
    kind: Literal["headers"] = "headers"
    headers: dict[str, str]


class EnvAuth(BaseModel):
    kind: Literal["env"] = "env"
    env: dict[str, str]


class OAuthRefreshTokenAuth(BaseModel):
    kind: Literal["oauth_refresh_token"] = "oauth_refresh_token"
    client_id: str
    client_secret: str
    refresh_token: str
    token_url: AnyUrl
    scopes: tuple[str, ...] = ()


class OpaqueAuth(BaseModel):
    kind: Literal["opaque"] = "opaque"
    scheme: str
    payload: dict[str, object] = Field(default_factory=dict)


AuthVariant = Annotated[
    BearerAuth | HeaderAuth | EnvAuth | OAuthRefreshTokenAuth | OpaqueAuth,
    Field(discriminator="kind"),
]


class StoredAuthRecord(BaseModel):
    id: str
    auth: AuthVariant
    metadata: dict[str, object] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        validate_auth_id(self.id)


def auth_record_from_compat(
    *,
    id: str,
    scheme: str,
    payload: Mapping[str, object],
    metadata: Mapping[str, object] | None = None,
) -> StoredAuthRecord:
    payload_dict = dict(payload)
    metadata_dict = dict(metadata or {})
    match scheme:
        case "bearer":
            token = payload_dict.get("token") or payload_dict.get("access_token")
            if not isinstance(token, str) or not token:
                raise ValueError("bearer token is required")
            auth: AuthVariant = BearerAuth(access_token=token)
        case "headers":
            raw_headers = payload_dict.get("headers", {})
            headers = (
                {
                    str(key): str(value)
                    for key, value in raw_headers.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
                if isinstance(raw_headers, dict)
                else {}
            )
            auth = HeaderAuth(headers=headers)
        case "env":
            raw_env = payload_dict.get("env", {})
            env = (
                {
                    str(key): str(value)
                    for key, value in raw_env.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
                if isinstance(raw_env, dict)
                else {}
            )
            auth = EnvAuth(env=env)
        case _:
            auth = OpaqueAuth(scheme=scheme, payload=payload_dict)
    return StoredAuthRecord(id=id, auth=auth, metadata=metadata_dict)
```

Update `__all__` to export all new symbols.

- [ ] **Step 4: Run tests and typecheck**

Run:

```bash
uv run pytest tests/wf_api/test_auth.py -q
uv run basedpyright --level error src/wf_api/auth.py tests/wf_api/test_auth.py
uv run ruff check src/wf_api/auth.py tests/wf_api/test_auth.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_api/auth.py tests/wf_api/test_auth.py
git commit -m "feat: add typed auth record variants"
```

## Task 2: MCP Auth Binder

**Files:**
- Modify: `src/wf_sources_mcp/auth.py`
- Test: `tests/wf_sources_mcp/test_auth.py`

- [ ] **Step 1: Add failing MCP binder tests**

Append tests:

```python
import httpx
import pytest

from wf_api.auth import (
    BearerAuth,
    EnvAuth,
    HeaderAuth,
    OAuthRefreshTokenAuth,
    StoredAuthRecord,
)
from wf_sources_mcp.auth import McpAuthBinder, OAuthAccessToken


class _FakeRefresher:
    def __init__(self) -> None:
        self.calls: list[OAuthRefreshTokenAuth] = []

    async def refresh(self, auth: OAuthRefreshTokenAuth) -> OAuthAccessToken:
        self.calls.append(auth)
        return OAuthAccessToken(access_token="fresh-token", expires_in=3600)


async def test_mcp_binder_binds_bearer_for_http() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(
        id="demo.auth",
        auth=BearerAuth(access_token="token"),
    )

    bound = await binder.bind_http_auth(record)

    assert bound.headers == {"Authorization": "Bearer token"}
    assert bound.auth is None


async def test_mcp_binder_binds_headers_for_http() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(
        id="demo.auth",
        auth=HeaderAuth(headers={"X-Test": "yes"}),
    )

    bound = await binder.bind_http_auth(record)

    assert bound.headers == {"X-Test": "yes"}


async def test_mcp_binder_binds_env_for_stdio() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(
        id="demo.auth",
        auth=EnvAuth(env={"TOKEN": "abc"}),
    )

    bound = await binder.bind_stdio_auth(record)

    assert bound.env == {"TOKEN": "abc"}


async def test_mcp_binder_refreshes_oauth_for_http() -> None:
    refresher = _FakeRefresher()
    binder = McpAuthBinder(oauth_refresher=refresher)
    record = StoredAuthRecord(
        id="google.drive.personal",
        auth=OAuthRefreshTokenAuth(
            client_id="client",
            client_secret="secret",
            refresh_token="refresh",
            token_url="https://oauth2.googleapis.com/token",
        ),
    )

    bound = await binder.bind_http_auth(record)

    assert bound.headers == {"Authorization": "Bearer fresh-token"}
    assert len(refresher.calls) == 1


async def test_mcp_binder_rejects_env_for_http() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(id="demo.auth", auth=EnvAuth(env={"TOKEN": "abc"}))

    with pytest.raises(ValueError, match="not supported for MCP HTTP"):
        await binder.bind_http_auth(record)


async def test_mcp_binder_rejects_headers_for_stdio() -> None:
    binder = McpAuthBinder()
    record = StoredAuthRecord(
        id="demo.auth",
        auth=HeaderAuth(headers={"Authorization": "Bearer token"}),
    )

    with pytest.raises(ValueError, match="not supported for MCP stdio"):
        await binder.bind_stdio_auth(record)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_auth.py -q
```

Expected: fails because `McpAuthBinder` and `OAuthAccessToken` do not exist.

- [ ] **Step 3: Implement binder**

In `src/wf_sources_mcp/auth.py`, import typed variants from `wf_api.auth` and add:

```python
from dataclasses import dataclass, field
from typing import Protocol

import httpx
from wf_api.auth import (
    BearerAuth,
    EnvAuth,
    HeaderAuth,
    OAuthRefreshTokenAuth,
    OpaqueAuth,
    StoredAuthRecord,
)


@dataclass(frozen=True, slots=True)
class OAuthAccessToken:
    access_token: str
    expires_in: int | None = None


class OAuthTokenRefresher(Protocol):
    async def refresh(self, auth: OAuthRefreshTokenAuth) -> OAuthAccessToken: ...


@dataclass(frozen=True, slots=True)
class BoundMcpHttpAuth:
    headers: dict[str, str] = field(default_factory=dict)
    auth: httpx.Auth | None = None


@dataclass(frozen=True, slots=True)
class BoundMcpStdioAuth:
    env: dict[str, str] = field(default_factory=dict)


class McpAuthBinder:
    def __init__(self, oauth_refresher: OAuthTokenRefresher | None = None) -> None:
        self._oauth_refresher = oauth_refresher

    async def bind_http_auth(
        self,
        record: StoredAuthRecord | None,
    ) -> BoundMcpHttpAuth:
        if record is None:
            return BoundMcpHttpAuth()
        auth = record.auth
        if isinstance(auth, BearerAuth):
            return BoundMcpHttpAuth(
                headers={"Authorization": f"Bearer {auth.access_token}"}
            )
        if isinstance(auth, HeaderAuth):
            return BoundMcpHttpAuth(headers=dict(auth.headers))
        if isinstance(auth, OAuthRefreshTokenAuth):
            if self._oauth_refresher is None:
                raise ValueError("oauth_refresh_token requires an OAuthTokenRefresher")
            token = await self._oauth_refresher.refresh(auth)
            return BoundMcpHttpAuth(
                headers={"Authorization": f"Bearer {token.access_token}"}
            )
        if isinstance(auth, EnvAuth):
            raise ValueError("env auth is not supported for MCP HTTP")
        if isinstance(auth, OpaqueAuth):
            raise ValueError(f"opaque auth scheme {auth.scheme!r} is not supported for MCP HTTP")
        raise TypeError(f"unsupported auth variant {type(auth).__name__}")

    async def bind_stdio_auth(
        self,
        record: StoredAuthRecord | None,
    ) -> BoundMcpStdioAuth:
        if record is None:
            return BoundMcpStdioAuth()
        auth = record.auth
        if isinstance(auth, EnvAuth):
            return BoundMcpStdioAuth(env=dict(auth.env))
        if isinstance(auth, BearerAuth | HeaderAuth | OAuthRefreshTokenAuth | OpaqueAuth):
            raise ValueError(f"{auth.kind} auth is not supported for MCP stdio")
        raise TypeError(f"unsupported auth variant {type(auth).__name__}")
```

Keep existing `mcp_auth_headers()` and `mcp_auth_env()` compatibility helpers for old callers in this slice.

Update `__all__` with binder symbols.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_auth.py -q
uv run basedpyright --level error src/wf_sources_mcp/auth.py tests/wf_sources_mcp/test_auth.py
uv run ruff check src/wf_sources_mcp/auth.py tests/wf_sources_mcp/test_auth.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_sources_mcp/auth.py tests/wf_sources_mcp/test_auth.py
git commit -m "feat: add mcp auth binder"
```

## Task 3: Store Compatibility For New Auth Shape

**Files:**
- Modify: `src/wf_sources_mcp/storage/store.py`
- Test: `tests/wf_sources_mcp/test_auth_storage_exports.py` or `tests/wf_mcp/test_store.py`

- [ ] **Step 1: Add failing store tests**

Add tests near existing auth store tests:

```python
from wf_api.auth import BearerAuth, StoredAuthRecord
from wf_sources_mcp.storage import FileAuthStore


def test_file_auth_store_loads_new_stored_auth_record_shape(tmp_path: Path) -> None:
    store = FileAuthStore(tmp_path)
    path = tmp_path / "auth" / "google.drive.personal.json"
    path.write_text(
        json.dumps(
            {
                "id": "google.drive.personal",
                "auth": {"kind": "bearer", "access_token": "token"},
                "metadata": {"provider": "google"},
            }
        ),
        encoding="utf-8",
    )

    record = store.load_auth_record("google.drive.personal")

    assert isinstance(record, StoredAuthRecord)
    assert isinstance(record.auth, BearerAuth)
    assert record.auth.access_token == "token"
    assert record.metadata["provider"] == "google"


def test_file_auth_store_writes_new_stored_auth_record_shape(tmp_path: Path) -> None:
    store = FileAuthStore(tmp_path)
    record = StoredAuthRecord(
        id="google.drive.personal",
        auth=BearerAuth(access_token="token"),
        metadata={"provider": "google"},
    )

    store.save_auth_record(record)

    data = json.loads((tmp_path / "auth" / "google.drive.personal.json").read_text())
    assert data["id"] == "google.drive.personal"
    assert data["auth"]["kind"] == "bearer"
    assert data["auth"]["access_token"] == "token"
    assert data["metadata"]["provider"] == "google"
```

Adjust import path if the chosen existing test file already imports `Path`/`json`.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_auth_storage_exports.py -q
```

Expected: fails because store returns old neutral `AuthRecord` or writes old shape.

- [ ] **Step 3: Update store read/write**

In `src/wf_sources_mcp/storage/store.py`:

- Import `StoredAuthRecord` and `auth_record_from_compat`.
- Change `save_auth_record()` to accept `NeutralAuthRecord | StoredAuthRecord`; if `StoredAuthRecord`, write `record.model_dump(mode="json", indent=2)` shape.
- Change `load_auth_record()` to return `StoredAuthRecord | NeutralAuthRecord` only if too many callers break; preferred return is `StoredAuthRecord`.
- Keep `load_auth()` returning legacy `wf_sources_mcp.auth.AuthRecord` for compatibility by converting the stored typed record back to legacy where possible.

Minimal conversion helper:

```python
def _stored_to_legacy(record: StoredAuthRecord) -> AuthRecord:
    auth = record.auth
    if isinstance(auth, BearerAuth):
        return AuthRecord(record.id, "bearer", {"token": auth.access_token})
    if isinstance(auth, HeaderAuth):
        return AuthRecord(record.id, "headers", {"headers": dict(auth.headers)})
    if isinstance(auth, EnvAuth):
        return AuthRecord(record.id, "env", {"env": dict(auth.env)})
    if isinstance(auth, OAuthRefreshTokenAuth):
        return AuthRecord(
            record.id,
            "oauth_refresh_token",
            auth.model_dump(mode="json", exclude={"kind"}),
        )
    if isinstance(auth, OpaqueAuth):
        return AuthRecord(record.id, auth.scheme, dict(auth.payload))
    raise TypeError(f"unsupported auth variant {type(auth).__name__}")
```

- [ ] **Step 4: Run focused auth/store tests**

Run:

```bash
uv run pytest tests/wf_api/test_auth.py tests/wf_sources_mcp/test_auth.py tests/wf_sources_mcp/test_auth_storage_exports.py tests/wf_mcp/test_store.py -q
uv run basedpyright --level error src/wf_api/auth.py src/wf_sources_mcp/auth.py src/wf_sources_mcp/storage/store.py
uv run ruff check src/wf_api/auth.py src/wf_sources_mcp/auth.py src/wf_sources_mcp/storage/store.py tests/wf_api/test_auth.py tests/wf_sources_mcp/test_auth.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_sources_mcp/storage/store.py tests/wf_sources_mcp/test_auth_storage_exports.py tests/wf_mcp/test_store.py
git commit -m "feat: read and write typed auth records"
```

## Task 4: Wire Binder Into MCP Session Opening

**Files:**
- Modify: `src/wf_sources_mcp/client/transport.py`
- Test: `tests/wf_sources_mcp/test_client_transport.py`

- [ ] **Step 1: Add failing client transport tests**

Add tests that capture `httpx.AsyncClient` kwargs and stdio env using existing monkeypatch style in `test_client_transport.py`:

```python
from wf_api.auth import BearerAuth, EnvAuth, StoredAuthRecord


async def test_open_mcp_session_uses_binder_for_http_headers(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _AsyncClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        async def __aenter__(self) -> "_AsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("wf_sources_mcp.client.transport.httpx.AsyncClient", _AsyncClient)
    # Reuse existing fake streamable_http_client/ClientSession helpers in this file.

    connection = McpSourceConnection(
        id="google.drive",
        provider="google",
        transport=HttpSourceTransport(url="https://drivemcp.googleapis.com/mcp/v1"),
    )
    auth = StoredAuthRecord(
        id="google.drive.personal",
        auth=BearerAuth(access_token="token"),
    )

    async with open_mcp_session(connection, auth):
        pass

    assert captured["headers"] == {"Authorization": "Bearer token"}


async def test_open_mcp_session_uses_binder_for_stdio_env(monkeypatch) -> None:
    # Follow existing stdio capture pattern in this file.
    connection = McpSourceConnection(
        id="demo.default",
        provider="demo",
        transport=StdioSourceTransport(command="demo", env={"BASE": "1"}),
    )
    auth = StoredAuthRecord(id="demo.auth", auth=EnvAuth(env={"TOKEN": "abc"}))

    async with open_mcp_session(connection, auth):
        pass

    assert captured_stdio_params.env == {"BASE": "1", "TOKEN": "abc"}
```

Use the existing fake helpers in `tests/wf_sources_mcp/test_client_transport.py`; do not duplicate a second fake session stack if the file already has one.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_client_transport.py -q
```

Expected: fails because `open_mcp_session()` still calls `mcp_auth_headers()` / `mcp_auth_env()`.

- [ ] **Step 3: Update `open_mcp_session()`**

Change signature to accept both old MCP auth and new stored auth during transition:

```python
async def open_mcp_session(
    connection: McpSourceConnection,
    auth: AuthRecord | StoredAuthRecord | None,
    *,
    auth_binder: McpAuthBinder | None = None,
) -> AsyncIterator[ClientSession]:
```

Inside, normalize old `AuthRecord` through compatibility if needed, or keep a small helper:

```python
def _as_stored_auth(auth: AuthRecord | StoredAuthRecord | None) -> StoredAuthRecord | None:
    if auth is None or isinstance(auth, StoredAuthRecord):
        return auth
    return auth_record_from_compat(
        id=auth.connection_id,
        scheme=auth.scheme,
        payload=auth.payload,
        metadata={},
    )
```

Use:

```python
binder = auth_binder or McpAuthBinder()
stored_auth = _as_stored_auth(auth)
```

For stdio:

```python
bound = await binder.bind_stdio_auth(stored_auth)
env = {**transport.env, **bound.env}
```

For HTTP:

```python
bound = await binder.bind_http_auth(stored_auth)
http_client = httpx.AsyncClient(
    headers=bound.headers or None,
    auth=bound.auth,
)
```

- [ ] **Step 4: Run MCP source tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/test_compat_imports.py -q
uv run basedpyright --level error src/wf_sources_mcp
uv run ruff check src/wf_sources_mcp tests/wf_sources_mcp
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_sources_mcp/client/transport.py tests/wf_sources_mcp/test_client_transport.py
git commit -m "feat: bind auth when opening mcp sessions"
```

## Task 5: Docs And Final Verification

**Files:**
- Modify: `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update status**

In the auth spec `## Status`, add:

```md
Slice 5 introduces typed stored auth records and MCP auth binding while preserving old `scheme + payload` compatibility input.
```

In `docs/current_roadmap.md`, mark typed auth records and MCP binder as completed, leaving OAuth refresh-token and Drive smoke as next.

- [ ] **Step 2: Run focused verification**

Run:

```bash
uv run pytest tests/wf_api/test_auth.py tests/wf_sources_mcp tests/wf_mcp/service/test_auth_admin.py tests/wf_mcp/test_auth.py -q
uv run ruff check src/wf_api/auth.py src/wf_sources_mcp tests/wf_api/test_auth.py tests/wf_sources_mcp
uv run basedpyright --level error src/wf_api/auth.py src/wf_sources_mcp
git diff --check
```

Expected: tests pass, lint clean, typecheck clean, no whitespace errors except acceptable CRLF warnings on Windows.

- [ ] **Step 3: Final review**

Check:

- `wf_api` still imports no `wf_mcp`.
- No secret payload values are returned by auth admin summaries.
- Existing `scheme + payload` auth files can still be read.
- `open_mcp_session()` accepts old auth records and new typed records.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md docs/current_roadmap.md
git commit -m "docs: record typed mcp auth binding"
```

## Self-Review Checklist

- Spec coverage: typed records, source-owned binder, Drive-compatible bearer output, and compatibility parsing are covered.
- Placeholder scan: no TODO/TBD placeholders.
- Type consistency: plan consistently uses `StoredAuthRecord`, `AuthVariant`, `McpAuthBinder`, `BoundMcpHttpAuth`, and `BoundMcpStdioAuth`.
