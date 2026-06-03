from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

import httpx

from wf_api.models import TraceRange


@dataclass(slots=True)
class RpcWorkflowApiClient:
    """Small WorkflowApi-compatible adapter for JSON-RPC HTTP targets.

    This is intentionally not a full WorkflowApi clone. It implements only the
    methods used by CLI commands targeting rpc_http transports.
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

    # -- capabilities --

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

    # -- draft workspaces --

    async def list_draft_workspaces(self) -> dict[str, Any]:
        return await self._call("workflow.draft_workspaces.list", {})

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.get",
            {"workspace_id": workspace_id, "include_draft": include_draft},
        )

    async def create_draft_workspace_from_capability(
        self,
        *,
        workspace_id: str,
        capability_name: str,
        name: str | None = None,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": workspace_id,
                "capability_name": capability_name,
                "name": name,
                "title": title,
                "input_schema": input_schema,
                "state_schema": state_schema,
                "output_schema": output_schema,
                "input": input,
                "output": output,
                "input_map": input_map,
                "output_map": output_map,
                "error_message_source": error_message_source,
            },
        )

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.patch",
            {"workspace_id": workspace_id, "revision": revision, "patch": patch},
        )

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.validate",
            {"workspace_id": workspace_id},
        )

    async def create_artifact_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        kind: Literal["workflow", "wrapper"] = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.create_artifact",
            {
                "workspace_id": workspace_id,
                "artifact_id": artifact_id,
                "version": version,
                "title": title,
                "outcomes": list(outcomes),
                "kind": kind,
                "description": description,
                "required_capabilities": required_capabilities,
                "source_bindings": source_bindings,
                "created_from_catalog_version": created_from_catalog_version,
            },
        )

    async def create_wrapper_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.create_wrapper",
            {
                "workspace_id": workspace_id,
                "artifact_id": artifact_id,
                "version": version,
                "title": title,
                "outcomes": list(outcomes),
                "description": description,
                "required_capabilities": required_capabilities,
                "source_bindings": source_bindings,
                "created_from_catalog_version": created_from_catalog_version,
            },
        )

    # -- artifacts --

    async def list_artifacts(
        self,
        *,
        query: str | None = None,
        kind: Literal["workflow", "wrapper"] | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.artifacts.list",
            {
                "query": query,
                "kind": kind,
                "cursor": cursor,
                "limit": limit,
            },
        )

    async def inspect_artifact(
        self, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.artifacts.inspect",
            {"artifact_id": artifact_id, "version": version},
        )

    async def save_artifact(self, artifact: dict[str, Any]) -> dict[str, Any]:
        return await self._call("workflow.artifacts.save", {"artifact": artifact})

    # -- deployments --

    async def list_deployments(self) -> dict[str, Any]:
        return await self._call("workflow.deployments.list", {})

    async def inspect_deployment(self, *, deployment_id: str) -> dict[str, Any]:
        return await self._call(
            "workflow.deployments.inspect",
            {"deployment_id": deployment_id},
        )

    async def validate_deployment(
        self, *, deployment_id: str, live_check: bool = False
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.deployments.validate",
            {"deployment_id": deployment_id, "live_check": live_check},
        )

    async def save_deployment(self, deployment: dict[str, Any]) -> dict[str, Any]:
        return await self._call("workflow.deployments.save", {"deployment": deployment})

    async def delete_deployment(self, *, deployment_id: str) -> dict[str, Any]:
        return await self._call(
            "workflow.deployments.delete",
            {"deployment_id": deployment_id},
        )

    # -- runs --

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
