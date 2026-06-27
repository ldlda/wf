from __future__ import annotations

import pytest

from wf_authoring import state, state_path
from wf_authoring.dsl.path_inputs import (
    coerce_graph_path,
    coerce_local_path,
    coerce_state_path,
)
from wf_core.models.conditions import BinaryCondition, PathOperand
from wf_core.paths import GraphSourcePath, LocalPath, StatePath


def test_single_string_path_input_uses_toml_dotted_key_syntax() -> None:
    assert coerce_state_path("person.name") == StatePath(("person", "name"))
    assert coerce_state_path('"person.name"') == StatePath(("person.name",))
    assert coerce_state_path('person."three and four"') == StatePath(
        (
            "person",
            "three and four",
        )
    )


def test_vararg_path_input_treats_parts_as_literal_segments() -> None:
    assert coerce_state_path("person.name", "email address") == StatePath(
        (
            "person.name",
            "email address",
        )
    )


def test_iterable_path_input_treats_items_as_literal_segments() -> None:
    assert coerce_local_path(("payload.text",)) == LocalPath(("payload.text",))
    assert coerce_local_path(iter(["payload.text"])) == LocalPath(("payload.text",))


def test_existing_path_objects_pass_through() -> None:
    source = GraphSourcePath("state", ("person.name",))
    assert coerce_graph_path(source) is source


def test_structural_path_dicts_validate_through_core_models() -> None:
    assert coerce_graph_path({"root": "state", "parts": ["person.name"]}) == (
        GraphSourcePath("state", ("person.name",))
    )


def test_invalid_toml_path_expression_has_actionable_message() -> None:
    with pytest.raises(ValueError, match="TOML path"):
        coerce_state_path("person..name")


def test_state_path_helper_supports_toml_strings_and_literal_varargs() -> None:
    assert state_path('"person.name"').path == GraphSourcePath(
        "state", ("person.name",)
    )
    assert state_path("person.name", "email address").path == GraphSourcePath(
        "state", ("person.name", "email address")
    )


def test_state_expr_helper_uses_same_path_input_rules() -> None:
    condition = state('"person.name"').eq("Ada").to_condition()

    assert isinstance(condition, BinaryCondition)
    assert isinstance(condition.left, PathOperand)
    assert condition.left.path == GraphSourcePath("state", ("person.name",))


def test_authoring_paths_share_core_toml_grammar() -> None:
    assert coerce_graph_path('state."person.name"') == GraphSourcePath(
        "state", ("person.name",)
    )
    assert coerce_graph_path('"person.name"', root="state") == GraphSourcePath(
        "state", ("person.name",)
    )
