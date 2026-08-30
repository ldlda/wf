from __future__ import annotations

from typing import Any, cast

import pytest

from wf_artifacts import WorkflowArtifact as ArtifactModel
from wf_client import DeploymentRequired, WorkflowClientPort
from wf_client.errors import DeploymentNotRunnable
from wf_client.workflows import WorkflowArtifact
from wf_core import Workflow


def _artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "report",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "outcomes": ["ok"],
        "start": "end",
        "nodes": [{"id": "end", "type": "end", "outcome": "ok"}],
        "edges": [],
    }
    artifact = ArtifactModel(
        id="report",
        version=1,
        title="Report",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("ok",),
        plan=plan,
    )
    return WorkflowArtifact(
        cast(WorkflowClientPort, _FakePort()), artifact, Workflow.model_validate(plan)
    )


class _FakePort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.list_result: dict[str, Any] = {"deployments": []}
        self.validation_result: dict[str, Any] = {
            "deployment_id": "report.production",
            "artifact_id": "report",
            "artifact_version": 1,
            "status": "runnable",
            "diagnostics": [],
            "next_actions": {
                "can_continue": True,
                "can_save_now": None,
                "recommended_next_tool": None,
                "reason": "ready",
                "patch_examples": [],
                "warnings": [],
            },
        }
        self.run_result: dict[str, Any] = {
            "artifact_id": "report",
            "artifact_version": 1,
            "deployment_id": "report.production",
            "status": "completed",
            "run_id": "run-1",
            "resume_readiness": "not_applicable",
            "interrupt": None,
            "outcome": "ok",
            "error": None,
            "output": {"result": "done"},
            "trace_count": 0,
            "diagnostics": [],
            "next_actions": {
                "can_continue": False,
                "can_save_now": None,
                "recommended_next_tool": None,
                "reason": "done",
                "patch_examples": [],
                "warnings": [],
            },
        }

    async def save_deployment(self, deployment: dict[str, Any]) -> object:
        self.calls.append(("save_deployment", {"deployment": deployment}))
        return {"deployment_id": deployment["id"], "saved": True}

    async def inspect_deployment(self, *, deployment_id: str) -> object:
        self.calls.append(("inspect_deployment", {"deployment_id": deployment_id}))
        return {
            "id": deployment_id,
            "artifact_id": "report",
            "artifact_version": 1,
            "bindings": [
                {
                    "logical_source": "app.default",
                    "concrete_source": "company.production",
                }
            ],
            "drift_policy": "block",
        }

    async def validate_deployment(self, **params: Any) -> object:
        self.calls.append(("validate_deployment", params))
        return self.validation_result

    async def list_deployments(self) -> object:
        self.calls.append(("list_deployments", {}))
        return self.list_result

    async def run_deployment(self, **params: Any) -> object:
        self.calls.append(("run_deployment", params))
        return self.run_result


@pytest.mark.asyncio
async def test_artifact_deploys_with_explicit_bindings() -> None:
    artifact = _artifact()
    port = cast(_FakePort, artifact._port)
    deployment = await artifact.deploy(
        "report.production", bindings={"app.default": "company.production"}
    )
    assert deployment.deployment_id == "report.production"
    assert deployment.bindings == {"app.default": "company.production"}
    assert deployment.runnable is True
    assert [call[0] for call in port.calls[-3:]] == [
        "save_deployment",
        "inspect_deployment",
        "validate_deployment",
    ]


@pytest.mark.asyncio
async def test_artifact_run_rejects_ambiguous_deployments() -> None:
    artifact = _artifact()
    port = cast(_FakePort, artifact._port)
    port.list_result = {
        "deployments": [
            {
                "id": "report.prod",
                "artifact_id": "report",
                "artifact_version": 1,
                "binding_count": 0,
                "drift_policy": "block",
            },
            {
                "id": "report.dev",
                "artifact_id": "report",
                "artifact_version": 1,
                "binding_count": 0,
                "drift_policy": "block",
            },
        ]
    }
    with pytest.raises(DeploymentRequired) as captured:
        await artifact.run({"topic": "workflow"})
    assert captured.value.candidate_deployment_ids == ("report.dev", "report.prod")
    assert not any(call[0] == "run_deployment" for call in port.calls)


@pytest.mark.asyncio
async def test_deployment_run_rejects_missing_run_id() -> None:
    artifact = _artifact()
    deployment = await artifact.deploy("report.production")
    cast(_FakePort, deployment._port).run_result["run_id"] = None
    with pytest.raises((DeploymentNotRunnable, AttributeError)):
        await deployment.run({})
