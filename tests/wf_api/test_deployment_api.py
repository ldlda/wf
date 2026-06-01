"""Tests for wf_api.deployments module."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any, cast

from wf_artifacts import (
    FileWorkflowArtifactStore,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_api.deployments import WorkflowDeploymentApi
from wf_mcp.broker import WfMcpService
from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.capabilities import DiscoveredTool
from wf_mcp.sdk import BackendAdapter
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers
from wf_mcp.broker.service.workflow_operation_context import context_from_service

from tests.wf_mcp.test_support import echo_tool, local_temp_root


def _echo_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "echo",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": {
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        "start": "echo",
        "nodes": [
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
                "input": [
                    {
                        "path": {"root": "input", "parts": ["text"]},
                        "target": {"root": "local", "parts": ["text"]},
                    }
                ],
                "output": [
                    {
                        "source": {"root": "local", "parts": ["echoed"]},
                        "target": {"root": "state", "parts": ["echoed"]},
                    }
                ],
            }
        ],
        "edges": [{"from": "echo", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="echo",
        version=1,
        title="Echo",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities={
            "demo.echo_tool": RequiredCapability(
                ref="demo.echo_tool",
                kind="node_spec",
            )
        },
    )


def _deployment_api(
    artifact_store: FileWorkflowArtifactStore,
    *,
    register_echo: bool = False,
) -> tuple[WorkflowDeploymentApi, WfMcpService]:
    service = WfMcpService(
        store=FileStore(artifact_store.root / "deployments_mcp" / str(id(artifact_store))),
        artifact_store=artifact_store,
    )
    if register_echo:
        service.register_connection(
            ConnectionConfig(id="demo.personal", server="demo", account="personal")
        )
        service.register_specs("demo.personal", echo_tool)
    context = context_from_service(service)
    return WorkflowDeploymentApi(context), service


def test_save_deployment_stores_and_returns_stable_fields() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "deploy_save")
    api, _service = _deployment_api(artifact_store)

    result = asyncio.run(
        api.save_deployment(
            WorkflowDeployment(
                id="echo.personal",
                artifact_id="echo",
                artifact_version=1,
                bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
            ).model_dump(mode="json")
        )
    )

    assert result["saved"] is True
    assert result["deployment_id"] == "echo.personal"
    assert result["artifact_id"] == "echo"
    assert result["artifact_version"] == 1


def test_list_deployments_returns_compact_summaries() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "deploy_list")
    api, _service = _deployment_api(artifact_store)
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )

    result = asyncio.run(api.list_deployments())

    assert len(result["deployments"]) == 1
    assert result["deployments"][0]["id"] == "echo.personal"
    assert result["deployments"][0]["binding_count"] == 1
    assert "bindings" not in result["deployments"][0]


def test_list_deployments_returns_empty_without_artifact_store() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "deploy_no_store")
    _api, service = _deployment_api(artifact_store)
    context = replace(context_from_service(service), artifact_store=None)
    api = WorkflowDeploymentApi(context)

    result = asyncio.run(api.list_deployments())

    assert result["deployments"] == []


def test_delete_deployment_removes_one() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "deploy_delete")
    api, _service = _deployment_api(artifact_store)
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )

    result = asyncio.run(api.delete_deployment(deployment_id="echo.personal"))

    assert result["deployment_id"] == "echo.personal"
    assert result["deleted"] is True
    assert artifact_store.list_deployments() == []


def test_validate_deployment_returns_runnable_for_valid_binding() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "deploy_validate_runnable"
    )
    api, service = _deployment_api(artifact_store, register_echo=True)
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )

    result = asyncio.run(
        api.validate_deployment(deployment_id="echo.personal", live_check=False)
    )

    assert result["status"] == "runnable"
    assert result["diagnostics"] == []


class FailingLivenessAdapter:
    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        raise OSError("stdio process exited")


def test_validate_deployment_live_check_calls_live_checker() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "deploy_validate_live"
    )
    api, service = _deployment_api(artifact_store, register_echo=True)
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service.register_adapter(
        "demo",
        cast(BackendAdapter, FailingLivenessAdapter()),
    )

    result = asyncio.run(
        api.validate_deployment(deployment_id="echo.personal", live_check=True)
    )

    assert result["status"] == "unrunnable"
    assert result["diagnostics"][0]["code"] == "source_unreachable"


def test_handler_delegation_for_validate_deployment() -> None:
    """WorkflowSurfaceHandlers.validate_deployment delegates to WorkflowDeploymentApi."""
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "deploy_delegation"
    )
    service = WfMcpService(
        store=FileStore(artifact_store.root / "delegation_mcp"),
        artifact_store=artifact_store,
    )
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )

    h = WorkflowSurfaceHandlers(service)
    context = context_from_service(service)
    api = WorkflowDeploymentApi(context)

    handler_result = asyncio.run(
        h.validate_deployment(deployment_id="echo.personal")
    )
    api_result = asyncio.run(
        api.validate_deployment(deployment_id="echo.personal")
    )

    assert handler_result["status"] == api_result["status"]
    assert len(handler_result["diagnostics"]) == len(api_result["diagnostics"])
    if handler_result["diagnostics"]:
        assert (
            handler_result["diagnostics"][0]["code"]
            == api_result["diagnostics"][0]["code"]
        )
