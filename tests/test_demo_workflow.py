from __future__ import annotations

from wf_core import (
    END,
    FrameStatus,
    RunStatus,
    execute_workflow,
    resume_workflow,
    step_workflow,
)
from wf_core.demo_workflow import build_demo_registry, build_demo_workflow
from wf_core.run_factory import create_run_state


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
    assert len(
        [
            frame
            for frame in run.frames.values()
            if frame.kind == "foreach_iteration"
            and frame.status == FrameStatus.COMPLETED
        ]
    ) == document_count
    assert len([entry for entry in run.trace if entry.step_type == "foreach"]) == (
        document_count + 1
    )
