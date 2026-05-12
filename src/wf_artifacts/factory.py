from __future__ import annotations

from collections.abc import Mapping

from .models import JsonObject, RequiredCapability, WorkflowArtifact


def create_workflow_artifact_from_plan(
    *,
    artifact_id: str,
    version: int,
    title: str,
    plan: JsonObject,
    outcomes: tuple[str, ...],
    description: str | None = None,
    required_capabilities: Mapping[str, RequiredCapability] | None = None,
    created_from_catalog_version: str | None = None,
) -> WorkflowArtifact:
    """Create an immutable artifact from a declarative workflow plan."""
    return WorkflowArtifact(
        id=artifact_id,
        version=version,
        title=title,
        description=description,
        input_schema=_required_object_field(plan, "input_schema"),
        output_schema=_required_object_field(plan, "output_schema"),
        outcomes=outcomes,
        plan=plan,
        required_capabilities=dict(required_capabilities or {}),
        created_from_catalog_version=created_from_catalog_version,
    )


def _required_object_field(plan: JsonObject, field_name: str) -> JsonObject:
    value = plan.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"workflow plan is missing object field {field_name!r}")
    return value
