from __future__ import annotations

import asyncio

from pydantic import BaseModel

from wf_core import (
    END,
    FrameStatus,
    RuntimeContext,
    RunStatus,
    execute_workflow_async,
    execute_workflow,
    resume_workflow,
    step_workflow,
)
from wf_core.demo_workflow import build_demo_registry, build_demo_workflow
from wf_core.run_factory import create_run_state
from wf_authoring import (
    NodeReturn,
    WorkflowBuilder,
    bind_fields,
    build_async_registry,
    bind_state,
    build_registry,
    expr,
    exists,
    state,
    state_path,
    context_path,
    input_path,
    node,
    subgraph_node,
)


class DriveListFilesInput(BaseModel):
    folder_id: str


class DriveListFilesOutput(BaseModel):
    documents: list[str]


class SummarizeDocumentInput(BaseModel):
    document: str


class SummarizeDocumentOutput(BaseModel):
    item_summary: str


class CombineSummariesInput(BaseModel):
    item_summaries: list[str]


class CombineSummariesOutput(BaseModel):
    summary: str


class SendEmailInput(BaseModel):
    summary: str


class SendEmailOutput(BaseModel):
    email_status: str


class MarkEmailSkippedInput(BaseModel):
    pass


class MarkEmailSkippedOutput(BaseModel):
    email_status: str


class InferredEchoInput(BaseModel):
    value: str


class InferredEchoOutput(BaseModel):
    echoed: str


class InferredOutcomeInput(BaseModel):
    value: str


class InferredOutcomeOutput(BaseModel):
    echoed: str


class InferredAsyncInput(BaseModel):
    value: str


class InferredAsyncOutput(BaseModel):
    echoed: str


@node(
    name="drive_list_files",
    input_model=DriveListFilesInput,
    output_model=DriveListFilesOutput,
)
def drive_list_files_spec(
    payload: DriveListFilesInput,
    ctx: RuntimeContext,
) -> DriveListFilesOutput:
    return DriveListFilesOutput(
        documents=[
            f"{payload.folder_id}/meeting-notes.md",
            f"{payload.folder_id}/weekly-report.md",
        ]
    )


@node(
    name="summarize_document",
    input_model=SummarizeDocumentInput,
    output_model=SummarizeDocumentOutput,
)
def summarize_document_spec(
    payload: SummarizeDocumentInput,
    ctx: RuntimeContext,
) -> SummarizeDocumentOutput:
    return SummarizeDocumentOutput(item_summary=f"Summary of {payload.document}")


@node(
    name="combine_summaries",
    input_model=CombineSummariesInput,
    output_model=CombineSummariesOutput,
)
def combine_summaries_spec(
    payload: CombineSummariesInput,
    ctx: RuntimeContext,
) -> CombineSummariesOutput:
    return CombineSummariesOutput(summary=" | ".join(payload.item_summaries))


@node(
    name="send_email",
    input_model=SendEmailInput,
    output_model=SendEmailOutput,
    outcomes=("sent",),
)
def send_email_spec(
    payload: SendEmailInput,
    ctx: RuntimeContext,
) -> NodeReturn[SendEmailOutput]:
    return NodeReturn(
        outcome="sent",
        output=SendEmailOutput(email_status=f"sent: {payload.summary}"),
    )


@node(
    name="mark_email_skipped",
    input_model=MarkEmailSkippedInput,
    output_model=MarkEmailSkippedOutput,
)
def mark_email_skipped_spec(
    payload: MarkEmailSkippedInput,
    ctx: RuntimeContext,
) -> MarkEmailSkippedOutput:
    return MarkEmailSkippedOutput(email_status="skipped")


def build_authoring_demo_workflow():
    declared = build_demo_workflow()
    builder = WorkflowBuilder(
        name=declared.name,
        input_schema=declared.input_schema,
        state_schema=declared.state_schema,
        output_schema=declared.output_schema,
        start="list_files",
    )

    list_files = builder.use(
        drive_list_files_spec,
        id="list_files",
        in_map=bind_fields(folder_id=input_path("folder_id")),
        out_map=bind_state(documents=state_path("documents")),
        desc="List files from a Google Drive folder",
    )
    summarize_each = builder.foreach(
        id="summarize_each",
        over=state_path("documents"),
        as_="document",
        mode="serial",
        on_item_error="fail",
    )
    summarize_one = builder.use(
        summarize_document_spec,
        id="summarize_one",
        in_map=bind_fields(document=context_path("document")),
        out_map=bind_state(item_summary=state_path("item_summaries")),
        desc="Summarize one document",
    )
    combine_summaries = builder.use(
        combine_summaries_spec,
        id="combine_summaries",
        in_map=bind_fields(item_summaries=state_path("item_summaries")),
        out_map=bind_state(summary=state_path("summary")),
        desc="Combine item summaries into one final summary",
    )
    should_email = builder.condition(
        id="should_email",
        check=state("should_email").eq(True),
    )
    send_email = builder.use(
        send_email_spec,
        id="send_email",
        in_map=bind_fields(summary=state_path("summary")),
        out_map=bind_state(email_status=state_path("email_status")),
        desc="Send the summary by email",
    )
    approve_email = builder.interrupt(
        id="approve_email",
        kind="approval",
        request_map=bind_fields(
            summary=state_path("summary"),
            folder_id=input_path("folder_id"),
        ),
        out_map=bind_state(
            approved=state_path("approved"),
            comment=state_path("approval_comment"),
        ),
        outcomes=["submitted", "cancelled"],
    )
    skip_email = builder.use(
        mark_email_skipped_spec,
        id="skip_email",
        out_map=bind_state(email_status=state_path("email_status")),
        desc="Record that email delivery was skipped",
    )

    builder.connect(list_files, "ok", summarize_each)
    builder.connect(summarize_each, "loop", summarize_one)
    builder.connect(summarize_each, "done", combine_summaries)
    builder.connect(summarize_one, "ok", END)
    builder.connect(combine_summaries, "ok", should_email)
    builder.connect(should_email, "true", approve_email)
    builder.connect(should_email, "false", skip_email)
    builder.connect(approve_email, "submitted", send_email)
    builder.connect(approve_email, "cancelled", skip_email)
    builder.connect(send_email, "sent", END)
    builder.connect(skip_email, "ok", END)

    registry = build_registry(
        drive_list_files_spec,
        summarize_document_spec,
        combine_summaries_spec,
        send_email_spec,
        mark_email_skipped_spec,
    )
    return builder.compile(), registry


def _strip_schema_titles(value: object) -> object:
    if isinstance(value, dict):
        normalized = {
            key: _strip_schema_titles(inner)
            for key, inner in value.items()
            if key not in {"title", "items"}
        }
        return normalized
    if isinstance(value, list):
        return [_strip_schema_titles(item) for item in value]
    return value


def test_interrupt_then_resume_to_send_email() -> None:
    workflow = build_demo_workflow()
    registry = build_demo_registry()

    interrupted_run = execute_workflow(
        workflow,
        {"folder_id": "demo-folder", "should_email": True},
        registry,
    )

    assert interrupted_run.status == RunStatus.INTERRUPTED
    assert interrupted_run.current_node_id == "approve_email"
    assert interrupted_run.interrupt is not None
    assert interrupted_run.interrupt.kind == "approval"
    assert interrupted_run.state["summary"].startswith("Summary of demo-folder/")

    resumed_run = resume_workflow(
        workflow,
        interrupted_run,
        registry,
        resume_payload={"approved": True, "comment": "Looks good to send."},
        resume_outcome="submitted",
    )

    assert resumed_run.status == RunStatus.COMPLETED
    assert resumed_run.current_node_id == END
    assert resumed_run.output["email_status"].startswith("sent:")
    assert resumed_run.state["approved"] is True
    assert resumed_run.state["approval_comment"] == "Looks good to send."


def test_non_interrupt_path_skips_email() -> None:
    workflow = build_demo_workflow()
    registry = build_demo_registry()

    run = execute_workflow(
        workflow,
        {"folder_id": "demo-folder", "should_email": False},
        registry,
    )

    assert run.status == RunStatus.COMPLETED
    assert run.output["email_status"] == "skipped"
    assert run.interrupt is None


def test_stepwise_execution_reaches_interrupt() -> None:
    workflow = build_demo_workflow()
    registry = build_demo_registry()
    run = create_run_state(
        workflow,
        {"folder_id": "demo-folder", "should_email": True},
    )

    workflow.validate_structure().raise_for_errors()

    while run.status not in {RunStatus.INTERRUPTED, RunStatus.COMPLETED}:
        step_workflow(workflow, run, registry)

    assert run.status == RunStatus.INTERRUPTED
    assert run.current_node_id == "approve_email"
    assert any(entry.step_type == "foreach" for entry in run.trace)
    assert len(run.trace) == 9


def test_foreach_stress_with_many_documents() -> None:
    workflow = build_demo_workflow()
    registry = build_demo_registry()

    document_count = 25

    def many_files(payload: dict[str, object], ctx: object) -> dict[str, object]:
        folder_id = payload["folder_id"]
        return {
            "outcome": "ok",
            "output": {
                "documents": [
                    f"{folder_id}/doc-{index:02d}.md" for index in range(document_count)
                ]
            },
        }

    registry["drive_list_files"] = many_files

    run = execute_workflow(
        workflow,
        {"folder_id": "bulk-folder", "should_email": False},
        registry,
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.state["documents"]) == document_count
    assert len(run.state["item_summaries"]) == document_count
    assert (
        len(
            [
                frame
                for frame in run.frames.values()
                if frame.kind == "foreach_iteration"
                and frame.status == FrameStatus.COMPLETED
            ]
        )
        == document_count
    )
    assert len([entry for entry in run.trace if entry.step_type == "foreach"]) == (
        document_count + 1
    )


def test_builder_compiles_same_workflow_as_declared_demo() -> None:
    declared = build_demo_workflow()
    built, _registry = build_authoring_demo_workflow()

    assert _strip_schema_titles(
        built.model_dump(by_alias=True)
    ) == _strip_schema_titles(declared.model_dump(by_alias=True))


def test_builder_compiled_workflow_executes_like_declared_demo() -> None:
    declared = build_demo_workflow()
    declared_registry = build_demo_registry()
    built, built_registry = build_authoring_demo_workflow()

    declared_run = execute_workflow(
        declared,
        {"folder_id": "demo-folder", "should_email": False},
        declared_registry,
    )
    built_run = execute_workflow(
        built,
        {"folder_id": "demo-folder", "should_email": False},
        built_registry,
    )

    assert built_run.status == declared_run.status
    assert built_run.output == declared_run.output
    assert built_run.state == declared_run.state
    assert built_run.current_node_id == declared_run.current_node_id


def test_async_node_spec_cannot_export_sync_registry_handler() -> None:
    class AsyncInput(BaseModel):
        value: str

    class AsyncOutput(BaseModel):
        echoed: str

    @node(
        name="async_echo",
        input_model=AsyncInput,
        output_model=AsyncOutput,
        is_async=True,
    )
    async def async_echo(
        payload: AsyncInput,
        ctx: RuntimeContext,
    ) -> AsyncOutput:
        return AsyncOutput(echoed=payload.value)

    try:
        async_echo.to_registry_handler()
    except TypeError as exc:
        assert "async" in str(exc)
    else:
        raise AssertionError("expected async node export to fail for sync registry")


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


@node()
def inferred_echo(
    payload: InferredEchoInput,
    ctx: RuntimeContext,
) -> InferredEchoOutput:
    return InferredEchoOutput(echoed=payload.value)


@node(outcomes=("done", "retry"))
def inferred_echo_with_outcome(
    payload: InferredOutcomeInput,
    ctx: RuntimeContext,
) -> NodeReturn[InferredOutcomeOutput]:
    return NodeReturn(
        outcome="done",
        output=InferredOutcomeOutput(echoed=payload.value),
    )


@node()
async def inferred_async_echo(
    payload: InferredAsyncInput,
    ctx: RuntimeContext,
) -> InferredAsyncOutput:
    return InferredAsyncOutput(echoed=payload.value)


def test_node_decorator_infers_models_from_annotations() -> None:
    assert inferred_echo.input_model is InferredEchoInput
    assert inferred_echo.output_model is InferredEchoOutput
    assert inferred_echo.outcomes == ("ok",)
    assert inferred_echo.is_async is False

    registry = build_registry(inferred_echo)
    result = registry["inferred_echo"](
        {"value": "hello"},
        RuntimeContext(current_node_id="x"),
    )
    assert result == {"outcome": "ok", "output": {"echoed": "hello"}}


def test_node_decorator_infers_nodereturn_output_model() -> None:
    assert inferred_echo_with_outcome.input_model is InferredOutcomeInput
    assert inferred_echo_with_outcome.output_model is InferredOutcomeOutput

    registry = build_registry(inferred_echo_with_outcome)
    result = registry["inferred_echo_with_outcome"](
        {"value": "hello"},
        RuntimeContext(current_node_id="x"),
    )
    assert result == {"outcome": "done", "output": {"echoed": "hello"}}


def test_node_decorator_detects_async_automatically() -> None:
    assert inferred_async_echo.is_async is True


def test_condition_dsl_compiles_to_core_condition() -> None:
    condition = expr(state_path("should_email")).eq(True) & exists(
        state_path("summary")
    )

    assert condition.to_condition().model_dump() == {
        "op": "and",
        "args": [
            {
                "op": "eq",
                "left": {"path": "state.should_email"},
                "right": {"value": True},
            },
            {
                "op": "exists",
                "path": "state.summary",
            },
        ],
    }


def test_subgraph_node_wraps_compiled_workflow() -> None:
    class ChildInput(BaseModel):
        folder_id: str
        should_email: bool

    class ChildOutput(BaseModel):
        summary: str
        email_status: str

    child_workflow = build_demo_workflow()
    child_registry = build_demo_registry()
    wrapped = subgraph_node(
        name="wrapped_demo",
        workflow=child_workflow,
        registry=child_registry,
        input_model=ChildInput,
        output_model=ChildOutput,
    )

    registry = build_registry(wrapped)
    result = registry["wrapped_demo"](
        {"folder_id": "demo-folder", "should_email": False},
        RuntimeContext(current_node_id="parent"),
    )

    assert result["outcome"] == "ok"
    assert result["output"]["email_status"] == "skipped"
    assert "summary" in result["output"]
