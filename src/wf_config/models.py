from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkflowConfigModel(BaseModel):
    """Base config model: reject typos so config mistakes fail fast."""

    model_config = ConfigDict(extra="forbid")


class LocalTargetConfig(WorkflowConfigModel):
    kind: Literal["local"] = "local"


class RpcHttpTargetConfig(WorkflowConfigModel):
    kind: Literal["rpc_http"]
    url: str = Field(min_length=1)
    timeout_seconds: float = Field(default=30.0, gt=0)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("rpc_http target url must start with http:// or https://")
        return value


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


class StdlibSourceConfig(WorkflowConfigModel):
    kind: Literal["stdlib"]
    id: Literal["wf.std", "wf.recipes"]


SourceConfig = Annotated[
    StdlibSourceConfig,
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
