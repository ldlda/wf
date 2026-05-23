from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from examples.authoring_concurrent_foreach import (
    ConcurrentForeachOutput,
    ConcurrentForeachState,
    ItemsInput,
    build_concurrent_foreach_workflow,
    record_item,
    run_async_ordered_example,
    run_collected_errors_example,
    run_replace_conflict_example,
)
from wf_authoring import WorkflowBuilder, state_path
from wf_core import ForeachConcurrentPolicy
from wf_core import RunStatus


def test_authoring_concurrent_foreach_collects_item_errors() -> None:
    run = run_collected_errors_example()

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
    run = asyncio.run(run_async_ordered_example())

    assert run.status == RunStatus.COMPLETED
    assert run.output["seen"] == ["a", "b", "c"]


def test_authoring_foreach_accepts_item_error_mapping_with_authoring_path() -> None:
    builder = build_concurrent_foreach_workflow(
        record_item,
        item_error={"action": "collect", "collect_to": state_path("errors")},
    )

    foreach = builder.compile().nodes[0]

    assert foreach.model_dump(mode="json")["item_error"]["collect_to"] == {
        "root": "state",
        "parts": ["errors"],
    }


def test_authoring_foreach_accepts_item_error_action_string() -> None:
    builder = build_concurrent_foreach_workflow(record_item, item_error="skip")

    foreach = builder.compile().nodes[0]

    assert foreach.model_dump(mode="json")["item_error"]["action"] == "skip"


def test_authoring_foreach_accepts_concurrent_policy_object() -> None:
    builder = build_concurrent_foreach_workflow(
        record_item,
        concurrent=ForeachConcurrentPolicy(max_active=1, max_outstanding=3),
    )

    foreach = builder.compile().nodes[0]

    assert foreach.model_dump(mode="json")["concurrent"]["max_active"] == 1
    assert foreach.model_dump(mode="json")["concurrent"]["max_outstanding"] == 3


def test_authoring_concurrent_foreach_example_documents_replace_conflict() -> None:
    run_replace_conflict_example()


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
