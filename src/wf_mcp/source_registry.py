from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal, Protocol
from uuid import uuid4

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .connections import parse_connection_id
from .shared.names import RESERVED_CONNECTION_IDS


class SourceRegistryModel(BaseModel):
    """Base model for persisted source registry state; reject misspelled fields."""

    model_config = ConfigDict(extra="forbid")


class StdioSourceTransport(SourceRegistryModel):
    kind: Literal["stdio"] = "stdio"
    command: str = Field(min_length=1)
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)


class HttpSourceTransport(SourceRegistryModel):
    kind: Literal["http"] = "http"
    url: AnyHttpUrl
    headers: dict[str, str] = Field(default_factory=dict)


SourceTransport = Annotated[
    StdioSourceTransport | HttpSourceTransport,
    Field(discriminator="kind"),
]


class McpSourceRegistryEntry(SourceRegistryModel):
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


class SourceRegistryFile(SourceRegistryModel):
    version: Literal[1] = 1
    sources: list[McpSourceRegistryEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> SourceRegistryFile:
        seen: set[str] = set()
        for source in self.sources:
            if source.id in seen:
                raise ValueError(f"duplicate source id {source.id!r}")
            seen.add(source.id)
        return self

    def source_map(self) -> dict[str, McpSourceRegistryEntry]:
        return {source.id: source for source in self.sources}


class SourceRegistryStore(Protocol):
    """Persistence boundary for desired server-owned source configuration."""

    def load_registry(self) -> SourceRegistryFile:
        """Return the stored registry, or an empty registry when absent."""
        ...

    def save_registry(self, registry: SourceRegistryFile) -> None:
        """Persist one validated registry atomically."""
        ...


class FileSourceRegistryStore:
    """Filesystem implementation for desired source registry state."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.root / "source_registry.json"

    def load_registry(self) -> SourceRegistryFile:
        if not self.path.exists():
            return SourceRegistryFile()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"source registry file is corrupted: {self.path}") from exc
        return SourceRegistryFile.model_validate(data)

    def save_registry(self, registry: SourceRegistryFile) -> None:
        validated = SourceRegistryFile.model_validate(registry.model_dump(mode="json"))
        payload = json.dumps(validated.model_dump(mode="json"), indent=2)
        # Use a unique temp file so multiple store objects pointing at the same
        # root do not trample each other's pending writes before replacement.
        tmp_path = self.path.with_name(f"{self.path.name}.{uuid4().hex}.tmp")
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(self.path)


__all__ = [
    "FileSourceRegistryStore",
    "HttpSourceTransport",
    "McpSourceRegistryEntry",
    "SourceRegistryFile",
    "SourceRegistryStore",
    "SourceTransport",
    "StdioSourceTransport",
]
