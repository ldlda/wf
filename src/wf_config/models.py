from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class WorkflowConfigModel(BaseModel):
    """Base config model: reject typos so config mistakes fail fast."""

    model_config = ConfigDict(extra="forbid")


class LocalTargetConfig(WorkflowConfigModel):
    kind: Literal["local"] = "local"


class RpcHttpTargetConfig(WorkflowConfigModel):
    kind: Literal["rpc_http"]
    url: AnyHttpUrl
    timeout_seconds: float = Field(default=30.0, gt=0)


TargetConfig = Annotated[
    LocalTargetConfig | RpcHttpTargetConfig,
    Field(discriminator="kind"),
]


class ClientConfig(WorkflowConfigModel):
    target: TargetConfig = Field(default_factory=LocalTargetConfig)


class FilesystemStoreConfig(WorkflowConfigModel):
    kind: Literal["filesystem"] = "filesystem"
    root: Path = Path(".wf_store")


StoreConfig = Annotated[
    FilesystemStoreConfig,
    Field(discriminator="kind"),
]


class RpcHttpTransportConfig(WorkflowConfigModel):
    kind: Literal["rpc_http"]
    host: str = "127.0.0.1"
    port: int = Field(default=8765, ge=1, le=65535)
    path: str = "/rpc"

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("transport path must start with '/'")
        return value


ServerTransportConfig = Annotated[
    RpcHttpTransportConfig,
    Field(discriminator="kind"),
]

SourceConfigOwnership = Literal["locked", "seed"]
SOURCE_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"


class StdioSourceTransportConfig(WorkflowConfigModel):
    kind: Literal["stdio"] = "stdio"
    command: str = Field(min_length=1)
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)


class HttpSourceTransportConfig(WorkflowConfigModel):
    kind: Literal["http"] = "http"
    url: AnyHttpUrl
    headers: dict[str, str] = Field(default_factory=dict)


SourceTransportConfig = Annotated[
    StdioSourceTransportConfig | HttpSourceTransportConfig,
    Field(discriminator="kind"),
]


class StdlibSourceConfig(WorkflowConfigModel):
    kind: Literal["stdlib"]
    id: Literal["wf.std", "wf.recipes"]


class McpSourceConfig(WorkflowConfigModel):
    """Neutral config shape for MCP-backed workflow capability sources.

    This intentionally mirrors `wf_mcp.source_registry.McpSourceRegistryEntry`
    without importing MCP modules. `ownership` carries the old
    `ConnectionConfig.source_config_ownership` policy with neutral terminology.
    """

    kind: Literal["mcp"] = "mcp"
    id: str
    enabled: bool = True
    provider: str = Field(min_length=1)
    account: str = Field(min_length=1)
    profile: str | None = None
    ownership: SourceConfigOwnership = "locked"
    transport: SourceTransportConfig
    auth_ref: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        if not re.fullmatch(SOURCE_ID_PATTERN, value):
            raise ValueError(
                "source id must start with alphanumeric or underscore and contain "
                "only [A-Za-z0-9_.-]"
            )
        if "." not in value:
            raise ValueError("source id must look like '<provider>.<account>'")
        provider, account = value.split(".", 1)
        if not provider or not account:
            raise ValueError("source id must look like '<provider>.<account>'")
        return value


SourceConfig = Annotated[
    StdlibSourceConfig | McpSourceConfig,
    Field(discriminator="kind"),
]


class ServerConfig(WorkflowConfigModel):
    store: StoreConfig = Field(default_factory=FilesystemStoreConfig)
    transports: list[ServerTransportConfig] = Field(default_factory=list)
    sources: list[SourceConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> ServerConfig:
        seen: set[str] = set()
        for source in self.sources:
            if source.id in seen:
                raise ValueError(f"duplicate source id {source.id!r}")
            seen.add(source.id)
        return self


class WorkflowConfigFile(WorkflowConfigModel):
    version: Literal[1] = 1
    client: ClientConfig = Field(default_factory=ClientConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
