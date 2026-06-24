from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHALLENGES_ROOT = ROOT / "examples" / "agent_challenges"


@dataclass(frozen=True, slots=True)
class TrialSummary:
    challenge: str
    model: str
    profile: str
    trial: int
    manual: str
    task: str
    validity: str
    duration_seconds: float
    tokens_total: int
    attempts: str
    read_flags: str
    notes: str


def _short_model(model: str) -> str:
    name = model.rsplit("/", 1)[-1]
    for suffix in ("-v4-flash-free", "-v2.5-free", "-3-ultra-free"):
        name = name.replace(suffix, "")
    return name


def _short_challenge(challenge: str) -> str:
    return {
        "browser_click": "browser",
        "report_workflow": "report",
    }.get(challenge, challenge)


def _string(value: object, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def _float(value: object, default: float = 0.0) -> float:
    return float(value) if isinstance(value, int | float) else default


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _attempts(agent_self_report: dict[str, Any]) -> str:
    attempts = _dict(agent_self_report.get("attempts"))
    total = attempts.get("total")
    failed = attempts.get("failed")
    if isinstance(total, int) and isinstance(failed, int):
        return f"{failed}/{total}"
    return ""


def _read_flags(agent_self_report: dict[str, Any]) -> str:
    reads = _dict(agent_self_report.get("read"))
    enabled = [key for key, value in sorted(reads.items()) if value is True]
    return ",".join(enabled)


def load_trial_summary(path: Path) -> TrialSummary:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"report must be a JSON object: {path}")

    identity = _dict(data.get("identity"))
    outcome = _dict(data.get("outcome"))
    manual_audit = _dict(data.get("manual_audit"))
    evidence = _dict(data.get("automatic_evidence"))
    tokens = _dict(evidence.get("tokens"))
    self_report = _dict(data.get("agent_self_report"))

    challenge = _short_challenge(_string(identity.get("challenge_id")))
    model = _short_model(_string(identity.get("model")))
    manual = _string(manual_audit.get("official_outcome"), "pending")
    notes = _string(manual_audit.get("notes"))

    return TrialSummary(
        challenge=challenge,
        model=model,
        profile=_string(identity.get("instruction_profile")),
        trial=_int(identity.get("trial_index")),
        manual=manual or "pending",
        task=_string(outcome.get("task_outcome")),
        validity=_string(outcome.get("evaluation_validity")),
        duration_seconds=_float(outcome.get("duration_seconds")),
        tokens_total=_int(tokens.get("total")),
        attempts=_attempts(self_report),
        read_flags=_read_flags(self_report),
        notes=" ".join(notes.split()),
    )


def find_report_files(paths: list[Path]) -> list[Path]:
    roots = paths or sorted(DEFAULT_CHALLENGES_ROOT.glob("*_challenge"))
    reports: list[Path] = []
    for root in roots:
        if root.is_file():
            reports.append(root)
            continue
        results_dir = root / "results"
        if results_dir.is_dir():
            reports.extend(sorted(results_dir.glob("*.report.json")))
            continue
        reports.extend(sorted(root.glob("*.report.json")))
    return sorted(set(reports))


def _markdown_escape(value: object) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def render_markdown(summaries: list[TrialSummary]) -> str:
    headers = [
        "challenge",
        "model",
        "profile",
        "trial",
        "manual",
        "task",
        "validity",
        "minutes",
        "tokens",
        "attempts",
        "reads",
        "notes",
    ]
    rows = [
        [
            item.challenge,
            item.model,
            item.profile,
            f"{item.trial:03d}",
            item.manual,
            item.task,
            item.validity,
            f"{item.duration_seconds / 60:.1f}",
            str(item.tokens_total),
            item.attempts,
            item.read_flags,
            item.notes,
        ]
        for item in summaries
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(_markdown_escape(cell) for cell in row) + " |" for row in rows
    )
    return "\n".join(lines) + "\n"


def render_json(summaries: list[TrialSummary]) -> str:
    return json.dumps(
        [asdict(item) for item in summaries],
        indent=2,
        sort_keys=True,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize agent challenge report projections."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Challenge directories, results directories, or .report.json files.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    reports = find_report_files(args.paths)
    summaries = [load_trial_summary(path) for path in reports]
    if args.format == "json":
        print(render_json(summaries))
    else:
        print(render_markdown(summaries), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
