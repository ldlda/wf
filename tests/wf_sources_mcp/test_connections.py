from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

import pytest
from pydantic import TypeAdapter

from wf_sources_mcp.auth import auth_ref_for_connection
from wf_sources_mcp.connections import (
    McpSourceConnection,
    mcp_source_connection_from_connection_config,
    mcp_source_connection_from_registry_entry,
)
from wf_sources_mcp.ids import (
    CONNECTION_ID_PATTERN,
    RESERVED_CONNECTION_IDS,
    parse_connection_id,
)
from wf_sources_mcp.sdk import BackendAdapter, ToolExecutor
from wf_sources_mcp.source_registry import McpSourceRegistryEntry
from wf_sources_mcp.transports import (
    HttpSourceTransport,
    SourceTransport,
    StdioSourceTransport,
)


@dataclass(slots=True)
class _LegacyConnectionLike:
    id: str
    server: str
    account: str
    enabled: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)


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
    transport = HttpSourceTransport.model_validate(
        {"url": "http://127.0.0.1:8000/mcp"}
    )

    assert transport.kind == "http"
    assert str(transport.url) == "http://127.0.0.1:8000/mcp"


def test_source_transport_discriminated_union_parses() -> None:
    adapter = TypeAdapter(SourceTransport)

    transport = adapter.validate_python(
        {"kind": "stdio", "command": "pnpx", "args": ["-y", "server"]}
    )

    assert isinstance(transport, StdioSourceTransport)
    assert transport.args == ("-y", "server")


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
            "cwd": "C:/repo",
            "auth_ref": "github.token",
            "profile": "engineering",
            "source_registry": True,
            "team": "platform",
        },
    )

    connection = mcp_source_connection_from_connection_config(legacy)  # type: ignore[arg-type]

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
    assert connection.transport.cwd == "C:/repo"


def test_mcp_source_connection_allows_stable_id_distinct_from_account() -> None:
    """Config source ids are stable keys; provider/account describe upstream identity."""

    legacy = _LegacyConnectionLike(
        id="everything.default",
        server="everything",
        account="demo",
        metadata={"transport": "stdio", "command": "npx"},
    )

    connection = mcp_source_connection_from_connection_config(legacy)

    assert connection.id == "everything.default"
    assert connection.provider == "everything"
    assert connection.account == "demo"


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

    connection = mcp_source_connection_from_connection_config(legacy)  # type: ignore[arg-type]

    assert isinstance(connection.transport, HttpSourceTransport)
    assert str(connection.transport.url) == "http://127.0.0.1:8000/mcp"
    assert connection.transport.headers == {"X-Test": "yes"}


def test_mcp_source_connection_accepts_missing_legacy_transport_until_open() -> None:
    from wf_mcp.broker.models import ConnectionConfig

    legacy = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={},
    )

    connection = mcp_source_connection_from_connection_config(legacy)  # type: ignore[arg-type]

    assert connection.transport is None


def test_structural_legacy_connection_stdio_without_wf_mcp() -> None:
    legacy = _LegacyConnectionLike(
        id="github.work",
        server="github",
        account="work",
        enabled=False,
        metadata={
            "transport": "stdio",
            "command": "uvx",
            "args": ["github-mcp"],
            "env": {"A": "B"},
            "cwd": "C:/repo",
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
    assert connection.transport.cwd == "C:/repo"


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
