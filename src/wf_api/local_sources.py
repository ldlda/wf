from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from wf_authoring import (
    NodeSpec,
    coalesce,
    concat,
    constant,
    default_if_none,
    extract_field,
    extract_text_content,
    filter_items,
    filter_items_present,
    first_item,
    first_item_maybe,
    first_item_or_none,
    is_empty,
    last_item,
    last_item_or_none,
    length,
    node,
    pick_key,
    pick_path,
    project_fields,
    rename_fields,
    runtime_error,
    truthy,
)
from wf_core import RuntimeContext
from wf_core.runtime.ops.merges import DEFAULT_REDUCER_DEFINITIONS
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourcePolicy,
    SourceVisibility,
)

from .source_helpers import ReadResourceOutput, read_resource
from .source_refs import SourceResourceRef

if TYPE_CHECKING:
    from wf_core import ReducerSpec

BUILTIN_SOURCE_ID = "wf.std"
"""Internal source id for workflow standard-library node specs."""

BUILTIN_CONNECTION_ID = BUILTIN_SOURCE_ID
"""Compatibility alias for older MCP broker code."""

MCP_SOURCE_ID = "wf.mcp"
"""Reserved source id for future workflow-safe MCP utility node specs."""

RECIPE_SOURCE_ID = "wf.recipes"
"""Internal source id for first-party composed workflow recipes."""

AUTHORING_STD_SPECS: tuple[NodeSpec[Any, Any], ...] = (
    coalesce,
    default_if_none,
    constant,
    pick_key,
    pick_path,
    project_fields,
    rename_fields,
    truthy,
    runtime_error,
    first_item,
    first_item_or_none,
    first_item_maybe,
    last_item,
    last_item_or_none,
    length,
    is_empty,
    filter_items,
    filter_items_present,
    extract_field,
    concat,
)
"""Existing authoring ops exposed through the workflow stdlib."""

RECIPE_SPECS: tuple[NodeSpec[Any, Any], ...] = (extract_text_content,)
"""Composed first-party recipes exposed as workflow-facing capabilities."""

SOURCE_SOURCE_ID = "wf.source"
"""Internal source id for explicit source-ref helper nodes."""


class ReadResourceInput(BaseModel):
    """Input model for wf.source.read_resource node."""

    ref: SourceResourceRef
    max_chars: int = Field(default=4000, ge=1, le=20000)


@node(name="read_resource")
async def read_resource_node(
    payload: ReadResourceInput,
    ctx: RuntimeContext,
) -> ReadResourceOutput:
    return await read_resource(payload.ref, ctx, max_chars=payload.max_chars)


def qualify_node_name(source_id: str, local_name: str) -> str:
    """Return one source-qualified node name without assuming MCP connections."""
    if not source_id:
        raise ValueError("source_id must not be empty")
    if not local_name:
        raise ValueError("local node name must not be empty")
    return f"{source_id}.{local_name}"


def qualify_spec(source_id: str, spec: NodeSpec[Any, Any]) -> NodeSpec[Any, Any]:
    """Return a copy of a spec with its node name scoped to a source."""
    return NodeSpec(
        name=qualify_node_name(source_id, spec.name),
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


def _qualified_specs(
    source_id: str,
    specs: tuple[NodeSpec[Any, Any], ...],
) -> dict[str, NodeSpec[Any, Any]]:
    """Return specs with authoring names rewritten under one source id."""
    local_specs = [
        node(spec, name=spec.name.removeprefix("authoring.")) for spec in specs
    ]
    qualified_specs = [qualify_spec(source_id, spec) for spec in local_specs]
    return {spec.name: spec for spec in qualified_specs}


def builtin_specs() -> dict[str, NodeSpec[Any, Any]]:
    """Return primitive built-in NodeSpecs available to raw workflow plans."""
    return _qualified_specs(BUILTIN_SOURCE_ID, AUTHORING_STD_SPECS)


def recipe_specs() -> dict[str, NodeSpec[Any, Any]]:
    """Return composed first-party recipe specs."""
    return _qualified_specs(RECIPE_SOURCE_ID, RECIPE_SPECS)


def builtin_reducers() -> dict[str, ReducerSpec]:
    """Return built-in reducers owned by the workflow standard library."""
    return {
        definition.spec.name: definition.spec
        for definition in DEFAULT_REDUCER_DEFINITIONS.values()
    }


def builtin_reducer_definitions():
    """Return executable built-in reducers for trusted runtime dependency wiring."""
    return dict(DEFAULT_REDUCER_DEFINITIONS)


def builtin_sources() -> dict[str, CapabilitySource]:
    """Return all local workflow-facing capability sources."""
    return {
        BUILTIN_SOURCE_ID: CapabilitySource(
            id=BUILTIN_SOURCE_ID,
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs=builtin_specs(),
                reducers=builtin_reducers(),
                reducer_definitions=builtin_reducer_definitions(),
            ),
            visibility=SourceVisibility(
                planner=True,
                client=True,
                admin_dashboard=True,
            ),
            permissions=SourcePermissions(safe_for_workflow=True),
            policy=SourcePolicy(platform=True, binding_required=False),
            description="Workflow standard-library nodes.",
        ),
        RECIPE_SOURCE_ID: CapabilitySource(
            id=RECIPE_SOURCE_ID,
            kind="system",
            capabilities=CapabilityBuckets(node_specs=recipe_specs()),
            visibility=SourceVisibility(
                planner=True,
                client=True,
                admin_dashboard=True,
            ),
            permissions=SourcePermissions(safe_for_workflow=True),
            policy=SourcePolicy(platform=True, binding_required=False),
            description="First-party workflow recipes composed from standard nodes.",
        ),
        SOURCE_SOURCE_ID: CapabilitySource(
            id=SOURCE_SOURCE_ID,
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs=_qualified_specs(SOURCE_SOURCE_ID, (read_resource_node,)),
            ),
            visibility=SourceVisibility(
                planner=True,
                client=True,
                admin_dashboard=True,
            ),
            permissions=SourcePermissions(safe_for_workflow=True, calls_upstream=True),
            policy=SourcePolicy(platform=True, binding_required=False),
            description="Platform helpers for explicit source refs.",
        ),
    }


__all__ = [
    "AUTHORING_STD_SPECS",
    "BUILTIN_CONNECTION_ID",
    "BUILTIN_SOURCE_ID",
    "MCP_SOURCE_ID",
    "RECIPE_SOURCE_ID",
    "RECIPE_SPECS",
    "builtin_reducer_definitions",
    "builtin_reducers",
    "builtin_sources",
    "builtin_specs",
    "get_qualified_spec",
    "qualify_node_name",
    "qualify_spec",
    "recipe_specs",
]
