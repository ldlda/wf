from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wf_api.models import RawWorkflowPlan
from wf_authoring import WorkflowBuilder
from wf_core import Workflow

HERE = Path(__file__).resolve().parent

WORKFLOW_OUTPUT = [
    {"path": "state.approved", "target": "approved"},
    {"path": "state.final_markdown", "target": "markdown"},
    {"path": "state.created_issues", "target": "created_issues"},
    {"path": "state.selected_issue_ids", "target": "selected_issue_ids"},
]


def build_workflow() -> Workflow:
    """Build the demo workflow with the public authoring API.

    `WorkflowBuilder` does not yet expose a workflow-output setter, so this
    module adds the final output projection in `_with_workflow_output()` after
    compiling the graph. Keep that seam small and validated.
    """
    builder = WorkflowBuilder(
        name="lda_report_case_study",
        input_schema={
            "type": "object",
            "properties": {
                "selected_documents": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "board_path": {"type": "string"},
            },
            "required": ["selected_documents", "board_path"],
        },
        state_schema={
            "type": "object",
            "properties": {
                "documents": {"type": "array"},
                "analysis": {"type": "array"},
                "report": {"type": "object"},
                "report_markdown": {"type": "string"},
                "proposed_issues": {"type": "array"},
                "selected_issue_ids": {"type": "array"},
                "approval_comment": {"type": "string"},
                "approved": {"type": "boolean"},
                "created_issues": {"type": "array"},
                "final_markdown": {"type": "string"},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "approved": {"type": "boolean"},
                "markdown": {"type": "string"},
                "created_issues": {"type": "array"},
                "selected_issue_ids": {"type": "array"},
            },
        },
        outcomes=["completed", "cancelled"],
    )

    read_docs = builder.use_ref(
        "local.lda_docs.read_documents",
        id="read_docs",
        input=[{"path": "input.selected_documents", "target": "names"}],
        output=[{"source": "documents", "target": "state.documents"}],
    )
    reset_board = builder.use_ref(
        "local.issue_board.reset_issue_board",
        id="reset_board",
        input=[{"path": "input.board_path", "target": "board_path"}],
    )
    analyze = builder.use_ref(
        "local.lda_report.analyze_documents",
        id="analyze",
        input=[{"path": "state.documents", "target": "documents"}],
        output=[{"source": "analysis", "target": "state.analysis"}],
    )
    build_report = builder.use_ref(
        "local.lda_report.build_report",
        id="build_report",
        input=[{"path": "state.analysis", "target": "analysis"}],
        output=[
            {"source": "report", "target": "state.report"},
            {"source": "markdown", "target": "state.report_markdown"},
        ],
    )
    draft_issues = builder.use_ref(
        "local.lda_report.create_issue_drafts",
        id="draft_issues",
        input=[{"path": "state.report", "target": "report"}],
        output=[{"source": "issues", "target": "state.proposed_issues"}],
    )
    review_issues = builder.interrupt(
        id="review_issues",
        kind="issue_review",
        request=[
            {"path": "state.report_markdown", "target": "report_markdown"},
            {"path": "state.proposed_issues", "target": "proposed_issues"},
        ],
        resume=[
            {"source": "approved", "target": "state.approved"},
            {"source": "selected_issue_ids", "target": "state.selected_issue_ids"},
            {"source": "comment", "target": "state.approval_comment"},
        ],
        outcomes=["submitted", "cancelled"],
        request_schema={
            "type": "object",
            "properties": {
                "report_markdown": {"type": "string"},
                "proposed_issues": {"type": "array"},
            },
            "required": ["report_markdown", "proposed_issues"],
            "additionalProperties": False,
        },
        resume_schema={
            "type": "object",
            "properties": {
                "approved": {"type": "boolean"},
                "selected_issue_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "comment": {"type": "string"},
            },
            "required": ["approved", "selected_issue_ids"],
            "additionalProperties": False,
        },
    )
    create_issues = builder.use_ref(
        "local.issue_board.create_issues",
        id="create_issues",
        input=[
            {"path": "state.proposed_issues", "target": "issues"},
            {"path": "state.selected_issue_ids", "target": "selected_issue_ids"},
            {"path": "input.board_path", "target": "board_path"},
        ],
        output=[{"source": "created_issues", "target": "state.created_issues"}],
    )
    finalise = builder.use_ref(
        "local.lda_report.finalise_report",
        id="finalise",
        input=[
            {"path": "state.report", "target": "report"},
            {"path": "state.created_issues", "target": "created_issues"},
            {"path": "state.approved", "target": "approved"},
            {"path": "state.selected_issue_ids", "target": "selected_issue_ids"},
            {"path": "state.approval_comment", "target": "comment"},
        ],
        output=[{"source": "markdown", "target": "state.final_markdown"}],
    )
    revision_requested = builder.use_ref(
        "local.lda_report.record_revision_request",
        id="revision_requested",
        input=[{"path": "state.approval_comment", "target": "comment"}],
        output=[
            {"source": "approved", "target": "state.approved"},
            {"source": "markdown", "target": "state.final_markdown"},
            {"source": "created_issues", "target": "state.created_issues"},
            {"source": "selected_issue_ids", "target": "state.selected_issue_ids"},
        ],
    )
    end_completed = builder.end("completed", id="end_completed")
    end_cancelled = builder.end("cancelled", id="end_cancelled")

    builder.set_entry_point(reset_board)
    builder.connect(reset_board, "ok", read_docs)
    builder.connect(read_docs, "ok", analyze)
    builder.connect(analyze, "ok", build_report)
    builder.connect(build_report, "ok", draft_issues)
    builder.connect(draft_issues, "ok", review_issues)
    builder.branch(
        review_issues,
        {
            "submitted": create_issues,
            "cancelled": revision_requested,
        },
    )
    builder.connect(create_issues, "ok", finalise)
    builder.connect(finalise, "ok", end_completed)
    builder.connect(revision_requested, "ok", end_cancelled)
    return _with_workflow_output(builder.compile())


def _with_workflow_output(workflow: Workflow) -> Workflow:
    payload = workflow.model_dump(mode="json", by_alias=True)
    payload["output"] = WORKFLOW_OUTPUT
    return Workflow.model_validate(payload)


def workflow_plan_payload() -> dict[str, Any]:
    payload = build_workflow().model_dump(mode="json", by_alias=True)
    payload.pop("node_defs", None)
    RawWorkflowPlan.model_validate(payload)
    return payload


def write_plan(path: Path = HERE / "workflow.plan.json") -> None:
    payload = workflow_plan_payload()
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_plan()
