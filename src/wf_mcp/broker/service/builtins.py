from __future__ import annotations

from typing import TYPE_CHECKING, Any

from wf_authoring import NodeSpec, coalesce, concat, constant, default_if_none
from wf_authoring import extract_field, filter_items, filter_items_present, first_item
from wf_authoring import first_item_maybe, first_item_or_none, is_empty, last_item
from wf_authoring import last_item_or_none, length, node, pick_key, pick_path
from wf_authoring import project_fields, rename_fields, runtime_error, truthy
from wf_core.runtime.ops.merges import DEFAULT_REDUCER_DEFINITIONS

from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)
from wf_mcp.broker.service.specs import qualify_spec

if TYPE_CHECKING:
    from wf_core import ReducerSpec

BUILTIN_CONNECTION_ID = "wf.std"
"""Internal source id for workflow standard-library node specs."""

MCP_SOURCE_ID = "wf.mcp"
"""Reserved source id for future workflow-safe MCP utility node specs."""


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
"""Existing authoring ops that are also exposed through the workflow stdlib."""


def builtin_specs() -> dict[str, NodeSpec[Any, Any]]:
    """Return built-in NodeSpecs available to raw broker workflow plans."""
    specs = [
        node(spec, name=spec.name.removeprefix("authoring."))
        for spec in AUTHORING_STD_SPECS
    ]
    qualified_specs = [qualify_spec(BUILTIN_CONNECTION_ID, spec) for spec in specs]
    return {spec.name: spec for spec in qualified_specs}


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
    """Return all broker-local capability sources."""
    return {
        BUILTIN_CONNECTION_ID: CapabilitySource(
            id=BUILTIN_CONNECTION_ID,
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs=builtin_specs(),
                reducers=builtin_reducers(),
                reducer_definitions=builtin_reducer_definitions(),
            ),
            visibility=SourceVisibility(
                planner=True,
                mcp_client=True,
                admin_dashboard=True,
            ),
            permissions=SourcePermissions(safe_for_workflow=True),
            description="Workflow standard-library nodes.",
        ),
    }
