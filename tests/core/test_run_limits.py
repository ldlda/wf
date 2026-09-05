"""Run limit model and admission tests."""

from __future__ import annotations

from typing import Any, cast

import pytest

from wf_core import (
    END,
    Edge,
    NodeDef,
    NodeUse,
    RunLimits,
    SchemaRef,
    StateSchema,
    Workflow,
    WorkflowExecutionError,
)
from wf_core.errors import WorkflowStepLimitExceeded
from wf_core.runtime.limits import admit_step_attempt, remaining_step_attempts
from wf_core.runtime.ops.runs import create_run_state


def _minimal_workflow(name: str = "budget") -> Workflow:
    return Workflow(
        name=name,
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=StateSchema.from_field_map({}),
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[
            NodeDef(
                name="finish",
                input_schema=SchemaRef(type="object", properties={}),
                output_schema=SchemaRef(type="object", properties={}),
                outcomes=["ok"],
            )
        ],
        start="finish",
        nodes=[
            NodeUse.model_validate({"id": "finish", "type": "node", "node": "finish"})
        ],
        edges=[Edge.model_validate({"from": "finish", "outcome": "ok", "to": END})],
    )


def test_run_limits_default() -> None:
    limits = RunLimits()

    assert limits.max_steps == 10_000


def test_run_limits_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        RunLimits(max_steps=0)
    with pytest.raises(ValueError):
        RunLimits(max_steps=-3)


def test_run_limits_rejects_bool_and_non_int() -> None:
    with pytest.raises(TypeError):
        RunLimits(max_steps=cast(Any, True))
    with pytest.raises(TypeError):
        RunLimits(max_steps=cast(Any, False))
    with pytest.raises(TypeError):
        RunLimits(max_steps=cast(Any, "10"))
    with pytest.raises(TypeError):
        RunLimits(max_steps=cast(Any, 10.0))


def test_create_run_state_defaults_to_budget() -> None:
    workflow = _minimal_workflow()

    run = create_run_state(workflow, {})

    assert run.limits.max_steps == 10_000
    assert run.steps_executed == 0
    assert run.steps_remaining == 10_000
    assert run.current_frame().step_number is None
    assert remaining_step_attempts(run) == 10_000


def test_create_run_state_captures_limits() -> None:
    workflow = _minimal_workflow()
    limits = RunLimits(max_steps=5)

    run = create_run_state(workflow, {}, limits=limits)

    assert run.limits.max_steps == 5
    assert run.steps_remaining == 5


def test_budget_of_one() -> None:
    workflow = _minimal_workflow()
    limits = RunLimits(max_steps=1)
    run = create_run_state(workflow, {}, limits=limits)
    number = admit_step_attempt(run, run.current_frame(), workflow.start)

    assert number == 1
    assert run.steps_executed == 1
    assert run.steps_remaining == 0
    with pytest.raises(WorkflowStepLimitExceeded):
        admit_step_attempt(run, run.current_frame(), workflow.start)


def test_denied_admission_does_not_increment() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=1))
    admit_step_attempt(run, run.current_frame(), workflow.start)

    with pytest.raises(WorkflowStepLimitExceeded):
        admit_step_attempt(run, run.current_frame(), workflow.start)

    assert run.steps_executed == 1
    assert run.current_frame().step_number == 1
    assert run.steps_remaining == 0
    assert remaining_step_attempts(run) == 0


def test_admission_assigns_step_numbers() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=3))

    first = admit_step_attempt(run, run.current_frame(), workflow.start)
    second = admit_step_attempt(run, run.current_frame(), workflow.start)

    assert first == 1
    assert second == 2
    assert run.steps_executed == 2
    assert run.current_frame().step_number == 2
    assert run.steps_remaining == 1
    assert remaining_step_attempts(run) == 1


def test_step_limit_error_details() -> None:
    workflow = _minimal_workflow(name="budget_details")
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=1))
    frame = run.current_frame()
    admit_step_attempt(run, frame, workflow.start)

    with pytest.raises(WorkflowStepLimitExceeded) as exc_info:
        admit_step_attempt(run, frame, workflow.start)

    assert isinstance(exc_info.value, WorkflowExecutionError)
    message = str(exc_info.value)
    assert "budget_details" in message
    assert "1" in message
    assert frame.id in message
    assert frame.scope_id in message
    assert workflow.start in message


def test_remaining_never_negative() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=1))
    run.steps_executed = 5

    assert run.steps_remaining == 0
    assert remaining_step_attempts(run) == 0


def test_remaining_delegates_to_run_property() -> None:
    """`remaining_step_attempts` is the computed `steps_remaining` convenience."""
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=4))
    admit_step_attempt(run, run.current_frame(), workflow.start)

    assert remaining_step_attempts(run) == run.steps_remaining == 3
