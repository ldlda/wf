from __future__ import annotations

import pytest

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


@pytest.mark.parametrize("name", ["wf.std.first_item", "wf.std.last_item"])
def test_non_empty_sequence_catalog_contracts_publish_min_items(name: str) -> None:
    spec = get_qualified_spec(builtin_sources(), name)

    items_schema = (spec.input_schema_contract or spec.input_model.model_json_schema())[
        "properties"
    ]["items"]
    assert items_schema["minItems"] == 1


@pytest.mark.parametrize(
    "name",
    [
        "wf.std.first_item_maybe",
        "wf.std.first_item_or_none",
        "wf.std.last_item_or_none",
        "wf.std.length",
        "wf.std.is_empty",
    ],
)
def test_empty_aware_sequence_catalog_contracts_allow_empty_arrays(name: str) -> None:
    spec = get_qualified_spec(builtin_sources(), name)

    items_schema = (spec.input_schema_contract or spec.input_model.model_json_schema())[
        "properties"
    ]["items"]
    assert "minItems" not in items_schema


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
