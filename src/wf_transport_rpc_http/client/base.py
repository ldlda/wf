from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import httpx


@dataclass(slots=True)
class RpcProtocolError(RuntimeError):
    """Structured JSON-RPC application error returned by a remote endpoint.

    The exception intentionally remains a ``RuntimeError`` for compatibility
    with the existing CLI's remote-operation handling, while retaining the
    server's machine-readable code and data for richer clients.
    """

    code: int | str | None
    message: str
    data: object = None

    def __post_init__(self) -> None:
        # ``Exception`` stores positional arguments separately from dataclass
        # fields; populate them so generic exception tooling sees the useful
        # rendered message as well.
        object.__setattr__(self, "args", (str(self),))

    def __str__(self) -> str:
        if isinstance(self.data, dict) and isinstance(self.data.get("message"), str):
            return f"{self.message}: {self.data['message']}"
        return self.message


class RpcCaller(Protocol):
    """Transport primitive required by domain RPC client mixins."""

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(slots=True)
class RpcClientTransport:
    """Shared JSON-RPC request plumbing for workflow RPC client mixins.

    If `http_client` is provided, that client's own timeout configuration wins;
    `timeout_seconds` is only used when this transport creates an `AsyncClient`.
    """

    url: str
    timeout_seconds: float = 30.0
    http_client: httpx.AsyncClient | None = None

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = uuid4().hex
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }
        if self.http_client is None:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.url, json=request)
        else:
            response = await self.http_client.post(self.url, json=request)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("JSON-RPC response must be an object")
        if payload.get("jsonrpc") != "2.0":
            raise RuntimeError("JSON-RPC response must declare version '2.0'")
        if payload.get("id") != request_id:
            raise RuntimeError("JSON-RPC response id does not match the request")
        if "error" in payload:
            error = payload["error"]
            if not isinstance(error, dict):
                raise RpcProtocolError(None, "JSON-RPC error", error)
            code = error.get("code")
            if not isinstance(code, (int, str)):
                code = None
            message = error.get("message", "JSON-RPC error")
            if not isinstance(message, str):
                message = "JSON-RPC error"
            raise RpcProtocolError(code, message, error.get("data"))
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("JSON-RPC response result must be an object")
        return result
