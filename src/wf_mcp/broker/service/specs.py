from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wf_authoring import NodeSpec
from wf_mcp.connections import qualify_node_name
from wf_platform import CapabilitySource


def qualify_spec(connection_id: str, spec: NodeSpec[Any, Any]) -> NodeSpec[Any, Any]:
    """Return a copy of a spec with its node name scoped to a connection."""
    return NodeSpec(
        name=qualify_node_name(connection_id, spec.name),
        input_model=spec.input_model,
        output_model=spec.output_model,
        outcomes=spec.outcomes,
        fn=spec.fn,
        description=spec.description,
        is_async=spec.is_async,
        accepts_context=spec.accepts_context,
        input_schema_contract=spec.input_schema_contract,
        output_schema_contract=spec.output_schema_contract,
    )


def get_qualified_spec(
    sources: Mapping[str, CapabilitySource],
    qualified_name: str,
) -> NodeSpec[Any, Any]:
    """Resolve a namespaced node spec from enabled planner-visible sources."""
    for source in sources.values():
        if not source.enabled or not source.visibility.planner:
            continue
        spec = source.capabilities.node_specs.get(qualified_name)
        if spec is not None:
            return spec
    raise KeyError(f"unknown qualified node {qualified_name!r}")
