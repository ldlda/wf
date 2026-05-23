from __future__ import annotations

import asyncio
from typing import Annotated
from typing import Any, cast

import pytest
from pydantic import BaseModel, Field

from wf_authoring import (
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
    ForeachItemErrorPolicy,
    RunStatus,
    execute_workflow_async,
)
from wf_core.paths import StatePath


class ItemsInput(BaseModel):
    items: list[str]


class ConcurrentForeachState(BaseModel):
    items: list[str]
    seen: Annotated[list[str], state_field(reducer="wf.std.append")] = Field(
        default_factory=list
    )
    errors: list[dict[str, object]] = Field(default_factory=list)


class ConcurrentForeachOutput(BaseModel):
    seen: list[str]
    errors: list[dict[str, object]]


class RecordInput(BaseModel):
    value: str
    seen: str


class RecordOutput(BaseModel):
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


def test_authoring_concurrent_foreach_collects_item_errors() -> None:
    builder = _concurrent_foreach_builder(
        record_item,
        item_error=ForeachItemErrorPolicy(
            action="collect",
            collect_to=StatePath.of("errors"),
        ),
    )

    run = builder.execute({"items": ["a", "bad", "c"]})

    assert run.status == RunStatus.COMPLETED
    assert run.output["seen"] == ["a", "c"]
    assert len(run.output["errors"]) == 1
    error = run.output["errors"][0]
    assert error["index"] == 1
    assert error["node_id"] == "record"
    assert error["error_type"] == "ValueError"
    assert error["message"] == "bad item"
    assert error["item"] == "bad"


def test_authoring_async_concurrent_foreach_commits_in_item_order() -> None:
    builder = _concurrent_foreach_builder(record_item_async)
    registry = build_async_registry(record_item_async)

    run = asyncio.run(
        execute_workflow_async(
            builder.compile(),
            {"items": ["a", "b", "c"]},
            registry,
        )
    )

    assert run.status == RunStatus.COMPLETED
    assert run.output["seen"] == ["a", "b", "c"]


def test_authoring_foreach_accepts_item_error_mapping_with_authoring_path() -> None:
    builder = _concurrent_foreach_builder(
        record_item,
        item_error={"action": "collect", "collect_to": state_path("errors")},
    )

    foreach = builder.compile().nodes[0]

    assert foreach.model_dump(mode="json")["item_error"]["collect_to"] == {
        "root": "state",
        "parts": ["errors"],
    }


def test_authoring_foreach_accepts_item_error_action_string() -> None:
    builder = _concurrent_foreach_builder(record_item, item_error="skip")

    foreach = builder.compile().nodes[0]

    assert foreach.model_dump(mode="json")["item_error"]["action"] == "skip"


def test_authoring_foreach_deprecated_on_item_error_warns() -> None:
    builder = WorkflowBuilder(
        name="deprecated_item_error",
        input_schema=ItemsInput,
        state_schema=ConcurrentForeachState,
        output_schema=ConcurrentForeachOutput,
    )

    with pytest.warns(DeprecationWarning, match="on_item_error"):
        foreach = builder.foreach(
            id="each",
            over=state_path("items"),
            as_="item",
            on_item_error="skip",
        )

    assert foreach.item_error.action == "skip"


def test_authoring_foreach_rejects_mixed_item_error_styles() -> None:
    builder = WorkflowBuilder(
        name="mixed_item_error",
        input_schema=ItemsInput,
        state_schema=ConcurrentForeachState,
        output_schema=ConcurrentForeachOutput,
    )

    with pytest.raises(TypeError, match="cannot mix item_error"):
        cast(Any, builder.foreach)(
            id="each",
            over=state_path("items"),
            as_="item",
            item_error="skip",
            on_item_error="collect",
        )


def _concurrent_foreach_builder(
    spec,
    *,
    item_error: ForeachItemErrorPolicy | dict[str, object] | str | None = None,
) -> WorkflowBuilder:
    """Build the public authoring shape for concurrent foreach examples."""
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
        concurrent={"max_active": 2, "max_outstanding": 2},
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


def _item_error_action(
    item_error: ForeachItemErrorPolicy | dict[str, object] | str | None,
) -> object:
    if isinstance(item_error, ForeachItemErrorPolicy):
        return item_error.action
    if isinstance(item_error, dict):
        return item_error.get("action")
    if isinstance(item_error, str):
        return item_error
    return None
