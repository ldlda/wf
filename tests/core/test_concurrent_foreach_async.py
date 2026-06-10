from __future__ import annotations

import asyncio
from typing import Any

from wf_core import (
    END,
    Edge,
    ForeachNode,
    NodeDef,
    NodeUse,
    ReducerRef,
    SchemaRef,
    StateField,
    StateSchema,
    Workflow,
    execute_workflow_async,
)


async def test_async_concurrent_foreach_respects_max_active() -> None:
    workflow = _workflow(max_active=2)
    active = 0
    max_seen = 0

    async def record(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        nonlocal active, max_seen
        active += 1
        max_seen = max(max_seen, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"outcome": "ok", "output": payload}

    run = await execute_workflow_async(
        workflow,
        {"items": ["a", "b", "c", "d"]},
        {"record": record},
    )

    assert max_seen == 2
    assert run.state["seen"] == ["a", "b", "c", "d"]


async def test_async_concurrent_foreach_commits_in_item_index_order() -> None:
    workflow = _workflow(max_active=3)

    async def record(payload: dict[str, Any], _ctx: object) -> dict[str, Any]:
        delay = {"a": 0.03, "b": 0.01, "c": 0.02}[payload["value"]]
        await asyncio.sleep(delay)
        return {"outcome": "ok", "output": payload}

    run = await execute_workflow_async(
        workflow,
        {"items": ["a", "b", "c"]},
        {"record": record},
    )

    assert run.state["seen"] == ["a", "b", "c"]
    foreach_entries = [entry for entry in run.trace if entry.step_type == "foreach"]
    assert foreach_entries[-1].state_changes["state.seen"] == ["a", "b", "c"]


def _workflow(*, max_active: int) -> Workflow:
    return Workflow(
        name="async_concurrent_foreach",
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
            Edge.model_validate({"from": "record", "outcome": "ok", "to": END}),
            Edge.model_validate({"from": "each", "outcome": "done", "to": END}),
        ],
    )
