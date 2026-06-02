from __future__ import annotations

from .operation_context import WorkflowOperationContext
from .service import WorkflowApi
from .stores import WorkflowStores


def require_workflow_stores(context: WorkflowOperationContext) -> WorkflowStores:
    """Return required stores or fail before constructing durable frontends.

    `WorkflowOperationContext` keeps stores optional for compatibility tests and
    lightweight MCP surfaces. Durable API surfaces need all stores up front so a
    run cannot start without somewhere to persist artifacts, drafts, and stopped
    execution state.
    """
    missing = []
    if context.artifact_store is None:
        missing.append("artifact_store")
    if context.draft_workspace_store is None:
        missing.append("draft_workspace_store")
    if context.run_store is None:
        missing.append("run_store")
    if missing:
        raise ValueError("durable workflow API requires stores: " + ", ".join(missing))
    assert context.artifact_store is not None
    assert context.draft_workspace_store is not None
    assert context.run_store is not None
    return WorkflowStores(
        artifact_store=context.artifact_store,
        draft_workspace_store=context.draft_workspace_store,
        run_store=context.run_store,
    )


def durable_workflow_api(context: WorkflowOperationContext) -> WorkflowApi:
    """Construct a WorkflowApi only after durable store dependencies exist."""
    require_workflow_stores(context)
    return WorkflowApi(context)


__all__ = ["durable_workflow_api", "require_workflow_stores"]
