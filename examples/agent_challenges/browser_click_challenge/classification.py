from __future__ import annotations

from typing import Any

import yaml

from examples.agent_challenges.browser_click_challenge.challenge import (
    CHALLENGE_REPORT_ATTEMPT_FIELDS,
    CHALLENGE_REPORT_READ_FIELDS,
    CHALLENGE_REPORT_REQUIRED_FIELDS,
    Classification,
)


def classify_output(text: str) -> Classification:
    report = extract_challenge_report(text)
    if report is not None:
        return classify_challenge_report(report)

    lowered = text.lower()
    product_command_markers = [
        "wf ",
        "wf-rpc-server",
    ]
    workflow_evidence_markers = [
        "deployment",
        "run id",
        "run_",
    ]
    used_product_command = any(marker in lowered for marker in product_command_markers)
    has_workflow_evidence = any(
        marker in lowered for marker in workflow_evidence_markers
    )
    used_helper_script = (
        "uv run python" in lowered
        or "python examples/" in lowered
        or "run_workflow.py" in lowered
    )
    failed = any(
        marker in lowered
        for marker in [
            "error:",
            "failed",
            "traceback",
            "exception",
            "validation failed",
        ]
    )
    before_false = _contains_bool_marker(lowered, "before.clicked", "false") or (
        '"before"' in lowered and '"clicked": false' in lowered
    )
    after_true = _contains_bool_marker(lowered, "after.clicked", "true") or (
        '"after"' in lowered and '"clicked": true' in lowered
    )

    if used_product_command and before_false and after_true and not failed:
        return "success"
    if has_workflow_evidence and used_helper_script and before_false and after_true:
        return "workflow_script"
    if (used_product_command or has_workflow_evidence) and failed:
        return "run_failed"
    if not has_workflow_evidence and (
        before_false or after_true or "playwright" in lowered
    ):
        return "workflow_not_used"
    return "unknown"


def extract_challenge_report(text: str) -> dict[str, Any] | None:
    """Extract the required final YAML challenge report from agent output."""
    marker = "```yaml"
    start = text.lower().rfind(marker)
    if start == -1:
        return None
    body_start = text.find("\n", start)
    if body_start == -1:
        return None
    end = text.find("```", body_start + 1)
    if end == -1:
        return None
    raw_yaml = text[body_start + 1 : end]
    loaded = yaml.safe_load(raw_yaml)
    if not isinstance(loaded, dict):
        return None
    report = loaded.get("challenge_report")
    return report if isinstance(report, dict) else None


def classify_challenge_report(report: dict[str, Any]) -> Classification:
    if challenge_report_schema_errors(report):
        return "unknown"

    used_product_path = report.get("used_product_path") is True
    used_helper_script = report.get("used_helper_script") is True
    workflow_file = report.get("workflow_file")
    deployment_id = report.get("deployment_id")
    run_id = report.get("run_id")
    before_clicked = report.get("before_clicked")
    after_clicked = report.get("after_clicked")
    failed = report.get("run_failed") is True

    if failed:
        return "run_failed"
    if used_helper_script:
        return "workflow_script"
    if (
        used_product_path
        and isinstance(workflow_file, str)
        and bool(workflow_file)
        and isinstance(deployment_id, str)
        and bool(deployment_id)
        and isinstance(run_id, str)
        and bool(run_id)
        and before_clicked is False
        and after_clicked is True
    ):
        return "success"
    if not used_product_path and (
        before_clicked is not None or after_clicked is not None
    ):
        return "workflow_not_used"
    return "unknown"


def challenge_report_schema_errors(report: dict[str, Any]) -> list[str]:
    """Return human-readable schema errors for the final YAML report block."""
    errors: list[str] = []
    missing = sorted(CHALLENGE_REPORT_REQUIRED_FIELDS.difference(report))
    errors.extend(f"missing challenge_report.{field}" for field in missing)

    for field in (
        "used_product_path",
        "used_helper_script",
        "before_clicked",
        "after_clicked",
        "run_failed",
        "leftover_processes",
    ):
        if field in report and not isinstance(report[field], bool):
            errors.append(f"challenge_report.{field} must be boolean")
    for field in ("workflow_file", "deployment_id", "run_id", "notes"):
        if field in report and not isinstance(report[field], str):
            errors.append(f"challenge_report.{field} must be string")

    read = report.get("read")
    if isinstance(read, dict):
        missing_read = sorted(CHALLENGE_REPORT_READ_FIELDS.difference(read))
        errors.extend(
            f"missing challenge_report.read.{field}" for field in missing_read
        )
        for field in CHALLENGE_REPORT_READ_FIELDS.intersection(read):
            if not isinstance(read[field], bool):
                errors.append(f"challenge_report.read.{field} must be boolean")
    elif "read" in report:
        errors.append("challenge_report.read must be object")

    attempts = report.get("attempts")
    if isinstance(attempts, dict):
        missing_attempts = sorted(CHALLENGE_REPORT_ATTEMPT_FIELDS.difference(attempts))
        errors.extend(
            f"missing challenge_report.attempts.{field}" for field in missing_attempts
        )
        for field in CHALLENGE_REPORT_ATTEMPT_FIELDS.intersection(attempts):
            value = attempts[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"challenge_report.attempts.{field} must be >= 0 integer")
    elif "attempts" in report:
        errors.append("challenge_report.attempts must be object")

    missed = report.get("missed_requirements")
    if "missed_requirements" in report and (
        not isinstance(missed, list)
        or any(not isinstance(item, str) for item in missed)
    ):
        errors.append("challenge_report.missed_requirements must be list of strings")

    return errors


def _contains_bool_marker(text: str, marker: str, value: str) -> bool:
    marker_index = text.find(marker)
    if marker_index == -1:
        return False
    return value in text[marker_index : marker_index + 80]
