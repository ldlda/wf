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


def test_openrpc_exposes_typed_capability_list_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.capabilities.list",
        component_name="ListCapabilitiesResult",
        properties={"capabilities", "next_cursor", "total"},
    )
    capabilities = openrpc_document["components"]["schemas"]["ListCapabilitiesResult"][
        "properties"
    ]["capabilities"]
    assert capabilities["items"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/NodeSpecCapabilitySummary"},
            {"$ref": "#/components/schemas/WrapperArtifactCapabilitySummary"},
        ]
    }


def test_openrpc_exposes_typed_capability_inspect_result(
    openrpc_document: dict[str, Any],
) -> None:
    method = _method_by_name(openrpc_document, "workflow.capabilities.inspect")

    assert method["result"]["schema"] == {
        "$ref": "#/components/schemas/InspectCapabilityResult"
    }
    schemas = openrpc_document["components"]["schemas"]
    assert schemas["InspectCapabilityResult"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/NodeSpecCapabilityDetail"},
            {"$ref": "#/components/schemas/WrapperArtifactCapabilityDetail"},
        ]
    }
    assert schemas["NodeSpecCapabilityDetail"]["properties"]["wrapper_hints"] == {
        "$ref": "#/components/schemas/WrapperAuthoringHintsPayload"
    }
    assert schemas["NodeSpecCapabilityDetail"]["properties"]["kind"]["const"] == (
        "node_spec"
    )
    assert (
        schemas["WrapperArtifactCapabilityDetail"]["properties"]["kind"]["const"]
        == "wrapper_artifact"
    )
    assert schemas["WrapperArtifactCapabilityDetail"]["properties"][
        "required_capabilities"
    ]["additionalProperties"] == {
        "$ref": "#/components/schemas/RequiredCapabilityPayload"
    }


def test_openrpc_exposes_typed_capability_call_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.capabilities.call",
        component_name="CapabilityCallResult",
        properties={
            "qualified_name",
            "source_id",
            "kind",
            "deployment_id",
            "outcome",
            "output",
            "diagnostics",
        },
    )


def test_openrpc_exposes_typed_source_list_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.sources.list",
        component_name="ListSourcesResult",
        properties={"sources", "next_cursor", "total"},
    )
    sources = openrpc_document["components"]["schemas"]["ListSourcesResult"][
        "properties"
    ]["sources"]
    assert sources["items"] == {"$ref": "#/components/schemas/SourceStatusPayload"}
    assert set(
        openrpc_document["components"]["schemas"]["ListSourcesResult"]["required"]
    ) == {"sources", "next_cursor", "total"}


def test_openrpc_exposes_typed_source_inspect_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.sources.inspect",
        component_name="InspectSourceResult",
        properties={"id", "kind", "capabilities"},
    )
    inspected = openrpc_document["components"]["schemas"]["InspectSourceResult"]
    assert inspected["properties"]["capabilities"] == {
        "$ref": "#/components/schemas/SourceCapabilityInventoryPayload"
    }
    assert inspected["properties"]["diagnostics"]["anyOf"][:2] == [
        {"$ref": "#/components/schemas/SourceDiagnosisResult"},
        {"$ref": "#/components/schemas/SourceDiagnosticsUnavailablePayload"},
    ]
    assert {"id", "kind", "capabilities"} <= set(inspected["required"])


def test_openrpc_exposes_typed_source_diagnosis_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.sources.diagnose",
        component_name="SourceDiagnosisResult",
        properties={"source_id", "status", "diagnostics"},
    )
    diagnosed = openrpc_document["components"]["schemas"]["SourceDiagnosisResult"]
    assert set(diagnosed["required"]) == {"source_id", "status", "diagnostics"}
    assert diagnosed["additionalProperties"] is True


def test_openrpc_exposes_typed_source_registry_read_results(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.admin.source_registry.list",
        component_name="ListRegistryEntriesResult",
        properties={"entries", "next_cursor", "total"},
    )
    _assert_result_component(
        openrpc_document,
        method_name="workflow.admin.source_registry.inspect",
        component_name="InspectRegistryEntryResult",
        properties={"entry", "shadowed_by_config", "config_ownership", "mutable"},
    )
    schemas = openrpc_document["components"]["schemas"]
    assert schemas["ListRegistryEntriesResult"]["properties"]["entries"]["items"] == {
        "$ref": "#/components/schemas/RegistryEntrySummaryPayload"
    }
    assert schemas["InspectRegistryEntryResult"]["properties"]["entry"] == {
        "$ref": "#/components/schemas/RegistryEntryPayload"
    }
    assert schemas["RegistryEntryPayload"]["additionalProperties"] is True
    assert set(schemas["ListRegistryEntriesResult"]["required"]) == {
        "entries",
        "next_cursor",
        "total",
    }
    assert set(schemas["RegistryEntrySummaryPayload"]["required"]) == {
        "id",
        "kind",
        "enabled",
        "provider",
        "account",
        "profile",
        "transport_kind",
        "auth_ref",
        "shadowed_by_config",
        "config_ownership",
        "mutable",
    }
    assert set(schemas["InspectRegistryEntryResult"]["required"]) == {
        "entry",
        "shadowed_by_config",
        "config_ownership",
        "mutable",
    }


@pytest.mark.parametrize(
    "method_name",
    [
        "workflow.admin.source_registry.add",
        "workflow.admin.source_registry.update",
        "workflow.admin.source_registry.enable",
        "workflow.admin.source_registry.disable",
    ],
)
def test_openrpc_exposes_typed_source_registry_mutation_result(
    openrpc_document: dict[str, Any],
    method_name: str,
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name=method_name,
        component_name="RegistryEntryMutationResult",
        properties={"entry", "shadowed_by_config"},
    )
    mutation = openrpc_document["components"]["schemas"]["RegistryEntryMutationResult"]
    assert set(mutation["required"]) == {"entry", "shadowed_by_config"}
    assert mutation["properties"]["entry"] == {
        "$ref": "#/components/schemas/RegistryEntryPayload"
    }


def test_openrpc_exposes_typed_source_registry_remove_and_apply_results(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.admin.source_registry.remove",
        component_name="RemoveRegistryEntryResult",
        properties={"removed", "source_id"},
    )
    _assert_result_component(
        openrpc_document,
        method_name="workflow.admin.source_registry.apply",
        component_name="ApplyRegistryChangesResult",
        properties={
            "applied",
            "registered",
            "updated",
            "removed",
            "connection_count",
            "registry_entry_count",
        },
    )
    schemas = openrpc_document["components"]["schemas"]
    assert set(schemas["RemoveRegistryEntryResult"]["required"]) == {
        "removed",
        "source_id",
    }
    assert set(schemas["ApplyRegistryChangesResult"]["required"]) == {
        "applied",
        "registered",
        "updated",
        "removed",
        "connection_count",
        "registry_entry_count",
    }
    assert schemas["ApplyRegistryChangesResult"]["properties"]["auth_diagnostics"][
        "items"
    ] == {"$ref": "#/components/schemas/DependencyDiagnosticPayload"}


def test_openrpc_exposes_typed_admin_inventory_results(
    openrpc_document: dict[str, Any],
) -> None:
    for method_name, component_name, collection_name, item_name in [
        (
            "workflow.admin.connections.list",
            "ListConnectionsResult",
            "connections",
            "ConnectionPayload",
        ),
        (
            "workflow.admin.connection_statuses.list",
            "ListConnectionStatusesResult",
            "statuses",
            "ConnectionStatusPayload",
        ),
        (
            "workflow.admin.events.list",
            "ListAdminEventsResult",
            "events",
            "AdminEventPayload",
        ),
        (
            "workflow.admin.auth.list",
            "ListAuthRecordsResult",
            "auth_records",
            "AuthRecordSummaryPayload",
        ),
    ]:
        _assert_result_component(
            openrpc_document,
            method_name=method_name,
            component_name=component_name,
            properties={collection_name, "total"},
        )
        schema = openrpc_document["components"]["schemas"][component_name]
        assert schema["properties"][collection_name]["items"] == {
            "$ref": f"#/components/schemas/{item_name}"
        }
        assert set(schema["required"]) == {collection_name, "total"}

    schemas = openrpc_document["components"]["schemas"]
    assert set(schemas["ConnectionPayload"]["required"]) == {
        "id",
        "server",
        "account",
        "enabled",
        "metadata",
    }
    assert set(schemas["ConnectionStatusPayload"]["required"]) == {
        "connection_id",
        "enabled",
    }
    assert set(schemas["AdminEventPayload"]["required"]) == {
        "kind",
        "timestamp_epoch_ms",
        "payload",
    }
    for component_name in [
        "ConnectionPayload",
        "ConnectionStatusPayload",
        "AdminEventPayload",
    ]:
        assert schemas[component_name]["additionalProperties"] is True


@pytest.mark.parametrize(
    "method_name",
    [
        "workflow.admin.auth.inspect",
        "workflow.admin.auth.save",
    ],
)
def test_openrpc_exposes_secret_safe_auth_record_results(
    openrpc_document: dict[str, Any],
    method_name: str,
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name=method_name,
        component_name="AuthRecordSummaryPayload",
        properties={"id", "scheme", "metadata", "payload_keys"},
    )
    schema = openrpc_document["components"]["schemas"]["AuthRecordSummaryPayload"]
    assert set(schema["required"]) == {
        "id",
        "scheme",
        "metadata",
        "payload_keys",
    }
    assert "payload" not in schema["properties"]
    assert schema["additionalProperties"] is False


def test_openrpc_exposes_typed_auth_delete_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.admin.auth.delete",
        component_name="DeleteAuthRecordResult",
        properties={"deleted", "id"},
    )
    schema = openrpc_document["components"]["schemas"]["DeleteAuthRecordResult"]
    assert set(schema["required"]) == {"deleted", "id"}


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


def test_openrpc_exposes_typed_stateless_draft_validation_result(
    openrpc_document: dict[str, Any],
) -> None:
    method = _method_by_name(openrpc_document, "workflow.drafts.validate")
    schemas = openrpc_document["components"]["schemas"]

    assert method["result"]["schema"] == {
        "$ref": "#/components/schemas/ValidateDraftResult"
    }
    assert schemas["ValidateDraftResult"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/ValidDraftResult"},
            {"$ref": "#/components/schemas/InvalidDraftResult"},
        ]
    }
    assert schemas["ValidDraftResult"]["required"] == [
        "status",
        "diagnostics",
        "compiled_plan",
    ]


def test_openrpc_exposes_typed_stateless_draft_patch_result(
    openrpc_document: dict[str, Any],
) -> None:
    method = _method_by_name(openrpc_document, "workflow.drafts.patch")
    schemas = openrpc_document["components"]["schemas"]

    assert method["result"]["schema"] == {
        "$ref": "#/components/schemas/PatchDraftResult"
    }
    assert schemas["PatchDraftResult"] == {
        "anyOf": [
            {"$ref": "#/components/schemas/PatchedDraftValidResult"},
            {"$ref": "#/components/schemas/PatchedDraftInvalidResult"},
        ]
    }
    assert "draft" in schemas["PatchedDraftValidResult"]["required"]
    assert "draft" not in schemas["PatchedDraftInvalidResult"]["required"]
    assert schemas["PatchedDraftValidResult"]["properties"]["draft"] == {
        "$ref": "#/components/schemas/JsonObject"
    }
    assert schemas["PatchedDraftInvalidResult"]["properties"]["draft"] == {
        "$ref": "#/components/schemas/JsonObject"
    }


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
