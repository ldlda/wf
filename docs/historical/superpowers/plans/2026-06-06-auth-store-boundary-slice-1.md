# Auth Store Boundary Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a neutral auth record/store boundary and make current MCP auth loading prefer source `auth_ref` while preserving legacy connection-id behavior.

**Architecture:** `wf_api` owns neutral auth ids, records, and the read-only auth-store protocol. `wf_mcp` keeps its current `AuthRecord` compatibility type, but adds adapter helpers that convert neutral records into MCP runtime records and centralize MCP payload interpretation. No diagnostics, admin mutation, OAuth, or secret-manager behavior in this slice.

**Tech Stack:** Python 3.14, dataclasses, protocols, pytest, ruff, basedpyright.

---

## Scope

Implement only:

- neutral auth model/protocol in `wf_api`
- MCP file-store adapter bridge
- MCP runtime auth resolution by `metadata["auth_ref"]` with legacy fallback
- central MCP auth payload interpretation helper

Do not implement:

- auth admin CLI/RPC/MCP tools
- auth diagnostics in deployment validation
- OAuth/browser flows
- encrypted file format
- source-provider packages beyond current `wf_mcp`

## Files

- Create: `src/wf_api/auth.py`
  - neutral `AUTH_ID_PATTERN`
  - `validate_auth_id`
  - frozen `AuthRecord`
  - read-only `AuthStore` protocol
- Modify: `src/wf_api/__init__.py`
  - export neutral auth symbols
- Create: `tests/wf_api/test_auth.py`
  - neutral auth model/protocol tests
- Create: `src/wf_mcp/auth.py`
  - adapter helpers between neutral auth and `wf_mcp.models.AuthRecord`
  - centralized MCP header/env extraction
- Modify: `src/wf_mcp/storage/store.py`
  - add neutral `load_auth_record(auth_ref)` / `save_auth_record(record)` methods
  - keep old `save_auth(AuthRecord)` / `load_auth(connection_id)` methods
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
  - add `load_connection_auth(connection)` helper
  - update all `load_auth(connection.id)` call sites to use the helper
  - keep `load_auth(connection_id)` facade for compatibility
- Modify: `src/wf_mcp/broker/service/source_catalog.py`
  - change `AuthLoader` from `Callable[[str], AuthRecord | None]` to `Callable[[ConnectionConfig], AuthRecord | None]`
  - update hydrated wrapper calls to pass the connection object
- Modify: `src/wf_mcp/broker/service/core.py`
  - pass `self.upstream.load_connection_auth` to `SourceCatalogService`
- Modify: `src/wf_mcp/sdk/adapter.py`
  - replace local `_auth_headers` / env payload reads with `wf_mcp.auth` helpers
- Modify: `src/wf_mcp/runtime/factory.py`
  - replace local `_auth_headers` / env payload reads with `wf_mcp.auth` helpers
- Test: `tests/wf_mcp/test_auth.py`
  - adapter bridge tests
- Test: `tests/wf_mcp/service/test_upstream_transport.py`
  - `auth_ref` lookup / fallback tests
- Test: existing focused suites listed below

## Task 1: Neutral auth model and store protocol

**Files:**
- Create: `src/wf_api/auth.py`
- Modify: `src/wf_api/__init__.py`
- Create: `tests/wf_api/test_auth.py`

- [ ] **Step 1: Write neutral auth tests**

Create `tests/wf_api/test_auth.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import assert_type

import pytest

from wf_api.auth import AuthRecord, AuthStore, validate_auth_id


def test_validate_auth_id_accepts_safe_dotted_ids() -> None:
    assert validate_auth_id("github.work") == "github.work"
    assert validate_auth_id("api_ci-1") == "api_ci-1"


@pytest.mark.parametrize("auth_id", ["", ".hidden", "../secret", "bad/id"])
def test_validate_auth_id_rejects_unsafe_ids(auth_id: str) -> None:
    with pytest.raises(ValueError, match="auth id must start"):
        validate_auth_id(auth_id)


def test_auth_record_is_immutable_and_mapping_typed() -> None:
    record = AuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
        metadata={"owner": "test"},
    )

    assert record.id == "github.work"
    assert record.scheme == "bearer"
    assert record.payload["token"] == "secret"
    assert_type(record.payload, Mapping[str, object])

    with pytest.raises(AttributeError):
        record.scheme = "headers"  # type: ignore[misc]


class MemoryAuthStore:
    def __init__(self, records: dict[str, AuthRecord]) -> None:
        self.records = records

    def load_auth(self, auth_ref: str) -> AuthRecord | None:
        return self.records.get(auth_ref)


def test_auth_store_protocol_is_read_only_lookup() -> None:
    record = AuthRecord(id="github.work", scheme="opaque", payload={"x": 1})
    store: AuthStore = MemoryAuthStore({"github.work": record})

    assert store.load_auth("github.work") is record
    assert store.load_auth("missing") is None
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_api/test_auth.py -q
```

Expected: fails because `wf_api.auth` does not exist.

- [ ] **Step 3: Implement neutral auth module**

Create `src/wf_api/auth.py`:

```python
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

AUTH_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"


def validate_auth_id(value: str) -> str:
    """Validate auth refs that are safe as store keys and path segments.

    Auth refs deliberately carry no provider semantics. Source providers decide
    how a resolved auth record is interpreted.
    """

    if not re.fullmatch(AUTH_ID_PATTERN, value):
        raise ValueError(
            "auth id must start with alphanumeric or underscore and contain "
            "only [A-Za-z0-9_.-]"
        )
    return value


@dataclass(frozen=True, slots=True)
class AuthRecord:
    """Neutral credential record resolved by auth ref.

    `scheme + payload` is a compatibility bridge, not the long-term taxonomy.
    Keep payload interpretation inside provider adapters so a future
    discriminated union can replace this without touching workflow/config code.
    """

    id: str
    scheme: str
    payload: Mapping[str, object]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_auth_id(self.id)
        if not self.scheme:
            raise ValueError("auth scheme must be non-empty")


class AuthStore(Protocol):
    """Read-only runtime credential lookup by auth ref."""

    def load_auth(self, auth_ref: str) -> AuthRecord | None: ...


__all__ = [
    "AUTH_ID_PATTERN",
    "AuthRecord",
    "AuthStore",
    "validate_auth_id",
]
```

- [ ] **Step 4: Export from `wf_api`**

Modify `src/wf_api/__init__.py`:

```python
from .auth import AUTH_ID_PATTERN, AuthRecord, AuthStore, validate_auth_id
```

Add these entries to `__all__`:

```python
"AUTH_ID_PATTERN",
"AuthRecord",
"AuthStore",
"validate_auth_id",
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_auth.py tests/wf_api/test_import_direction.py -q
uv run ruff check src/wf_api/auth.py tests/wf_api/test_auth.py
uv run basedpyright --level error src/wf_api tests/wf_api/test_auth.py
```

Expected: all pass.

## Task 2: MCP auth adapter helpers

**Files:**
- Create: `src/wf_mcp/auth.py`
- Create: `tests/wf_mcp/test_auth.py`

- [ ] **Step 1: Write MCP adapter tests**

Create `tests/wf_mcp/test_auth.py`:

```python
from __future__ import annotations

from wf_api.auth import AuthRecord as NeutralAuthRecord
from wf_mcp.auth import (
    mcp_auth_env,
    mcp_auth_headers,
    mcp_auth_from_neutral,
    neutral_auth_from_mcp,
)
from wf_mcp.models import AuthRecord as McpAuthRecord


def test_mcp_auth_from_neutral_preserves_scheme_and_payload() -> None:
    neutral = NeutralAuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
        metadata={"owner": "test"},
    )

    mcp = mcp_auth_from_neutral(neutral)

    assert mcp == McpAuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
    )


def test_neutral_auth_from_mcp_preserves_payload() -> None:
    mcp = McpAuthRecord(
        connection_id="github.work",
        scheme="headers",
        payload={"headers": {"X-Test": "yes"}},
    )

    neutral = neutral_auth_from_mcp(mcp)

    assert neutral.id == "github.work"
    assert neutral.scheme == "headers"
    assert neutral.payload == {"headers": {"X-Test": "yes"}}


def test_mcp_auth_headers_extracts_explicit_headers_and_bearer_token() -> None:
    auth = McpAuthRecord(
        connection_id="api.work",
        scheme="bearer",
        payload={"headers": {"X-Test": "yes"}, "token": "secret"},
    )

    assert mcp_auth_headers(auth) == {
        "X-Test": "yes",
        "Authorization": "Bearer secret",
    }


def test_mcp_auth_headers_does_not_override_authorization_header() -> None:
    auth = McpAuthRecord(
        connection_id="api.work",
        scheme="bearer",
        payload={
            "headers": {"Authorization": "Basic already"},
            "token": "secret",
        },
    )

    assert mcp_auth_headers(auth) == {"Authorization": "Basic already"}


def test_mcp_auth_env_returns_string_map_only() -> None:
    auth = McpAuthRecord(
        connection_id="mcp.local",
        scheme="env",
        payload={"env": {"TOKEN": "secret", "BAD": 123}},
    )

    assert mcp_auth_env(auth) == {"TOKEN": "secret"}
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_auth.py -q
```

Expected: fails because `wf_mcp.auth` does not exist.

- [ ] **Step 3: Implement MCP adapter module**

Create `src/wf_mcp/auth.py`:

```python
from __future__ import annotations

from wf_api.auth import AuthRecord as NeutralAuthRecord

from .models import AuthRecord as McpAuthRecord


def mcp_auth_from_neutral(record: NeutralAuthRecord) -> McpAuthRecord:
    """Adapt neutral auth to the current MCP compatibility record."""

    return McpAuthRecord(
        connection_id=record.id,
        scheme=record.scheme,
        payload=dict(record.payload),
    )


def neutral_auth_from_mcp(record: McpAuthRecord) -> NeutralAuthRecord:
    """Adapt legacy MCP auth into the neutral record shape."""

    return NeutralAuthRecord(
        id=record.connection_id,
        scheme=record.scheme,
        payload=dict(record.payload),
    )


def mcp_auth_headers(auth: McpAuthRecord | None) -> dict[str, str]:
    """Return HTTP headers understood by MCP HTTP transports.

    This is intentionally MCP-specific. Neutral code must not inspect payload
    keys such as `headers` or `token`.
    """

    if auth is None:
        return {}
    raw_headers = auth.payload.get("headers", {})
    headers = {
        str(key): str(value)
        for key, value in raw_headers.items()
        if isinstance(key, str) and isinstance(value, str)
    } if isinstance(raw_headers, dict) else {}
    token = auth.payload.get("token")
    if isinstance(token, str) and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def mcp_auth_env(auth: McpAuthRecord | None) -> dict[str, str]:
    """Return environment variables understood by MCP stdio transports."""

    if auth is None:
        return {}
    raw_env = auth.payload.get("env", {})
    if not isinstance(raw_env, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw_env.items()
        if isinstance(key, str) and isinstance(value, str)
    }


__all__ = [
    "mcp_auth_env",
    "mcp_auth_from_neutral",
    "mcp_auth_headers",
    "neutral_auth_from_mcp",
]
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_auth.py -q
uv run ruff check src/wf_mcp/auth.py tests/wf_mcp/test_auth.py
uv run basedpyright --level error src/wf_mcp/auth.py tests/wf_mcp/test_auth.py
```

Expected: all pass.

## Task 3: Store adapter bridge

**Files:**
- Modify: `src/wf_mcp/storage/store.py`
- Modify: `tests/wf_mcp/test_auth.py`

- [ ] **Step 1: Add store bridge tests**

Append to `tests/wf_mcp/test_auth.py`:

```python
from pathlib import Path

from wf_mcp.storage import FileStore


def test_file_store_saves_and_loads_neutral_auth_record(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    record = NeutralAuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
        metadata={"owner": "test"},
    )

    store.save_auth_record(record)

    loaded = store.load_auth_record("github.work")
    assert loaded == record


def test_file_store_legacy_auth_methods_still_work(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    legacy = McpAuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
    )

    store.save_auth(legacy)

    assert store.load_auth("github.work") == legacy
    assert store.load_auth_record("github.work") == NeutralAuthRecord(
        id="github.work",
        scheme="bearer",
        payload={"token": "secret"},
    )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_auth.py::test_file_store_saves_and_loads_neutral_auth_record tests/wf_mcp/test_auth.py::test_file_store_legacy_auth_methods_still_work -q
```

Expected: fails because `FileStore.save_auth_record` / `load_auth_record` do not exist.

- [ ] **Step 3: Extend store interface and file store**

Modify `src/wf_mcp/storage/store.py`:

Add imports:

```python
from wf_api.auth import AuthRecord as NeutralAuthRecord

from ..auth import mcp_auth_from_neutral, neutral_auth_from_mcp
```

Add to `class Store`:

```python
    def save_auth_record(self, record: NeutralAuthRecord) -> None:
        raise NotImplementedError

    def load_auth_record(self, auth_ref: str) -> NeutralAuthRecord | None:
        raise NotImplementedError
```

Add to `class FileStore`:

```python
    def save_auth_record(self, record: NeutralAuthRecord) -> None:
        """Save neutral auth through the legacy MCP file shape."""

        self.save_auth(mcp_auth_from_neutral(record))

    def load_auth_record(self, auth_ref: str) -> NeutralAuthRecord | None:
        """Load neutral auth from the legacy MCP file shape."""

        record = self.load_auth(auth_ref)
        if record is None:
            return None
        return neutral_auth_from_mcp(record)
```

Do not change the existing on-disk JSON shape in this task.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_auth.py -q
uv run ruff check src/wf_mcp/storage/store.py tests/wf_mcp/test_auth.py
uv run basedpyright --level error src/wf_mcp/storage/store.py tests/wf_mcp/test_auth.py
```

Expected: all pass.

## Task 4: Runtime auth resolution by auth_ref with fallback

**Files:**
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `tests/wf_mcp/service/test_upstream_transport.py`

- [ ] **Step 1: Add upstream resolution tests**

Open `tests/wf_mcp/service/test_upstream_transport.py`. Add imports if missing:

```python
from pathlib import Path

from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.storage import FileStore
```

Add helper if the file does not already have one:

```python
def _transport(root: Path) -> UpstreamTransportService:
    events: list[object] = []
    return UpstreamTransportService(
        store=FileStore(root),
        event_sink=events.append,
    )
```

Add tests:

```python
def test_upstream_load_connection_auth_prefers_auth_ref(tmp_path: Path) -> None:
    service = _transport(tmp_path)
    service.save_auth(
        AuthRecord(
            connection_id="github.creds",
            scheme="bearer",
            payload={"token": "secret"},
        )
    )
    service.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "wrong"},
        )
    )
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={"auth_ref": "github.creds"},
    )

    assert service.load_connection_auth(connection) == AuthRecord(
        connection_id="github.creds",
        scheme="bearer",
        payload={"token": "secret"},
    )


def test_upstream_load_connection_auth_falls_back_to_connection_id(
    tmp_path: Path,
) -> None:
    service = _transport(tmp_path)
    service.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "legacy"},
        )
    )
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
    )

    assert service.load_connection_auth(connection) == AuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={"token": "legacy"},
    )


def test_upstream_load_connection_auth_ignores_non_string_auth_ref(
    tmp_path: Path,
) -> None:
    service = _transport(tmp_path)
    service.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "legacy"},
        )
    )
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={"auth_ref": 123},
    )

    assert service.load_connection_auth(connection) == AuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={"token": "legacy"},
    )
```

If the file already has a helper for `UpstreamTransportService`, use it instead
of adding `_transport`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py -q
```

Expected: fails because `load_connection_auth` does not exist.

- [ ] **Step 3: Implement `load_connection_auth`**

Modify `src/wf_mcp/broker/service/upstream_transport.py`.

Add method to `UpstreamTransportService` after `load_auth`:

```python
    def load_connection_auth(self, connection: ConnectionConfig) -> AuthRecord | None:
        """Resolve auth for a connection, preferring explicit source auth_ref.

        Legacy MCP auth records are keyed by connection id. New source registry
        and neutral config entries carry `auth_ref`; keep both paths until the
        old compatibility surface has no callers.
        """

        auth_ref = connection.metadata.get("auth_ref")
        if isinstance(auth_ref, str):
            return self.load_auth(auth_ref)
        return self.load_auth(connection.id)
```

- [ ] **Step 4: Replace direct connection-id auth lookups in upstream transport**

In `src/wf_mcp/broker/service/upstream_transport.py`, replace these patterns:

```python
auth = self.load_auth(connection.id)
```

with:

```python
auth = self.load_connection_auth(connection)
```

Also replace the live-check lookup:

```python
auth = self.load_auth(source_id)
```

with:

```python
auth = self.load_connection_auth(connection)
```

Keep `load_auth(connection_id)` unchanged as a compatibility facade.

- [ ] **Step 5: Update source catalog auth callback**

Modify `src/wf_mcp/broker/service/source_catalog.py`.

Change:

```python
AuthLoader = Callable[[str], AuthRecord | None]
```

to:

```python
AuthLoader = Callable[[ConnectionConfig], AuthRecord | None]
```

Inside `spec_from_snapshot_entry.invoke_tool`, change:

```python
connection = self.connection_lookup(entry.connection_id)
auth = self.load_auth(entry.connection_id)
```

to:

```python
connection = self.connection_lookup(entry.connection_id)
auth = self.load_auth(connection)
```

- [ ] **Step 6: Wire source catalog to the new resolver**

Modify `src/wf_mcp/broker/service/core.py`.

In `SourceCatalogService(...)` construction, change:

```python
load_auth=self.upstream.load_auth,
```

to:

```python
load_auth=self.upstream.load_connection_auth,
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_workflow_runtime.py -q
uv run ruff check src/wf_mcp/broker/service/upstream_transport.py src/wf_mcp/broker/service/source_catalog.py src/wf_mcp/broker/service/core.py tests/wf_mcp/service/test_upstream_transport.py
uv run basedpyright --level error src/wf_mcp/broker/service tests/wf_mcp/service/test_upstream_transport.py
```

Expected: all pass.

## Task 5: Centralize MCP payload interpretation

**Files:**
- Modify: `src/wf_mcp/sdk/adapter.py`
- Modify: `src/wf_mcp/runtime/factory.py`
- Test: existing MCP auth/runtime tests

- [ ] **Step 1: Update SDK adapter imports**

Modify `src/wf_mcp/sdk/adapter.py`.

Add import:

```python
from ..auth import mcp_auth_env, mcp_auth_headers
```

Delete local `_auth_headers`.

In stdio branch, replace:

```python
            if auth is not None:
                auth_env = auth.payload.get("env")
                if isinstance(auth_env, dict):
                    env = {**(env or {}), **auth_env}
```

with:

```python
            auth_env = mcp_auth_env(auth)
            if auth_env:
                env = {**(env or {}), **auth_env}
```

In HTTP branch, replace:

```python
            headers = _auth_headers(auth)
```

with:

```python
            headers = mcp_auth_headers(auth)
```

- [ ] **Step 2: Update runtime factory imports**

Modify `src/wf_mcp/runtime/factory.py`.

Add import:

```python
from ..auth import mcp_auth_env, mcp_auth_headers
```

Delete local `_auth_headers`.

In stdio branch, replace:

```python
            if auth is not None:
                auth_env = auth.payload.get("env")
                if isinstance(auth_env, dict):
                    env = {**(env or {}), **auth_env}
```

with:

```python
            auth_env = mcp_auth_env(auth)
            if auth_env:
                env = {**(env or {}), **auth_env}
```

In HTTP branch, replace:

```python
httpx.AsyncClient(headers=_auth_headers(auth) or None)
```

with:

```python
httpx.AsyncClient(headers=mcp_auth_headers(auth) or None)
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_auth.py tests/wf_mcp/service/test_adapters.py tests/wf_mcp/service/test_workflow_runtime.py tests/wf_mcp/service/test_upstream_transport.py -q
uv run ruff check src/wf_mcp/auth.py src/wf_mcp/sdk/adapter.py src/wf_mcp/runtime/factory.py
uv run basedpyright --level error src/wf_mcp/auth.py src/wf_mcp/sdk/adapter.py src/wf_mcp/runtime/factory.py
```

Expected: all pass.

## Task 6: Docs and final verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`

- [ ] **Step 1: Update roadmap status**

In `docs/current_roadmap.md`, under the auth/source secrets boundary bullet,
append:

```markdown
    First implementation slice complete: neutral auth records/store protocol
    exist in `wf_api`, MCP runtime auth resolution prefers explicit `auth_ref`
    with legacy connection-id fallback, and MCP payload interpretation is
    isolated in provider-specific adapter helpers.
```

- [ ] **Step 2: Update spec status**

In `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`, add
after `## Purpose`:

```markdown
## Status

Slice 1 implements the neutral auth record/store protocol and MCP compatibility
bridge. Diagnostics, auth admin surfaces, and provider-specific auth unions are
future slices.
```

- [ ] **Step 3: Run final verification**

Run:

```bash
uv run pytest tests/wf_api/test_auth.py tests/wf_api/test_import_direction.py tests/wf_mcp/test_auth.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_catalog.py tests/wf_mcp/service/test_workflow_runtime.py tests/wf_mcp/service/test_adapters.py -q
uv run ruff check src/wf_api src/wf_mcp tests/wf_api/test_auth.py tests/wf_mcp/test_auth.py tests/wf_mcp/service/test_upstream_transport.py
uv run basedpyright --level error src/wf_api src/wf_mcp tests/wf_api/test_auth.py tests/wf_mcp/test_auth.py tests/wf_mcp/service/test_upstream_transport.py
```

Expected: all pass.

- [ ] **Step 4: Final report**

Report:

- files created/modified
- verification outputs
- whether any old `auth.payload[...]` reads remain outside `src/wf_mcp/auth.py`
- deviations from this plan

Search command for the payload check:

```bash
rg -n 'auth\.payload|get\("headers"|get\("token"|get\("env"' src/wf_mcp
```

Expected: payload interpretation is either in `src/wf_mcp/auth.py` or unrelated
connection/source metadata handling. If adapter/runtime files still read
`auth.payload`, fix before reporting.

