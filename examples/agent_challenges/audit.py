from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from examples.agent_challenges.classification import extract_challenge_report
from examples.agent_challenges.reports import report_from_result


def audit_from_result(
    result_path: Path,
    *,
    manual_classification: str,
    report_path: Path | None = None,
    audited_at: str | None = None,
    auditor: str = "human",
    read_overrides: dict[str, bool] | None = None,
    evidence_overrides: dict[str, object] | None = None,
    corrections: list[str] | None = None,
    notes: str = "",
) -> tuple[Path, dict[str, Any]]:
    if report_path is None:
        workspace, report_text = report_from_result(result_path)
    else:
        workspace = report_path.parent
        report_text = report_path.read_text(encoding="utf-8")
    result = _load_result(result_path)
    challenge_report = extract_challenge_report(report_text) or {}
    read_flags = _dict_or_empty(challenge_report.get("read"))
    read_flags.update(read_overrides or {})
    evidence = _evidence_from_report(challenge_report)
    evidence.update(evidence_overrides or {})

    audit = {
        "manual_audit": {
            "auditor": auditor,
            "audited_at": audited_at or _utc_now(),
            "auto_classification": _string_or_none(result.get("classification")),
            "manual_classification": manual_classification,
            "valid_product_run": _valid_product_run(challenge_report),
            "product_path_used": challenge_report.get("used_product_path") is True,
            "helper_script_used": challenge_report.get("used_helper_script") is True,
            "run_succeeded": challenge_report.get("run_failed") is False,
            "duration_seconds": result.get("duration_seconds"),
            "returncode": result.get("returncode"),
            "evidence": evidence,
            "read_flags": read_flags,
            "attempts": _dict_or_empty(challenge_report.get("attempts")),
            "missed_requirements": _list_or_empty(
                challenge_report.get("missed_requirements")
            ),
            "agent_notes": challenge_report.get("notes"),
            "corrections": corrections or [],
            "notes": notes,
        }
    }
    return workspace, audit


def save_manual_audit(
    result_path: Path,
    *,
    manual_classification: str,
    report_path: Path | None = None,
    audited_at: str | None = None,
    auditor: str = "human",
    read_overrides: dict[str, bool] | None = None,
    evidence_overrides: dict[str, object] | None = None,
    corrections: list[str] | None = None,
    notes: str = "",
    output_name: str = "manual-audit.yaml",
) -> Path:
    workspace, audit = audit_from_result(
        result_path,
        manual_classification=manual_classification,
        report_path=report_path,
        audited_at=audited_at,
        auditor=auditor,
        read_overrides=read_overrides,
        evidence_overrides=evidence_overrides,
        corrections=corrections,
        notes=notes,
    )
    output_path = workspace / output_name
    output_path.write_text(
        yaml.safe_dump(audit, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return output_path


def _load_result(result_path: Path) -> dict[str, Any]:
    loaded = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("result file must contain a JSON object")
    return loaded


def _evidence_from_report(report: dict[str, Any]) -> dict[str, object]:
    return {
        key: report[key]
        for key in (
            "deployment_id",
            "run_id",
            "before_clicked",
            "after_clicked",
            "leftover_processes",
        )
        if key in report
    }


def _valid_product_run(report: dict[str, Any]) -> bool:
    return (
        report.get("used_product_path") is True
        and report.get("used_helper_script") is False
        and report.get("run_failed") is False
    )


def _dict_or_empty(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list_or_empty(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_bool_assignment(value: str) -> tuple[str, bool]:
    key, separator, raw = value.partition("=")
    if separator != "=" or not key:
        raise ValueError("expected KEY=true or KEY=false")
    lowered = raw.lower()
    if lowered == "true":
        return key, True
    if lowered == "false":
        return key, False
    raise ValueError("boolean override value must be true or false")


def _parse_value_assignment(value: str) -> tuple[str, object]:
    key, separator, raw = value.partition("=")
    if separator != "=" or not key:
        raise ValueError("expected KEY=VALUE")
    lowered = raw.lower()
    if lowered == "true":
        return key, True
    if lowered == "false":
        return key, False
    try:
        return key, int(raw)
    except ValueError:
        return key, raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-result", type=Path, required=True)
    parser.add_argument(
        "--from-report",
        type=Path,
        default=None,
        help=(
            "Use this final report Markdown for challenge_report YAML while "
            "keeping timeout/duration metadata from --from-result."
        ),
    )
    parser.add_argument("--manual-classification", required=True)
    parser.add_argument("--auditor", default="human")
    parser.add_argument("--audited-at", default=None)
    parser.add_argument("--set-read", action="append", default=[])
    parser.add_argument("--set-evidence", action="append", default=[])
    parser.add_argument("--correction", action="append", default=[])
    parser.add_argument("--notes", default="")
    parser.add_argument("--output-name", default="manual-audit.yaml")
    args = parser.parse_args(argv)

    try:
        read_overrides = dict(_parse_bool_assignment(item) for item in args.set_read)
        evidence_overrides = dict(
            _parse_value_assignment(item) for item in args.set_evidence
        )
        output_path = save_manual_audit(
            args.from_result,
            manual_classification=args.manual_classification,
            report_path=args.from_report,
            audited_at=args.audited_at,
            auditor=args.auditor,
            read_overrides=read_overrides,
            evidence_overrides=evidence_overrides,
            corrections=list(args.correction),
            notes=args.notes,
            output_name=args.output_name,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(output_path.as_posix())
    return 0
