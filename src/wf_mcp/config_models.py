from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from .models import BrokerConfig, ConnectionConfig


class StdioConnectionMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    transport: Literal["stdio"] = "stdio"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    description: str | None = None


class HttpConnectionMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    transport: Literal["http", "streamable-http", "streamable_http", "sse"]
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    description: str | None = None


TypedConnectionMetadata = Annotated[
    StdioConnectionMetadata | HttpConnectionMetadata,
    Field(discriminator="transport"),
]
_METADATA_ADAPTER = TypeAdapter(TypedConnectionMetadata)


class ConnectionConfigFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    server: str
    account: str
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be an object")
        if not value:
            return {}
        if "transport" not in value:
            value = {**value, "transport": "stdio"}
        metadata = _METADATA_ADAPTER.validate_python(value)
        return metadata.model_dump(exclude_none=True)

    def to_runtime(self) -> ConnectionConfig:
        return ConnectionConfig(
            id=self.id,
            server=self.server,
            account=self.account,
            enabled=self.enabled,
            metadata=self.metadata,
        )


class BrokerConfigFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_root: Path = Path(".wf_mcp_store")
    connections: list[ConnectionConfigFile] = Field(default_factory=list)

    def to_runtime(self, *, config_path: Path) -> BrokerConfig:
        store_root = self.store_root
        if not store_root.is_absolute():
            store_root = (config_path.parent / store_root).resolve()
        return BrokerConfig(
            store_root=store_root,
            connections=[connection.to_runtime() for connection in self.connections],
        )
