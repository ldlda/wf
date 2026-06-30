from __future__ import annotations

from typing import Any

import pytest

from wf_core import (
    END,
    Edge,
    InterruptNode,
    NodeDef,
    NodeUse,
    RunStatus,
    RuntimeContext,
    SchemaRef,
    StateSchema,
    Workflow,
    execute_workflow_async,
    execute_workflow_result_async,
    resume_workflow_async,
    resume_workflow_result_async,
)
from wf_core.models.steps import InputValueBinding


async def explode(_payload: dict[str, Any], _context: RuntimeContext) -> dict[str, Any]:
    raise ValueError("boom")


@pytest.mark.asyncio
async def test_execute_result_api_returns_failed_state_without_changing_strict_execute() -> (
    None
):
    workflow = _failing_workflow()

    failed = await execute_workflow_result_async(workflow, {}, {"explode": explode})

    assert failed.status is RunStatus.FAILED
    assert failed.error == "boom"

    with pytest.raises(ValueError, match="boom"):
        await execute_workflow_async(workflow, {}, {"explode": explode})


@pytest.mark.asyncio
async def test_resume_result_api_returns_failed_state_without_changing_strict_resume() -> (
    None
):
    workflow = _interrupt_then_fail_workflow()
    interrupted = await execute_workflow_async(workflow, {}, {"explode": explode})

    failed = await resume_workflow_result_async(
        workflow,
        interrupted,
        {"explode": explode},
        resume_payload={},
    )

    assert failed.status is RunStatus.FAILED
    assert failed.error == "boom"

    interrupted = await execute_workflow_async(workflow, {}, {"explode": explode})
    with pytest.raises(ValueError, match="boom"):
        await resume_workflow_async(
            workflow,
            interrupted,
            {"explode": explode},
            resume_payload={},
        )


def _failing_workflow() -> Workflow:
    return Workflow(
        name="failing",
        input_schema=_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_schema(),
        outcomes=["ok"],
        start="explode",
        node_defs=[
            NodeDef(
                name="explode",
                input_schema=_schema(),
                output_schema=_schema(),
                outcomes=["ok"],
            )
        ],
        nodes=[NodeUse(id="explode", type="node", node="explode")],
        edges=[Edge.model_validate({"from": "explode", "outcome": "ok", "to": END})],
    )


def _interrupt_then_fail_workflow() -> Workflow:
    return Workflow(
        name="interrupt_then_fail",
        input_schema=_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_schema(),
        outcomes=["ok"],
        start="ask",
        node_defs=[
            NodeDef(
                name="explode",
                input_schema=_schema(),
                output_schema=_schema(),
                outcomes=["ok"],
            )
        ],
        nodes=[
            InterruptNode(id="ask", type="interrupt", kind="approval"),
            NodeUse(id="explode", type="node", node="explode"),
        ],
        edges=[
            Edge.model_validate(
                {"from": "ask", "outcome": "submitted", "to": "explode"}
            ),
            Edge.model_validate({"from": "explode", "outcome": "ok", "to": END}),
        ],
    )


def _schema() -> SchemaRef:
    return SchemaRef(type="object", properties={})


async def test_interrupt_request_payload_validates_against_schema() -> None:
    workflow = Workflow(
        name="bad_interrupt_request",
        input_schema=_schema(),
        state_schema=StateSchema.from_field_map({}),
        output_schema=_schema(),
        outcomes=["ok"],
        start="ask",
        nodes=[
            InterruptNode(
                id="ask",
                type="interrupt",
                kind="approval",
                request=[
                    InputValueBinding(target="count", value="not a number")  # type: ignore[arg-type]
                ],
                request_schema={
                    "type": "object",
                    "properties": {"count": {"type": "number"}},
                    "required": ["count"],
                    "additionalProperties": False,
                },
            ),
        ],
        edges=[Edge.model_validate({"from": "ask", "outcome": "submitted", "to": END})],
    )

    run = await execute_workflow_result_async(workflow, {}, {})

    assert run.status == RunStatus.FAILED
    assert run.interrupt is None
    assert run.error is not None
    assert "interrupt request for ask" in run.error
