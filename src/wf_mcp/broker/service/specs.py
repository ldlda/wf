from __future__ import annotations

from typing import Any

from wf_authoring import NodeSpec

from ...connections import qualify_node_name


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
    )


def get_qualified_spec(
    specs_by_connection: dict[str, dict[str, NodeSpec[Any, Any]]],
    qualified_name: str,
) -> NodeSpec[Any, Any]:
    """Resolve a namespaced node spec from the service's connection cache."""
    connection_id, _ = qualified_name.rsplit(".", 1)
    specs = specs_by_connection.get(connection_id)
    if specs is None or qualified_name not in specs:
        raise KeyError(f"unknown qualified node {qualified_name!r}")
    return specs[qualified_name]
