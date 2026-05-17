from __future__ import annotations

from wf_core import (
    ReducerRef,
    ReducerSpec,
    SchemaRef,
    StateField,
    StateSchema,
    Workflow,
)
from wf_core.runtime.ops.merges import ReducerDefinition, apply_reducer
from wf_core.runtime.ops.state import write_state_value


def test_exact_nested_state_path_uses_declared_reducer() -> None:
    workflow = _workflow(
        fields={
            "person.tags": StateField(
                reducer=ReducerRef(name="wf.std.append"), type="array"
            )
        }
    )
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["seed", "next"]


def test_parent_state_declaration_does_not_apply_to_nested_write() -> None:
    workflow = _workflow(
        fields={
            "person": StateField(
                reducer=ReducerRef(name="wf.std.merge_object"), type="object"
            )
        }
    )
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["next"]


def test_undeclared_nested_state_path_defaults_to_replace() -> None:
    workflow = _workflow(fields={})
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["next"]


def test_state_field_defaults_to_replace_reducer() -> None:
    assert StateField(type="string").reducer == ReducerRef(name="wf.std.replace")


def test_state_field_accepts_string_reducer_shorthand() -> None:
    field = StateField.model_validate({"type": "array", "reducer": "wf.std.set_union"})

    assert field.reducer == ReducerRef(name="wf.std.set_union")


def test_state_field_accepts_configured_reducer_reference() -> None:
    field = StateField(
        type="integer",
        reducer=ReducerRef(name="wf.std.max", config={"sample": True}),
    )

    # PYLINT!!!! what is u on ts is so clear
    assert field.reducer.name == "wf.std.max"  # pylint: disable=no-member
    assert field.reducer.config == {"sample": True}  # pylint: disable=no-member


def test_unknown_state_reducer_fails_clearly() -> None:
    workflow = _workflow(
        fields={
            "person.tags": StateField(reducer=ReducerRef(name="x.nope"), type="array")
        }
    )
    state = {"person": {"tags": ["seed"]}}

    try:
        write_state_value(workflow, state, "state.person.tags", ["next"])
    except Exception as exc:
        assert "unknown reducer 'x.nope'" in str(exc)
    else:
        raise AssertionError("expected unknown reducer to fail")


def test_set_union_reducer_preserves_first_seen_order() -> None:
    workflow = _workflow(
        fields={
            "person.tags": StateField(
                reducer=ReducerRef(name="wf.std.set_union"), type="array"
            )
        }
    )
    state = {"person": {"tags": ["alpha", "beta"]}}

    write_state_value(workflow, state, "state.person.tags", ["beta", "gamma"])

    assert state["person"]["tags"] == ["alpha", "beta", "gamma"]


def test_unexpected_reducer_config_fails_before_state_mutation() -> None:
    workflow = _workflow(
        fields={
            "person.tags": StateField(
                type="array",
                reducer=ReducerRef(name="wf.std.set_union", config={"bad": True}),
            )
        }
    )
    state = {"person": {"tags": ["alpha"]}}

    try:
        write_state_value(workflow, state, "state.person.tags", ["beta"])
    except Exception as exc:
        assert "reducer config for 'wf.std.set_union'" in str(exc)
    else:
        raise AssertionError("expected invalid reducer config to fail")
    assert state["person"]["tags"] == ["alpha"]


def test_max_reducer_keeps_larger_value() -> None:
    workflow = _workflow(
        fields={
            "best_score": StateField(
                reducer=ReducerRef(name="wf.std.max"), type="integer"
            )
        }
    )
    state = {"best_score": 7}

    write_state_value(workflow, state, "state.best_score", 9)

    assert state["best_score"] == 9


def test_add_reducer_sums_numeric_values() -> None:
    workflow = _workflow(
        fields={
            "count": StateField(reducer=ReducerRef(name="wf.std.add"), type="integer")
        }
    )
    state = {"count": 7}

    write_state_value(workflow, state, "state.count", 5)

    assert state["count"] == 12


def test_reducer_definition_can_wrap_plain_two_arg_callable() -> None:
    definition = ReducerDefinition(
        spec=ReducerSpec(name="test.add"),
        fn=lambda current, incoming: (current or 0) + incoming,
    )

    result = apply_reducer(
        reducer=ReducerRef(name="test.add"),
        current_value=2,
        incoming_value=3,
        destination_path="state.total",
        reducers={"test.add": definition},
    )

    assert result == 5


def test_reducer_definition_can_wrap_config_aware_callable() -> None:
    definition = ReducerDefinition(
        spec=ReducerSpec(
            name="test.modulo_add",
            config_schema={
                "type": "object",
                "properties": {"modulus": {"type": "integer"}},
                "required": ["modulus"],
                "additionalProperties": False,
            },
        ),
        fn=lambda current, incoming, config: ((current or 0) + incoming)
        % config["modulus"],
        accepts_config=True,
    )

    result = apply_reducer(
        reducer=ReducerRef(name="test.modulo_add", config={"modulus": 10}),
        current_value=8,
        incoming_value=5,
        destination_path="state.total",
        reducers={"test.modulo_add": definition},
    )

    assert result == 3


def _workflow(*, fields: dict[str, StateField]) -> Workflow:
    return Workflow(
        name="nested_state_paths",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema(fields=fields),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[],
        start="unused",
        nodes=[],
        edges=[],
    )
