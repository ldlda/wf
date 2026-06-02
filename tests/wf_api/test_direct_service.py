from __future__ import annotations

import asyncio

from wf_artifacts import FileWorkflowArtifactStore
from wf_api import WorkflowApi
from wf_api.artifacts import WorkflowArtifactApi
from wf_api.capabilities import WorkflowCapabilityApi
from wf_api.deployments import WorkflowDeploymentApi
from wf_api.drafts import WorkflowDraftApi
from wf_api.runs import WorkflowRunApi
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore

from tests.wf_mcp.test_support import echo_tool, local_temp_root


def _api() -> WorkflowApi:
    root = local_temp_root() / "wf_api_direct_composition"
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=FileWorkflowArtifactStore(root),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    return WorkflowApi(context_from_service(service))


def test_workflow_api_composes_domain_services() -> None:
    api = _api()

    assert isinstance(api.capabilities, WorkflowCapabilityApi)
    assert isinstance(api.drafts, WorkflowDraftApi)
    assert isinstance(api.artifacts, WorkflowArtifactApi)
    assert isinstance(api.deployments, WorkflowDeploymentApi)
    assert isinstance(api.runs, WorkflowRunApi)
    assert not hasattr(api, "backend")


def test_workflow_api_direct_capability_call() -> None:
    api = _api()

    result = asyncio.run(
        api.call_capability(
            qualified_name="demo.personal.echo_tool",
            payload={"text": "hello"},
        )
    )

    assert result["kind"] == "node_spec"
    assert result["outcome"] == "ok"
    assert result["output"] == {"echoed": "hello"}


def test_workflow_surface_handlers_is_compatibility_shim() -> None:
    from wf_api import WorkflowApi
    from wf_mcp.workflow_surface import WorkflowSurfaceHandlers

    root = local_temp_root() / "workflow_surface_handler_shim"
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=FileWorkflowArtifactStore(root),
    )

    handlers = WorkflowSurfaceHandlers(service)

    assert isinstance(handlers, WorkflowApi)
    assert handlers.service is service
    assert handlers.context.artifact_store is service.artifact_store
