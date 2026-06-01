"""Compatibility shim — canonical implementation moved to wf_api.saved_subgraphs.

This module re-exports every public symbol so that existing
``from wf_mcp.workflow_surface.saved_subgraphs import ...`` continues to work
without changes.  New code should import from ``wf_api.saved_subgraphs``
directly.
"""

from __future__ import annotations

from wf_api.saved_subgraphs import (
    SavedSubgraphTree,
    direct_wrapper_interrupt_diagnostic,
    prepare_saved_subgraphs,
    resolve_saved_subgraph_tree,
    saved_subgraph_tree_from_snapshots,
    validate_saved_subgraph_tree,
)

__all__ = [
    "SavedSubgraphTree",
    "direct_wrapper_interrupt_diagnostic",
    "prepare_saved_subgraphs",
    "resolve_saved_subgraph_tree",
    "saved_subgraph_tree_from_snapshots",
    "validate_saved_subgraph_tree",
]
