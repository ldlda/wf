from __future__ import annotations

from dataclasses import dataclass

from .admin import RpcAdminClientMixin
from .artifacts import RpcArtifactClientMixin
from .base import RpcClientTransport
from .capabilities import RpcCapabilityClientMixin
from .deployments import RpcDeploymentClientMixin
from .drafts import RpcDraftClientMixin
from .runs import RpcRunClientMixin
from .source_registry import RpcSourceRegistryClientMixin
from .sources import RpcSourceAdminClientMixin


@dataclass(slots=True)
class RpcWorkflowApiClient(
    RpcClientTransport,
    RpcCapabilityClientMixin,
    RpcDraftClientMixin,
    RpcArtifactClientMixin,
    RpcDeploymentClientMixin,
    RpcRunClientMixin,
    RpcSourceAdminClientMixin,
    RpcSourceRegistryClientMixin,
    RpcAdminClientMixin,
):
    """WorkflowApiSurface implementation backed by JSON-RPC HTTP calls.

    The inheritance order is intentional: `RpcClientTransport` owns dataclass
    fields and `_call`; domain mixins are stateless method groups that may only
    depend on `_call`. If a domain needs state or lifecycle later, prefer a
    composed domain client instead of adding fields to a mixin.
    """


__all__ = ["RpcWorkflowApiClient"]
