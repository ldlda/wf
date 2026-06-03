from __future__ import annotations

from typing import Any


class RpcDeploymentClientMixin:
    """JSON-RPC implementation of workflow deployment surface methods."""

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...

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
