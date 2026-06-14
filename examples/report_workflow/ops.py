from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from wf_authoring import node


class ReadInput(BaseModel):
    path: str = Field(description="Path to a UTF-8 Markdown notes file.")


class ReadOutput(BaseModel):
    text: str


class ExtractInput(BaseModel):
    text: str


class ActionItem(BaseModel):
    owner: str
    task: str
    due: str


class ReportOutput(BaseModel):
    title: str
    summary: str
    action_items: list[ActionItem]
    risks: list[str]
    followups: list[str]


class MarkdownInput(BaseModel):
    report: ReportOutput


class MarkdownOutput(BaseModel):
    markdown: str


@node(name="read_notes")
def read_notes(payload: ReadInput) -> ReadOutput:
    return ReadOutput(text=Path(payload.path).read_text(encoding="utf-8"))


@node(name="extract_report")
def extract_report(payload: ExtractInput) -> ReportOutput:
    title = ""
    summary_lines: list[str] = []
    actions: list[ActionItem] = []
    risks: list[str] = []
    followups: list[str] = []
    section: str | None = None

    for raw_line in payload.text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            continue
        if line.endswith(":"):
            section = line[:-1].lower()
            continue
        if section == "summary":
            summary_lines.append(line)
        elif section == "actions" and line.startswith("- "):
            parts = [part.strip() for part in line.removeprefix("- ").split("|")]
            if len(parts) == 3:
                owner, task, due = parts
                actions.append(ActionItem(owner=owner, task=task, due=due))
        elif section == "risks" and line.startswith("- "):
            risks.append(line.removeprefix("- ").strip())
        elif section == "followups" and line.startswith("- "):
            followups.append(line.removeprefix("- ").strip())

    return ReportOutput(
        title=title,
        summary=" ".join(summary_lines),
        action_items=actions,
        risks=risks,
        followups=followups,
    )


@node(name="render_markdown_report")
def render_markdown_report(payload: MarkdownInput) -> MarkdownOutput:
    report = payload.report
    lines = [
        f"# {report.title}",
        "",
        report.summary,
        "",
        "## Action Items",
    ]
    lines.extend(
        f"- {item.owner}: {item.task} (due: {item.due})"
        for item in report.action_items
    )
    lines.extend(["", "## Risks"])
    lines.extend(f"- {risk}" for risk in report.risks)
    lines.extend(["", "## Followups"])
    lines.extend(f"- {followup}" for followup in report.followups)
    return MarkdownOutput(markdown="\n".join(lines))


registry = [read_notes, extract_report, render_markdown_report]
