from __future__ import annotations

import pytest

from wf_core import (
    END,
    Edge,
    NodeDef,
    NodeUse,
    SchemaRef,
    StateSchema,
    Workflow,
    WorkflowExecutionError,
    dump_run_state,
    load_run_state,
)
from wf_core.errors import WorkflowStepLimitExceeded
from wf_core.run_codec import load_run_state_with_upgrade
from wf_core.runtime.limits import (
    RunLimits,
    admit_step_attempt,
    remaining_step_attempts,
)
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
        RunLimits(max_steps=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        RunLimits(max_steps=False)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        RunLimits(max_steps="10")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        RunLimits(max_steps=10.0)  # type: ignore[arg-type]


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


def test_dump_writes_v2_envelope() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=7))
    admit_step_attempt(run, run.current_frame(), workflow.start)

    stored = dump_run_state(run)

    assert stored["version"] == 2


def test_v2_round_trip() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=7))
    admit_step_attempt(run, run.current_frame(), workflow.start)

    stored = dump_run_state(run)
    restored, upgraded = load_run_state_with_upgrade(stored)

    assert upgraded is False
    assert restored.limits.max_steps == 7
    assert restored.steps_executed == 1
    assert restored.steps_remaining == 6
    assert restored.frames["root"].step_number == 1

    via_legacy = load_run_state(stored)
    assert via_legacy.limits.max_steps == 7
    assert via_legacy.steps_executed == 1
    assert via_legacy.frames["root"].step_number == 1


def _strip_to_v1(stored: dict) -> dict:
    state = dict(stored["state"])
    state.pop("limits", None)
    state.pop("steps_executed", None)
    frames = {
        frame_id: {key: value for key, value in frame.items() if key != "step_number"}
        for frame_id, frame in dict(state["frames"]).items()
    }
    state["frames"] = frames
    return {"version": 1, "state": state}


def test_v1_payload_receives_defaults_once() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=7))
    stored = _strip_to_v1(dump_run_state(run))

    restored, upgraded = load_run_state_with_upgrade(stored)

    assert upgraded is True
    assert restored.limits.max_steps == 10_000
    assert restored.steps_executed == 0
    assert restored.steps_remaining == 10_000
    assert restored.frames["root"].step_number is None

    via_legacy = load_run_state(stored)
    assert via_legacy.limits.max_steps == 10_000
    assert via_legacy.steps_executed == 0


def test_v2_missing_limits_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {})
    stored = dump_run_state(run)
    stored["state"].pop("limits")

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_missing_steps_executed_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {})
    stored = dump_run_state(run)
    stored["state"].pop("steps_executed")

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_missing_frame_step_number_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {})
    stored = dump_run_state(run)
    del stored["state"]["frames"]["root"]["step_number"]

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)
