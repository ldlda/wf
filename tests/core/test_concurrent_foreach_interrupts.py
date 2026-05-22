from __future__ import annotations

import asyncio
from typing import Any

from wf_core import (
    END,
    Edge,
    ForeachNode,
    InterruptNode,
    NodeDef,
    NodeUse,
    ReducerRef,
    RunStatus,
    SchemaRef,
    StateField,
    StateSchema,
    Workflow,
    execute_workflow_async,
    resume_workflow_async,
)


def test_concurrent_foreach_interrupt_returns_before_refill() -> None:
    asyncio.run(_assert_concurrent_foreach_interrupt_returns_before_refill())


async def _assert_concurrent_foreach_interrupt_returns_before_refill() -> None:
    run = await execute_workflow_async(
        _workflow(),
        {"items": ["a", "b", "c"]},
        {"route": _interrupt_on_b},
    )

    assert run.status is RunStatus.INTERRUPTED
    assert run.interrupt is not None
    assert run.interrupt.payload["item"] == "b"
    assert run.frames["root:each:1"].status == "interrupted"
    assert "root:each:2" not in run.frames
    assert "seen" not in run.state


def test_resume_prioritizes_interrupted_item_before_siblings() -> None:
    asyncio.run(_assert_resume_prioritizes_interrupted_item_before_siblings())


async def _assert_resume_prioritizes_interrupted_item_before_siblings() -> None:
    workflow = _workflow()
    run = await execute_workflow_async(
        workflow,
        {"items": ["a", "b", "c"]},
        {"route": _interrupt_on_b},
    )
    interrupted_trace_len = len(run.trace)

    resumed = await resume_workflow_async(
        workflow,
        run,
        {"route": _interrupt_on_b},
        resume_payload={},
    )

    assert resumed.status is RunStatus.COMPLETED
    assert resumed.state["seen"] == ["a", "b", "c"]
    assert resumed.trace[interrupted_trace_len].frame_id == "root:each:1"
    assert resumed.trace[interrupted_trace_len].step_type == "interrupt"
    assert resumed.trace[interrupted_trace_len].outcome == "submitted"
    foreach_entries = [entry for entry in resumed.trace if entry.step_type == "foreach"]
    assert foreach_entries[-1].state_changes["state.seen"] == ["a", "b", "c"]


async def _interrupt_on_b(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
    await asyncio.sleep(0.01 if payload["value"] == "a" else 0.02)
    outcome = "needs_input" if payload["value"] == "b" else "ok"
    return {"outcome": outcome, "output": {"seen": payload["value"]}}


def _workflow() -> Workflow:
    return Workflow(
        name="concurrent_foreach_interrupts",
        input_schema=SchemaRef(
            type="object",
            properties={"items": {"type": "array"}},
        ),
        state_schema=StateSchema.from_field_map(
            {
                "items": StateField(type="array"),
                "seen": StateField(
                    type="array",
                    reducer=ReducerRef(name="wf.std.append"),
                ),
            }
        ),
        output_schema=SchemaRef(type="object", properties={"seen": {"type": "array"}}),
        node_defs=[
            NodeDef(
                name="route",
                input_schema=SchemaRef(
                    type="object",
                    properties={"value": {}},
                    required=["value"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"seen": {}},
                    required=["seen"],
                ),
                outcomes=["ok", "needs_input"],
            )
        ],
        start="each",
        nodes=[
            ForeachNode.model_validate(
                {
                    "id": "each",
                    "type": "foreach",
                    "over": "state.items",
                    "as": "item",
                    "mode": "concurrent",
                    "concurrent": {"max_active": 2, "max_outstanding": 2},
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "route",
                    "type": "node",
                    "node": "route",
                    "input": [{"target": "value", "path": "context.item"}],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
            InterruptNode.model_validate(
                {
                    "id": "ask",
                    "type": "interrupt",
                    "kind": "approval",
                    "request": [{"target": "item", "path": "context.item"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "route"}),
            Edge.model_validate({"from": "route", "outcome": "ok", "to": END}),
            Edge.model_validate(
                {
                    "from": "route",
                    "outcome": "needs_input",
                    "to": "ask",
                }
            ),
            Edge.model_validate({"from": "ask", "outcome": "submitted", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
