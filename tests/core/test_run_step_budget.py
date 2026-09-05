from __future__ import annotations

import pytest

from wf_core import (
    END,
    ConditionNode,
    Edge,
    EndNode,
    ForeachNode,
    InterruptNode,
    NodeDef,
    NodeUse,
    PreparedSubgraph,
    ReducerRef,
    RunStatus,
    SchemaRef,
    StateField,
    StateSchema,
    SubgraphNode,
    Workflow,
    WorkflowExecutionError,
    dump_run_state,
    execute_workflow,
    load_run_state,
    resume_workflow,
    step_workflow,
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


# --- Task 2: sync dispatch and trace numbering ---


def _empty_schema() -> SchemaRef:
    return SchemaRef(type="object", properties={})


def _ok_handler(payload: dict, _context: object) -> dict:
    return {"outcome": "ok", "output": {}}


def _trace_numbers(run) -> list:
    return [entry.step_number for entry in run.trace]


def _chain_workflow() -> Workflow:
    defs = [
        NodeDef(
            name="da",
            input_schema=_empty_schema(),
            output_schema=_empty_schema(),
            outcomes=["ok"],
        ),
        NodeDef(
            name="db",
            input_schema=_empty_schema(),
            output_schema=_empty_schema(),
            outcomes=["ok"],
        ),
    ]
    return Workflow(
        name="chain",
        input_schema=_empty_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_empty_schema(),
        outcomes=["ok"],
        node_defs=defs,
        start="a",
        nodes=[
            NodeUse(id="a", type="node", node="da"),
            NodeUse(id="b", type="node", node="db"),
        ],
        edges=[
            Edge.model_validate({"from": "a", "outcome": "ok", "to": "b"}),
            Edge.model_validate({"from": "b", "outcome": "ok", "to": END}),
        ],
    )


def test_sync_node_use_counts_and_numbers_trace() -> None:
    workflow = _chain_workflow()

    run = execute_workflow(workflow, {}, {"da": _ok_handler, "db": _ok_handler})

    assert run.status == RunStatus.COMPLETED
    assert run.steps_executed == 2
    assert _trace_numbers(run) == [1, 2]
    assert [entry.node_id for entry in run.trace] == ["a", "b"]
    assert run.steps_remaining == 10_000 - 2


def test_sync_condition_counts() -> None:
    workflow = Workflow(
        name="condition_counts",
        input_schema=SchemaRef(
            type="object", properties={"count": {"type": "integer"}}
        ),
        state_schema=StateSchema.from_field_map({"count": StateField(type="integer")}),
        output_schema=_empty_schema(),
        outcomes=["ok"],
        node_defs=[
            NodeDef(
                name="finish",
                input_schema=_empty_schema(),
                output_schema=_empty_schema(),
                outcomes=["done"],
            )
        ],
        start="pick",
        nodes=[
            ConditionNode.model_validate(
                {
                    "id": "pick",
                    "type": "condition",
                    "check": {
                        "op": "lt",
                        "left": {"path": "state.count"},
                        "right": {"value": 1},
                    },
                }
            ),
            NodeUse(id="finish", type="node", node="finish"),
        ],
        edges=[
            Edge.model_validate({"from": "pick", "outcome": "true", "to": "finish"}),
            Edge.model_validate({"from": "pick", "outcome": "false", "to": END}),
            Edge.model_validate({"from": "finish", "outcome": "done", "to": END}),
        ],
    )

    run = execute_workflow(workflow, {"count": 10}, {"finish": _ok_handler})

    assert run.status == RunStatus.COMPLETED
    assert run.steps_executed == 1
    assert _trace_numbers(run) == [1]
    assert run.trace[0].node_id == "pick"
    assert run.trace[0].outcome == "false"


def _serial_foreach_workflow() -> Workflow:
    foreach = ForeachNode.model_validate(
        {
            "id": "each",
            "type": "foreach",
            "over": "state.items",
            "as": "item",
            "mode": "serial",
        }
    )
    return Workflow(
        name="foreach_counts",
        input_schema=SchemaRef(type="object", properties={"items": {"type": "array"}}),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array", reducer=ReducerRef(name="wf.std.append")
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="record",
                input_schema=SchemaRef(
                    type="object", properties={"value": {}}, required=["value"]
                ),
                output_schema=SchemaRef(
                    type="object", properties={"seen": {}}, required=["seen"]
                ),
                outcomes=["ok"],
            )
        ],
        start="each",
        nodes=[
            foreach,
            NodeUse.model_validate(
                {
                    "id": "work",
                    "type": "node",
                    "node": "record",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "work"}),
            Edge.model_validate({"from": "work", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )


def test_sync_foreach_controller_and_body_share_counter() -> None:
    workflow = _serial_foreach_workflow()

    run = execute_workflow(
        workflow,
        {"items": ["a", "b"]},
        {
            "record": lambda payload, _ctx: {
                "outcome": "ok",
                "output": {"seen": payload["value"]},
            }
        },
    )

    assert run.status == RunStatus.COMPLETED
    assert run.steps_executed == 5
    assert _trace_numbers(run) == [1, 2, 3, 4, 5]
    assert [entry.node_id for entry in run.trace] == [
        "each",
        "work",
        "each",
        "work",
        "each",
    ]
    assert [entry.outcome for entry in run.trace] == [
        "loop",
        "ok",
        "loop",
        "ok",
        "done",
    ]


def _subgraph_parent_workflow() -> Workflow:
    node = SubgraphNode.model_validate(
        {
            "id": "child",
            "type": "subgraph",
            "workflow": "child.workflow",
            "input_schema": _empty_schema(),
            "output_schema": _empty_schema(),
            "input": [],
            "output": [],
        }
    )
    return Workflow(
        name="subgraph_parent",
        input_schema=_empty_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_empty_schema(),
        outcomes=["ok"],
        start="child",
        nodes=[node],
        edges=[Edge.model_validate({"from": "child", "outcome": "ok", "to": END})],
    )


def _subgraph_child_workflow() -> Workflow:
    return Workflow(
        name="child.workflow",
        input_schema=_empty_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_empty_schema(),
        outcomes=["ok"],
        node_defs=[
            NodeDef(
                name="answer",
                input_schema=_empty_schema(),
                output_schema=_empty_schema(),
                outcomes=["ok"],
            )
        ],
        start="answer",
        nodes=[NodeUse(id="answer", type="node", node="answer")],
        edges=[Edge.model_validate({"from": "answer", "outcome": "ok", "to": END})],
    )


def test_sync_subgraph_entry_and_return_share_counter() -> None:
    parent = _subgraph_parent_workflow()
    child = _subgraph_child_workflow()

    run = execute_workflow(
        parent,
        {},
        {},
        subgraphs={
            "child.workflow": PreparedSubgraph(
                workflow=child, registry={"answer": _ok_handler}
            )
        },
    )

    assert run.status == RunStatus.COMPLETED
    # Parent entry admits once without emitting a trace (gap), the child body
    # admits once, and the parent return admits once more.
    assert run.steps_executed == 3
    assert _trace_numbers(run) == [2, 3]
    assert run.trace[0].node_id == "answer"
    assert run.trace[-1].node_id == "child"


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


def test_sync_interrupt_activation_counts_once() -> None:
    workflow = _interrupt_workflow()

    run = execute_workflow(workflow, {}, {"work": _ok_handler})

    assert run.status == RunStatus.INTERRUPTED
    assert run.steps_executed == 1
    assert _trace_numbers(run) == [1]
    assert run.trace[0].outcome == "interrupt"
    assert run.interrupt is not None
    assert run.interrupt.step_number == 1


def test_sync_interrupt_resume_reuses_activation_number() -> None:
    workflow = _interrupt_workflow()
    interrupted = execute_workflow(workflow, {}, {"work": _ok_handler})

    resumed = resume_workflow(
        workflow,
        interrupted,
        {"work": _ok_handler},
        resume_payload={},
        resume_outcome="submitted",
    )

    assert resumed.status == RunStatus.COMPLETED
    # Resume completes the admitted activation without a new attempt: both the
    # interrupt entry and its completion entry carry number 1.
    assert resumed.steps_executed == 2
    assert _trace_numbers(resumed) == [1, 1, 2]
    assert resumed.trace[1].node_id == "ask"
    assert resumed.trace[1].outcome == "submitted"
    assert resumed.interrupt is None


def test_sync_explicit_end_counts() -> None:
    workflow = Workflow(
        name="explicit_end",
        input_schema=_empty_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_empty_schema(),
        outcomes=["done"],
        node_defs=[
            NodeDef(
                name="finish",
                input_schema=_empty_schema(),
                output_schema=_empty_schema(),
                outcomes=["done"],
            )
        ],
        start="finish",
        nodes=[
            NodeUse(id="finish", type="node", node="finish"),
            EndNode(id="end", type="end", outcome="done"),
        ],
        edges=[Edge.model_validate({"from": "finish", "outcome": "done", "to": "end"})],
    )

    def finish(_payload: dict, _context: object) -> dict:
        return {"outcome": "done", "output": {}}

    run = execute_workflow(workflow, {}, {"finish": finish})

    assert run.status == RunStatus.COMPLETED
    assert run.outcome == "done"
    assert run.steps_executed == 2
    assert _trace_numbers(run) == [1, 2]
    assert run.trace[-1].step_type == "end"


def test_sync_legacy_end_creates_no_extra_attempt() -> None:
    workflow = _minimal_workflow()

    run = execute_workflow(workflow, {}, {"finish": _ok_handler})

    assert run.status == RunStatus.COMPLETED
    assert run.steps_executed == 1
    assert _trace_numbers(run) == [1]


def test_sync_handler_failure_consumes_attempt() -> None:
    workflow = _minimal_workflow()

    def explode(_payload: dict, _context: object) -> dict:
        raise ValueError("boom")

    run = create_run_state(workflow, {})
    with pytest.raises(ValueError, match="boom"):
        step_workflow(workflow, run, {"finish": explode})

    assert run.steps_executed == 1
    # The attempt failed before any normal trace entry existed (gap, not a recount).
    assert run.trace == []


def test_sync_handled_error_outcome_counts_once() -> None:
    workflow = Workflow(
        name="error_outcome",
        input_schema=_empty_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_empty_schema(),
        outcomes=["ok"],
        node_defs=[
            NodeDef(
                name="risky",
                input_schema=_empty_schema(),
                output_schema=_empty_schema(),
                outcomes=["ok", "error"],
            )
        ],
        start="work",
        nodes=[NodeUse(id="work", type="node", node="risky")],
        edges=[
            Edge.model_validate({"from": "work", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "work", "outcome": "error", "to": END}),
        ],
    )

    def fail_soft(_payload: dict, _context: object) -> dict:
        return {"outcome": "error", "output": {}}

    run = execute_workflow(workflow, {}, {"risky": fail_soft})

    assert run.status == RunStatus.COMPLETED
    assert run.steps_executed == 1
    assert _trace_numbers(run) == [1]
    assert run.trace[0].outcome == "error"


def _cyclic_workflow() -> Workflow:
    defs = [
        NodeDef(
            name="da",
            input_schema=_empty_schema(),
            output_schema=_empty_schema(),
            outcomes=["ok"],
        ),
        NodeDef(
            name="db",
            input_schema=_empty_schema(),
            output_schema=_empty_schema(),
            outcomes=["ok"],
        ),
    ]
    return Workflow(
        name="cycle",
        input_schema=_empty_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_empty_schema(),
        outcomes=["ok"],
        node_defs=defs,
        start="a",
        nodes=[
            NodeUse(id="a", type="node", node="da"),
            NodeUse(id="b", type="node", node="db"),
        ],
        edges=[
            Edge.model_validate({"from": "a", "outcome": "ok", "to": "b"}),
            Edge.model_validate({"from": "b", "outcome": "ok", "to": "a"}),
        ],
    )


def test_sync_closed_cycle_fails_at_limit() -> None:
    workflow = _cyclic_workflow()
    calls: list[str] = []

    def make(name: str):  # type: ignore[no-untyped-def]
        def handler(_payload: dict, _context: object) -> dict:
            calls.append(name)
            return {"outcome": "ok", "output": {}}

        return handler

    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=3))

    # Bounded manual stepping: without a budget this cycle would never stop,
    # so the test itself caps iterations instead of relying on the engine loop.
    with pytest.raises(WorkflowStepLimitExceeded):
        for _ in range(10):
            step_workflow(workflow, run, {"da": make("a"), "db": make("b")})

    assert run.steps_executed == 3
    assert _trace_numbers(run) == [1, 2, 3]
    assert calls == ["a", "b", "a"]


def _counting_loop_workflow() -> Workflow:
    return Workflow(
        name="counting_loop",
        input_schema=SchemaRef(
            type="object", properties={"count": {"type": "integer"}}
        ),
        state_schema=StateSchema.from_field_map({"count": StateField(type="integer")}),
        output_schema=_empty_schema(),
        outcomes=["ok"],
        node_defs=[
            NodeDef(
                name="bump",
                input_schema=SchemaRef(
                    type="object", properties={"count": {"type": "integer"}}
                ),
                output_schema=SchemaRef(
                    type="object", properties={"count": {"type": "integer"}}
                ),
                outcomes=["ok"],
            )
        ],
        start="again",
        nodes=[
            ConditionNode.model_validate(
                {
                    "id": "again",
                    "type": "condition",
                    "check": {
                        "op": "lt",
                        "left": {"path": "state.count"},
                        "right": {"value": 2},
                    },
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "bump",
                    "type": "node",
                    "node": "bump",
                    "input": [{"target": "count", "path": "state.count"}],
                    "output": [{"source": "count", "target": "state.count"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "again", "outcome": "true", "to": "bump"}),
            Edge.model_validate({"from": "bump", "outcome": "ok", "to": "again"}),
            Edge.model_validate({"from": "again", "outcome": "false", "to": END}),
        ],
    )


def test_sync_exiting_loop_completes_within_budget() -> None:
    workflow = _counting_loop_workflow()

    def bump(payload: dict, _context: object) -> dict:
        count = payload.get("count", 0)
        assert isinstance(count, int)
        return {"outcome": "ok", "output": {"count": count + 1}}

    run = execute_workflow(workflow, {"count": 0}, {"bump": bump})

    assert run.status == RunStatus.COMPLETED
    assert run.steps_executed == 5
    assert _trace_numbers(run) == [1, 2, 3, 4, 5]


def test_sync_denial_never_invokes_handler() -> None:
    workflow = _chain_workflow()
    b_calls: list[dict] = []

    def b_handler(payload: dict, _context: object) -> dict:
        b_calls.append(payload)
        return {"outcome": "ok", "output": {}}

    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=1))

    with pytest.raises(WorkflowStepLimitExceeded):
        resume_workflow(workflow, run, {"da": _ok_handler, "db": b_handler})

    assert run.steps_executed == 1
    assert _trace_numbers(run) == [1]
    assert b_calls == []


def _strip_budget_fields(stored: dict) -> dict:
    state = dict(_strip_to_v1(stored)["state"])
    state["trace"] = [
        {key: value for key, value in entry.items() if key != "step_number"}
        for entry in state.get("trace", [])
    ]
    if state.get("interrupt") is not None:
        state["interrupt"] = {
            key: value
            for key, value in state["interrupt"].items()
            if key != "step_number"
        }
    return {"version": 1, "state": state}


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
    del stored["state"]["trace"][0]["step_number"]

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)


def test_v2_missing_interrupt_step_number_is_corrupt() -> None:
    workflow = _interrupt_workflow()
    run = execute_workflow(workflow, {}, {"work": _ok_handler})
    stored = dump_run_state(run)
    del stored["state"]["interrupt"]["step_number"]

    with pytest.raises(ValueError):
        load_run_state_with_upgrade(stored)
