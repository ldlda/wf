"""Run step budget creation and inspection tests (Task 4).

Pins the API surface for persisted step budgets: optional ``max_steps`` on
run creation only, effective ``max_steps``/``steps_executed``/
``steps_remaining`` on every run result, counter preservation across resume,
and no replacement budget on resume.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from tests.wf_mcp.test_support import echo_tool
from tests.wf_mcp.workflow_surface.conftest import echo_artifact
from wf_api.runs import WorkflowRunApi
from wf_artifacts import (
    FileRunStore,
    FileWorkflowArtifactStore,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore


def _echo_service(root: Path) -> WfMcpService:
    artifact_store = FileWorkflowArtifactStore(root)
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=artifact_store,
        run_store=FileRunStore(root / "mcp"),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    return service


def _unrunnable_service(root: Path) -> WfMcpService:
    artifact_store = FileWorkflowArtifactStore(root)
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.unbound",
            artifact_id="echo",
            artifact_version=1,
            bindings=[],
        )
    )
    return WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=artifact_store,
        run_store=FileRunStore(root / "mcp"),
    )


def _interrupt_artifact() -> WorkflowArtifact:
    return WorkflowArtifact(
        id="approval",
        version=1,
        title="Approval",
        input_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        output_schema={"type": "object", "properties": {}},
        outcomes=("submitted",),
        plan={
            "name": "approval",
            "input_schema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            "state_schema": {"fields": {}},
            "output_schema": {"type": "object", "properties": {}},
            "outcomes": ["submitted"],
            "start": "approval",
            "nodes": [
                {
                    "id": "approval",
                    "type": "interrupt",
                    "kind": "approval",
                    "request": [
                        {
                            "path": {"root": "input", "parts": ["message"]},
                            "target": {"root": "local", "parts": ["message"]},
                        }
                    ],
                    "resume": [],
                    "outcomes": ["submitted"],
                    "resume_schema": {
                        "type": "object",
                        "properties": {"approved": {"type": "boolean"}},
                        "required": ["approved"],
                        "additionalProperties": False,
                    },
                },
                {"id": "end_submitted", "type": "end", "outcome": "submitted"},
            ],
            "edges": [
                {"from": "approval", "outcome": "submitted", "to": "end_submitted"}
            ],
        },
    )


def _interrupt_service(root: Path) -> WfMcpService:
    artifact_store = FileWorkflowArtifactStore(root)
    artifact_store.save_artifact(_interrupt_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="approval.default",
            artifact_id="approval",
            artifact_version=1,
            bindings=[],
        )
    )
    return WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=artifact_store,
        run_store=FileRunStore(root / "mcp"),
    )


async def test_run_deployment_reports_default_budget(tmp_path: Path) -> None:
    api = WorkflowRunApi(context_from_service(_echo_service(tmp_path / "default")))

    result = await api.run_deployment(
        deployment_id="echo.personal",
        workflow_input={"text": "hello"},
    )

    assert result["status"] == "completed"
    assert result["max_steps"] == 10_000
    assert result["steps_executed"] == 1
    assert result["steps_remaining"] == 10_000 - result["steps_executed"]


async def test_run_deployment_accepts_requested_max_steps(tmp_path: Path) -> None:
    api = WorkflowRunApi(context_from_service(_echo_service(tmp_path / "requested")))

    result = await api.run_deployment(
        deployment_id="echo.personal",
        workflow_input={"text": "hello"},
        max_steps=5,
    )

    assert result["status"] == "completed"
    assert result["max_steps"] == 5
    assert result["steps_executed"] == 1
    assert result["steps_remaining"] == 4


async def test_run_deployment_rejects_non_positive_max_steps(tmp_path: Path) -> None:
    api = WorkflowRunApi(context_from_service(_echo_service(tmp_path / "invalid")))

    with pytest.raises(ValueError, match="positive"):
        await api.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
            max_steps=0,
        )


async def test_invalid_budget_wins_over_unrunnable_deployment(tmp_path: Path) -> None:
    api = WorkflowRunApi(
        context_from_service(_unrunnable_service(tmp_path / "invalid_unrunnable"))
    )

    with pytest.raises(ValueError, match="positive"):
        await api.run_deployment(
            deployment_id="echo.unbound",
            workflow_input={"text": "hello"},
            max_steps=0,
        )


async def test_unrunnable_deployment_reports_requested_budget(tmp_path: Path) -> None:
    api = WorkflowRunApi(
        context_from_service(_unrunnable_service(tmp_path / "requested_unrunnable"))
    )

    result = await api.run_deployment(
        deployment_id="echo.unbound",
        workflow_input={"text": "hello"},
        max_steps=7,
    )

    assert result["status"] == "unrunnable"
    assert result["max_steps"] == 7
    assert result["steps_executed"] == 0
    assert result["steps_remaining"] == 7


async def test_inspect_run_reports_effective_budget(tmp_path: Path) -> None:
    api = WorkflowRunApi(context_from_service(_echo_service(tmp_path / "inspect")))
    started = await api.run_deployment(
        deployment_id="echo.personal",
        workflow_input={"text": "hello"},
        max_steps=7,
    )
    run_id = started["run_id"]
    assert isinstance(run_id, str)

    summary = await api.inspect_run(run_id=run_id)

    assert summary["max_steps"] == 7
    assert summary["steps_executed"] == started["steps_executed"]
    assert summary["steps_remaining"] == 7 - started["steps_executed"]


async def test_interrupted_resume_preserves_budget_counter(tmp_path: Path) -> None:
    api = WorkflowRunApi(context_from_service(_interrupt_service(tmp_path / "resume")))
    started = await api.run_deployment(
        deployment_id="approval.default",
        workflow_input={"message": "approve?"},
        max_steps=9,
    )
    run_id = started["run_id"]
    assert isinstance(run_id, str)

    assert started["status"] == "interrupted"
    assert started["max_steps"] == 9
    assert started["steps_executed"] == 1
    assert started["steps_remaining"] == 8

    resumed = await api.resume_run(
        run_id=run_id,
        resume_payload={"approved": True},
        resume_outcome="submitted",
    )

    assert resumed["status"] == "completed"
    assert resumed["max_steps"] == 9
    assert resumed["steps_executed"] == started["steps_executed"] + 1
    assert resumed["steps_remaining"] == 9 - resumed["steps_executed"]


async def test_resume_run_accepts_no_replacement_limit(tmp_path: Path) -> None:
    api = WorkflowRunApi(context_from_service(_echo_service(tmp_path / "resume_sig")))
    parameters = inspect.signature(WorkflowRunApi.resume_run).parameters

    assert "max_steps" not in parameters
    assert "limits" not in parameters

    extra: dict[str, Any] = {"max_steps": 5}
    with pytest.raises(TypeError):
        await api.resume_run(
            run_id="missing",
            resume_payload={},
            **extra,
        )
