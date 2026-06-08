"""MCP upstream-source registry models and conversion helpers.

This module is canonical for MCP-as-source desired registry state. Legacy
broker DTO conversions have moved to `wf_mcp.source_registry`. This module
accepts legacy-shaped inputs structurally and must not construct broker
runtime DTOs.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Protocol, cast

from pydantic import Field, field_validator, model_validator

from wf_api.source_registry import (
    AtomicJsonRegistryStore,
    SourceRegistryBaseModel,
    validate_unique_source_ids,
)
from wf_api.source_registry import (
    SourceRegistryStore as GenericSourceRegistryStore,
)
from wf_sources_mcp.ids import RESERVED_CONNECTION_IDS, parse_connection_id
from wf_sources_mcp.transports import (
    HttpSourceTransport,
    SourceTransport,
    StdioSourceTransport,
)

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


class LegacyConnectionConfigLike(Protocol):
    """Structural shape needed from legacy broker connection configs."""

    id: str
    server: str
    account: str
    enabled: bool
    metadata: Mapping[str, object]


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


def connection_config_to_registry_entry(
    connection: LegacyConnectionConfigLike,
) -> McpSourceRegistryEntry:
    """Materialize a seed config connection into persisted registry state.

    Seed config is bootstrap-only. The registry entry must carry enough source
    identity to become the future desired-state owner after first startup.
    """
    transport = connection.metadata.get("transport")
    legacy_transport_value: str | None = None
    if isinstance(transport, dict):
        pass
    elif isinstance(transport, str):
        if transport == "stdio":
            args_raw = connection.metadata.get("args", ())
            env_raw = connection.metadata.get("env", {})
            transport = {
                "kind": "stdio",
                "command": connection.metadata.get("command", ""),
                "args": list(cast("tuple[object, ...]", args_raw)),
                "env": dict(cast("dict[str, object]", env_raw)),
                "cwd": connection.metadata.get("cwd"),
            }
        elif transport in _FLAT_HTTP_TRANSPORTS:
            legacy_transport_value = transport
            headers_raw = connection.metadata.get("headers", {})
            transport = {
                "kind": "http",
                "url": connection.metadata.get("url", ""),
                "headers": dict(cast("dict[str, object]", headers_raw)),
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
    if legacy_transport_value is not None:
        source_metadata["legacy_transport"] = legacy_transport_value
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


__all__ = [
    "FileSourceRegistryStore",
    "HttpSourceTransport",
    "LegacyConnectionConfigLike",
    "McpSourceRegistryEntry",
    "SourceRegistryFile",
    "SourceRegistryStore",
    "SourceTransport",
    "StdioSourceTransport",
    "connection_config_to_registry_entry",
]
