from __future__ import annotations

import pytest

from wf_api import WorkflowApi
from wf_api.durable_context import durable_workflow_api, require_workflow_stores
from wf_api.stores import file_workflow_stores
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.storage import FileStore


def test_require_workflow_stores_returns_existing_store_bundle(tmp_path) -> None:
    stores = file_workflow_stores(tmp_path / "workflow_stores")
    service = WfMcpService(
        store=FileStore(tmp_path / "mcp"),
        artifact_store=stores.artifact_store,
        draft_workspace_store=stores.draft_workspace_store,
        run_store=stores.run_store,
    )
    context = context_from_service(service)

    required = require_workflow_stores(context)

    assert required.artifact_store is stores.artifact_store
    assert required.draft_workspace_store is stores.draft_workspace_store
    assert required.run_store is stores.run_store


def test_require_workflow_stores_rejects_missing_store(tmp_path) -> None:
    service = WfMcpService(
        store=FileStore(tmp_path / "mcp"),
        artifact_store=None,
        draft_workspace_store=None,
        run_store=None,
    )
    context = context_from_service(service)

    with pytest.raises(ValueError, match="durable workflow API requires stores"):
        require_workflow_stores(context)


def test_durable_workflow_api_returns_workflow_api_with_same_context(tmp_path) -> None:
    stores = file_workflow_stores(tmp_path / "workflow_stores")
    service = WfMcpService(
        store=FileStore(tmp_path / "mcp"),
        artifact_store=stores.artifact_store,
        draft_workspace_store=stores.draft_workspace_store,
        run_store=stores.run_store,
    )
    context = context_from_service(service)

    api = durable_workflow_api(context)

    assert isinstance(api, WorkflowApi)
    assert api.context is context
