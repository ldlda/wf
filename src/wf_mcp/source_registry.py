from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, Protocol

from pathlib import Path

from pydantic import (
    AnyHttpUrl,
    Field,
    field_validator,
    model_validator,
)

from wf_api.source_registry import (
    AtomicJsonRegistryStore,
    SourceRegistryBaseModel,
    SourceRegistryStore as GenericSourceRegistryStore,
    validate_unique_source_ids,
)

from .connections import parse_connection_id
from .shared.names import RESERVED_CONNECTION_IDS

if TYPE_CHECKING:
    from .models import ConnectionConfig

_FLAT_HTTP_TRANSPORTS = {"http", "streamable-http", "streamable_http", "sse"}
_TRANSPORT_METADATA_KEYS = {
    "transport",
    "command",
    "args",
    "env",
    "cwd",
    "url",
    "headers",
    "profile",
    "auth_ref",
    "source_registry",
}


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


class McpSourceRegistryEntry(SourceRegistryBaseModel):
    """Desired MCP source configuration persisted by server-owned mutation."""

    id: str
    kind: Literal["mcp"] = "mcp"
    enabled: bool = True
    provider: str = Field(min_length=1)
    account: str = Field(min_length=1)
    profile: str | None = None
    transport: SourceTransport
    auth_ref: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        parse_connection_id(value)
        if value in RESERVED_CONNECTION_IDS:
            raise ValueError(f"source id {value!r} is reserved")
        return value


class SourceRegistryFile(SourceRegistryBaseModel):
    version: Literal[1] = 1
    sources: list[McpSourceRegistryEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> SourceRegistryFile:
        validate_unique_source_ids(self.sources)
        return self

    def source_map(self) -> dict[str, McpSourceRegistryEntry]:
        return {source.id: source for source in self.sources}


class SourceRegistryStore(GenericSourceRegistryStore[SourceRegistryFile], Protocol):
    """MCP-specialized persistence boundary for desired source configuration."""


class FileSourceRegistryStore:
    """Filesystem implementation for desired source registry state."""

    def __init__(self, root: Path) -> None:
        self._delegate = AtomicJsonRegistryStore(
            root,
            filename="source_registry.json",
            registry_type=SourceRegistryFile,
            empty_factory=SourceRegistryFile,
            corrupt_label="source registry file",
        )

    @property
    def path(self) -> Path:
        return self._delegate.path

    def load_registry(self) -> SourceRegistryFile:
        return self._delegate.load_registry()

    def save_registry(self, registry: SourceRegistryFile) -> None:
        self._delegate.save_registry(registry)


def registry_entry_to_connection_config(
    entry: McpSourceRegistryEntry,
) -> ConnectionConfig:
    """Convert a registry entry to a broker connection config."""
    from .models import ConnectionConfig

    return ConnectionConfig(
        id=entry.id,
        server=entry.provider,
        account=entry.account,
        enabled=entry.enabled,
        metadata={
            **entry.metadata,
            "auth_ref": entry.auth_ref,
            "profile": entry.profile,
            "transport": entry.transport.model_dump(mode="json"),
            "source_registry": True,
        },
    )


def connection_config_to_registry_entry(
    connection: ConnectionConfig,
) -> McpSourceRegistryEntry:
    """Materialize a seed config connection into persisted registry state.

    Seed config is bootstrap-only. The registry entry must carry enough source
    identity to become the future desired-state owner after first startup.
    """
    transport = connection.metadata.get("transport")
    if isinstance(transport, dict):
        pass
    elif isinstance(transport, str):
        if transport == "stdio":
            transport = {
                "kind": "stdio",
                "command": connection.metadata.get("command", ""),
                "args": list(connection.metadata.get("args", [])),
                "env": dict(connection.metadata.get("env", {})),
            }
        elif transport in _FLAT_HTTP_TRANSPORTS:
            legacy_transport = transport
            transport = {
                "kind": "http",
                "url": connection.metadata.get("url", ""),
                "headers": dict(connection.metadata.get("headers", {})),
            }
        else:
            raise ValueError(
                f"seed connection {connection.id!r} has unrecognized transport {transport!r}"
            )
    else:
        raise ValueError(
            f"seed connection {connection.id!r} requires metadata.transport"
        )
    profile = connection.metadata.get("profile")
    auth_ref = connection.metadata.get("auth_ref")
    source_metadata = {
        key: value
        for key, value in connection.metadata.items()
        if key not in _TRANSPORT_METADATA_KEYS
    }
    if "legacy_transport" in locals():
        source_metadata["legacy_transport"] = legacy_transport
    entry = McpSourceRegistryEntry.model_validate(
        {
            "id": connection.id,
            "enabled": connection.enabled,
            "provider": connection.server,
            "account": connection.account,
            "profile": profile if isinstance(profile, str) else None,
            "transport": transport,
            "auth_ref": auth_ref if isinstance(auth_ref, str) else None,
            "metadata": source_metadata,
        }
    )
    return entry


def workflow_mcp_source_to_connection_config(source: object) -> ConnectionConfig:
    """Convert neutral wf_config MCP source config into a broker connection.

    Keep this adapter in wf_mcp because the output is MCP broker runtime state.
    The input is intentionally typed as object to avoid making wf_mcp's public
    registry module part of wf_config's import graph.
    """
    from .models import ConnectionConfig

    if getattr(source, "kind", None) != "mcp":
        raise ValueError("expected wf_config MCP source")
    for field in ("id", "provider", "account", "enabled", "ownership"):
        if getattr(source, field, None) is None:
            raise ValueError(f"wf_config MCP source missing required field: {field}")
    transport = getattr(source, "transport")
    metadata = dict(getattr(source, "metadata", {}))
    if transport.kind == "stdio":
        metadata.update(
            {
                "transport": "stdio",
                "command": transport.command,
                "args": list(transport.args),
                "env": dict(transport.env),
                "source_registry": False,
            }
        )
    elif transport.kind == "http":
        metadata.update(
            {
                "transport": "streamable_http",
                "url": str(transport.url),
                "headers": dict(transport.headers),
                "source_registry": False,
            }
        )
    else:
        raise ValueError(f"unsupported wf_config MCP transport {transport.kind!r}")
    profile = getattr(source, "profile", None)
    if profile is not None:
        metadata["profile"] = profile
    auth_ref = getattr(source, "auth_ref", None)
    if auth_ref is not None:
        metadata["auth_ref"] = auth_ref
    return ConnectionConfig(
        id=getattr(source, "id"),
        server=getattr(source, "provider"),
        account=getattr(source, "account"),
        enabled=getattr(source, "enabled"),
        metadata=metadata,
        source_config_ownership=getattr(source, "ownership"),
    )


__all__ = [
    "FileSourceRegistryStore",
    "HttpSourceTransport",
    "McpSourceRegistryEntry",
    "SourceRegistryFile",
    "SourceRegistryStore",
    "SourceTransport",
    "StdioSourceTransport",
    "connection_config_to_registry_entry",
    "registry_entry_to_connection_config",
    "workflow_mcp_source_to_connection_config",
]
