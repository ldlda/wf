from __future__ import annotations

from wf_api.local_sources import (
    BUILTIN_SOURCE_ID,
    RECIPE_SOURCE_ID,
    builtin_sources,
    get_qualified_spec,
    qualify_spec,
)
from wf_authoring import constant


def test_builtin_sources_expose_workflow_stdlib() -> None:
    sources = builtin_sources()

    assert BUILTIN_SOURCE_ID == "wf.std"
    assert RECIPE_SOURCE_ID == "wf.recipes"
    assert "wf.std" in sources
    assert "wf.std.constant" in sources["wf.std"].capabilities.node_specs
    assert "wf.std.replace" in sources["wf.std"].capabilities.reducers


def test_get_qualified_spec_resolves_planner_visible_spec() -> None:
    sources = builtin_sources()

    spec = get_qualified_spec(sources, "wf.std.constant")

    assert spec.name == "wf.std.constant"
    assert spec.outcomes == ("ok",)


def test_qualify_spec_scopes_authoring_node_name() -> None:
    qualified = qualify_spec("custom.local", constant)

    assert qualified.name == "custom.local.authoring.constant"
    assert qualified.input_model is constant.input_model
    assert qualified.output_model is constant.output_model


def test_mcp_builtin_module_reexports_canonical_helpers() -> None:
    from wf_mcp.broker.service import builtins as mcp_builtins

    assert mcp_builtins.BUILTIN_CONNECTION_ID == BUILTIN_SOURCE_ID
    assert mcp_builtins.BUILTIN_SOURCE_ID == BUILTIN_SOURCE_ID
    assert mcp_builtins.builtin_sources is builtin_sources
