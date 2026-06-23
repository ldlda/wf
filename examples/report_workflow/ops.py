from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from wf_authoring import node

_EXAMPLE_DIR = Path(__file__).resolve().parent


class ReadInput(BaseModel):
    text: str | None = Field(
        default=None,
        description="Structured Markdown notes passed by value. Preferred for workflows.",
    )
    path: str | None = Field(
        default=None,
        description="Legacy path to a UTF-8 Markdown notes file inside the example.",
    )


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
    return _read_notes(payload)


@node(name="extract_report")
def extract_report(payload: ExtractInput) -> ReportOutput:
    return _extract_report(payload)


@node(name="render_markdown_report")
def render_markdown_report(payload: MarkdownInput) -> MarkdownOutput:
    return _render_markdown_report(payload)


def _read_notes(payload: ReadInput) -> ReadOutput:
    if payload.text is not None:
        return ReadOutput(text=payload.text)
    if payload.path is None:
        raise ValueError("read_notes requires either text or path")
    path = _resolve_example_path(payload.path)
    return ReadOutput(text=path.read_text(encoding="utf-8"))


def _extract_report(payload: ExtractInput) -> ReportOutput:
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


def _render_markdown_report(payload: MarkdownInput) -> MarkdownOutput:
    report = payload.report
    lines = [
        f"# {report.title}",
        "",
        "Summary:",
        report.summary,
        "",
        "Actions:",
    ]
    lines.extend(
        f"- {item.owner} | {item.task} | {item.due}" for item in report.action_items
    )
    lines.extend(["", "Risks:"])
    lines.extend(f"- {risk}" for risk in report.risks)
    lines.extend(["", "Followups:"])
    lines.extend(f"- {followup}" for followup in report.followups)
    return MarkdownOutput(markdown="\n".join(lines))


def _resolve_example_path(path: str) -> Path:
    """Resolve user input to a file inside this example directory only."""
    candidate = Path(path)
    if candidate.is_absolute():
        raise ValueError("read_notes only accepts paths relative to the example")
    resolved = (_EXAMPLE_DIR / candidate).resolve()
    if not resolved.is_relative_to(_EXAMPLE_DIR):
        raise ValueError("read_notes path must stay inside the example directory")
    return resolved


registry = [read_notes, extract_report, render_markdown_report]
