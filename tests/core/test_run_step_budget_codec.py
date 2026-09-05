"""Step budget codec and migration tests."""

from __future__ import annotations

from typing import Any, cast

import pytest

from wf_core import (
    END,
    Edge,
    InterruptNode,
    NodeDef,
    NodeUse,
    RunLimits,
    SchemaRef,
    StateSchema,
    Workflow,
    dump_run_state,
    execute_workflow,
    load_run_state,
)
from wf_core.run_codec import load_run_state_with_upgrade
from wf_core.run_state import RunState
from wf_core.runtime.limits import admit_step_attempt
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


def _empty_schema() -> SchemaRef:
    return SchemaRef(type="object", properties={})


def _ok_handler(payload: dict[str, Any], _context: object) -> dict[str, Any]:
    return {"outcome": "ok", "output": {}}


def _interrupt_workflow() -> Workflow:
    return Workflow(
        name="interrupt_counts",
        input_schema=_empty_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_empty_schema(),
        outcomes=["ok"],
        node_defs=[
            NodeDef(
                name="work",
                input_schema=_empty_schema(),
                output_schema=_empty_schema(),
                outcomes=["ok"],
            )
        ],
        start="ask",
        nodes=[
            InterruptNode(id="ask", type="interrupt", kind="approval"),
            NodeUse(id="work", type="node", node="work"),
        ],
        edges=[
            Edge.model_validate({"from": "ask", "outcome": "submitted", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": END}),
        ],
    )


def _state_dict(stored: dict[str, object]) -> dict[str, Any]:
    return cast(dict[str, Any], stored["state"])


def _strip_to_v1(stored: dict[str, object]) -> dict[str, Any]:
    state = dict(_state_dict(stored))
    state.pop("limits", None)
    state.pop("steps_executed", None)
    frames = {
        frame_id: {key: value for key, value in frame.items() if key != "step_number"}
        for frame_id, frame in dict(cast(dict[str, Any], state["frames"])).items()
    }
    state["frames"] = frames
    return {"version": 1, "state": state}


def _strip_budget_fields(stored: dict[str, object]) -> dict[str, Any]:
    state = dict(_strip_to_v1(stored)["state"])
    state["trace"] = [
        {key: value for key, value in entry.items() if key != "step_number"}
        for entry in cast(list[dict[str, Any]], state.get("trace", []))
    ]
    if state.get("interrupt") is not None:
        state["interrupt"] = {
            key: value
            for key, value in cast(dict[str, Any], state["interrupt"]).items()
            if key != "step_number"
        }
    return {"version": 1, "state": state}


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
    _state_dict(stored).pop("limits")

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_missing_steps_executed_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {})
    stored = dump_run_state(run)
    _state_dict(stored).pop("steps_executed")

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_missing_frame_step_number_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {})
    stored = dump_run_state(run)
    del cast(dict[str, Any], _state_dict(stored)["frames"])["root"]["step_number"]

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v1_smuggled_budget_fields_receive_defaults() -> None:
    """V1 envelopes predate budgets; smuggled fields must not survive."""
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=7))
    stored = _strip_to_v1(dump_run_state(run))
    state = cast(dict[str, Any], stored["state"])
    state["limits"] = {"max_steps": 999_999}
    state["steps_executed"] = 999

    restored, upgraded = load_run_state_with_upgrade(stored)

    assert upgraded is True
    assert restored.limits.max_steps == 10_000
    assert restored.steps_executed == 0


def test_v2_bool_max_steps_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=2))
    stored = dump_run_state(run)
    _state_dict(stored)["limits"] = {"max_steps": True}

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_str_max_steps_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=2))
    stored = dump_run_state(run)
    _state_dict(stored)["limits"] = {"max_steps": "10"}

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_unknown_limits_field_is_corrupt() -> None:
    """Strict v2: unknown fields inside limits are corrupt, not preserved."""
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=2))
    stored = dump_run_state(run)
    _state_dict(stored)["limits"] = {"max_steps": 2, "future_quota": 99}

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_negative_steps_executed_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=2))
    stored = dump_run_state(run)
    _state_dict(stored)["steps_executed"] = -100

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_exceeding_steps_executed_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=2))
    stored = dump_run_state(run)
    _state_dict(stored)["steps_executed"] = 5

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_bool_steps_executed_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=2))
    stored = dump_run_state(run)
    _state_dict(stored)["steps_executed"] = True

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_incoherent_frame_step_number_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=2))
    admit_step_attempt(run, run.current_frame(), workflow.start)
    stored = dump_run_state(run)
    state = _state_dict(stored)
    frames = cast(dict[str, Any], state["frames"])
    cast(dict[str, Any], frames["root"])["step_number"] = 999

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_bool_frame_step_number_is_corrupt() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=2))
    admit_step_attempt(run, run.current_frame(), workflow.start)
    stored = dump_run_state(run)
    state = _state_dict(stored)
    frames = cast(dict[str, Any], state["frames"])
    cast(dict[str, Any], frames["root"])["step_number"] = True

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_pending_frame_none_number_round_trips() -> None:
    """Fresh V2 runs legitimately persist unadmitted (None) frame numbers."""
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=2))

    restored, upgraded = load_run_state_with_upgrade(dump_run_state(run))

    assert upgraded is False
    assert restored.steps_executed == 0
    assert restored.frames["root"].step_number is None


def test_v1_traces_and_interrupt_receive_none_step_numbers() -> None:
    workflow = _interrupt_workflow()
    run = execute_workflow(workflow, {}, {"work": _ok_handler})
    stored = _strip_budget_fields(dump_run_state(run))

    restored, upgraded = load_run_state_with_upgrade(stored)

    assert upgraded is True
    assert restored.trace[0].step_number is None
    assert restored.interrupt is not None
    assert restored.interrupt.step_number is None


def test_v2_missing_trace_step_number_is_corrupt() -> None:
    workflow = _interrupt_workflow()
    run = execute_workflow(workflow, {}, {"work": _ok_handler})
    stored = dump_run_state(run)
    del cast(dict[str, Any], cast(list[Any], _state_dict(stored)["trace"])[0])[
        "step_number"
    ]

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_missing_interrupt_step_number_is_corrupt() -> None:
    workflow = _interrupt_workflow()
    run = execute_workflow(workflow, {}, {"work": _ok_handler})
    stored = dump_run_state(run)
    del cast(dict[str, Any], _state_dict(stored)["interrupt"])["step_number"]

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_restored_run_state_type() -> None:
    workflow = _minimal_workflow()
    run = create_run_state(workflow, {})

    restored = load_run_state(dump_run_state(run))

    assert isinstance(restored, RunState)
