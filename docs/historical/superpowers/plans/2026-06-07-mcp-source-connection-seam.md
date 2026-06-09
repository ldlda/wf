# MCP Source Connection Seam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a typed MCP source connection seam in `wf_sources_mcp` so runtime/session code can stop depending on `wf_mcp.broker.models.ConnectionConfig.metadata`.

**Architecture:** This is the preparatory slice before moving MCP runtime/session code. Move low-level source ID validation and MCP transport models into focused `wf_sources_mcp` modules, then add `McpSourceConnection` plus explicit converters from the legacy broker DTO and source registry entries. Do not move `runtime/factory.py`, `runtime/session.py`, `runtime/pool.py`, or `McpSdkAdapter` in this plan.

**Tech Stack:** Python 3.14, dataclasses, Pydantic v2, pytest, ruff, basedpyright.

---

## Why This Slice Exists

Persistent MCP connections are the real product need. Stdio MCP startup and HTTP session initialization are expensive and failure-prone, so runtime code needs one clear object that means:

> one configured upstream MCP source account that can be opened, authenticated, catalogued, called, and eventually reused.

Today that object is implicitly `ConnectionConfig` plus `metadata: dict[str, Any]`. That keeps old code working, but it makes runtime/session extraction unsafe. This slice creates the typed seam first:

```text
ConnectionConfig -> McpSourceConnection -> shared MCP session opener -> persistent runtime
```

After this slice, later runtime moves become mechanical instead of dragging broker config bags into `wf_sources_mcp`.

---

## File Structure

Create:

- `src/wf_sources_mcp/ids.py`
  - Owns source/connection ID validation for MCP upstream sources.
  - Exports `CONNECTION_ID_PATTERN`, `RESERVED_CONNECTION_IDS`, `parse_connection_id`.

- `src/wf_sources_mcp/transports.py`
  - Owns `StdioSourceTransport`, `HttpSourceTransport`, `SourceTransport`.
  - Replaces transport model definitions currently embedded in `source_registry.py`.

- `src/wf_sources_mcp/connections.py`
  - Owns `McpSourceConnection`.
  - Owns conversion helpers from legacy broker `ConnectionConfig` and registry entries.

- `tests/wf_sources_mcp/test_connections.py`
  - Tests ID validation, transport parsing, legacy conversion, registry conversion, and package exports.

Modify:

- `src/wf_sources_mcp/source_registry.py`
  - Import ID helpers from `wf_sources_mcp.ids`.
  - Import transport models from `wf_sources_mcp.transports`.
  - Keep existing public exports for compatibility.

- `src/wf_sources_mcp/auth.py`
  - Make auth helpers accept `McpSourceConnection` / source-like objects instead of directly depending on `ConnectionConfig`.

- `src/wf_sources_mcp/sdk/protocols.py`
  - Introduce a source-connection protocol/type alias for backend protocols.
  - Remove the `TYPE_CHECKING` dependency on `wf_mcp.broker.models.ConnectionConfig`.

- `src/wf_sources_mcp/__init__.py`
  - Export new seam types lazily if needed to avoid circular imports.

- `src/wf_mcp/connections.py`
  - Re-export `CONNECTION_ID_PATTERN` and `parse_connection_id` from `wf_sources_mcp.ids`.
  - Keep `ConnectionRegistry` and `qualify_node_name` behavior unchanged.

- `src/wf_mcp/shared/names.py`
  - Import/re-export `RESERVED_CONNECTION_IDS` from `wf_sources_mcp.ids`.
  - Keep FastMCP namespace helpers unchanged.

- `tests/wf_mcp/test_compat_imports.py`
  - Add identity checks for moved ID/transport exports where appropriate.

- `docs/current_roadmap.md`
  - Add a status note for the typed MCP source connection seam.

- `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`
  - Add this slice to the MCP source provider package direction list.

---

## Non-Goals

- Do not move `src/wf_mcp/runtime/factory.py`.
- Do not move `src/wf_mcp/runtime/session.py`.
- Do not move `src/wf_mcp/runtime/pool.py`.
- Do not move `src/wf_mcp/sdk/adapter.py`.
- Do not change `ConnectionConfig` field shape.
- Do not change on-disk registry/auth/catalog JSON shapes.
- Do not change MCP proxy/frontend behavior.

---

## Task 1: Move ID Validation Into `wf_sources_mcp.ids`

**Files:**
- Create: `src/wf_sources_mcp/ids.py`
- Modify: `src/wf_mcp/connections.py`
- Modify: `src/wf_mcp/shared/names.py`
- Test: `tests/wf_sources_mcp/test_connections.py`

- [ ] **Step 1: Write failing ID tests**

Create `tests/wf_sources_mcp/test_connections.py` with these tests first:

```python
import pytest

from wf_sources_mcp.ids import (
    CONNECTION_ID_PATTERN,
    RESERVED_CONNECTION_IDS,
    parse_connection_id,
)


def test_parse_connection_id_splits_provider_and_account() -> None:
    assert parse_connection_id("github.work") == ("github", "work")


@pytest.mark.parametrize(
    "source_id",
    ["github", ".github.work", "github.", "github/work", "github work"],
)
def test_parse_connection_id_rejects_unsafe_or_unqualified_ids(source_id: str) -> None:
    with pytest.raises(ValueError):
        parse_connection_id(source_id)


def test_reserved_connection_ids_are_source_provider_constants() -> None:
    assert "wf.admin" in RESERVED_CONNECTION_IDS
    assert "wf.mcp" in RESERVED_CONNECTION_IDS
    assert CONNECTION_ID_PATTERN.startswith("^")
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py -q
```

Expected: fail because `wf_sources_mcp.ids` does not exist.

- [ ] **Step 3: Implement `wf_sources_mcp.ids`**

Create `src/wf_sources_mcp/ids.py`:

```python
from __future__ import annotations

import re

CONNECTION_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"

RESERVED_CONNECTION_IDS = frozenset({"wf.admin", "wf.mcp"})
"""Source ids reserved by built-in workflow/MCP control surfaces."""


def parse_connection_id(connection_id: str) -> tuple[str, str]:
    """Validate and split one MCP source id into provider/account parts.

    Source ids also key persisted auth, registry, and catalog files. Keep this
    conservative so unsafe ids are rejected before reaching store boundaries.
    """

    if not re.fullmatch(CONNECTION_ID_PATTERN, connection_id):
        raise ValueError(
            "connection id must start with alphanumeric or underscore and contain "
            "only [A-Za-z0-9_.-]"
        )
    if "." not in connection_id:
        raise ValueError("connection id must look like '<server>.<account>'")
    server, account = connection_id.split(".", 1)
    if not server or not account:
        raise ValueError("connection id must look like '<server>.<account>'")
    return server, account


__all__ = [
    "CONNECTION_ID_PATTERN",
    "RESERVED_CONNECTION_IDS",
    "parse_connection_id",
]
```

- [ ] **Step 4: Update compatibility imports**

In `src/wf_mcp/connections.py`, remove local `re` and `CONNECTION_ID_PATTERN` / `parse_connection_id` definitions. Import instead:

```python
from wf_sources_mcp.ids import CONNECTION_ID_PATTERN, parse_connection_id
```

Keep `qualify_node_name` and `ConnectionRegistry` in `wf_mcp.connections`.

In `src/wf_mcp/shared/names.py`, replace local `RESERVED_CONNECTION_IDS` with:

```python
from wf_sources_mcp.ids import RESERVED_CONNECTION_IDS
```

Keep `ADMIN_NAMESPACE = "wf.admin"` for MCP frontend namespace logic.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py tests/wf_mcp/test_source_registry.py tests/wf_mcp/test_store.py -q
```

Expected: pass.

---

## Task 2: Move Transport Models Into `wf_sources_mcp.transports`

**Files:**
- Create: `src/wf_sources_mcp/transports.py`
- Modify: `src/wf_sources_mcp/source_registry.py`
- Modify: `src/wf_sources_mcp/__init__.py`
- Test: `tests/wf_sources_mcp/test_connections.py`

- [ ] **Step 1: Add failing transport tests**

Append to `tests/wf_sources_mcp/test_connections.py`:

```python
from pydantic import TypeAdapter

from wf_sources_mcp.transports import (
    HttpSourceTransport,
    SourceTransport,
    StdioSourceTransport,
)


def test_stdio_source_transport_is_typed() -> None:
    transport = StdioSourceTransport(
        command="uvx",
        args=("mcp-server",),
        env={"TOKEN": "x"},
    )

    assert transport.kind == "stdio"
    assert transport.command == "uvx"
    assert transport.args == ("mcp-server",)
    assert transport.env == {"TOKEN": "x"}


def test_http_source_transport_is_typed() -> None:
    transport = HttpSourceTransport(url="http://127.0.0.1:8000/mcp")

    assert transport.kind == "http"
    assert str(transport.url) == "http://127.0.0.1:8000/mcp"


def test_source_transport_discriminated_union_parses() -> None:
    adapter = TypeAdapter(SourceTransport)

    transport = adapter.validate_python(
        {"kind": "stdio", "command": "pnpx", "args": ["-y", "server"]}
    )

    assert isinstance(transport, StdioSourceTransport)
    assert transport.args == ("-y", "server")
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py -q
```

Expected: fail because `wf_sources_mcp.transports` does not exist.

- [ ] **Step 3: Implement `wf_sources_mcp.transports`**

Create `src/wf_sources_mcp/transports.py`:

```python
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field

from wf_api.source_registry import SourceRegistryBaseModel


class StdioSourceTransport(SourceRegistryBaseModel):
    kind: Literal["stdio"] = "stdio"
    command: str = Field(min_length=1)
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)


class HttpSourceTransport(SourceRegistryBaseModel):
    kind: Literal["http"] = "http"
    url: AnyHttpUrl
    headers: dict[str, str] = Field(default_factory=dict)


SourceTransport = Annotated[
    StdioSourceTransport | HttpSourceTransport,
    Field(discriminator="kind"),
]


__all__ = [
    "HttpSourceTransport",
    "SourceTransport",
    "StdioSourceTransport",
]
```

- [ ] **Step 4: Update `source_registry.py` to use canonical transport models**

In `src/wf_sources_mcp/source_registry.py`:

- Remove local `StdioSourceTransport`, `HttpSourceTransport`, and `SourceTransport` definitions.
- Remove now-unused imports `Annotated`, `AnyHttpUrl`.
- Import:

```python
from wf_sources_mcp.ids import RESERVED_CONNECTION_IDS, parse_connection_id
from wf_sources_mcp.transports import (
    HttpSourceTransport,
    SourceTransport,
    StdioSourceTransport,
)
```

Keep all three names in `__all__` so existing imports from `wf_sources_mcp.source_registry` continue to work.

- [ ] **Step 5: Update package exports**

In `src/wf_sources_mcp/__init__.py`, export or lazily expose:

```python
HttpSourceTransport
SourceTransport
StdioSourceTransport
```

If direct imports create a circular dependency, use the existing lazy `__getattr__` pattern.

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py tests/wf_sources_mcp/test_source_registry.py tests/wf_mcp/test_source_registry.py -q
```

Expected: pass.

---

## Task 3: Add `McpSourceConnection` And Converters

**Files:**
- Create: `src/wf_sources_mcp/connections.py`
- Modify: `src/wf_sources_mcp/__init__.py`
- Test: `tests/wf_sources_mcp/test_connections.py`

- [ ] **Step 1: Add failing connection seam tests**

Append to `tests/wf_sources_mcp/test_connections.py`:

```python
from wf_sources_mcp.connections import (
    McpSourceConnection,
    mcp_source_connection_from_connection_config,
    mcp_source_connection_from_registry_entry,
)
from wf_sources_mcp.source_registry import McpSourceRegistryEntry


def test_mcp_source_connection_from_registry_entry() -> None:
    entry = McpSourceRegistryEntry.model_validate(
        {
            "id": "github.work",
            "provider": "github",
            "account": "work",
            "profile": "engineering",
            "transport": {
                "kind": "stdio",
                "command": "uvx",
                "args": ["github-mcp"],
                "env": {"A": "B"},
            },
            "auth_ref": "github.token",
            "metadata": {"team": "platform"},
        }
    )

    connection = mcp_source_connection_from_registry_entry(entry)

    assert connection == McpSourceConnection(
        id="github.work",
        provider="github",
        account="work",
        enabled=True,
        profile="engineering",
        transport=StdioSourceTransport(
            command="uvx",
            args=("github-mcp",),
            env={"A": "B"},
        ),
        auth_ref="github.token",
        metadata={"team": "platform"},
    )


def test_mcp_source_connection_from_legacy_connection_config_stdio() -> None:
    from wf_mcp.broker.models import ConnectionConfig

    legacy = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        enabled=False,
        metadata={
            "transport": "stdio",
            "command": "uvx",
            "args": ["github-mcp"],
            "env": {"A": "B"},
            "auth_ref": "github.token",
            "profile": "engineering",
            "source_registry": True,
            "team": "platform",
        },
    )

    connection = mcp_source_connection_from_connection_config(legacy)

    assert connection.id == "github.work"
    assert connection.provider == "github"
    assert connection.account == "work"
    assert connection.enabled is False
    assert connection.profile == "engineering"
    assert connection.auth_ref == "github.token"
    assert connection.metadata == {"source_registry": True, "team": "platform"}
    assert isinstance(connection.transport, StdioSourceTransport)
    assert connection.transport.command == "uvx"
    assert connection.transport.args == ("github-mcp",)


def test_mcp_source_connection_from_legacy_connection_config_http() -> None:
    from wf_mcp.broker.models import ConnectionConfig

    legacy = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={
            "transport": "streamable_http",
            "url": "http://127.0.0.1:8000/mcp",
            "headers": {"X-Test": "yes"},
        },
    )

    connection = mcp_source_connection_from_connection_config(legacy)

    assert isinstance(connection.transport, HttpSourceTransport)
    assert str(connection.transport.url) == "http://127.0.0.1:8000/mcp"
    assert connection.transport.headers == {"X-Test": "yes"}


def test_mcp_source_connection_rejects_missing_legacy_transport() -> None:
    from wf_mcp.broker.models import ConnectionConfig

    legacy = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={},
    )

    with pytest.raises(ValueError, match="requires metadata.transport"):
        mcp_source_connection_from_connection_config(legacy)
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py -q
```

Expected: fail because `wf_sources_mcp.connections` does not exist.

- [ ] **Step 3: Implement `wf_sources_mcp.connections`**

Create `src/wf_sources_mcp/connections.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from wf_sources_mcp.ids import parse_connection_id
from wf_sources_mcp.source_registry import McpSourceRegistryEntry
from wf_sources_mcp.transports import (
    HttpSourceTransport,
    SourceTransport,
    StdioSourceTransport,
)

if TYPE_CHECKING:
    from wf_mcp.broker.models import ConnectionConfig

_FLAT_HTTP_TRANSPORTS = {"http", "streamable-http", "streamable_http", "sse"}
_CONNECTION_METADATA_KEYS = {
    "transport",
    "command",
    "args",
    "env",
    "cwd",
    "url",
    "headers",
    "profile",
    "auth_ref",
}


@dataclass(frozen=True, slots=True)
class McpSourceConnection:
    """Typed runtime-facing MCP source connection.

    This is the object runtime/session code should consume. Legacy broker
    `ConnectionConfig.metadata` remains at the compatibility edge only.
    """

    id: str
    provider: str
    account: str
    transport: SourceTransport
    enabled: bool = True
    profile: str | None = None
    auth_ref: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        provider, account = parse_connection_id(self.id)
        if not self.provider:
            raise ValueError("provider must not be empty")
        if not self.account:
            raise ValueError("account must not be empty")
        if provider != self.provider or account != self.account:
            raise ValueError(
                "MCP source connection id must match provider/account fields"
            )


def mcp_source_connection_from_registry_entry(
    entry: McpSourceRegistryEntry,
) -> McpSourceConnection:
    """Adapt persisted desired-source registry state to runtime source shape."""

    return McpSourceConnection(
        id=entry.id,
        provider=entry.provider,
        account=entry.account,
        enabled=entry.enabled,
        profile=entry.profile,
        transport=entry.transport,
        auth_ref=entry.auth_ref,
        metadata=dict(entry.metadata),
    )


def mcp_source_connection_from_connection_config(
    connection: ConnectionConfig,
) -> McpSourceConnection:
    """Adapt legacy broker connection config into typed source shape.

    Keep all metadata-bag reads in this compatibility converter. Runtime/session
    code should use `McpSourceConnection.transport` directly.
    """

    transport = _transport_from_connection_metadata(connection)
    profile = connection.metadata.get("profile")
    auth_ref = connection.metadata.get("auth_ref")
    metadata = {
        str(key): value
        for key, value in connection.metadata.items()
        if key not in _CONNECTION_METADATA_KEYS
    }
    return McpSourceConnection(
        id=connection.id,
        provider=connection.server,
        account=connection.account,
        enabled=connection.enabled,
        profile=profile if isinstance(profile, str) else None,
        transport=transport,
        auth_ref=auth_ref if isinstance(auth_ref, str) else None,
        metadata=metadata,
    )


def _transport_from_connection_metadata(connection: ConnectionConfig) -> SourceTransport:
    transport = connection.metadata.get("transport")
    if isinstance(transport, dict):
        kind = transport.get("kind")
        if kind == "stdio":
            return StdioSourceTransport.model_validate(transport)
        if kind == "http":
            return HttpSourceTransport.model_validate(transport)
        raise ValueError(
            f"connection {connection.id!r} has unsupported metadata.transport.kind {kind!r}"
        )
    if isinstance(transport, str):
        if transport == "stdio":
            return StdioSourceTransport(
                command=str(connection.metadata.get("command", "")),
                args=tuple(str(arg) for arg in connection.metadata.get("args", ())),
                env={
                    str(key): str(value)
                    for key, value in dict(connection.metadata.get("env", {})).items()
                },
            )
        if transport in _FLAT_HTTP_TRANSPORTS:
            return HttpSourceTransport(
                url=str(connection.metadata.get("url", "")),
                headers={
                    str(key): str(value)
                    for key, value in dict(
                        connection.metadata.get("headers", {})
                    ).items()
                },
            )
        raise ValueError(
            f"connection {connection.id!r} has unrecognized metadata.transport {transport!r}"
        )
    raise ValueError(f"connection {connection.id!r} requires metadata.transport")


__all__ = [
    "McpSourceConnection",
    "mcp_source_connection_from_connection_config",
    "mcp_source_connection_from_registry_entry",
]
```

- [ ] **Step 4: Export the new seam from the package**

In `src/wf_sources_mcp/__init__.py`, export or lazily expose:

```python
McpSourceConnection
mcp_source_connection_from_connection_config
mcp_source_connection_from_registry_entry
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py tests/wf_sources_mcp/test_source_registry.py -q
```

Expected: pass.

---

## Task 4: Update Auth And SDK Protocols To Use The Source Seam

**Files:**
- Modify: `src/wf_sources_mcp/auth.py`
- Modify: `src/wf_sources_mcp/sdk/protocols.py`
- Test: `tests/wf_sources_mcp/test_auth.py`
- Test: `tests/wf_sources_mcp/test_sdk_protocols.py`
- Test: `tests/wf_sources_mcp/test_connections.py`

- [ ] **Step 1: Add protocol/conformance tests**

Append to `tests/wf_sources_mcp/test_connections.py`:

```python
from typing import Protocol

from wf_sources_mcp.auth import auth_ref_for_connection
from wf_sources_mcp.sdk import BackendAdapter, ToolExecutor


class _ConnectionLike(Protocol):
    id: str
    auth_ref: str | None


def test_auth_ref_for_typed_mcp_source_connection() -> None:
    connection = McpSourceConnection(
        id="github.work",
        provider="github",
        account="work",
        transport=StdioSourceTransport(command="uvx"),
        auth_ref="github.token",
    )

    assert auth_ref_for_connection(connection) == "github.token"


def test_sdk_protocols_are_importable_without_broker_connection_config() -> None:
    assert BackendAdapter is not None
    assert ToolExecutor is not None
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py tests/wf_sources_mcp/test_auth.py tests/wf_sources_mcp/test_sdk_protocols.py -q
```

Expected: likely fail until auth/protocols stop importing `ConnectionConfig`.

- [ ] **Step 3: Update `auth.py`**

In `src/wf_sources_mcp/auth.py`:

- Remove the `TYPE_CHECKING` import of `wf_mcp.broker.models.ConnectionConfig`.
- Define a small protocol:

```python
class SourceConnectionLike(Protocol):
    id: str
    auth_ref: str | None
```

- Change:

```python
def auth_ref_for_connection(connection: ConnectionConfig) -> str | None:
    auth_ref = connection.metadata.get("auth_ref")
    return auth_ref if isinstance(auth_ref, str) else None
```

to:

```python
def auth_ref_for_connection(connection: SourceConnectionLike) -> str | None:
    return connection.auth_ref
```

- Change `connection_auth_diagnostic(connection: ConnectionConfig, ...)` to accept `SourceConnectionLike`.

Important: this intentionally means callers that still hold `ConnectionConfig` must convert to `McpSourceConnection` before using auth diagnostics. If current production callers need a compatibility path, use `mcp_source_connection_from_connection_config(connection)` at that call site instead of reintroducing metadata reads in `auth.py`.

- [ ] **Step 4: Update `sdk/protocols.py`**

In `src/wf_sources_mcp/sdk/protocols.py`:

- Remove `TYPE_CHECKING` and `ConnectionConfig`.
- Import:

```python
from wf_sources_mcp.connections import McpSourceConnection
```

- Change all `connection: ConnectionConfig` parameters in `BackendAdapter` and `ToolExecutor` to:

```python
connection: McpSourceConnection
```

This is a type-only protocol change. Production adapters may need a follow-up slice to convert broker DTOs before calling the protocol.

- [ ] **Step 5: Run focused type/tests**

Run:

```bash
uv run pytest tests/wf_sources_mcp/test_connections.py tests/wf_sources_mcp/test_auth.py tests/wf_sources_mcp/test_sdk_protocols.py -q
uv run basedpyright --level error src/wf_sources_mcp
```

Expected: pass or reveal call sites that still need explicit conversion. Fix call sites by converting at the broker boundary, not by weakening `McpSourceConnection` back into `metadata`.

---

## Task 5: Update Current Broker Call Sites At The Boundary

**Files:**
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `src/wf_mcp/broker/service/source_catalog.py`
- Modify: `src/wf_mcp/runtime/factory.py`
- Modify: `src/wf_mcp/runtime/session.py`
- Modify: `src/wf_mcp/runtime/pool.py`
- Modify: `src/wf_mcp/sdk/adapter.py`
- Test: existing focused tests

- [ ] **Step 1: Find all protocol call sites**

Run:

```bash
rg -n 'BackendAdapter|ToolExecutor|call_tool\\(|list_tools\\(|list_resources\\(|list_prompts\\(|read_resource\\(|get_prompt\\(|invoke_method\\(|send_notification\\(' src\\wf_mcp src\\wf_sources_mcp
```

Inspect call sites that pass a `ConnectionConfig` into a `BackendAdapter` or `ToolExecutor`.

- [ ] **Step 2: Convert at the broker edge**

Where broker services call source-provider protocols, convert with:

```python
from wf_sources_mcp.connections import mcp_source_connection_from_connection_config

source_connection = mcp_source_connection_from_connection_config(connection)
```

Then pass `source_connection` to `BackendAdapter` / `ToolExecutor` methods.

Keep `ConnectionConfig` in broker services for registry/config ownership and source catalog behavior. Do not rewrite the whole broker service in this slice.

- [ ] **Step 3: Keep runtime files compiling without moving them**

If `PersistentMcpSession`, `McpRuntimePool`, or `McpSdkAdapter` currently implement `ToolExecutor` / `BackendAdapter`, update their method signatures to accept `McpSourceConnection` where needed.

If their public callers still pass `ConnectionConfig`, convert at the public method boundary and keep a comment:

```python
# Compatibility boundary: broker callers still pass ConnectionConfig. Runtime
# internals use McpSourceConnection so the session code can move to
# wf_sources_mcp in a later slice.
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_sources_mcp -q
uv run basedpyright --level error src
```

Expected: pass.

---

## Task 6: Documentation And Verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`

- [ ] **Step 1: Update roadmap**

In `docs/current_roadmap.md`, under the MCP source provider / long-lived API section, add a short note:

```markdown
- Completed: typed MCP source connection seam is introduced in `wf_sources_mcp`.
  Source IDs, reserved IDs, transport models, and `McpSourceConnection` are now
  canonical source-provider concepts. Legacy broker `ConnectionConfig` remains
  intact and converts at compatibility edges; runtime/session files are not
  moved yet.
```

- [ ] **Step 2: Update long-lived boundary spec**

In `docs/superpowers/specs/2026-06-03-long-lived-workflow-api-boundary.md`, extend the MCP source provider package direction list:

```markdown
6. Complete: typed MCP source connection seam introduced. `McpSourceConnection`
   is the runtime-facing source object; legacy `ConnectionConfig` converts at
   broker edges.
7. Next: shared MCP session opener, then runtime/session/pool move.
```

- [ ] **Step 3: Run final verification**

Run:

```bash
uv run pytest tests/wf_sources_mcp tests/wf_mcp/test_sdk_adapter.py tests/wf_mcp/test_stateful_runtime.py tests/wf_mcp/service/test_upstream_transport.py -q
uv run ruff check src tests
uv run basedpyright --level error src
git diff --check
```

Expected:

- tests pass
- ruff passes
- basedpyright has 0 errors
- no diff whitespace errors

- [ ] **Step 4: Report remaining future slices**

Final report must explicitly state:

- runtime/factory/session/pool were not moved
- proxy/frontend MCP code was not touched
- old `ConnectionConfig` shape is unchanged
- next planned slice is shared session opener using `McpSourceConnection`

---

## Future Slices After This Plan

1. **Shared MCP session opener**
   - Create `wf_sources_mcp.sdk.transport.open_mcp_session(connection, auth)`.
   - Replace duplicated session opening in `wf_mcp/runtime/factory.py` and `wf_mcp/sdk/adapter.py`.

2. **Move persistent runtime package**
   - Move `PersistentSessionFactory`, `PersistentMcpSession`, and `McpRuntimePool` to `wf_sources_mcp.runtime`.
   - Keep `wf_mcp.runtime.*` shims.

3. **Move one-shot SDK adapter**
   - Move `McpSdkAdapter` to `wf_sources_mcp.sdk.adapter`.
   - Keep `wf_mcp.sdk.adapter` shim.

4. **Eventually split MCP frontend transport**
   - Move FastMCP server/proxy/admin/workflow tool registration toward `wf_transport_mcp`.
   - This is separate from upstream source runtime and should not block persistent connection work.

---

## Self-Review Notes

- This plan intentionally creates focused files before touching runtime. That keeps the first change testable and limits blast radius.
- The plan does not attempt to phase out all 369 `ConnectionConfig` references. It converts only at source-provider protocol edges.
- The likely implementation risk is type fallout after `BackendAdapter` / `ToolExecutor` signatures change. Resolve by explicit conversion at broker boundaries, not by weakening the typed seam.
