from __future__ import annotations

from wf_api import WorkflowApi
from wf_mcp.broker.service import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.storage import FileStore
from wf_transport_rpc_http import RpcWorkflowApiClient


def test_workflow_api_satisfies_surface_protocol(tmp_path) -> None:
    from wf_api.surface import WorkflowApiSurface

    service = WfMcpService(store=FileStore(tmp_path / "mcp"))
    api: WorkflowApiSurface = WorkflowApi(context_from_service(service))

    assert api is not None


def test_rpc_workflow_client_satisfies_surface_protocol() -> None:
    from wf_api.surface import WorkflowApiSurface

    api: WorkflowApiSurface = RpcWorkflowApiClient("http://example.test/rpc")

    assert api is not None
