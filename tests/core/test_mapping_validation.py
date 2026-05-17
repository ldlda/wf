from __future__ import annotations

from wf_core import Edge, NodeDef, NodeUse, SchemaRef, StateField, StateSchema, Workflow


def test_validation_allows_nested_node_local_paths() -> None:
    report = _workflow(
        in_map={"input.person.name": "user.name"},
        out_map={"user.age": "state.person.age"},
    ).validate_structure()

    assert report.errors == []


def test_validation_rejects_overlapping_node_input_destinations() -> None:
    report = _workflow(
        in_map={
            "input.person": "user",
            "input.person.name": "user.name",
        },
        out_map={},
    ).validate_structure()

    assert any("overlapping node-local input paths" in issue.message for issue in report.errors)


def test_validation_rejects_overlapping_state_write_destinations() -> None:
    report = _workflow(
        in_map={},
        out_map={
            "user": "state.person",
            "user.age": "state.person.age",
        },
    ).validate_structure()

    assert any("overlapping state destination paths" in issue.message for issue in report.errors)


def _workflow(*, in_map: dict[str, str], out_map: dict[str, str]) -> Workflow:
    return Workflow(
        name="mapping_validation",
        input_schema=SchemaRef.model_validate(
            {"type": "object", "properties": {"person": {"type": "object"}}}
        ),
        state_schema=StateSchema(fields={"person": StateField(type="object")}),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="tool",
                input_schema=SchemaRef.model_validate(
                    {"type": "object", "properties": {"user": {"type": "object"}}}
                ),
                output_schema=SchemaRef.model_validate(
                    {"type": "object", "properties": {"user": {"type": "object"}}}
                ),
                outcomes=["ok"],
            )
        ],
        start="tool",
        nodes=[
            NodeUse(
                id="tool",
                type="node",
                node="tool",
                in_map=in_map,
                out_map=out_map,
            )
        ],
        edges=[Edge.model_validate({"from": "tool", "outcome": "ok", "to": "__end__"})],
    )
