from __future__ import annotations

from wf_artifacts import (
    AvailableCapability,
    AvailableSource,
    DriftPolicy,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
    validate_deployment_dependencies,
)


def required_capability(
    *,
    logical_source: str = "context7",
    capability_name: str = "query-docs",
    input_hash: str = "sha256:input",
    output_hash: str = "sha256:output",
) -> RequiredCapability:
    return RequiredCapability(
        logical_source=logical_source,
        capability_name=capability_name,
        kind="tool",
        input_schema_hash=input_hash,
        input_schema_snapshot={"type": "object", "properties": {}},
        output_schema_hash=output_hash,
        output_schema_snapshot={"type": "object", "properties": {}},
    )


def artifact_with(capability: RequiredCapability) -> WorkflowArtifact:
    return WorkflowArtifact(
        id="summarize_docs",
        version=1,
        title="Summarize Docs",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("done",),
        plan={"name": "summarize_docs", "nodes": [], "edges": []},
        required_capabilities={
            f"{capability.logical_source}.{capability.capability_name}": capability
        },
    )


def deployment(
    *,
    bindings: dict[str, str] | None = None,
    drift_policy: DriftPolicy = DriftPolicy.BLOCK,
) -> WorkflowDeployment:
    return WorkflowDeployment(
        id="summarize_docs.personal",
        artifact_id="summarize_docs",
        artifact_version=1,
        bindings={"context7": "context7.personal"} if bindings is None else bindings,
        drift_policy=drift_policy,
    )


def source(
    *,
    id: str = "context7.personal",
    enabled: bool = True,
    capability_name: str = "query-docs",
    input_hash: str = "sha256:input",
    output_hash: str = "sha256:output",
) -> AvailableSource:
    return AvailableSource(
        id=id,
        enabled=enabled,
        capabilities={
            capability_name: AvailableCapability(
                name=capability_name,
                kind="tool",
                input_schema_hash=input_hash,
                output_schema_hash=output_hash,
            )
        },
    )


def test_validate_deployment_accepts_matching_bound_capability() -> None:
    diagnostics = validate_deployment_dependencies(
        artifact=artifact_with(required_capability()),
        deployment=deployment(),
        sources=[source()],
    )

    assert diagnostics == []


def test_validate_deployment_reports_missing_binding() -> None:
    diagnostics = validate_deployment_dependencies(
        artifact=artifact_with(required_capability()),
        deployment=deployment(bindings={}),
        sources=[source()],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].code == "binding_missing"
    assert diagnostics[0].logical_ref == "context7.query-docs"
    assert diagnostics[0].bound_source is None


def test_validate_deployment_reports_missing_source() -> None:
    diagnostics = validate_deployment_dependencies(
        artifact=artifact_with(required_capability()),
        deployment=deployment(),
        sources=[],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].code == "source_missing"
    assert diagnostics[0].logical_ref == "context7.query-docs"
    assert diagnostics[0].bound_source == "context7.personal"


def test_validate_deployment_reports_disabled_source() -> None:
    diagnostics = validate_deployment_dependencies(
        artifact=artifact_with(required_capability()),
        deployment=deployment(),
        sources=[source(enabled=False)],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].code == "source_disabled"
    assert diagnostics[0].bound_source == "context7.personal"


def test_validate_deployment_reports_missing_capability() -> None:
    diagnostics = validate_deployment_dependencies(
        artifact=artifact_with(required_capability()),
        deployment=deployment(),
        sources=[source(capability_name="other-tool")],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].code == "capability_missing"
    assert diagnostics[0].logical_ref == "context7.query-docs"


def test_validate_deployment_blocks_changed_schema_by_default() -> None:
    diagnostics = validate_deployment_dependencies(
        artifact=artifact_with(required_capability()),
        deployment=deployment(),
        sources=[source(input_hash="sha256:changed")],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == "error"
    assert diagnostics[0].code == "schema_changed"


def test_validate_deployment_warns_for_changed_schema_when_policy_warns() -> None:
    diagnostics = validate_deployment_dependencies(
        artifact=artifact_with(required_capability()),
        deployment=deployment(drift_policy=DriftPolicy.WARN),
        sources=[source(output_hash="sha256:changed")],
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].severity == "warning"
    assert diagnostics[0].code == "schema_changed"


def test_validate_deployment_allows_changed_schema_when_policy_allows() -> None:
    diagnostics = validate_deployment_dependencies(
        artifact=artifact_with(required_capability()),
        deployment=deployment(drift_policy=DriftPolicy.ALLOW),
        sources=[source(input_hash="sha256:changed")],
    )

    assert diagnostics == []


def test_validate_deployment_accepts_reducer_capability() -> None:
    reducer = RequiredCapability(
        logical_source="wf.std",
        capability_name="set_union",
        kind="reducer",
    )
    diagnostics = validate_deployment_dependencies(
        artifact=artifact_with(reducer),
        deployment=deployment(bindings={"wf.std": "wf.std"}),
        sources=[
            AvailableSource(
                id="wf.std",
                capabilities={
                    "set_union": AvailableCapability(
                        name="set_union",
                        kind="reducer",
                    )
                },
            )
        ],
    )

    assert diagnostics == []
