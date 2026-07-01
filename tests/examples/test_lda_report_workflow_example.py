from __future__ import annotations

import json
from pathlib import Path

import pytest

from examples.lda_report_workflow.build_workflow import (
    build_workflow,
    workflow_plan_payload,
)
from examples.lda_report_workflow.document_source import (
    ListDocumentsInput,
    ReadDocumentsInput,
    _list_documents,
    _read_documents,
)
from examples.lda_report_workflow.issue_board_source import (
    CreateIssuesInput,
    ResetIssueBoardInput,
    _create_issues,
    _reset_issue_board,
)
from examples.lda_report_workflow.report_source import (
    AnalyzeDocumentsInput,
    BuildReportInput,
    CreateIssueDraftsInput,
    FinaliseReportInput,
    ReadinessReport,
    RecordRevisionRequestInput,
    _analyze_documents,
    _build_report,
    _create_issue_drafts,
    _finalise_report,
    _record_revision_request,
)
from wf_api.models import RawWorkflowPlan
from wf_config import load_workflow_config
from wf_server.config import build_workflow_server_from_workflow_config

EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "lda_report_workflow"


def test_lda_docs_lists_known_documents() -> None:
    result = _list_documents(ListDocumentsInput())

    names = {document.name for document in result.documents}

    assert "project-brief.md" in names
    assert "architecture-notes.md" in names
    assert len(result.documents) == 5


def test_lda_docs_reads_selected_documents() -> None:
    result = _read_documents(
        ReadDocumentsInput(names=["project-brief.md", "roadmap.md"])
    )

    assert [document.name for document in result.documents] == [
        "project-brief.md",
        "roadmap.md",
    ]
    assert "workflow substrate" in result.documents[0].text


def test_lda_docs_rejects_path_traversal() -> None:
    with pytest.raises(ValueError, match="known document"):
        _read_documents(ReadDocumentsInput(names=["../README.md"]))


def test_lda_report_source_builds_report_and_issue_drafts() -> None:
    docs = _read_documents(
        ReadDocumentsInput(names=["project-brief.md", "risk-register.md", "roadmap.md"])
    )

    analysis = _analyze_documents(AnalyzeDocumentsInput(documents=docs.documents))
    report = _build_report(BuildReportInput(analysis=analysis.analysis))
    issue_drafts = _create_issue_drafts(CreateIssueDraftsInput(report=report.report))

    assert report.report.title == "lda.chat Thesis And Project Readiness Report"
    assert "workflow substrate" in report.report.summary
    assert issue_drafts.issues
    assert issue_drafts.issues[0].id
    assert issue_drafts.issues[0].title


def test_lda_report_source_finalises_approved_report() -> None:
    docs = _read_documents(ReadDocumentsInput(names=["project-brief.md", "roadmap.md"]))
    analysis = _analyze_documents(AnalyzeDocumentsInput(documents=docs.documents))
    report = _build_report(BuildReportInput(analysis=analysis.analysis))
    issue_drafts = _create_issue_drafts(CreateIssueDraftsInput(report=report.report))

    final = _finalise_report(
        FinaliseReportInput(
            report=report.report,
            created_issues=[],
            approved=True,
            selected_issue_ids=[issue_drafts.issues[0].id],
            comment="Looks good.",
        )
    )

    assert final.approved is True
    assert final.markdown.startswith("# lda.chat Thesis And Project Readiness Report")
    assert "Looks good." in final.markdown


def test_lda_report_source_records_revision_request() -> None:
    result = _record_revision_request(
        RecordRevisionRequestInput(comment="Needs revision")
    )

    assert result.approved is False
    assert "Needs revision" in result.markdown


def test_issue_board_creates_selected_issues(tmp_path: Path) -> None:
    board_path = tmp_path / "issue-board.json"
    drafts = _create_issue_drafts(
        CreateIssueDraftsInput(
            report=ReadinessReport(
                title="Test",
                summary="Summary",
                achievements=[],
                risks=["Risk one", "Risk two"],
                next_actions=[],
            )
        )
    )

    result = _create_issues(
        CreateIssuesInput(
            board_path=str(board_path),
            issues=drafts.issues,
            selected_issue_ids=[drafts.issues[0].id],
        )
    )

    assert len(result.created_issues) == 1
    assert result.created_issues[0].title == drafts.issues[0].title
    assert board_path.exists()


def test_issue_board_reset_removes_existing_file(tmp_path: Path) -> None:
    board_path = tmp_path / "issue-board.json"
    board_path.write_text("[]", encoding="utf-8")

    result = _reset_issue_board(ResetIssueBoardInput(board_path=str(board_path)))

    assert result.reset is True
    assert not board_path.exists()


def test_issue_board_rejects_paths_outside_example_or_temp() -> None:
    unsafe_path = Path.home() / "lda-chat-unsafe-issue-board.json"

    with pytest.raises(ValueError, match="board_path must stay"):
        _reset_issue_board(ResetIssueBoardInput(board_path=str(unsafe_path)))


@pytest.mark.asyncio
async def test_lda_report_workflow_config_loads_sources(tmp_path: Path) -> None:
    config = load_workflow_config(EXAMPLE_DIR / "wf.config.json")
    config.server.store.root = tmp_path / "store"
    server = build_workflow_server_from_workflow_config(config)

    listed = await server.api.list_capabilities(source_id="local.lda_report")
    names = {capability["name"] for capability in listed["capabilities"]}

    assert "local.lda_report.build_report" in names
    assert "local.lda_report.finalise_report" in names


def test_lda_report_workflow_builder_generates_committed_raw_plan() -> None:
    workflow = build_workflow()
    payload = workflow_plan_payload()
    committed = json.loads(
        (EXAMPLE_DIR / "workflow.plan.json").read_text(encoding="utf-8")
    )
    validated = RawWorkflowPlan.model_validate(payload)

    assert workflow.name == "lda_report_case_study"
    assert validated.name == "lda_report_case_study"
    assert any(node.id == "review_issues" for node in validated.nodes)
    assert payload == committed


@pytest.mark.asyncio
async def test_lda_report_workflow_artifact_interrupt_resume_path(
    tmp_path: Path,
) -> None:
    config = load_workflow_config(EXAMPLE_DIR / "wf.config.json")
    config.server.store.root = tmp_path / "store"
    server = build_workflow_server_from_workflow_config(config)
    plan = json.loads((EXAMPLE_DIR / "workflow.plan.json").read_text(encoding="utf-8"))

    await server.api.create_artifact_from_plan(
        artifact_id="lda_report_case_study",
        version=1,
        title="lda.chat Report Case Study",
        plan=plan,
        outcomes=["completed", "cancelled"],
        source_bindings={
            "local.lda_docs": "local.lda_docs",
            "local.lda_report": "local.lda_report",
            "local.issue_board": "local.issue_board",
        },
    )
    await server.api.save_deployment(
        {
            "id": "lda_report_case_study.default",
            "artifact_id": "lda_report_case_study",
            "artifact_version": 1,
            "bindings": {
                "local.lda_docs": "local.lda_docs",
                "local.lda_report": "local.lda_report",
                "local.issue_board": "local.issue_board",
            },
        }
    )
    run_input = json.loads((EXAMPLE_DIR / "run-input.json").read_text(encoding="utf-8"))
    run_input["board_path"] = str(tmp_path / "issue-board.json")
    started = await server.api.run_deployment(
        deployment_id="lda_report_case_study.default",
        workflow_input=run_input,
    )

    assert started["status"] == "interrupted"
    assert started["interrupt"]["kind"] == "issue_review"
    assert started["interrupt"]["typed"] is True
    assert started["interrupt"]["request_schema"]["required"] == [
        "report_markdown",
        "proposed_issues",
    ]
    assert started["interrupt"]["resume_schema"]["required"] == [
        "approved",
        "selected_issue_ids",
    ]
    proposed_ids = [
        issue["id"] for issue in started["interrupt"]["payload"]["proposed_issues"]
    ]
    assert proposed_ids

    resumed = await server.api.resume_run(
        run_id=started["run_id"],
        resume_payload={
            "approved": True,
            "selected_issue_ids": proposed_ids[:2],
            "comment": "Create selected issues before the defense.",
        },
        resume_outcome="submitted",
    )

    assert resumed["status"] == "completed"
    assert resumed["outcome"] == "completed"
    assert resumed["output"]["approved"] is True
    assert resumed["output"]["created_issues"]
    assert resumed["output"]["markdown"].startswith(
        "# lda.chat Thesis And Project Readiness Report"
    )


@pytest.mark.asyncio
async def test_lda_report_workflow_cancelled_resume_path(tmp_path: Path) -> None:
    config = load_workflow_config(EXAMPLE_DIR / "wf.config.json")
    config.server.store.root = tmp_path / "store"
    server = build_workflow_server_from_workflow_config(config)
    plan = json.loads((EXAMPLE_DIR / "workflow.plan.json").read_text(encoding="utf-8"))

    await server.api.create_artifact_from_plan(
        artifact_id="lda_report_cancel_case",
        version=1,
        title="lda.chat Report Cancel Case",
        plan=plan,
        outcomes=["completed", "cancelled"],
        source_bindings={
            "local.lda_docs": "local.lda_docs",
            "local.lda_report": "local.lda_report",
            "local.issue_board": "local.issue_board",
        },
    )
    await server.api.save_deployment(
        {
            "id": "lda_report_cancel_case.default",
            "artifact_id": "lda_report_cancel_case",
            "artifact_version": 1,
            "bindings": {
                "local.lda_docs": "local.lda_docs",
                "local.lda_report": "local.lda_report",
                "local.issue_board": "local.issue_board",
            },
        }
    )
    run_input = json.loads((EXAMPLE_DIR / "run-input.json").read_text(encoding="utf-8"))
    run_input["board_path"] = str(tmp_path / "issue-board.json")
    started = await server.api.run_deployment(
        deployment_id="lda_report_cancel_case.default",
        workflow_input=run_input,
    )

    resumed = await server.api.resume_run(
        run_id=started["run_id"],
        resume_payload={
            "approved": False,
            "selected_issue_ids": [],
            "comment": "Revise risk wording.",
        },
        resume_outcome="cancelled",
    )

    assert resumed["status"] == "completed"
    assert resumed["outcome"] == "cancelled"
    assert resumed["output"]["approved"] is False
    assert "Revision Requested" in resumed["output"]["markdown"]
