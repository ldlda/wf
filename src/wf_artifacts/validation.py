from __future__ import annotations

from .models import (
    AvailableSource,
    DependencyDiagnostic,
    DiagnosticSeverity,
    DriftPolicy,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
)


def validate_deployment_dependencies(
    *,
    artifact: WorkflowArtifact,
    deployment: WorkflowDeployment,
    sources: list[AvailableSource],
) -> list[DependencyDiagnostic]:
    """Validate that a deployment can satisfy an artifact's required contracts."""
    sources_by_id = {source.id: source for source in sources}
    bindings = deployment.binding_map()
    diagnostics: list[DependencyDiagnostic] = []

    for logical_ref, required in artifact.required_capability_map().items():
        platform_source = sources_by_id.get(required.logical_source)
        if platform_source is not None and platform_source.platform:
            bound_source_id = required.logical_source
        else:
            bound_source_id = bindings.get(required.logical_source)
            if bound_source_id is None:
                diagnostics.append(
                    _diagnostic(
                        code="binding_missing",
                        logical_ref=logical_ref,
                        required=required,
                        message=(
                            f"No binding exists for logical source "
                            f"{required.logical_source!r}."
                        ),
                        repair_hint=(
                            "Bind the logical source to a compatible concrete source."
                        ),
                    )
                )
                continue

        source = sources_by_id.get(bound_source_id)
        if source is None:
            diagnostics.append(
                _diagnostic(
                    code="source_missing",
                    logical_ref=logical_ref,
                    required=required,
                    bound_source=bound_source_id,
                    message=f"Bound source {bound_source_id!r} is not available.",
                    repair_hint=(
                        "Reconnect this source or bind the logical source to "
                        "another compatible source."
                    ),
                )
            )
            continue

        if not source.enabled:
            diagnostics.append(
                _diagnostic(
                    code="source_disabled",
                    logical_ref=logical_ref,
                    required=required,
                    bound_source=bound_source_id,
                    message=f"Bound source {bound_source_id!r} is disabled.",
                    repair_hint="Enable the source or choose another binding.",
                )
            )
            continue

        capability = source.capabilities.get(required.capability_name)
        if capability is None:
            diagnostics.append(
                _diagnostic(
                    code="capability_missing",
                    logical_ref=logical_ref,
                    required=required,
                    bound_source=bound_source_id,
                    message=(
                        f"Bound source {bound_source_id!r} does not expose "
                        f"capability {required.capability_name!r}."
                    ),
                    repair_hint=(
                        "Refresh the source catalog or bind to another compatible "
                        "source."
                    ),
                )
            )
            continue

        if _schema_changed(required, capability):
            drift = _schema_drift_diagnostic(
                logical_ref=logical_ref,
                required=required,
                bound_source=bound_source_id,
                policy=deployment.drift_policy,
            )
            if drift is not None:
                diagnostics.append(drift)

    return diagnostics


def _schema_changed(
    required: RequiredCapability,
    available: object,
) -> bool:
    input_hash = getattr(available, "input_schema_hash", None)
    output_hash = getattr(available, "output_schema_hash", None)
    return (
        required.input_schema_hash is not None
        and input_hash is not None
        and required.input_schema_hash != input_hash
    ) or (
        required.output_schema_hash is not None
        and output_hash is not None
        and required.output_schema_hash != output_hash
    )


def _schema_drift_diagnostic(
    *,
    logical_ref: str,
    required: RequiredCapability,
    bound_source: str,
    policy: DriftPolicy,
) -> DependencyDiagnostic | None:
    if policy == DriftPolicy.ALLOW:
        return None
    severity = (
        DiagnosticSeverity.WARNING
        if policy == DriftPolicy.WARN
        else DiagnosticSeverity.ERROR
    )
    return _diagnostic(
        severity=severity,
        code="schema_changed",
        logical_ref=logical_ref,
        required=required,
        bound_source=bound_source,
        message=(
            f"Capability {required.capability_name!r} on source {bound_source!r} "
            "has a different schema hash than the saved artifact contract."
        ),
        repair_hint=(
            "Review the changed capability contract, then update the deployment "
            "policy or migrate the workflow artifact."
        ),
    )


def _diagnostic(
    *,
    code: str,
    logical_ref: str,
    required: RequiredCapability,
    message: str,
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR,
    bound_source: str | None = None,
    repair_hint: str | None = None,
) -> DependencyDiagnostic:
    return DependencyDiagnostic(
        severity=severity,
        code=code,
        logical_ref=logical_ref,
        bound_source=bound_source,
        message=message,
        repair_hint=repair_hint,
    )
