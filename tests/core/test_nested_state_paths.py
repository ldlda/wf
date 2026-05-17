from __future__ import annotations

from wf_core import SchemaRef, StateField, StateSchema, Workflow
from wf_core.runtime.ops.state import write_state_value


def test_exact_nested_state_path_uses_declared_reducer() -> None:
    workflow = _workflow(
        fields={"person.tags": StateField(type="array", reducer="wf.std.append")}
    )
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["seed", "next"]


def test_parent_state_declaration_does_not_apply_to_nested_write() -> None:
    workflow = _workflow(
        fields={"person": StateField(type="object", reducer="wf.std.merge_object")}
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
    assert StateField(type="string").reducer == "wf.std.replace"


def test_unknown_state_reducer_fails_clearly() -> None:
    workflow = _workflow(fields={"person.tags": StateField(type="array", reducer="x.nope")})
    state = {"person": {"tags": ["seed"]}}

    try:
        write_state_value(workflow, state, "state.person.tags", ["next"])
    except Exception as exc:
        assert "unknown reducer 'x.nope'" in str(exc)
    else:
        raise AssertionError("expected unknown reducer to fail")


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
