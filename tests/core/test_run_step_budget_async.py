"""Async step-budget reservation tests (Task 3).

Covers deterministic async batch reservation: bound claims by remaining
budget, admit in ready-queue order before launching handlers, keep
reservations after failure, settle siblings before raising, and discard
later sibling commits after the first unhandled result in reservation order.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from wf_core import (
    END,
    Edge,
    ForeachNode,
    FrameStatus,
    NodeDef,
    NodeUse,
    ReducerRef,
    RunLimits,
    RunStatus,
    SchemaRef,
    StateField,
    StateSchema,
    Workflow,
    execute_workflow,
    execute_workflow_async,
    step_workflow_async,
)
from wf_core.errors import WorkflowStepLimitExceeded
from wf_core.runtime.limits import remaining_step_attempts
from wf_core.runtime.ops.runs import create_run_state
from wf_core.runtime.preparation import prepare_new_run, prepare_resume


async def _noop_record(payload: dict[str, Any], _context: object) -> dict[str, Any]:
    return {"outcome": "ok", "output": payload}


def _sync_noop_record(payload: dict[str, Any], _context: object) -> dict[str, Any]:
    return {"outcome": "ok", "output": payload}


def _concurrent_workflow(*, max_active: int, name: str = "async_budget") -> Workflow:
    return Workflow(
        name=name,
        input_schema=SchemaRef(type="object", properties={"items": {"type": "array"}}),
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
                name="record",
                input_schema=SchemaRef(
                    type="object",
                    properties={"value": {}, "seen": {}},
                    required=["value", "seen"],
                ),
                output_schema=SchemaRef(
                    type="object",
                    properties={"value": {}, "seen": {}},
                    required=["seen"],
                ),
                outcomes=["ok"],
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
                    "concurrent": {
                        "max_active": max_active,
                        "max_outstanding": max_active,
                    },
                }
            ),
            NodeUse.model_validate(
                {
                    "id": "record",
                    "type": "node",
                    "node": "record",
                    "input": [
                        {"target": "value", "path": "context.item"},
                        {"target": "seen", "path": "context.item"},
                    ],
                    "output": [{"source": "seen", "target": "state.seen"}],
                }
            ),
        ],
        edges=[
            Edge.model_validate({"from": "each", "outcome": "loop", "to": "record"}),
            Edge.model_validate({"from": "record", "outcome": "ok", "to": "each"}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )


def _prepare_limited_run(workflow: Workflow, items: list[Any], *, max_steps: int):
    run = create_run_state(
        workflow, {"items": items}, limits=RunLimits(max_steps=max_steps)
    )
    prepare_new_run(workflow, {"items": items}, run)
    index = prepare_resume(
        workflow, run, resume_payload=None, resume_outcome="submitted"
    )
    assert index is not None
    return run, index


async def _wait_for(predicate: Callable[[], bool], *, timeout: float = 2.0) -> None:
    async def _poll() -> None:
        while not predicate():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_poll(), timeout)


async def test_async_batch_bounded_to_remaining_budget() -> None:
    """A 3-unit remainder starts only the first 3 of 5 eligible frames."""
    workflow = _concurrent_workflow(max_active=5, name="async_bounded")
    items = ["a", "b", "c", "d", "e"]
    run, index = _prepare_limited_run(workflow, items, max_steps=4)

    await step_workflow_async(workflow, run, {"record": _noop_record}, index=index)
    assert run.steps_executed == 1
    assert remaining_step_attempts(run) == 3
    assert run.ready_frame_ids == [f"root:each#0:{i}" for i in range(5)]

    release = asyncio.Event()
    started: list[str] = []

    async def record(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        started.append(payload["value"])
        await release.wait()
        return {"outcome": "ok", "output": payload}

    batch = asyncio.create_task(
        step_workflow_async(workflow, run, {"record": record}, index=index)
    )
    try:
        # The first three in ready-queue order start while gated; the other
        # two must never start because only three units remain.
        await _wait_for(lambda: len(started) == 3)
        assert started == ["a", "b", "c"]
        await asyncio.sleep(0.05)
        assert started == ["a", "b", "c"]

        # Unclaimed siblings stay PENDING in their original ready-queue order
        # while the admitted batch is still in flight.
        assert run.frames["root:each#0:3"].status == FrameStatus.PENDING
        assert run.frames["root:each#0:4"].status == FrameStatus.PENDING
        assert run.frames["root:each#0:3"].step_number is None
        assert run.frames["root:each#0:4"].step_number is None
        unclaimed = [fid for fid in run.ready_frame_ids if fid.endswith((":3", ":4"))]
        assert unclaimed == ["root:each#0:3", "root:each#0:4"]
    finally:
        release.set()
    await batch

    # Numbers follow ready-queue order, reservations are consumed.
    assert run.steps_executed == 4
    assert remaining_step_attempts(run) == 0
    assert run.frames["root:each#0:0"].step_number == 2
    assert run.frames["root:each#0:1"].step_number == 3
    assert run.frames["root:each#0:2"].step_number == 4
    assert run.frames["root:each#0:3"].step_number is None
    assert run.frames["root:each#0:4"].step_number is None
    assert run.frames["root:each#0:3"].status == FrameStatus.PENDING
    assert run.frames["root:each#0:4"].status == FrameStatus.PENDING
    batch_numbers = [
        entry.step_number
        for entry in run.trace
        if entry.frame_id.startswith("root:each#0:")
    ]
    assert batch_numbers == [2, 3, 4]


async def test_async_batch_denies_first_when_remaining_zero() -> None:
    """With no remainder the first admission raises before any handler runs."""
    workflow = _concurrent_workflow(max_active=5, name="async_zero_remainder")
    items = ["a", "b", "c"]
    run, index = _prepare_limited_run(workflow, items, max_steps=1)

    await step_workflow_async(workflow, run, {"record": _noop_record}, index=index)
    assert run.steps_executed == 1
    assert remaining_step_attempts(run) == 0

    started: list[str] = []

    async def record(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        started.append(payload["value"])
        return {"outcome": "ok", "output": payload}

    with pytest.raises(WorkflowStepLimitExceeded):
        await step_workflow_async(workflow, run, {"record": record}, index=index)

    assert started == []
    assert run.steps_executed == 1
    # Nothing was claimed: the popped first frame stays RUNNING without a
    # number, every eligible sibling stays PENDING in queue order.
    assert run.frames["root:each#0:0"].status == FrameStatus.RUNNING
    assert run.frames["root:each#0:0"].step_number is None
    assert run.ready_frame_ids == [f"root:each#0:{i}" for i in range(1, 3)]
    for i in range(1, 3):
        frame = run.frames[f"root:each#0:{i}"]
        assert frame.status == FrameStatus.PENDING
        assert frame.step_number is None


async def test_async_batch_numbers_follow_queue_order_not_completion() -> None:
    """Step numbers and trace order follow reservation, not completion order."""
    workflow = _concurrent_workflow(max_active=3, name="async_queue_order")
    items = ["a", "b", "c"]
    run, index = _prepare_limited_run(workflow, items, max_steps=20)

    await step_workflow_async(workflow, run, {"record": _noop_record}, index=index)
    assert run.steps_executed == 1

    allow_a = asyncio.Event()
    started: list[str] = []
    finished: list[str] = []

    async def record(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        value = payload["value"]
        started.append(value)
        if value == "a":
            # Gate the queue-first item so it finishes last even though it
            # was admitted first.
            await allow_a.wait()
        else:
            await asyncio.sleep(0.01)
        finished.append(value)
        return {"outcome": "ok", "output": payload}

    batch = asyncio.create_task(
        step_workflow_async(workflow, run, {"record": record}, index=index)
    )
    try:
        await _wait_for(lambda: len(started) == 3)
        assert started == ["a", "b", "c"]
        await _wait_for(lambda: len(finished) == 2)
        assert sorted(finished) == ["b", "c"]
        assert "a" not in finished
    finally:
        allow_a.set()
    await batch

    assert finished[-1] == "a"
    assert finished != ["a", "b", "c"]
    # Reservation order still drives numbering and finalization order.
    assert run.frames["root:each#0:0"].step_number == 2
    assert run.frames["root:each#0:1"].step_number == 3
    assert run.frames["root:each#0:2"].step_number == 4
    batch_entries = [
        entry for entry in run.trace if entry.frame_id.startswith("root:each#0:")
    ]
    assert [entry.frame_id for entry in batch_entries] == [
        "root:each#0:0",
        "root:each#0:1",
        "root:each#0:2",
    ]
    assert [entry.step_number for entry in batch_entries] == [2, 3, 4]


async def test_async_batch_reservations_kept_after_failure() -> None:
    """Admitted attempts stay consumed even when a handler raises."""
    workflow = _concurrent_workflow(max_active=3, name="async_reserved_failure")
    items = ["a", "b", "c"]
    run, index = _prepare_limited_run(workflow, items, max_steps=20)

    await step_workflow_async(workflow, run, {"record": _noop_record}, index=index)
    base_steps = run.steps_executed
    assert base_steps == 1

    release = asyncio.Event()
    started: list[str] = []

    async def record(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        started.append(payload["value"])
        await release.wait()
        if payload["value"] == "b":
            raise ValueError("bad item")
        return {"outcome": "ok", "output": payload}

    batch = asyncio.create_task(
        step_workflow_async(workflow, run, {"record": record}, index=index)
    )
    await _wait_for(lambda: len(started) == 3)
    release.set()
    with pytest.raises(ValueError, match="bad item"):
        await batch

    # All three admissions remain consumed; the failure did not refund them.
    assert run.steps_executed == base_steps + 3
    assert remaining_step_attempts(run) == 20 - 4
    assert run.frames["root:each#0:0"].step_number == 2
    assert run.frames["root:each#0:1"].step_number == 3
    assert run.frames["root:each#0:2"].step_number == 4


async def test_async_batch_settles_siblings_and_discards_later_commits() -> None:
    """Siblings settle before raising; later commits are discarded in order."""
    workflow = _concurrent_workflow(max_active=3, name="async_settle_discard")
    items = ["a", "b", "c"]
    run, index = _prepare_limited_run(workflow, items, max_steps=20)

    await step_workflow_async(workflow, run, {"record": _noop_record}, index=index)

    release = asyncio.Event()
    started: list[str] = []
    finished: list[str] = []

    async def record(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        value = payload["value"]
        started.append(value)
        await release.wait()
        if value == "b":
            finished.append(value)
            raise ValueError("middle fails")
        if value == "c":
            # The reservation-later sibling is slow: it must still settle
            # before the middle failure is raised.
            await asyncio.sleep(0.05)
        finished.append(value)
        return {"outcome": "ok", "output": payload}

    batch = asyncio.create_task(
        step_workflow_async(workflow, run, {"record": record}, index=index)
    )
    await _wait_for(lambda: len(started) == 3)
    assert started == ["a", "b", "c"]
    release.set()
    with pytest.raises(ValueError, match="middle fails"):
        await batch

    # Every handler settled, including the slow reservation-later sibling.
    assert sorted(finished) == ["a", "b", "c"]
    # Reservations are kept even for the discarded sibling.
    assert run.steps_executed == 4
    # Preceding success committed in reservation order...
    committed = [entry.frame_id for entry in run.trace if entry.step_type == "node"]
    assert committed == ["root:each#0:0"]
    assert run.frames["root:each#0:0"].status == FrameStatus.COMPLETED
    # ...while the later sibling result was discarded without state/trace.
    assert "root:each#0:2" not in committed
    assert run.frames["root:each#0:2"].status == FrameStatus.RUNNING
    assert run.frames["root:each#0:2"].step_number == 4


async def test_sync_async_parity_for_serial_execution() -> None:
    """Equivalent serial runs count the same steps sync and async."""

    def _serial_workflow(name: str) -> Workflow:
        return Workflow(
            name=name,
            input_schema=SchemaRef(
                type="object", properties={"items": {"type": "array"}}
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
            output_schema=SchemaRef(
                type="object", properties={"seen": {"type": "array"}}
            ),
            node_defs=[
                NodeDef(
                    name="record",
                    input_schema=SchemaRef(
                        type="object",
                        properties={"value": {}, "seen": {}},
                        required=["value", "seen"],
                    ),
                    output_schema=SchemaRef(
                        type="object",
                        properties={"seen": {}},
                        required=["seen"],
                    ),
                    outcomes=["ok"],
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
                        "concurrent": {"max_active": 1, "max_outstanding": 1},
                    }
                ),
                NodeUse.model_validate(
                    {
                        "id": "record",
                        "type": "node",
                        "node": "record",
                        "input": [
                            {"target": "value", "path": "context.item"},
                            {"target": "seen", "path": "context.item"},
                        ],
                        "output": [{"source": "seen", "target": "state.seen"}],
                    }
                ),
            ],
            edges=[
                Edge.model_validate(
                    {"from": "each", "outcome": "loop", "to": "record"}
                ),
                Edge.model_validate({"from": "record", "outcome": "ok", "to": "each"}),
                Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
            ],
        )

    sync_workflow = _serial_workflow("parity_sync")
    async_workflow = _serial_workflow("parity_sync")

    sync_run = execute_workflow(
        sync_workflow,
        {"items": ["a", "b"]},
        {"record": _sync_noop_record},
    )

    async def record(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        return {"outcome": "ok", "output": payload}

    async_run = await execute_workflow_async(
        async_workflow, {"items": ["a", "b"]}, {"record": record}
    )

    assert sync_run.status == RunStatus.COMPLETED
    assert async_run.status == RunStatus.COMPLETED
    assert async_run.steps_executed == sync_run.steps_executed
    assert [entry.step_number for entry in async_run.trace] == [
        entry.step_number for entry in sync_run.trace
    ]
