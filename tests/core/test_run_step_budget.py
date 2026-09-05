"""Sync step-budget dispatch tests.

Covers run-wide counting for every current step kind, trace numbering,
and the engine-level limits seam. Model/admission unit tests live in
`test_run_limits.py`; codec and migration tests live in
`test_run_step_budget_codec.py`.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

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
    RunLimits,
    RunStatus,
    SchemaRef,
    StateField,
    StateSchema,
    SubgraphNode,
    Workflow,
    execute_workflow,
    execute_workflow_async,
    execute_workflow_result_async,
    resume_workflow,
    resume_workflow_async,
    resume_workflow_result_async,
    step_workflow,
)
from wf_core.errors import WorkflowStepLimitExceeded
from wf_core.run_state import RunState
from wf_core.runtime.ops.runs import create_run_state
from wf_core.runtime.preparation import prepare_resume


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


def _trace_numbers(run: RunState) -> list[int | None]:
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

    def record(payload: dict[str, Any], _context: object) -> dict[str, Any]:
        return {"outcome": "ok", "output": {"seen": payload["value"]}}

    run = execute_workflow(workflow, {"items": ["a", "b"]}, {"record": record})

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

    def finish(_payload: dict[str, Any], _context: object) -> dict[str, Any]:
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

    def explode(_payload: dict[str, Any], _context: object) -> dict[str, Any]:
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

    def fail_soft(_payload: dict[str, Any], _context: object) -> dict[str, Any]:
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

    def make(
        name: str,
    ) -> Callable[[dict[str, Any], object], dict[str, Any]]:
        def handler(_payload: dict[str, Any], _context: object) -> dict[str, Any]:
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

    def bump(payload: dict[str, Any], _context: object) -> dict[str, Any]:
        count = payload.get("count", 0)
        assert isinstance(count, int)
        return {"outcome": "ok", "output": {"count": count + 1}}

    run = execute_workflow(workflow, {"count": 0}, {"bump": bump})

    assert run.status == RunStatus.COMPLETED
    assert run.steps_executed == 5
    assert _trace_numbers(run) == [1, 2, 3, 4, 5]


def test_sync_denial_never_invokes_handler() -> None:
    workflow = _chain_workflow()
    b_calls: list[dict[str, Any]] = []

    def b_handler(payload: dict[str, Any], _context: object) -> dict[str, Any]:
        b_calls.append(payload)
        return {"outcome": "ok", "output": {}}

    run = create_run_state(workflow, {}, limits=RunLimits(max_steps=1))

    with pytest.raises(WorkflowStepLimitExceeded):
        resume_workflow(workflow, run, {"da": _ok_handler, "db": b_handler})

    assert run.steps_executed == 1
    assert _trace_numbers(run) == [1]
    assert b_calls == []


def test_execute_workflow_accepts_explicit_limits() -> None:
    workflow = _chain_workflow()

    run = execute_workflow(
        workflow,
        {},
        {"da": _ok_handler, "db": _ok_handler},
        limits=RunLimits(max_steps=10),
    )

    assert run.status == RunStatus.COMPLETED
    assert run.limits.max_steps == 10
    assert run.steps_executed == 2
    assert run.steps_remaining == 8


def test_execute_workflow_defaults_to_ten_thousand() -> None:
    workflow = _chain_workflow()

    run = execute_workflow(workflow, {}, {"da": _ok_handler, "db": _ok_handler})

    assert run.limits.max_steps == 10_000
    assert run.steps_executed == 2


def test_execute_workflow_enforces_limits() -> None:
    workflow = _cyclic_workflow()

    def ok_handler(_payload: dict[str, Any], _context: object) -> dict[str, Any]:
        return {"outcome": "ok", "output": {}}

    with pytest.raises(WorkflowStepLimitExceeded):
        execute_workflow(
            workflow,
            {},
            {"da": ok_handler, "db": ok_handler},
            limits=RunLimits(max_steps=2),
        )


async def test_execute_workflow_async_accepts_explicit_limits() -> None:
    workflow = _chain_workflow()

    async def ok_async(_payload: dict[str, Any], _context: object) -> dict[str, Any]:
        return {"outcome": "ok", "output": {}}

    run = await execute_workflow_async(
        workflow,
        {},
        {"da": ok_async, "db": ok_async},
        limits=RunLimits(max_steps=10),
    )

    assert run.status == RunStatus.COMPLETED
    assert run.limits.max_steps == 10
    assert run.steps_executed == 2
    assert run.steps_remaining == 8


async def test_execute_workflow_result_async_reports_exhaustion() -> None:
    workflow = _cyclic_workflow()

    async def ok_async(_payload: dict[str, Any], _context: object) -> dict[str, Any]:
        return {"outcome": "ok", "output": {}}

    run = await execute_workflow_result_async(
        workflow,
        {},
        {"da": ok_async, "db": ok_async},
        limits=RunLimits(max_steps=2),
    )

    assert run.status == RunStatus.FAILED
    assert run.limits.max_steps == 2
    assert run.steps_executed == 2
    assert "step budget" in (run.error or "")


def test_resume_entry_points_accept_no_replacement_limits() -> None:
    """Ordinary resume reuses persisted limits; it never takes new ones."""
    for entry in (
        resume_workflow,
        resume_workflow_async,
        resume_workflow_result_async,
        prepare_resume,
    ):
        assert "limits" not in inspect.signature(entry).parameters
