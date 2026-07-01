from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from wf_authoring import node

from .report_source import CreatedIssue, ProposedIssue

_EXAMPLE_DIR = Path(__file__).resolve().parent


class ResetIssueBoardInput(BaseModel):
    board_path: str = Field(default="issue-board.json")


class ResetIssueBoardOutput(BaseModel):
    reset: bool
    board_path: str


class CreateIssuesInput(BaseModel):
    issues: list[ProposedIssue]
    selected_issue_ids: list[str]
    board_path: str = Field(default="issue-board.json")


class CreateIssuesOutput(BaseModel):
    created_issues: list[CreatedIssue]
    board_path: str


@node(name="reset_issue_board", description="Reset the local demo issue board file.")
def reset_issue_board(payload: ResetIssueBoardInput) -> ResetIssueBoardOutput:
    return _reset_issue_board(payload)


@node(
    name="create_issues",
    description="Create selected issues in the local demo issue board.",
)
def create_issues(payload: CreateIssuesInput) -> CreateIssuesOutput:
    return _create_issues(payload)


def _reset_issue_board(payload: ResetIssueBoardInput) -> ResetIssueBoardOutput:
    path = _resolve_board_path(payload.board_path)
    path.unlink(missing_ok=True)
    return ResetIssueBoardOutput(reset=True, board_path=str(path))


def _create_issues(payload: CreateIssuesInput) -> CreateIssuesOutput:
    path = _resolve_board_path(payload.board_path)
    selected = set(payload.selected_issue_ids)
    existing = _read_board(path)
    created: list[CreatedIssue] = []
    next_number = len(existing) + 1
    for issue in payload.issues:
        if issue.id not in selected:
            continue
        issue_id = f"ISSUE-{next_number:03d}"
        created_issue = CreatedIssue(
            id=issue_id,
            title=issue.title,
            url=f"local://issue-board/{issue_id}",
        )
        existing.append(
            {
                "id": created_issue.id,
                "title": created_issue.title,
                "url": created_issue.url,
                "body": issue.body,
                "severity": issue.severity,
            }
        )
        created.append(created_issue)
        next_number += 1
    _write_board(path, existing)
    return CreateIssuesOutput(created_issues=created, board_path=str(path))


def _resolve_board_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (_EXAMPLE_DIR / candidate).resolve()
    # Keep the demo capability from deleting or writing arbitrary files while still
    # allowing pytest tmp_path fixtures to exercise isolated board files.
    allowed_roots = [_EXAMPLE_DIR.resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        raise ValueError("board_path must stay inside the example dir or temp dir")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _read_board(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("issue board file must contain a JSON list")
    return [item for item in value if isinstance(item, dict)]


def _write_board(path: Path, value: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


registry = [reset_issue_board, create_issues]
