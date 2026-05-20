from __future__ import annotations

import pytest

from wf_core import (
    END,
    Edge,
    NodeDef,
    NodeUse,
    ReducerRef,
    SchemaRef,
    StateField,
    StateSchema,
    Workflow,
    WorkflowExecutionError,
)
from wf_core.models.steps import OutputBinding
from wf_core.runtime.engine import resume_workflow
from wf_core.runtime.ops.runs import create_run_state
from wf_core.runtime.ops.state import apply_output_bindings


def test_output_bindings_commit_patch_atomically_when_source_is_missing() -> None:
    workflow = _workflow()
    state = {"person": {"name": "old"}}

    with pytest.raises(WorkflowExecutionError, match="missing"):
        apply_output_bindings(
            workflow,
            [
                _binding("person.name", "state.person.name"),
                _binding("missing", "state.person.extra"),
            ],
            {"person": {"name": "new"}},
            state,
        )

    assert state["person"]["name"] == "old"
    assert "extra" not in state["person"]


def test_output_bindings_reject_overlapping_write_targets_before_mutation() -> None:
    workflow = _workflow()
    state = {"person": {"name": "old"}}

    with pytest.raises(WorkflowExecutionError, match="overlapping"):
        apply_output_bindings(
            workflow,
            [
                _binding("person", "state.person"),
                _binding("person.name", "state.person.name"),
            ],
            {"person": {"name": "Ada"}},
            state,
        )

    assert state["person"]["name"] == "old"


def test_output_bindings_prepare_reducer_results_before_mutation() -> None:
    workflow = _workflow(
        fields={
            "person.name": StateField(type="string"),
            "person.tags": StateField(
                type="array",
                reducer=ReducerRef(name="wf.std.set_union", config={"bad": True}),
            ),
        }
    )
    state = {"person": {"name": "old", "tags": ["seed"]}}

    with pytest.raises(WorkflowExecutionError, match="reducer config"):
        apply_output_bindings(
            workflow,
            [
                _binding("person.name", "state.person.name"),
                _binding("person.tags", "state.person.tags"),
            ],
            {"person": {"name": "new", "tags": ["next"]}},
            state,
        )

    assert state["person"]["name"] == "old"
    assert state["person"]["tags"][0] == "seed"
    assert len(state["person"]["tags"]) == 1


def test_output_bindings_commit_to_staged_state_before_mutating_original() -> None:
    workflow = _workflow(
        fields={
            "person.name": StateField(type="string"),
            "blocked.child": StateField(type="string"),
        }
    )
    state = {"person": {"name": "old"}, "blocked": "not-an-object"}

    with pytest.raises(WorkflowExecutionError, match="cannot descend"):
        apply_output_bindings(
            workflow,
            [
                _binding("person.name", "state.person.name"),
                _binding("blocked.child", "state.blocked.child"),
            ],
            {"person": {"name": "new"}, "blocked": {"child": "value"}},
            state,
        )

    assert state["person"]["name"] == "old"
    assert state["blocked"] == "not-an-object"


def test_output_bindings_validate_exact_state_schema_before_mutation() -> None:
    workflow = _workflow(fields={"person.name": StateField(type="string")})
    state = {"person": {"name": "old"}}

    with pytest.raises(WorkflowExecutionError, match="state write state.person.name"):
        apply_output_bindings(
            workflow,
            [_binding("person.name", "state.person.name")],
            {"person": {"name": 7}},
            state,
        )

    assert state["person"]["name"] == "old"


def test_output_bindings_validate_declared_parent_schema_before_mutation() -> None:
    workflow = _workflow_from_state_schema(
        StateSchema.model_validate({
            "type": "object",
            "properties": {
                "person": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "additionalProperties": False,
                }
            },
        })
    )
    state = {"person": {"name": "old"}}

    with pytest.raises(WorkflowExecutionError, match="state write state.person"):
        apply_output_bindings(
            workflow,
            [_binding("person.extra", "state.person.extra")],
            {"person": {"extra": "bad"}},
            state,
        )

    assert state["person"] == {"name": "old"}


def test_full_workflow_execution_writes_canonical_output_bindings() -> None:
    workflow = _workflow_with_node()
    run = create_run_state(workflow, {})

    run = resume_workflow(
        workflow,
        run,
        {
            "rename": lambda _payload, _ctx: {
                "outcome": "ok",
                "output": {"person": {"name": "Ada"}},
            }
        },
    )

    assert run.state["person"]["name"] == "Ada"
    assert run.trace[0].state_changes["state.person.name"] == "Ada"


def _binding(source: str, target: str) -> OutputBinding:
    return OutputBinding.model_validate({"source": source, "target": target})


def _workflow(
    fields: dict[str, StateField] | None = None,
) -> Workflow:
    return _workflow_from_state_schema(
        StateSchema.from_field_map(
            fields
            or {
                "person": StateField(type="object"),
                "person.name": StateField(type="string"),
                "person.extra": StateField(type="string"),
            }
        )
    )


def _workflow_from_state_schema(state_schema: StateSchema) -> Workflow:
    return Workflow(
        name="patch",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=state_schema,
        output_schema=SchemaRef(type="object", properties={}),
        start="n",
        nodes=[],
        edges=[],
    )


def _workflow_with_node() -> Workflow:
    return Workflow(
        name="canonical_output",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map({
            "person.name": StateField(type="string")
        }),
        output_schema=SchemaRef(
            type="object", properties={"person": {"type": "object"}}
        ),
        node_defs=[
            NodeDef(
                name="rename",
                input_schema=SchemaRef(type="object", properties={}),
                output_schema=SchemaRef(
                    type="object",
                    properties={"person": {"type": "object"}},
                ),
                outcomes=["ok"],
            )
        ],
        start="rename",
        nodes=[
            NodeUse.model_validate({
                "id": "rename",
                "type": "node",
                "node": "rename",
                "output": [{"source": "person.name", "target": "state.person.name"}],
            })
        ],
        edges=[Edge.model_validate({"from": "rename", "outcome": "ok", "to": END})],
    )
