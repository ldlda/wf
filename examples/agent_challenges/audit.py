from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from examples.agent_challenges.classification import extract_challenge_report
from examples.agent_challenges.report_models import build_trial_report
from examples.agent_challenges.reports import (
    report_from_result,
    write_trial_report_projections,
)


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


def manual_audit_from_v2_result(
    result: dict[str, object],
    *,
    workspace: Path | None = None,
    official_outcome: str = "pending",
    auditor_notes: str = "",
    audited_at: str | None = None,
    auditor: str = "human",
    output_name: str = "manual-audit.yaml",
) -> tuple[Path, dict[str, Any]]:
    task_outcome = result.get("task_outcome", "unknown")
    evaluation_validity = result.get("evaluation_validity", "unknown")
    policy = result.get("policy", {})
    if not isinstance(policy, dict):
        policy = {}

    audit: dict[str, Any] = {
        "manual_audit": {
            "auditor": auditor,
            "audited_at": audited_at or _utc_now(),
            "task_outcome": task_outcome,
            "evaluation_validity": evaluation_validity,
            "official_outcome": official_outcome,
            "auditor_notes": auditor_notes,
            "automatic_evidence": {
                "task_outcome": task_outcome,
                "evaluation_validity": evaluation_validity,
                "policy": policy,
            },
            "duration_seconds": result.get("duration_seconds"),
            "returncode": result.get("returncode"),
        }
    }

    output_path: Path
    if workspace is not None:
        output_path = workspace / output_name
    else:
        output_path = Path(output_name)
    output_path.write_text(
        yaml.safe_dump(audit, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    return output_path, audit


_VALID_OFFICIAL_OUTCOMES = frozenset({"pass", "fail", "invalid"})


@dataclass(frozen=True, slots=True)
class V2AuditPaths:
    audit: Path
    markdown: Path
    machine: Path
    results_markdown: Path | None = None


def save_v2_manual_audit(
    result_path: Path,
    *,
    official_outcome: str,
    auditor: str = "human",
    audited_at: str | None = None,
    read_overrides: dict[str, bool] | None = None,
    evidence_overrides: dict[str, object] | None = None,
    corrections: list[str] | None = None,
    notes: str = "",
) -> V2AuditPaths:
    """Write authoritative audit data and regenerate both report projections.

    Args:
        result_path: Path to the V2 raw result JSON file.
        official_outcome: One of 'pass', 'fail', 'invalid'.
        auditor: Name or identifier of the human auditor.
        audited_at: ISO-8601 timestamp string.
        read_overrides: Override read flags from the challenge report.
        evidence_overrides: Override evidence values from the challenge report.
        corrections: List of correction strings.
        notes: Free-form auditor notes.

    Returns:
        V2AuditPaths with paths to audit YAML, markdown report, and machine report.
    """
    if official_outcome not in _VALID_OFFICIAL_OUTCOMES:
        raise ValueError(
            f"official_outcome must be one of {sorted(_VALID_OFFICIAL_OUTCOMES)}, "
            f"got {official_outcome!r}"
        )

    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("result file must contain a JSON object")

    harness_version = result.get("harness_version")
    if harness_version != "v2":
        raise ValueError(
            f"save_v2_manual_audit requires harness_version='v2', "
            f"got {harness_version!r}"
        )

    workspace_path_str = result.get("workspace_path")
    if not isinstance(workspace_path_str, str) or not workspace_path_str:
        raise ValueError("result is missing workspace_path")
    workspace_path = Path(workspace_path_str)

    result_path_str = result.get("result_path")
    if not isinstance(result_path_str, str) or not result_path_str:
        raise ValueError("result is missing result_path")

    audit_payload: dict[str, object] = {
        "manual_audit": {
            "official_outcome": official_outcome,
            "auditor": auditor,
            "audited_at": audited_at or _utc_now(),
            "task_outcome": result.get("task_outcome"),
            "evaluation_validity": result.get("evaluation_validity"),
            "corrections": corrections or [],
            "notes": notes,
            "read_flags": dict(read_overrides or {}),
            "evidence": dict(evidence_overrides or {}),
        }
    }

    yaml_text = yaml.safe_dump(audit_payload, sort_keys=False, allow_unicode=True)

    trial_report = build_trial_report(
        result,
        audit=audit_payload,
        raw_result_path=result_path_str,
        workspace_path=workspace_path_str,
    )

    markdown_path = workspace_path / "final-report.md"
    machine_path = result_path.with_suffix(".report.json")
    results_markdown_path = result_path.with_suffix(".report.md")
    write_trial_report_projections(
        trial_report,
        markdown_path=markdown_path,
        machine_path=machine_path,
        extra_markdown_paths=[results_markdown_path],
    )

    audit_path = workspace_path / "manual-audit.yaml"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = audit_path.with_name(f".{audit_path.name}.tmp")
    temporary.write_text(yaml_text, encoding="utf-8")
    temporary.replace(audit_path)

    return V2AuditPaths(
        audit=audit_path,
        markdown=markdown_path,
        machine=machine_path,
        results_markdown=results_markdown_path,
    )
