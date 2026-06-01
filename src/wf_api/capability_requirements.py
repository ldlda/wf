from __future__ import annotations

from typing import Any

from wf_artifacts import (
    RequiredCapability,
    create_workflow_artifact_from_plan as build_workflow_artifact_from_plan,
)
from wf_platform import CapabilityRef, NodeSpecInventory

from .artifact_plans import plan_nodes
from .operation_context import WorkflowOperationContext


def required_capability_payloads(
    requirements: dict[str, RequiredCapability],
) -> dict[str, dict[str, Any]]:
    """Return deterministic JSON payloads for required capabilities."""
    return {
        name: capability.model_dump(mode="json")
        for name, capability in sorted(requirements.items())
    }


def observed_node_specs(
    context: WorkflowOperationContext,
) -> dict[str, NodeSpecInventory]:
    """Project current executable specs into serializable observed contracts."""
    observed: dict[str, NodeSpecInventory] = {}
    for source in context.capability_sources.values():
        inventory = source.as_inventory()
        observed.update(
            {detail.name: detail for detail in inventory.capabilities.node_spec_details}
        )
    return observed


def required_capabilities_for_plan(
    plan: dict[str, Any],
    *,
    source_bindings: dict[str, str] | None,
    context: WorkflowOperationContext,
) -> dict[str, RequiredCapability]:
    """Infer a draft dependency summary without persisting an artifact."""
    artifact = build_workflow_artifact_from_plan(
        artifact_id="draft_preview",
        version=1,
        title="Draft Preview",
        plan=plan,
        outcomes=("completed",),
        source_bindings=source_bindings,
        observed_node_specs=observed_node_specs(context),
    )
    requirements = artifact.required_capability_map()
    for node in plan_nodes(artifact):
        raw_ref = node.get("node")
        if not isinstance(raw_ref, str) or raw_ref in requirements:
            continue
        try:
            parsed = CapabilityRef.parse(raw_ref)
        except ValueError:
            continue
        requirements[raw_ref] = RequiredCapability(
            ref=parsed,
            kind="node_spec",
        )
    return requirements
