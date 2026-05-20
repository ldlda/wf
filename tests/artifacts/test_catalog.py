from __future__ import annotations

from wf_artifacts import (
    DependencyDiagnostic,
    DiagnosticSeverity,
    RequiredCapability,
    WorkflowArtifact,
    artifact_catalog_entry,
    artifact_node_name,
)


def artifact() -> WorkflowArtifact:
    return WorkflowArtifact(
        id="summarize_docs",
        version=2,
        title="Summarize Docs",
        description="Summarize retrieved documentation.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={
            "type": "object",
            "properties": {"summary": {"type": "string"}},
        },
        outcomes=("done", "failed"),
        plan={"name": "summarize_docs", "nodes": [{"id": "hidden"}]},
        required_capabilities=[
            RequiredCapability(
                ref="context7.query-docs",
                kind="tool",
            )
        ],
    )


def test_artifact_node_name_is_stable_and_versioned() -> None:
    name = artifact_node_name(artifact())

    assert name == "workflow.summarize_docs.v2"


def test_artifact_catalog_entry_is_nodespec_shaped_without_internal_plan() -> None:
    entry = artifact_catalog_entry(artifact())
    dumped = entry.model_dump(mode="json")

    assert dumped["name"] == "workflow.summarize_docs.v2"
    assert dumped["display_name"] == "Summarize Docs"
    assert dumped["description"] == "Summarize retrieved documentation."
    assert dumped["outcomes"] == ["done", "failed"]
    assert dumped["input_schema"]["properties"]["query"]["type"] == "string"
    assert dumped["output_schema"]["properties"]["summary"]["type"] == "string"
    assert dumped["required_sources"] == ["context7"]
    assert "plan" not in dumped


def test_artifact_catalog_entry_includes_dependency_diagnostics() -> None:
    diagnostic = DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="source_missing",
        logical_ref="context7.query-docs",
        bound_source="context7.personal",
        message="Bound source is unavailable.",
    )

    entry = artifact_catalog_entry(artifact(), diagnostics=[diagnostic])
    dumped = entry.model_dump(mode="json")

    assert len(dumped["diagnostics"]) == 1
    assert dumped["diagnostics"][0]["code"] == "source_missing"
    assert dumped["diagnostics"][0]["logical_ref"] == "context7.query-docs"
