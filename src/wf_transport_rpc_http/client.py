from __future__ import annotations

from dataclasses import dataclass

import httpx  # noqa: F401  # Backcompat for tests patching client.httpx.AsyncClient.

from .client_artifacts import RpcArtifactClientMixin
from .client_base import RpcClientTransport
from .client_capabilities import RpcCapabilityClientMixin
from .client_deployments import RpcDeploymentClientMixin
from .client_drafts import RpcDraftClientMixin
from .client_runs import RpcRunClientMixin


@dataclass(slots=True)
class RpcWorkflowApiClient(
    RpcClientTransport,
    RpcCapabilityClientMixin,
    RpcDraftClientMixin,
    RpcArtifactClientMixin,
    RpcDeploymentClientMixin,
    RpcRunClientMixin,
):
    """WorkflowApiSurface implementation backed by JSON-RPC HTTP calls.

    The inheritance order is intentional: `RpcClientTransport` owns dataclass
    fields and `_call`; domain mixins are stateless method groups that may only
    depend on `_call`. If a domain needs state or lifecycle later, prefer a
    composed domain client instead of adding fields to a mixin.
    """


__all__ = ["RpcWorkflowApiClient"]
