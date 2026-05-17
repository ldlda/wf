from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from wf_platform import CapabilityRef, SourceRef

from .models import JsonObject, RequiredCapability


def normalize_plan_node_refs(
    plan: JsonObject,
    source_bindings: Mapping[str, str],
) -> tuple[JsonObject, dict[str, RequiredCapability]]:
    """Rewrite concrete node refs in a plan to deployment-bound logical refs.

    `source_bindings` uses the same direction as `WorkflowDeployment.bindings`:
    logical source -> concrete source. This lets artifact creation accept the
    source mapping authors already need at deployment time while saving portable
    plan refs such as `demo.echo_tool` instead of `demo.personal.echo_tool`.
    """
    if not source_bindings:
        return deepcopy(plan), {}

    normalized = deepcopy(plan)
    requirements: dict[str, RequiredCapability] = {}
    nodes = normalized.get("nodes")
    if not isinstance(nodes, list):
        return normalized, requirements

    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw_node_ref = node.get("node")
        if not isinstance(raw_node_ref, str):
            continue
        replacement = logical_ref_for_concrete_ref(raw_node_ref, source_bindings)
        if replacement is None:
            continue
        logical_ref, logical_source, capability_name, concrete_source = replacement
        node["node"] = logical_ref
        requirements[logical_ref] = RequiredCapability(
            logical_source=logical_source,
            capability_name=capability_name,
            kind="node_spec",
            observed_concrete_source=concrete_source,
        )

    return normalized, requirements


def logical_ref_for_concrete_ref(
    concrete_ref: str,
    source_bindings: Mapping[str, str],
) -> tuple[str, str, str, str] | None:
    """Return a logical ref for one concrete capability ref when bound.

    The longest concrete source match wins so `demo.personal.pro.echo` can be
    handled safely when both `demo.personal` and `demo.personal.pro` exist.
    """
    matches = sorted(
        source_bindings.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    )
    for logical_source, concrete_source in matches:
        prefix = f"{concrete_source}."
        if not concrete_ref.startswith(prefix):
            continue
        capability_name = concrete_ref[len(prefix) :]
        if not capability_name:
            continue
        logical_ref = str(
            CapabilityRef(source=SourceRef.parse(logical_source), name=capability_name)
        )
        return logical_ref, logical_source, capability_name, concrete_source
    return None
