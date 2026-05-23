from __future__ import annotations

import asyncio
from typing import Annotated, Any

from pydantic import BaseModel, Field

from wf_authoring import (
    NodeSpec,
    WorkflowBuilder,
    build_async_registry,
    context_path,
    input_from,
    node,
    output_to,
    state_field,
    state_path,
)
from wf_core import (
    END,
    ForeachConcurrentPolicy,
    ForeachItemErrorPolicy,
    execute_workflow_async,
)
from wf_core.paths import StatePath
from wf_core.run_state import RunState


class ItemsInput(BaseModel):
    """Workflow input containing items to process."""

    items: list[str]


class ConcurrentForeachState(BaseModel):
    """State shape used by the concurrent foreach authoring example."""

    items: list[str]
    seen: Annotated[list[str], state_field(reducer="wf.std.append")] = Field(
        default_factory=list
    )
    errors: list[dict[str, object]] = Field(default_factory=list)


class ConcurrentForeachOutput(BaseModel):
    """Workflow output showing successful items and collected item failures."""

    seen: list[str]
    errors: list[dict[str, object]]


class RecordInput(BaseModel):
    """Input for one foreach item node call."""

    value: str
    seen: str


class RecordOutput(BaseModel):
    """Output appended to workflow state at the foreach barrier."""

    seen: str


@node(name="example.record_item")
def record_item(payload: RecordInput) -> RecordOutput:
    """Record one foreach item, failing on a sentinel item for examples."""
    if payload.value == "bad":
        raise ValueError("bad item")
    return RecordOutput(seen=payload.seen)


@node(name="example.record_item_async")
async def record_item_async(payload: RecordInput) -> RecordOutput:
    """Async variant used to prove authoring workflows can use async batching."""
    await asyncio.sleep({"a": 0.03, "b": 0.01, "c": 0.02}[payload.value])
    return RecordOutput(seen=payload.seen)


def build_concurrent_foreach_workflow(
    spec: NodeSpec[Any, RecordOutput] = record_item,
    *,
    item_error: ForeachItemErrorPolicy | dict[str, object] | str | None = None,
    concurrent: ForeachConcurrentPolicy | dict[str, object] | None = None,
) -> WorkflowBuilder:
    """Build a public authoring workflow that uses concurrent foreach.

    `item_error` accepts the same canonical forms as `WorkflowBuilder.foreach`:
    a bare action string, a mapping, or a `ForeachItemErrorPolicy` object.
    """
    builder = WorkflowBuilder(
        name="authoring_concurrent_foreach",
        input_schema=ItemsInput,
        state_schema=ConcurrentForeachState,
        output_schema=ConcurrentForeachOutput,
    )
    each = builder.foreach(
        id="each",
        over=state_path("items"),
        as_="item",
        mode="concurrent",
        item_error=item_error,
        concurrent=concurrent or {"max_active": 2, "max_outstanding": 2},
    )
    record = builder.use(
        spec,
        id="record",
        input=[
            input_from(context_path("item"), "value"),
            input_from(context_path("item"), "seen"),
        ],
        output=[output_to("seen", state_path("seen"))],
    )
    builder.set_entry_point(each)
    builder.connect(each, "loop", record)
    builder.connect(record, "ok", END)
    builder.connect(each, "done", END)
    if _item_error_action(item_error) in {"collect", "skip"}:
        builder.connect(each, "completed_with_errors", END)
    return builder


def run_collected_errors_example() -> RunState:
    """Run the sync example with one failing item collected into state.errors."""
    builder = build_concurrent_foreach_workflow(
        record_item,
        item_error=ForeachItemErrorPolicy(
            action="collect",
            collect_to=StatePath.of("errors"),
        ),
    )
    return builder.execute({"items": ["a", "bad", "c"]})


async def run_async_ordered_example() -> RunState:
    """Run the async example; barrier commits still preserve item order."""
    builder = build_concurrent_foreach_workflow(record_item_async)
    return await execute_workflow_async(
        builder.compile(),
        {"items": ["a", "b", "c"]},
        build_async_registry(record_item_async),
    )


def _item_error_action(
    item_error: ForeachItemErrorPolicy | dict[str, object] | str | None,
) -> object:
    """Return the policy action without forcing callers into one input shape."""
    if isinstance(item_error, ForeachItemErrorPolicy):
        return item_error.action
    if isinstance(item_error, dict):
        return item_error.get("action")
    if isinstance(item_error, str):
        return item_error
    return None


def main() -> None:
    """Run the example directly from the command line."""
    sync_run = run_collected_errors_example()
    async_run = asyncio.run(run_async_ordered_example())
    print("collected_errors", sync_run.output)
    print("async_ordered", async_run.output)


if __name__ == "__main__":
    main()
