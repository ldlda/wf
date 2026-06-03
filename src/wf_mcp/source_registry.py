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


__all__ = [
    "FileSourceRegistryStore",
    "HttpSourceTransport",
    "McpSourceRegistryEntry",
    "SourceRegistryFile",
    "SourceRegistryStore",
    "SourceTransport",
    "StdioSourceTransport",
    "registry_entry_to_connection_config",
]
