from __future__ import annotations

import wf_api.saved_subgraphs as canonical
import wf_mcp.workflow_surface.saved_subgraphs as shim


def test_canonical_import_exports_expected_symbols() -> None:
    assert hasattr(canonical, "SavedSubgraphTree")
    assert hasattr(canonical, "resolve_saved_subgraph_tree")
    assert hasattr(canonical, "prepare_saved_subgraphs")
    assert hasattr(canonical, "validate_saved_subgraph_tree")
    assert hasattr(canonical, "saved_subgraph_tree_from_snapshots")
    assert hasattr(canonical, "direct_wrapper_interrupt_diagnostic")


def test_shim_import_still_works() -> None:
    assert hasattr(shim, "SavedSubgraphTree")
    assert hasattr(shim, "resolve_saved_subgraph_tree")
    assert hasattr(shim, "prepare_saved_subgraphs")


def test_shim_symbols_are_identical_to_canonical() -> None:
    assert shim.SavedSubgraphTree is canonical.SavedSubgraphTree
    assert shim.resolve_saved_subgraph_tree is canonical.resolve_saved_subgraph_tree
    assert shim.prepare_saved_subgraphs is canonical.prepare_saved_subgraphs
    assert shim.validate_saved_subgraph_tree is canonical.validate_saved_subgraph_tree
    assert (
        shim.saved_subgraph_tree_from_snapshots
        is canonical.saved_subgraph_tree_from_snapshots
    )
    assert (
        shim.direct_wrapper_interrupt_diagnostic
        is canonical.direct_wrapper_interrupt_diagnostic
    )
