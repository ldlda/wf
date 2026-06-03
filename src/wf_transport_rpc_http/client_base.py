from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx


@dataclass(slots=True)
class RpcClientTransport:
    """Shared JSON-RPC request plumbing for workflow RPC client mixins."""

    url: str
    timeout_seconds: float = 30.0
    http_client: httpx.AsyncClient | None = None

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": uuid4().hex,
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
        if "error" in payload:
            error = payload["error"]
            message = error.get("message", "JSON-RPC error")
            data = error.get("data")
            if isinstance(data, dict) and data.get("message"):
                message = f"{message}: {data['message']}"
            raise RuntimeError(message)
        result = payload.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("JSON-RPC response result must be an object")
        return result
