from __future__ import annotations

from collections.abc import Mapping

from wf_core import ReducerRef, Workflow
from wf_platform import CapabilityRef, NodeSpecInventory, hash_json_schema

from .models import ArtifactKind, JsonObject, RequiredCapability, WorkflowArtifact
from .references import normalize_plan_node_refs


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
    source_bindings: Mapping[str, str] | None = None,
    observed_node_specs: Mapping[str, NodeSpecInventory] | None = None,
    created_from_catalog_version: str | None = None,
) -> WorkflowArtifact:
    """Create an immutable artifact from a declarative workflow plan."""
    normalized_plan, node_requirements = normalize_plan_node_refs(
        plan,
        source_bindings or {},
        observed_node_specs,
    )
    _validate_workflow_plan(normalized_plan)
    required = {
        **_required_reducers_from_plan(normalized_plan),
        **_required_node_specs_from_plan(normalized_plan, observed_node_specs),
        **node_requirements,
        **dict(required_capabilities or {}),
    }
    return WorkflowArtifact(
        id=artifact_id,
        version=version,
        title=title,
        kind=kind,
        description=description,
        input_schema=_required_object_field(normalized_plan, "input_schema"),
        output_schema=_required_object_field(normalized_plan, "output_schema"),
        outcomes=outcomes,
        plan=normalized_plan,
        required_capabilities=list(required.values()),
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

    requirements: dict[str, RequiredCapability] = {}
    for reducer_payload in _iter_state_schema_reducer_payloads(state_schema):
        if isinstance(reducer_payload, str):
            reducer = ReducerRef(name=reducer_payload)
        else:
            try:
                reducer = ReducerRef.model_validate(reducer_payload)
            except ValueError:
                continue
        requirements[reducer.name] = RequiredCapability(
            ref=reducer.ref,
            kind="reducer",
        )
    return requirements


def _required_node_specs_from_plan(
    plan: JsonObject,
    observed_node_specs: Mapping[str, NodeSpecInventory] | None,
) -> dict[str, RequiredCapability]:
    """Infer direct node-spec dependencies that were not rewritten by bindings.

    Bound artifact creation already records concrete-to-logical rewrites in
    `normalize_plan_node_refs`. This fallback covers drafts saved with concrete
    refs and no source bindings, so validation still knows the workflow depends
    on that live source capability.
    """
    requirements: dict[str, RequiredCapability] = {}
    nodes = plan.get("nodes")
    if not isinstance(nodes, list):
        return requirements

    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw_ref = node.get("node")
        if not isinstance(raw_ref, str):
            continue
        try:
            parsed = CapabilityRef.parse(raw_ref)
        except ValueError:
            continue
        observed = (
            observed_node_specs.get(raw_ref)
            if observed_node_specs is not None
            else None
        )
        requirements[raw_ref] = RequiredCapability(
            ref=parsed,
            kind="node_spec",
            input_schema_hash=(
                hash_json_schema(observed.input_schema)
                if observed is not None
                else None
            ),
            input_schema_snapshot=(
                observed.input_schema if observed is not None else None
            ),
            output_schema_hash=(
                hash_json_schema(observed.output_schema)
                if observed is not None
                else None
            ),
            output_schema_snapshot=(
                observed.output_schema if observed is not None else None
            ),
        )
    return requirements


def _iter_state_schema_reducer_payloads(state_schema: JsonObject) -> list[object]:
    """Read reducer refs from canonical JSON Schema and legacy field metadata."""
    reducer_payloads: list[object] = []
    properties = state_schema.get("properties")
    if isinstance(properties, dict):
        reducer_payloads.extend(_iter_property_reducer_payloads(properties))

    fields = state_schema.get("fields")
    if isinstance(fields, dict):
        field_values = fields.values()
    elif isinstance(fields, list):
        field_values = fields
    else:
        field_values = []

    for field in field_values:
        if isinstance(field, dict):
            reducer_payloads.append(field.get("reducer", "wf.std.replace"))
    return reducer_payloads


def _iter_property_reducer_payloads(properties: JsonObject) -> list[object]:
    payloads: list[object] = []
    for property_schema in properties.values():
        if not isinstance(property_schema, dict):
            continue
        payloads.append(property_schema.get("reducer", "wf.std.replace"))
        child_properties = property_schema.get("properties")
        if isinstance(child_properties, dict):
            payloads.extend(_iter_property_reducer_payloads(child_properties))
    return payloads
