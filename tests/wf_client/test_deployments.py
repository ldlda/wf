from __future__ import annotations

from typing import Any, cast

import pytest

from wf_artifacts import WorkflowArtifact as ArtifactModel
from wf_client import DeploymentRequired
from wf_client.errors import DeploymentNotRunnable, InvalidResponse
from wf_client.protocols import WorkflowClientPort
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
        self.inspect_artifact_id = "report"
        self.inspect_artifact_version = 1
        self.inspect_deployment_id: str | None = None
        self.save_result: dict[str, Any] = {
            "deployment_id": "report.production",
            "artifact_id": "report",
            "artifact_version": 1,
            "saved": True,
        }
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
        return self.save_result

    async def inspect_deployment(self, *, deployment_id: str) -> object:
        self.calls.append(("inspect_deployment", {"deployment_id": deployment_id}))
        return {
            "id": self.inspect_deployment_id or deployment_id,
            "artifact_id": self.inspect_artifact_id,
            "artifact_version": self.inspect_artifact_version,
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
    with pytest.raises(DeploymentNotRunnable) as captured:
        await deployment.run({})
    assert captured.value.error is None


@pytest.mark.asyncio
async def test_explicit_artifact_run_rejects_deployment_for_another_artifact() -> None:
    artifact = _artifact()
    port = cast(_FakePort, artifact._port)
    port.inspect_artifact_id = "other"
    with pytest.raises(InvalidResponse, match="does not target artifact"):
        await artifact.run({}, deployment_id="report.production")
    assert not any(call[0] == "run_deployment" for call in port.calls)


@pytest.mark.asyncio
async def test_artifact_deploy_rejects_wrong_created_deployment_id() -> None:
    artifact = _artifact()
    port = cast(_FakePort, artifact._port)
    port.save_result["deployment_id"] = "other.deployment"
    with pytest.raises(InvalidResponse, match="save"):
        await artifact.deploy("report.production")


@pytest.mark.asyncio
async def test_artifact_deploy_rejects_wrong_created_artifact_identity() -> None:
    artifact = _artifact()
    port = cast(_FakePort, artifact._port)
    port.save_result["artifact_version"] = 2

    with pytest.raises(InvalidResponse, match="workflow.deployments.save"):
        await artifact.deploy("report.production")


@pytest.mark.asyncio
async def test_artifact_deploy_rejects_wrong_inspected_deployment_id() -> None:
    artifact = _artifact()
    port = cast(_FakePort, artifact._port)
    port.inspect_deployment_id = "other.deployment"
    with pytest.raises(InvalidResponse, match="inspect"):
        await artifact.deploy("report.production")


@pytest.mark.asyncio
async def test_discovered_deployment_rechecks_inspected_artifact_identity() -> None:
    artifact = _artifact()
    port = cast(_FakePort, artifact._port)
    port.list_result = {
        "deployments": [
            {
                "id": "report.production",
                "artifact_id": "report",
                "artifact_version": 1,
                "binding_count": 0,
                "drift_policy": "block",
            }
        ]
    }
    port.inspect_artifact_id = "other"
    with pytest.raises(InvalidResponse, match="does not target artifact"):
        await artifact.run({})


@pytest.mark.asyncio
async def test_deployment_validation_rejects_identity_mismatch() -> None:
    artifact = _artifact()
    deployment = await artifact.deploy("report.production")
    port = cast(_FakePort, deployment._port)
    port.validation_result["artifact_version"] = 2
    with pytest.raises(InvalidResponse, match="workflow.deployments.validate"):
        await deployment.validate()


@pytest.mark.asyncio
async def test_deployment_run_rejects_mismatched_start_deployment() -> None:
    artifact = _artifact()
    deployment = await artifact.deploy("report.production")
    port = cast(_FakePort, deployment._port)
    port.run_result["deployment_id"] = "other.deployment"
    with pytest.raises(InvalidResponse, match="workflow.runs.start"):
        await deployment.run({})


@pytest.mark.asyncio
async def test_deployment_run_rejects_mismatched_start_artifact() -> None:
    artifact = _artifact()
    deployment = await artifact.deploy("report.production")
    port = cast(_FakePort, deployment._port)
    port.run_result["artifact_id"] = "other"
    with pytest.raises(InvalidResponse, match="workflow.runs.start"):
        await deployment.run({})


@pytest.mark.asyncio
async def test_start_malformed_interrupt_reports_start_operation() -> None:
    artifact = _artifact()
    deployment = await artifact.deploy("report.production")
    port = cast(_FakePort, deployment._port)
    port.run_result["interrupt"] = {
        "id": "interrupt-1",
        "frame_id": "root",
        "node_id": "approve",
        "kind": "approval",
        "payload": {},
        "resumable": True,
        "route": {
            "frame_id": "child",
            "node_id": "approve",
            "scope_id": "scope",
            "lineage_id": "lineage",
            "parent_frame_id": "root",
            "workflow_ref": {
                "name": "local",
                "artifact_id": "invalid",
                "version": 1,
            },
        },
        "outcomes": ["submitted"],
        "request_schema": {"type": "object"},
        "resume_schema": {"type": "object"},
        "typed": False,
    }
    with pytest.raises(InvalidResponse, match="workflow.runs.start"):
        await deployment.run({})


@pytest.mark.asyncio
async def test_deployment_run_preserves_server_error_and_diagnostics() -> None:
    artifact = _artifact()
    deployment = await artifact.deploy("report.production")
    port = cast(_FakePort, deployment._port)
    port.run_result.update(
        run_id=None,
        outcome="rejected",
        error="dependency check failed",
        diagnostics=[
            {
                "severity": "error",
                "code": "missing_source",
                "logical_ref": "app.default",
                "bound_source": None,
                "message": "missing source",
                "repair_hint": "bind a source",
            }
        ],
    )
    with pytest.raises(DeploymentNotRunnable) as captured:
        await deployment.run({})
    assert captured.value.error == "dependency check failed"
    assert captured.value.outcome == "rejected"
    assert captured.value.diagnostics[0].code == "missing_source"


@pytest.mark.asyncio
async def test_artifact_snapshot_defensively_copies_nested_models() -> None:
    artifact = _artifact()

    exposed_artifact = artifact.artifact
    exposed_workflow = artifact.workflow
    exposed_artifact.id = "mutated"
    exposed_artifact.plan["name"] = "mutated"
    exposed_workflow.name = "mutated"

    assert artifact.ref.artifact_id == "report"
    assert artifact.inspect().name == "report"
    assert artifact.edit().name == "report"


@pytest.mark.asyncio
async def test_deployment_snapshot_defensively_copies_model_and_diagnostics() -> None:
    artifact = _artifact()
    port = cast(_FakePort, artifact._port)
    port.validation_result["diagnostics"] = [
        {
            "severity": "warning",
            "code": "drift",
            "logical_ref": "app.default",
            "bound_source": "company.production",
            "message": "original",
            "repair_hint": None,
        }
    ]
    deployment = await artifact.deploy("report.production")

    exposed_model = deployment.model
    exposed_diagnostics = deployment.diagnostics
    exposed_model.id = "mutated"
    exposed_model.bindings = []
    exposed_diagnostics[0].message = "mutated"

    assert deployment.deployment_id == "report.production"
    assert deployment.bindings == {"app.default": "company.production"}
    assert deployment.diagnostics[0].message == "original"
    await deployment.run({})
    assert port.calls[-1][1]["deployment_id"] == "report.production"
