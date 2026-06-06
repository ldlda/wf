from __future__ import annotations

from pathlib import Path

import pytest

from tests.wf_mcp.workflow_surface.conftest import echo_artifact
from wf_api.artifact_plans import plan_field, plan_nodes, raw_plan_from_artifact
from wf_api.artifact_refs import artifact_capability_id
from wf_api.capability_requirements import (
    observed_node_specs,
    required_capability_payloads,
)


def test_artifact_capability_id_uses_workflow_ref_shape() -> None:
    artifact = echo_artifact()
    assert artifact_capability_id(artifact) == (
        f"workflow.{artifact.id}.v{artifact.version}"
    )


def test_raw_plan_from_artifact_preserves_required_plan_fields() -> None:
    artifact = echo_artifact()
    plan = raw_plan_from_artifact(artifact)

    assert plan.name == artifact.plan["name"]
    assert plan.start == artifact.plan["start"]
    assert len(plan.nodes) == len(artifact.plan["nodes"])


def test_plan_field_reports_missing_field() -> None:
    artifact = echo_artifact()
    broken = artifact.model_copy(
        update={
            "plan": {
                key: value for key, value in artifact.plan.items() if key != "start"
            }
        }
    )

    with pytest.raises(ValueError, match="missing plan field 'start'"):
        plan_field(broken, "start")


def test_plan_nodes_returns_only_dict_nodes() -> None:
    artifact = echo_artifact()
    modified = artifact.model_copy(
        update={"plan": {**artifact.plan, "nodes": [{"id": "a"}, "bad"]}}
    )

    assert plan_nodes(modified) == [{"id": "a"}]


def test_required_capability_payloads_sorts_by_name() -> None:
    artifact = echo_artifact()
    required_capabilities = artifact.required_capability_map()

    payload = required_capability_payloads(required_capabilities)

    assert list(payload) == sorted(required_capabilities)
    first = next(iter(payload.values()))
    assert "ref" in first
    assert "kind" in first


def test_observed_node_specs_projects_enabled_context_specs(tmp_path: Path) -> None:
    from tests.wf_mcp.test_support import echo_tool
    from wf_artifacts import FileWorkflowArtifactStore
    from wf_mcp.broker import WfMcpService
    from wf_mcp.broker.service.workflow_operation_context import context_from_service
    from wf_mcp.models import ConnectionConfig
    from wf_mcp.storage import FileStore

    artifact_store = FileWorkflowArtifactStore(tmp_path / "cap_req_helpers")
    service = WfMcpService(
        store=FileStore(artifact_store.root / "mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    context = context_from_service(service)

    observed = observed_node_specs(context)

    assert isinstance(observed, dict)
    assert all(hasattr(detail, "name") for detail in observed.values())
