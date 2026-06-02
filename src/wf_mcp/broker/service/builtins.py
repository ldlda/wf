"""Compatibility exports for workflow local sources.

Canonical local workflow source helpers live in `wf_api.local_sources` so
non-MCP process hosts can construct `wf.std` without importing broker internals.
"""

from __future__ import annotations

from wf_api.local_sources import (
    AUTHORING_STD_SPECS,
    BUILTIN_CONNECTION_ID,
    BUILTIN_SOURCE_ID,
    MCP_SOURCE_ID,
    RECIPE_SOURCE_ID,
    RECIPE_SPECS,
    builtin_reducer_definitions,
    builtin_reducers,
    builtin_sources,
    builtin_specs,
    get_qualified_spec,
    qualify_node_name,
    qualify_spec,
    recipe_specs,
)

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
