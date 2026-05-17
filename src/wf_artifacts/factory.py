from __future__ import annotations

from collections.abc import Mapping

from wf_core import Workflow

from .models import ArtifactKind, JsonObject, RequiredCapability, WorkflowArtifact


def create_workflow_artifact_from_plan(
    *,
    artifact_id: str,
    version: int,
    title: str,
    plan: JsonObject,
    outcomes: tuple[str, ...],
    kind: ArtifactKind = "workflow",
    description: str | None = None,
    required_capabilities: Mapping[str, RequiredCapability] | None = None,
    created_from_catalog_version: str | None = None,
) -> WorkflowArtifact:
    """Create an immutable artifact from a declarative workflow plan."""
    _validate_workflow_plan(plan)
    return WorkflowArtifact(
        id=artifact_id,
        version=version,
        title=title,
        kind=kind,
        description=description,
        input_schema=_required_object_field(plan, "input_schema"),
        output_schema=_required_object_field(plan, "output_schema"),
        outcomes=outcomes,
        plan=plan,
        required_capabilities={
            **_required_reducers_from_plan(plan),
            **dict(required_capabilities or {}),
        },
        created_from_catalog_version=created_from_catalog_version,
    )


def _required_object_field(plan: JsonObject, field_name: str) -> JsonObject:
    value = plan.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"workflow plan is missing object field {field_name!r}")
    return value


def _validate_workflow_plan(plan: JsonObject) -> None:
    try:
        workflow = Workflow.model_validate(plan)
    except Exception as exc:
        raise ValueError(f"invalid workflow plan: {exc}") from exc

    node_ids = {node.id for node in workflow.nodes}
    if workflow.start not in node_ids:
        raise ValueError(
            f"invalid workflow plan: start node {workflow.start!r} does not exist"
        )

    # wf_core currently uses Workflow.start as the only entry-point source.
    # START is exported for future LangGraph-style edges, but core validation
    # does not accept START edges yet.
    edge_sources = set(node_ids)
    for edge in workflow.edges:
        if edge.from_ not in edge_sources:
            raise ValueError(
                f"invalid workflow plan: edge source {edge.from_!r} does not exist"
            )
        if edge.to not in node_ids and edge.to != "__end__":
            raise ValueError(
                f"invalid workflow plan: edge destination {edge.to!r} does not exist"
            )


def _required_reducers_from_plan(plan: JsonObject) -> dict[str, RequiredCapability]:
    """Infer reducer dependencies from declared state fields in one plan."""
    state_schema = plan.get("state_schema")
    if not isinstance(state_schema, dict):
        return {}
    fields = state_schema.get("fields")
    if not isinstance(fields, dict):
        return {}

    requirements: dict[str, RequiredCapability] = {}
    for field in fields.values():
        if not isinstance(field, dict):
            continue
        reducer = field.get("reducer", "wf.std.replace")
        if not isinstance(reducer, str) or "." not in reducer:
            continue
        logical_source, _, capability_name = reducer.rpartition(".")
        requirements[reducer] = RequiredCapability(
            logical_source=logical_source,
            capability_name=capability_name,
            kind="reducer",
        )
    return requirements
