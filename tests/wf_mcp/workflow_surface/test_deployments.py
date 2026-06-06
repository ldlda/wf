from __future__ import annotations

import asyncio
from typing import cast

import pytest

from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment
from wf_mcp.capabilities import DiscoveredTool
from wf_mcp.models import AuthRecord, ConnectionConfig
from wf_mcp.sdk import BackendAdapter

from ..test_support import echo_tool, local_temp_root
from .conftest import artifact, echo_artifact, handlers


class FailingLivenessAdapter:
    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        raise OSError("stdio process exited")


class RecordingLivenessAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def list_tools(
        self,
        connection: ConnectionConfig,
        auth: AuthRecord | None,
    ) -> list[DiscoveredTool]:
        self.calls += 1
        return []


def test_workflow_surface_validates_deployment_dependencies() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_validate")
    artifact_store.save_artifact(artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings=[
                {"logical_source": "context7", "concrete_source": "context7.personal"}
            ],
        )
    )
    h = handlers(artifact_store)

    payload = asyncio.run(
        h.validate_deployment(deployment_id="summarize_docs.personal")
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "source_missing"
    assert payload["next_actions"]["can_continue"] is True
    assert payload["next_actions"]["recommended_next_tool"] == (
        "wf.workflow.validate_deployment"
    )
    assert payload["next_actions"]["warnings"][0] == "source_missing: context7.personal"


def test_workflow_surface_validate_deployment_live_check_is_opt_in() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_live_opt_in"
    )
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    h = handlers(artifact_store)
    adapter = RecordingLivenessAdapter()
    h.service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    h.service.register_specs("demo.personal", echo_tool)
    h.service.register_adapter("demo", cast(BackendAdapter, adapter))

    payload = asyncio.run(h.validate_deployment(deployment_id="echo.personal"))

    assert payload["status"] == "runnable"
    assert payload["diagnostics"] == []
    assert adapter.calls == 0
    assert payload["next_actions"]["can_continue"] is True
    assert payload["next_actions"]["recommended_next_tool"] == (
        "wf.workflow.run_deployment"
    )


def test_workflow_surface_validate_deployment_live_check_reports_unreachable_source() -> (
    None
):
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_live_fail")
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    h = handlers(artifact_store)
    h.service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    h.service.register_specs("demo.personal", echo_tool)
    h.service.register_adapter(
        "demo",
        cast(BackendAdapter, FailingLivenessAdapter()),
    )

    payload = asyncio.run(
        h.validate_deployment(deployment_id="echo.personal", live_check=True)
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "source_unreachable"
    assert payload["diagnostics"][0]["bound_source"] == "demo.personal"
    assert "stdio process exited" in payload["diagnostics"][0]["message"]


def test_workflow_surface_validate_deployment_live_check_reports_missing_connection() -> (
    None
):
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_live_missing_connection"
    )
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    h = handlers(artifact_store)
    h.service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    h.service.register_specs("demo.personal", echo_tool)
    del h.service.connections.connections["demo.personal"]

    payload = asyncio.run(
        h.validate_deployment(deployment_id="echo.personal", live_check=True)
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "source_unreachable"
    assert payload["diagnostics"][0]["bound_source"] == "demo.personal"
    assert "demo.personal" in payload["diagnostics"][0]["message"]


def test_workflow_surface_records_artifact_and_deployment_save_events() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_events")
    h = handlers(artifact_store)

    artifact_payload = asyncio.run(
        h.save_artifact(echo_artifact().model_dump(mode="json"))
    )
    deployment_payload = asyncio.run(
        h.save_deployment(
            WorkflowDeployment(
                id="echo.personal",
                artifact_id="echo",
                artifact_version=1,
                bindings=[
                    {"logical_source": "demo", "concrete_source": "demo.personal"}
                ],
            ).model_dump(mode="json")
        )
    )

    events = h.service.list_events()
    assert artifact_payload["saved"] is True
    assert deployment_payload["saved"] is True
    assert [event.kind for event in events] == [
        "workflow_artifact_saved",
        "workflow_deployment_saved",
    ]
    assert events[0].capability_id == "workflow.echo.v1"
    assert events[1].capability_id == "deployment.echo.personal"


def test_workflow_surface_save_deployment_accepts_deployment_id_alias() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_alias")
    h = handlers(artifact_store)

    payload = asyncio.run(
        h.save_deployment(
            {
                "deployment_id": "echo.personal",
                "artifact_id": "echo",
                "artifact_version": 1,
                "bindings": [
                    {"logical_source": "demo", "concrete_source": "demo.personal"}
                ],
            }
        )
    )

    saved = artifact_store.get_deployment("echo.personal")
    assert payload["deployment_id"] == "echo.personal"
    assert saved.id == "echo.personal"


def test_workflow_surface_deletes_deployment() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_delete")
    h = handlers(artifact_store)
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )

    payload = asyncio.run(h.delete_deployment(deployment_id="echo.personal"))

    assert payload["deployment_id"] == "echo.personal"
    assert payload["deleted"] is True
    assert artifact_store.list_deployments() == []
    assert h.service.list_events()[-1].kind == "workflow_deployment_deleted"


def test_workflow_surface_save_deployment_rejects_id_and_deployment_id() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_alias_xor")
    h = handlers(artifact_store)

    with pytest.raises(ValueError, match="mutually exclusive"):
        asyncio.run(
            h.save_deployment(
                {
                    "id": "echo.personal",
                    "deployment_id": "echo.other",
                    "artifact_id": "echo",
                    "artifact_version": 1,
                    "bindings": [
                        {
                            "logical_source": "demo",
                            "concrete_source": "demo.personal",
                        }
                    ],
                }
            )
        )


def test_workflow_surface_lists_compact_deployment_summaries_and_inspects_detail() -> (
    None
):
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_deployment_list"
    )
    h = handlers(artifact_store)
    deployment = WorkflowDeployment(
        id="echo.personal",
        artifact_id="echo",
        artifact_version=1,
        bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
    )
    artifact_store.save_deployment(deployment)

    listed = asyncio.run(h.list_deployments())
    inspected = asyncio.run(h.inspect_deployment(deployment_id="echo.personal"))

    assert listed["deployments"][0]["id"] == "echo.personal"
    assert listed["deployments"][0]["binding_count"] == 1
    assert "bindings" not in listed["deployments"][0]
    assert inspected["bindings"][0]["logical_source"] == "demo"
    assert inspected["bindings"][0]["concrete_source"] == "demo.personal"
