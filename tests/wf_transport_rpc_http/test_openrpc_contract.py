from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

import pytest

from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import create_rpc_app


def _method_by_name(document: dict[str, Any], name: str) -> dict[str, Any]:
    return next(method for method in document["methods"] if method["name"] == name)


def _assert_result_component(
    document: dict[str, Any],
    *,
    method_name: str,
    component_name: str,
    properties: Collection[str],
) -> None:
    method = _method_by_name(document, method_name)
    assert method["result"]["schema"] == {
        "$ref": f"#/components/schemas/{component_name}"
    }
    component = document["components"]["schemas"][component_name]
    assert properties <= component["properties"].keys()


@pytest.fixture
def openrpc_document(tmp_path: Path) -> dict[str, Any]:
    app = create_rpc_app(build_local_static_workflow_server(tmp_path / "store"))
    return app.get_openrpc()


def test_openrpc_exposes_typed_health_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.health",
        component_name="HealthResult",
        properties={"status", "store_root"},
    )


@pytest.mark.parametrize(
    ("method_name", "component_name", "properties"),
    [
        (
            "workflow.artifacts.create_from_plan",
            "SaveArtifactResult",
            {"artifact_id", "version", "saved"},
        ),
        (
            "workflow.artifacts.save",
            "SaveArtifactResult",
            {"artifact_id", "version", "saved"},
        ),
        (
            "workflow.artifacts.list",
            "ListArtifactsResult",
            {"nodes", "next_cursor", "total"},
        ),
        (
            "workflow.artifacts.inspect",
            "WorkflowArtifactPayload",
            {
                "id",
                "version",
                "title",
                "kind",
                "input_schema",
                "output_schema",
                "outcomes",
                "plan",
            },
        ),
        (
            "workflow.artifacts.delete",
            "DeleteArtifactResult",
            {"artifact_id", "version", "deleted", "blocked_by_deployments"},
        ),
    ],
)
def test_openrpc_exposes_typed_artifact_results(
    openrpc_document: dict[str, Any],
    method_name: str,
    component_name: str,
    properties: set[str],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name=method_name,
        component_name=component_name,
        properties=properties,
    )


@pytest.mark.parametrize(
    "method_name",
    [
        "workflow.draft_workspaces.get",
        "workflow.draft_workspaces.create_empty",
        "workflow.draft_workspaces.patch",
        "workflow.draft_workspaces.replace_document",
        "workflow.draft_workspaces.set_name",
        "workflow.draft_workspaces.set_start",
        "workflow.draft_workspaces.set_contract",
        "workflow.draft_workspaces.set_route",
        "workflow.draft_workspaces.set_step_input_map",
        "workflow.draft_workspaces.set_step_input_bindings",
        "workflow.draft_workspaces.update_capability_step",
        "workflow.draft_workspaces.set_step_output_bindings",
        "workflow.draft_workspaces.set_step_output_map",
        "workflow.draft_workspaces.set_workflow_output_map",
        "workflow.draft_workspaces.set_workflow_output_bindings",
        "workflow.draft_workspaces.bind",
        "workflow.draft_workspaces.add_step_from_capability",
        "workflow.draft_workspaces.add_step",
        "workflow.draft_workspaces.branch",
        "workflow.draft_workspaces.handle",
        "workflow.draft_workspaces.validate",
        "workflow.draft_workspaces.remove_route",
        "workflow.draft_workspaces.remove_step",
        "workflow.draft_workspaces.remove_binding",
    ],
)
def test_openrpc_exposes_typed_draft_workspace_results(
    openrpc_document: dict[str, Any],
    method_name: str,
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name=method_name,
        component_name="DraftWorkspaceResult",
        properties={
            "workspace_id",
            "revision",
            "title",
            "status",
            "diagnostics",
            "summary",
        },
    )


def test_openrpc_exposes_typed_draft_workspace_list_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.draft_workspaces.list",
        component_name="ListDraftWorkspacesResult",
        properties={"workspaces"},
    )


def test_openrpc_exposes_typed_delete_draft_workspace_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.draft_workspaces.delete",
        component_name="DeleteDraftWorkspaceResult",
        properties={"workspace_id", "deleted", "status"},
    )


def test_openrpc_pins_nested_draft_workspace_contract(
    openrpc_document: dict[str, Any],
) -> None:
    schemas = openrpc_document["components"]["schemas"]
    workspace = schemas["DraftWorkspaceResult"]
    diagnostic = schemas["DraftDiagnosticPayload"]
    listed = schemas["ListDraftWorkspacesResult"]
    deleted = schemas["DeleteDraftWorkspaceResult"]

    assert workspace["required"] == [
        "workspace_id",
        "revision",
        "title",
        "status",
        "diagnostics",
        "summary",
    ]
    assert "draft" not in workspace["required"]
    assert workspace["properties"]["status"]["enum"] == [
        "valid",
        "invalid",
        "conflict",
    ]
    assert workspace["properties"]["diagnostics"]["items"] == {
        "$ref": "#/components/schemas/DraftDiagnosticPayload"
    }
    assert diagnostic["required"] == ["code", "path", "message"]
    assert listed["properties"]["workspaces"]["items"] == {
        "$ref": "#/components/schemas/DraftWorkspaceResult"
    }
    assert deleted["properties"]["status"]["enum"] == ["deleted", "not_found"]


def test_openrpc_exposes_typed_compile_draft_workspace_result(
    openrpc_document: dict[str, Any],
) -> None:
    method = _method_by_name(
        openrpc_document,
        "workflow.draft_workspaces.compile",
    )

    assert method["result"]["schema"] == {
        "$ref": "#/components/schemas/CompileDraftWorkspaceResult"
    }
    assert openrpc_document["components"]["schemas"]["CompileDraftWorkspaceResult"] == {
        "anyOf": [
            {"$ref": ("#/components/schemas/CompileDraftWorkspaceSuccess")},
            {"$ref": "#/components/schemas/InvalidDraftResult"},
        ]
    }
    schemas = openrpc_document["components"]["schemas"]
    assert schemas["CompileDraftWorkspaceSuccess"]["required"] == [
        "compiled_plan",
        "required_capabilities",
    ]
    assert schemas["InvalidDraftResult"]["properties"]["status"]["const"] == "invalid"


def test_openrpc_exposes_typed_capability_bootstrap_result(
    openrpc_document: dict[str, Any],
) -> None:
    for method_name in (
        "workflow.drafts.create_from_capability",
        "workflow.draft_workspaces.create_from_capability",
    ):
        _assert_result_component(
            openrpc_document,
            method_name=method_name,
            component_name="CreateDraftWorkspaceFromCapabilityResult",
            properties={
                "workspace_id",
                "revision",
                "wrapper_hints",
                "next_actions",
            },
        )
    result = openrpc_document["components"]["schemas"][
        "CreateDraftWorkspaceFromCapabilityResult"
    ]
    assert result["properties"]["wrapper_hints"] == {
        "$ref": "#/components/schemas/WrapperAuthoringHintsPayload"
    }
    assert result["properties"]["next_actions"] == {
        "$ref": "#/components/schemas/NextActionsPayload"
    }


@pytest.mark.parametrize(
    "method_name",
    [
        "workflow.draft_workspaces.create_artifact",
        "workflow.draft_workspaces.create_wrapper",
    ],
)
def test_openrpc_exposes_typed_workspace_artifact_save_result(
    openrpc_document: dict[str, Any],
    method_name: str,
) -> None:
    method = _method_by_name(openrpc_document, method_name)

    assert method["result"]["schema"] == {
        "$ref": "#/components/schemas/CreateArtifactFromWorkspaceResult"
    }
    assert openrpc_document["components"]["schemas"][
        "CreateArtifactFromWorkspaceResult"
    ] == {
        "anyOf": [
            {"$ref": "#/components/schemas/SavedDraftArtifactResult"},
            {"$ref": "#/components/schemas/UnsavedDraftArtifactResult"},
        ]
    }
    schemas = openrpc_document["components"]["schemas"]
    assert schemas["SavedDraftArtifactResult"]["properties"]["saved"]["const"] is True
    assert {
        "required_logical_sources",
        "suggested_bindings",
    } <= schemas["SavedDraftArtifactResult"]["properties"].keys()
    assert (
        schemas["UnsavedDraftArtifactResult"]["properties"]["saved"]["const"] is False
    )


@pytest.mark.parametrize(
    ("method_name", "component_name", "properties"),
    [
        (
            "workflow.deployments.list",
            "ListDeploymentsResult",
            {"deployments"},
        ),
        (
            "workflow.deployments.inspect",
            "WorkflowDeploymentPayload",
            {"id", "artifact_id", "artifact_version", "bindings", "drift_policy"},
        ),
        (
            "workflow.deployments.save",
            "SaveDeploymentResult",
            {"deployment_id", "artifact_id", "artifact_version", "saved"},
        ),
        (
            "workflow.deployments.delete",
            "DeleteDeploymentResult",
            {"deployment_id", "deleted"},
        ),
        (
            "workflow.deployments.validate",
            "ValidateDeploymentResult",
            {
                "deployment_id",
                "artifact_id",
                "artifact_version",
                "status",
                "diagnostics",
                "next_actions",
            },
        ),
    ],
)
def test_openrpc_exposes_typed_deployment_results(
    openrpc_document: dict[str, Any],
    method_name: str,
    component_name: str,
    properties: set[str],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name=method_name,
        component_name=component_name,
        properties=properties,
    )


@pytest.mark.parametrize(
    ("method_name", "component_name", "properties"),
    [
        (
            "workflow.runs.list",
            "ListRunsResult",
            {"runs", "total", "cursor", "next_cursor", "limit"},
        ),
        (
            "workflow.runs.start",
            "RunResult",
            {
                "deployment_id",
                "run_id",
                "status",
                "interrupt",
                "output",
                "next_actions",
            },
        ),
        (
            "workflow.runs.inspect",
            "RunResult",
            {"run_id", "status", "resume_readiness", "trace_count"},
        ),
        (
            "workflow.runs.resume",
            "RunResult",
            {"run_id", "status", "resume_readiness", "trace_count"},
        ),
        (
            "workflow.runs.trace",
            "RunTraceResult",
            {
                "run_id",
                "trace",
                "trace_start",
                "trace_limit",
                "trace_truncated",
            },
        ),
    ],
)
def test_openrpc_exposes_typed_run_results(
    openrpc_document: dict[str, Any],
    method_name: str,
    component_name: str,
    properties: set[str],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name=method_name,
        component_name=component_name,
        properties=properties,
    )
