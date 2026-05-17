from __future__ import annotations

import pytest

from wf_core import (
    END,
    Edge,
    NodeDef,
    NodeUse,
    SchemaRef,
    StateField,
    StateSchema,
    Workflow,
    WorkflowExecutionError,
    execute_workflow,
)


def test_nested_node_local_paths_build_input_and_read_output() -> None:
    workflow = _nested_mapping_workflow()

    run = execute_workflow(
        workflow,
        {"person": {"name": "Ada"}, "digital": {"email": "ada@example.com"}},
        {
            "big_tool": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {
                    "user": {"age": 36, "gender": "x"},
                    "job": {"years": 12},
                },
            }
        },
    )

    assert run.trace[0].resolved_input == {
        "user": {"name": "Ada", "email": "ada@example.com"}
    }
    assert run.state["person"]["age"] == 36
    assert run.state["person"]["gender"] == "x"
    assert run.state["experience"]["years"] == 12


def test_missing_nested_node_output_path_fails() -> None:
    workflow = _nested_mapping_workflow()

    with pytest.raises(
        WorkflowExecutionError,
        match="did not return required mapped field 'user.gender'",
    ):
        execute_workflow(
            workflow,
            {"person": {"name": "Ada"}, "digital": {"email": "ada@example.com"}},
            {
                "big_tool": lambda payload, _ctx: {
                    "outcome": "ok",
                    "output": {"user": {"age": 36}, "job": {"years": 12}},
                }
            },
        )


def _nested_mapping_workflow() -> Workflow:
    return Workflow(
        name="nested_mapping",
        input_schema=SchemaRef.model_validate(
            {
                "type": "object",
                "properties": {
                    "person": {"type": "object"},
                    "digital": {"type": "object"},
                },
            }
        ),
        state_schema=StateSchema(
            fields={
                "person": StateField(type="object"),
                "experience": StateField(type="object"),
            }
        ),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="big_tool",
                input_schema=SchemaRef.model_validate(
                    {
                        "type": "object",
                        "properties": {"user": {"type": "object"}},
                    }
                ),
                output_schema=SchemaRef.model_validate(
                    {
                        "type": "object",
                        "properties": {
                            "user": {"type": "object"},
                            "job": {"type": "object"},
                        },
                    }
                ),
                outcomes=["ok"],
            )
        ],
        start="big",
        nodes=[
            NodeUse(
                id="big",
                type="node",
                node="big_tool",
                in_map={
                    "input.person.name": "user.name",
                    "input.digital.email": "user.email",
                },
                out_map={
                    "user.age": "state.person.age",
                    "user.gender": "state.person.gender",
                    "job.years": "state.experience.years",
                },
            )
        ],
        edges=[Edge.model_validate({"from": "big", "outcome": "ok", "to": END})],
    )
