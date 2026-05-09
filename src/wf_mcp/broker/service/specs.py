from __future__ import annotations

from typing import Any

from collections.abc import Mapping

from wf_authoring import NodeSpec

from ...connections import qualify_node_name
from .sources import SpecSource


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
    spec_sources: Mapping[str, SpecSource],
    qualified_name: str,
) -> NodeSpec[Any, Any]:
    """Resolve a namespaced node spec from planner-visible sources."""
    source_id, _ = qualified_name.rsplit(".", 1)
    source = spec_sources.get(source_id)
    if source is None or qualified_name not in source.specs:
        raise KeyError(f"unknown qualified node {qualified_name!r}")
    return source.specs[qualified_name]
