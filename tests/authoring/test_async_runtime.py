from __future__ import annotations

import asyncio

from pydantic import BaseModel

from wf_authoring import build_async_registry, node
from wf_core import RunStatus, RuntimeContext, execute_workflow_async

from .test_demo_workflow import (
    build_authoring_demo_workflow,
    combine_summaries_spec,
    drive_list_files_spec,
    mark_email_skipped_spec,
    send_email_spec,
    summarize_document_spec,
)


class InferredEchoInput(BaseModel):
    value: str


class InferredEchoOutput(BaseModel):
    echoed: str


class InferredAsyncInput(BaseModel):
    value: str


class InferredAsyncOutput(BaseModel):
    echoed: str


def test_async_registry_accepts_sync_and_async_specs() -> None:
    @node()
    def sync_echo(
        payload: InferredEchoInput,
        ctx: RuntimeContext,
    ) -> InferredEchoOutput:
        return InferredEchoOutput(echoed=payload.value)

    @node()
    async def async_echo(
        payload: InferredAsyncInput,
        ctx: RuntimeContext,
    ) -> InferredAsyncOutput:
        return InferredAsyncOutput(echoed=f"async:{payload.value}")

    registry = build_async_registry(sync_echo, async_echo)
    ctx = RuntimeContext(current_node_id="demo")

    async def run_handler(name: str, value: str) -> dict[str, object]:
        return await registry[name]({"value": value}, ctx)

    sync_result = asyncio.run(run_handler("sync_echo", "hello"))
    async_result = asyncio.run(run_handler("async_echo", "world"))

    assert sync_result == {"outcome": "ok", "output": {"echoed": "hello"}}
    assert async_result == {"outcome": "ok", "output": {"echoed": "async:world"}}


def test_execute_workflow_async_runs_with_async_registry() -> None:
    workflow, _ = build_authoring_demo_workflow()
    registry = build_async_registry(
        drive_list_files_spec,
        summarize_document_spec,
        combine_summaries_spec,
        send_email_spec,
        mark_email_skipped_spec,
    )

    run = asyncio.run(
        execute_workflow_async(
            workflow,
            {"folder_id": "demo-folder", "should_email": False},
            registry,
        )
    )

    assert run.status == RunStatus.COMPLETED
    assert run.output["email_status"] == "skipped"
    assert run.interrupt is None
