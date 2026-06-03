from __future__ import annotations

import httpx  # noqa: F401  # Backcompat for tests patching client.httpx.AsyncClient.

from .client_artifacts import RpcArtifactClientMixin
from .client_base import RpcClientTransport
from .client_capabilities import RpcCapabilityClientMixin
from .client_deployments import RpcDeploymentClientMixin
from .client_drafts import RpcDraftClientMixin
from .client_runs import RpcRunClientMixin


class RpcWorkflowApiClient(
    RpcClientTransport,
    RpcCapabilityClientMixin,
    RpcDraftClientMixin,
    RpcArtifactClientMixin,
    RpcDeploymentClientMixin,
    RpcRunClientMixin,
):
    """WorkflowApiSurface implementation backed by JSON-RPC HTTP calls."""


__all__ = ["RpcWorkflowApiClient"]
