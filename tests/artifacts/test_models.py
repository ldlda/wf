from __future__ import annotations

from wf_artifacts import (
    DependencyDiagnostic,
    DiagnosticSeverity,
    DriftPolicy,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
)


def test_workflow_artifact_serializes_required_capability_contract() -> None:
    capability = RequiredCapability(
        logical_source="context7",
        capability_name="query-docs",
        kind="tool",
        input_schema_hash="sha256:input",
        input_schema_snapshot={"type": "object", "properties": {}},
        output_schema_hash="sha256:output",
        output_schema_snapshot={"type": "object", "properties": {}},
        observed_concrete_source="context7.default",
        observed_at_epoch_ms=123,
    )
    artifact = WorkflowArtifact(
        id="summarize_docs",
        version=1,
        title="Summarize Docs",
        description="Summarize retrieved documentation.",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("done", "failed"),
        plan={"name": "summarize_docs", "nodes": [], "edges": []},
        required_capabilities={"context7.query-docs": capability},
        created_from_catalog_version="catalog-1",
    )

    dumped = artifact.model_dump(mode="json")

    assert dumped["id"] == "summarize_docs"
    assert dumped["kind"] == "workflow"
    assert dumped["version"] == 1
    assert dumped["outcomes"] == ["done", "failed"]
    required = dumped["required_capabilities"]["context7.query-docs"]
    assert required["logical_source"] == "context7"
    assert required["input_schema_hash"] == "sha256:input"


def test_workflow_artifact_can_be_marked_as_wrapper_intent() -> None:
    artifact = WorkflowArtifact(
        id="normalize_status",
        version=1,
        title="Normalize Status",
        kind="wrapper",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("done", "needs_input"),
        plan={"name": "normalize_status", "nodes": [], "edges": []},
    )

    dumped = artifact.model_dump(mode="json")

    assert dumped["kind"] == "wrapper"


def test_workflow_deployment_binds_logical_sources_to_concrete_sources() -> None:
    deployment = WorkflowDeployment(
        id="summarize_docs.personal",
        artifact_id="summarize_docs",
        artifact_version=1,
        bindings={"context7": "context7.personal"},
        drift_policy=DriftPolicy.BLOCK,
    )

    dumped = deployment.model_dump(mode="json")

    assert dumped["id"] == "summarize_docs.personal"
    assert dumped["artifact_id"] == "summarize_docs"
    assert dumped["artifact_version"] == 1
    assert dumped["bindings"]["context7"] == "context7.personal"
    assert dumped["drift_policy"] == "block"


def test_dependency_diagnostic_is_structured() -> None:
    diagnostic = DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="capability_missing",
        logical_ref="context7.query-docs",
        bound_source="context7.default",
        message="Bound source no longer exposes query-docs.",
        repair_hint="Refresh catalog or bind context7 to another compatible source.",
    )

    dumped = diagnostic.model_dump(mode="json")

    assert dumped["severity"] == "error"
    assert dumped["code"] == "capability_missing"
    assert dumped["logical_ref"] == "context7.query-docs"
    assert dumped["bound_source"] == "context7.default"
    assert dumped["repair_hint"].startswith("Refresh catalog")
