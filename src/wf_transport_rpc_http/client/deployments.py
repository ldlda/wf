from __future__ import annotations

from typing import Any, cast

from wf_api.models import (
    DeleteDeploymentResult,
    ListDeploymentsResult,
    SaveDeploymentResult,
    ValidateDeploymentResult,
    WorkflowDeploymentPayload,
)

from .base import RpcCaller


class RpcDeploymentClientMixin:
    """JSON-RPC implementation of workflow deployment surface methods."""

    async def list_deployments(self: RpcCaller) -> ListDeploymentsResult:
        return cast(
            ListDeploymentsResult,
            await self._call("workflow.deployments.list", {}),
        )

    async def inspect_deployment(
        self: RpcCaller, *, deployment_id: str
    ) -> WorkflowDeploymentPayload:
        return cast(
            WorkflowDeploymentPayload,
            await self._call(
                "workflow.deployments.inspect",
                {"deployment_id": deployment_id},
            ),
        )

    async def validate_deployment(
        self: RpcCaller, *, deployment_id: str, live_check: bool = False
    ) -> ValidateDeploymentResult:
        return cast(
            ValidateDeploymentResult,
            await self._call(
                "workflow.deployments.validate",
                {"deployment_id": deployment_id, "live_check": live_check},
            ),
        )

    async def save_deployment(
        self: RpcCaller, deployment: dict[str, Any]
    ) -> SaveDeploymentResult:
        return cast(
            SaveDeploymentResult,
            await self._call(
                "workflow.deployments.save",
                {"deployment": deployment},
            ),
        )

    async def delete_deployment(
        self: RpcCaller, *, deployment_id: str
    ) -> DeleteDeploymentResult:
        return cast(
            DeleteDeploymentResult,
            await self._call(
                "workflow.deployments.delete",
                {"deployment_id": deployment_id},
            ),
        )
