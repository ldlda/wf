from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from wf_api.models import TraceRange


@dataclass(slots=True)
class RpcWorkflowApiClient:
    """Small WorkflowApi-compatible adapter for JSON-RPC HTTP targets.

    This is intentionally not a full WorkflowApi clone. It implements only the
    methods used by the first remote CLI slice.
    """

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

    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.capabilities.list",
            {
                "query": query,
                "source_id": source_id,
                "cursor": cursor,
                "limit": limit,
            },
        )

    async def inspect_capability(self, *, qualified_name: str) -> dict[str, Any]:
        return await self._call(
            "workflow.capabilities.inspect",
            {"qualified_name": qualified_name},
        )

    async def run_deployment(
        self,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRange | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.runs.start",
            {
                "deployment_id": deployment_id,
                "workflow_input": workflow_input,
                "trace_range": _trace_range_payload(trace_range),
            },
        )

    async def inspect_run(self, *, run_id: str) -> dict[str, Any]:
        return await self._call("workflow.runs.inspect", {"run_id": run_id})

    async def read_run_trace(
        self,
        *,
        run_id: str,
        trace_range: TraceRange,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.runs.trace",
            {
                "run_id": run_id,
                "trace_range": _trace_range_payload(trace_range),
            },
        )


def _trace_range_payload(trace_range: TraceRange | None) -> dict[str, int] | None:
    if trace_range is None:
        return None
    return {"start": trace_range.start, "limit": trace_range.limit}
