from __future__ import annotations

from pydantic import BaseModel, Field

from wf_authoring import node

from .document_source import DocumentText


class AnalyzeDocumentsInput(BaseModel):
    documents: list[DocumentText]


class Finding(BaseModel):
    source: str
    summary: str
    risks: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class AnalyzeDocumentsOutput(BaseModel):
    analysis: list[Finding]


class BuildReportInput(BaseModel):
    analysis: list[Finding]


class ReadinessReport(BaseModel):
    title: str
    summary: str
    achievements: list[str]
    risks: list[str]
    next_actions: list[str]


class BuildReportOutput(BaseModel):
    report: ReadinessReport
    markdown: str


class CreateIssueDraftsInput(BaseModel):
    report: ReadinessReport


class ProposedIssue(BaseModel):
    id: str
    title: str
    body: str
    severity: str = "medium"


class CreateIssueDraftsOutput(BaseModel):
    issues: list[ProposedIssue]


class CreatedIssue(BaseModel):
    id: str
    title: str
    url: str


class FinaliseReportInput(BaseModel):
    report: ReadinessReport
    created_issues: list[CreatedIssue] = Field(default_factory=list)
    approved: bool
    selected_issue_ids: list[str] = Field(default_factory=list)
    comment: str | None = None


class FinalReportOutput(BaseModel):
    approved: bool
    markdown: str
    created_issues: list[CreatedIssue]
    selected_issue_ids: list[str]
    comment: str | None = None


class RecordRevisionRequestInput(BaseModel):
    comment: str | None = None


@node(
    name="analyze_documents",
    description="Extract deterministic findings from lda.chat project documents.",
)
def analyze_documents(payload: AnalyzeDocumentsInput) -> AnalyzeDocumentsOutput:
    return _analyze_documents(payload)


@node(
    name="build_report",
    description="Build a typed lda.chat readiness report from document findings.",
)
def build_report(payload: BuildReportInput) -> BuildReportOutput:
    return _build_report(payload)


@node(
    name="create_issue_drafts",
    description="Create proposed local issue drafts from report risks and next actions.",
)
def create_issue_drafts(payload: CreateIssueDraftsInput) -> CreateIssueDraftsOutput:
    return _create_issue_drafts(payload)


@node(
    name="finalise_report",
    description="Render the approved report and include created issue references.",
)
def finalise_report(payload: FinaliseReportInput) -> FinalReportOutput:
    return _finalise_report(payload)


@node(
    name="record_revision_request",
    description="Return a cancelled report result when the human asks for revision.",
)
def record_revision_request(payload: RecordRevisionRequestInput) -> FinalReportOutput:
    return _record_revision_request(payload)


def _analyze_documents(payload: AnalyzeDocumentsInput) -> AnalyzeDocumentsOutput:
    findings: list[Finding] = []
    for document in payload.documents:
        text = document.text.lower()
        risks = _lines_after(document.text, "Material risks:")
        actions = _lines_after(document.text, "Near-term:") or _lines_after(
            document.text, "Mitigations:"
        )
        if "workflow substrate" in text:
            summary = (
                "lda.chat is positioned as a workflow substrate for external agents."
            )
        elif "evaluation" in text:
            summary = "Evaluation evidence is bounded and should be presented as operational evidence."
        elif "risk" in text:
            summary = "The current risk register emphasizes framing, evaluation, and storage limits."
        elif "roadmap" in text:
            summary = "Near-term roadmap focuses on typed interrupts, deterministic demos, and a console."
        else:
            summary = document.text.splitlines()[0].lstrip("# ").strip()
        findings.append(
            Finding(
                source=document.name,
                summary=summary,
                risks=risks[:3],
                actions=actions[:3],
            )
        )
    return AnalyzeDocumentsOutput(analysis=findings)


def _build_report(payload: BuildReportInput) -> BuildReportOutput:
    achievements = [
        finding.summary
        for finding in payload.analysis
        if "risk register" not in finding.summary
    ]
    risks = _unique(item for finding in payload.analysis for item in finding.risks)
    next_actions = _unique(
        item for finding in payload.analysis for item in finding.actions
    )
    report = ReadinessReport(
        title="lda.chat Thesis And Project Readiness Report",
        summary=(
            "lda.chat is a typed workflow substrate with lifecycle records, "
            "source-provider boundaries, and agent-operable CLI/RPC surfaces."
        ),
        achievements=achievements[:6],
        risks=risks[:6],
        next_actions=next_actions[:6],
    )
    return BuildReportOutput(report=report, markdown=_render_report(report))


def _create_issue_drafts(payload: CreateIssueDraftsInput) -> CreateIssueDraftsOutput:
    issues: list[ProposedIssue] = []
    for index, risk in enumerate(payload.report.risks[:4], start=1):
        issue_id = f"risk-{index}"
        issues.append(
            ProposedIssue(
                id=issue_id,
                title=risk.rstrip("."),
                body=f"Track mitigation for: {risk}",
                severity="high" if "title" in risk.lower() else "medium",
            )
        )
    if not issues:
        issues.append(
            ProposedIssue(
                id="follow-up-1",
                title="Review thesis demo readiness",
                body="Confirm the prepared workflow and replay are ready for defense.",
                severity="medium",
            )
        )
    return CreateIssueDraftsOutput(issues=issues)


def _finalise_report(payload: FinaliseReportInput) -> FinalReportOutput:
    markdown = _render_report(payload.report)
    if payload.created_issues:
        markdown += "\n\nCreated issues:\n"
        markdown += "\n".join(
            f"- {issue.id}: {issue.title} ({issue.url})"
            for issue in payload.created_issues
        )
    if payload.comment:
        markdown += f"\n\nApproval comment: {payload.comment}"
    return FinalReportOutput(
        approved=payload.approved,
        markdown=markdown,
        created_issues=payload.created_issues,
        selected_issue_ids=payload.selected_issue_ids,
        comment=payload.comment,
    )


def _record_revision_request(payload: RecordRevisionRequestInput) -> FinalReportOutput:
    comment = payload.comment or "Revision requested."
    return FinalReportOutput(
        approved=False,
        markdown=f"# Revision Requested\n\n{comment}",
        created_issues=[],
        selected_issue_ids=[],
        comment=comment,
    )


def _render_report(report: ReadinessReport) -> str:
    lines = [f"# {report.title}", "", "Summary:", report.summary, ""]
    lines.append("Achievements:")
    lines.extend(f"- {item}" for item in report.achievements)
    lines.extend(["", "Risks:"])
    lines.extend(f"- {item}" for item in report.risks)
    lines.extend(["", "Next actions:"])
    lines.extend(f"- {item}" for item in report.next_actions)
    return "\n".join(lines)


def _lines_after(text: str, heading: str) -> list[str]:
    lines: list[str] = []
    active = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == heading:
            active = True
            continue
        if active and line.endswith(":"):
            break
        if active and line.startswith("- "):
            lines.append(line.removeprefix("- ").strip())
    return lines


def _unique(items: object) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for item in items:  # type: ignore[union-attr]
        if isinstance(item, str) and item and item not in seen:
            seen.add(item)
            values.append(item)
    return values


registry = [
    analyze_documents,
    build_report,
    create_issue_drafts,
    finalise_report,
    record_revision_request,
]
