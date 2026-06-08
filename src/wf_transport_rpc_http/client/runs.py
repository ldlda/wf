from __future__ import annotations

from typing import Any

from wf_api.runs import TraceRangeLike

from .base import RpcCaller


class RpcRunClientMixin:
    """JSON-RPC implementation of workflow run lifecycle surface methods."""

    async def run_deployment(
        self: RpcCaller,
        *,
        deployment_id: str,
        workflow_input: dict[str, Any],
        trace_range: TraceRangeLike | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.runs.start",
            {
                "deployment_id": deployment_id,
                "workflow_input": workflow_input,
                "trace_range": _trace_range_payload(trace_range),
            },
        )

    async def resume_run(
        self: RpcCaller,
        *,
        run_id: str,
        resume_payload: dict[str, Any],
        resume_outcome: str = "submitted",
        trace_range: TraceRangeLike | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.runs.resume",
            {
                "run_id": run_id,
                "resume_payload": resume_payload,
                "resume_outcome": resume_outcome,
                "trace_range": _trace_range_payload(trace_range),
            },
        )

    async def inspect_run(self: RpcCaller, *, run_id: str) -> dict[str, Any]:
        return await self._call("workflow.runs.inspect", {"run_id": run_id})

    async def read_run_trace(
        self: RpcCaller,
        *,
        run_id: str,
        trace_range: TraceRangeLike,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.runs.trace",
            {
                "run_id": run_id,
                "trace_range": _trace_range_payload(trace_range),
            },
        )


def _trace_range_payload(
    trace_range: TraceRangeLike | None,
) -> dict[str, int] | None:
    if trace_range is None:
        return None
    return {"start": trace_range.start, "limit": trace_range.limit}
