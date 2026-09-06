"""Generic MCP messages for the deliberately untyped extension surface."""

from typing import Any

from mcp.types import Notification, Request
from pydantic import BaseModel, ConfigDict

type RawParams = dict[str, Any] | None
type RawRequest = Request[RawParams, str]
type RawNotification = Notification[RawParams, str]


class RawResult(BaseModel):
    """Preserve every field returned by an extension method."""

    model_config = ConfigDict(extra="allow")


def raw_request(method: str, params: RawParams) -> RawRequest:
    """Build an extension request without narrowing it to standard methods."""
    return Request[RawParams, str](method=method, params=params)


def raw_notification(method: str, params: RawParams) -> RawNotification:
    """Build an extension notification without narrowing its method name."""
    return Notification[RawParams, str](method=method, params=params)


__all__ = [
    "RawNotification",
    "RawParams",
    "RawRequest",
    "RawResult",
    "raw_notification",
    "raw_request",
]
