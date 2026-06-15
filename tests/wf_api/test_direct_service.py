from __future__ import annotations

from pathlib import Path

import pytest

from tests.wf_mcp.test_support import echo_tool
from wf_api import WorkflowApi
from wf_api.artifacts import WorkflowArtifactApi
from wf_api.capabilities import WorkflowCapabilityApi
from wf_api.deployments import WorkflowDeploymentApi
from wf_api.drafts import WorkflowDraftApi
from wf_api.runs import WorkflowRunApi
from wf_artifacts import FileWorkflowArtifactStore
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore


def _api(root: Path) -> WorkflowApi:
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=FileWorkflowArtifactStore(root),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    return WorkflowApi(context_from_service(service))


def test_workflow_api_composes_domain_services(tmp_path: Path) -> None:
    api = _api(tmp_path / "wf_api_direct_composition")

    assert isinstance(api.capabilities, WorkflowCapabilityApi)
    assert isinstance(api.drafts, WorkflowDraftApi)
    assert isinstance(api.artifacts, WorkflowArtifactApi)
    assert isinstance(api.deployments, WorkflowDeploymentApi)
    assert isinstance(api.runs, WorkflowRunApi)
    assert not hasattr(api, "backend")


@pytest.mark.asyncio
async def test_workflow_api_direct_capability_call(tmp_path: Path) -> None:
    api = _api(tmp_path / "wf_api_direct_composition")

    result = await api.call_capability(
        qualified_name="demo.personal.echo_tool",
        payload={"text": "hello"},
    )

    assert result["kind"] == "node_spec"
    assert result["outcome"] == "ok"
    assert result["output"] == {"echoed": "hello"}


def test_workflow_surface_handlers_is_compatibility_shim(tmp_path: Path) -> None:
    from wf_api import WorkflowApi
    from wf_mcp.workflow_surface import WorkflowSurfaceHandlers

    root = tmp_path / "workflow_surface_handler_shim"
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=FileWorkflowArtifactStore(root),
    )

    handlers = WorkflowSurfaceHandlers(service)

    assert isinstance(handlers, WorkflowApi)
    assert handlers.service is service
    assert handlers.context.artifact_store is service.artifact_store
