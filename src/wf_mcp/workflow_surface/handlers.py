from __future__ import annotations

from typing import TYPE_CHECKING

from wf_api import WorkflowApi

from ..broker.service.workflow_operation_context import context_from_service

if TYPE_CHECKING:
    from ..broker.service import WfMcpService


class WorkflowSurfaceHandlers(WorkflowApi):
    """Compatibility wrapper for old wf_mcp.workflow_surface imports.

    New code should construct `WorkflowApi(context_from_service(service), drafts=True)`
    directly. This shim keeps tests and legacy broker artifact tools working
    for legacy callers.
    """

    def __init__(self, service: WfMcpService) -> None:
        self.service = service
        # This compatibility surface exposes the draft methods used by the
        # workflow-surface tests and legacy broker artifact tools.
        super().__init__(context_from_service(service), drafts=True)


__all__ = ["WorkflowSurfaceHandlers"]
