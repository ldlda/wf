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
