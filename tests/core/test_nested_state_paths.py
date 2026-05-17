from __future__ import annotations

from wf_core import SchemaRef, StateField, StateSchema, Workflow
from wf_core.runtime.ops.state import write_state_value


def test_exact_nested_state_path_uses_declared_merge_strategy() -> None:
    workflow = _workflow(
        fields={"person.tags": StateField(type="array", merge_strategy="append")}
    )
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["seed", "next"]


def test_parent_state_declaration_does_not_apply_to_nested_write() -> None:
    workflow = _workflow(
        fields={"person": StateField(type="object", merge_strategy="merge_object")}
    )
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["next"]


def test_undeclared_nested_state_path_defaults_to_replace() -> None:
    workflow = _workflow(fields={})
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["next"]


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
