from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrialIdentity(StrictReportModel):
    challenge_id: str
    model: str
    variant: str
    instruction_profile: str
    trial_index: int
    repository_commit: str | None = None
    repository_dirty: bool | None = None
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    raw_result_path: str
    workspace_path: str


class TrialOutcome(StrictReportModel):
    task_outcome: str
    evaluation_validity: str
    duration_seconds: float
    returncode: int | None = None
    assertion_failures: list[str] = Field(default_factory=list)
    parse_errors: dict[str, dict[str, str]] = Field(default_factory=dict)


class CommandToolBrief(StrictReportModel):
    ordinal: int
    tool: str
    status: str
    title: str
    detail: str | None = None
    failed: bool
    output_chars: int
    output_sha256: str


class TokenSummary(StrictReportModel):
    total: int = 0
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0


class AutomaticEvidence(StrictReportModel):
    step_count: int = 0
    tool_call_count: int = 0
    failed_tool_call_count: int = 0
    tool_counts: dict[str, int] = Field(default_factory=dict)
    tokens: TokenSummary = Field(default_factory=TokenSummary)
    cost: float = 0.0
    unknown_event_count: int = 0
    reads_by_category: dict[str, list[str]] = Field(default_factory=dict)
    escalated_to_product_code: bool = False
    disallowed_reads: list[str] = Field(default_factory=list)
    opaque_shell_commands: list[str] = Field(default_factory=list)


class ManualAuditSummary(StrictReportModel):
    status: Literal["pending", "complete"] = "pending"
    official_outcome: str | None = None
    auditor: str | None = None
    audited_at: str | None = None
    corrections: list[str] = Field(default_factory=list)
    notes: str = ""
    read_flags: dict[str, bool] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class TrialReport(StrictReportModel):
    schema_version: Literal[1] = 1
    identity: TrialIdentity
    outcome: TrialOutcome
    agent_self_report: dict[str, Any] | None = None
    final_agent_answer: str | None = None
    commands_and_tools: list[CommandToolBrief] = Field(default_factory=list)
    automatic_evidence: AutomaticEvidence
    policy_findings: list[str] = Field(default_factory=list)
    self_report_discrepancies: list[str] = Field(default_factory=list)
    manual_audit: ManualAuditSummary = Field(default_factory=ManualAuditSummary)
    follow_up_notes: list[str] = Field(default_factory=list)


_MAX_FINAL_TEXT_CHARS = 8_000
_MAX_COMMAND_DETAIL_CHARS = 1_000


def _build_identity(
    result: dict[str, object], raw_result_path: str, workspace_path: str
) -> TrialIdentity:
    return TrialIdentity(
        challenge_id=_str(result.get("challenge_id")),
        model=_str(result.get("model")),
        variant=_str(result.get("variant")),
        instruction_profile=_str(result.get("instruction_profile")),
        trial_index=_int(result.get("trial_index", result.get("index"))),
        repository_commit=_str_none(result.get("repository_commit")),
        repository_dirty=_bool_none(result.get("repository_dirty")),
        prompt_hashes=_dict_str_str(result.get("prompt_hashes")),
        raw_result_path=raw_result_path,
        workspace_path=workspace_path,
    )


def _build_outcome(result: dict[str, object]) -> TrialOutcome:
    return TrialOutcome(
        task_outcome=_str(result.get("task_outcome")),
        evaluation_validity=_str(result.get("evaluation_validity")),
        duration_seconds=_float(result.get("duration_seconds")),
        returncode=_int_none(result.get("returncode")),
        assertion_failures=_list_str(result.get("assertion_failures")),
        parse_errors=_parse_errors(result),
    )


def _build_tool_briefs(result: dict[str, object]) -> list[CommandToolBrief]:
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        return []
    tool_calls = metrics.get("tool_calls")
    if not isinstance(tool_calls, list):
        return []
    briefs: list[CommandToolBrief] = []
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        raw_input = tc.get("input")
        tc_input: dict[str, object] = {}
        if isinstance(raw_input, dict):
            tc_input = raw_input
        detail_str = ""
        path_val = (
            tc_input.get("path")
            or tc_input.get("filePath")
            or tc_input.get("file")
            or ""
        )
        if isinstance(path_val, str) and path_val:
            detail_str = path_val[:_MAX_COMMAND_DETAIL_CHARS]
        elif "command" in tc_input:
            cmd = tc_input["command"]
            if isinstance(cmd, str):
                detail_str = cmd[:_MAX_COMMAND_DETAIL_CHARS]

        briefs.append(
            CommandToolBrief(
                ordinal=_int(tc.get("ordinal")),
                tool=_str(tc.get("tool")),
                status=_str(tc.get("status")),
                title=_str(tc.get("title")),
                detail=detail_str or None,
                failed=bool(tc.get("failed", False)),
                output_chars=_int(tc.get("output_chars")),
                output_sha256=_str(tc.get("output_sha256")),
            )
        )
    return briefs


def _build_automatic_evidence(result: dict[str, object]) -> AutomaticEvidence:
    metrics = result.get("metrics")
    tokens = TokenSummary()
    cost = 0.0
    tool_counts: dict[str, int] = {}
    step_count = 0
    tool_call_count = 0
    failed_tool_call_count = 0
    unknown_event_count = 0
    if isinstance(metrics, dict):
        step_count = _int(metrics.get("step_count"))
        tool_call_count = _int(metrics.get("tool_call_count"))
        failed_tool_call_count = _int(metrics.get("failed_tool_call_count"))
        tool_counts = _dict_str_int(metrics.get("tool_counts"))
        unknown_event_count = _int(metrics.get("unknown_event_count"))
        tokens_raw = metrics.get("tokens")
        if isinstance(tokens_raw, dict):
            tokens = TokenSummary(
                total=_int(tokens_raw.get("total")),
                input=_int(tokens_raw.get("input")),
                output=_int(tokens_raw.get("output")),
                reasoning=_int(tokens_raw.get("reasoning")),
                cache_read=_int(tokens_raw.get("cache_read")),
                cache_write=_int(tokens_raw.get("cache_write")),
            )
        cost = _float(metrics.get("cost"))

    policy = result.get("policy")
    reads_by_category: dict[str, list[str]] = {}
    disallowed_reads: list[str] = []
    escalated_to_product_code = False
    opaque_shell_commands: list[str] = []
    if isinstance(policy, dict):
        reads_in = policy.get("reads_by_category")
        if isinstance(reads_in, dict):
            reads_by_category = {
                k: list(v) if isinstance(v, (list, tuple)) else [str(v)]
                for k, v in reads_in.items()
            }
        disallowed_reads = _list_str(policy.get("disallowed_reads"))
        escalated_to_product_code = bool(policy.get("escalated_to_product_code", False))
        opaque_shell_commands = _list_str(policy.get("opaque_shell_commands"))

    return AutomaticEvidence(
        step_count=step_count,
        tool_call_count=tool_call_count,
        failed_tool_call_count=failed_tool_call_count,
        tool_counts=tool_counts,
        tokens=tokens,
        cost=cost,
        unknown_event_count=unknown_event_count,
        reads_by_category=reads_by_category,
        escalated_to_product_code=escalated_to_product_code,
        disallowed_reads=disallowed_reads,
        opaque_shell_commands=opaque_shell_commands,
    )


def _build_trial_report(
    result: dict[str, object],
    *,
    audit: dict[str, object] | None,
    raw_result_path: str,
    workspace_path: str,
) -> TrialReport:
    identity = _build_identity(result, raw_result_path, workspace_path)
    outcome = _build_outcome(result)
    commands_and_tools = _build_tool_briefs(result)
    automatic_evidence = _build_automatic_evidence(result)

    agent_self_report: dict[str, Any] | None = None
    challenge_report = result.get("challenge_report")
    if isinstance(challenge_report, dict):
        agent_self_report = challenge_report

    final_agent_answer: str | None = None
    parsed = result.get("parsed")
    if isinstance(parsed, dict):
        text = parsed.get("text")
        if isinstance(text, str) and text.strip():
            final_agent_answer = text[:_MAX_FINAL_TEXT_CHARS]

    policy_findings: list[str] = _build_policy_findings(result, automatic_evidence)
    self_report_discrepancies: list[str] = _build_self_report_discrepancies(
        result, agent_self_report
    )
    follow_up_notes: list[str] = _build_follow_up_notes(result, automatic_evidence)
    manual_audit = _build_manual_audit(audit)

    return TrialReport(
        identity=identity,
        outcome=outcome,
        agent_self_report=agent_self_report,
        final_agent_answer=final_agent_answer,
        commands_and_tools=commands_and_tools,
        automatic_evidence=automatic_evidence,
        policy_findings=policy_findings,
        self_report_discrepancies=self_report_discrepancies,
        follow_up_notes=follow_up_notes,
        manual_audit=manual_audit,
    )


def _build_policy_findings(
    result: dict[str, object], evidence: AutomaticEvidence
) -> list[str]:
    findings: list[str] = []
    policy = result.get("policy")
    if isinstance(policy, dict):
        validity = policy.get("validity")
        if isinstance(validity, str) and validity != "clean":
            findings.append(f"Evaluation validity: {validity}")
    if evidence.disallowed_reads:
        findings.append(f"Disallowed reads ({len(evidence.disallowed_reads)} paths)")
    if evidence.opaque_shell_commands:
        findings.append(
            f"Opaque shell commands ({len(evidence.opaque_shell_commands)} commands)"
        )
    return findings


def _build_self_report_discrepancies(
    result: dict[str, object], agent_self_report: dict[str, Any] | None
) -> list[str]:
    discrepancies: list[str] = []
    if agent_self_report is None:
        return discrepancies

    task_outcome = _str(result.get("task_outcome"))
    agent_run_failed = agent_self_report.get("run_failed")

    if agent_run_failed is True and task_outcome == "success":
        discrepancies.append(
            "Agent reported run_failed=true but task_outcome is 'success'"
        )
    elif agent_run_failed is False and task_outcome == "failed":
        discrepancies.append(
            "Agent reported run_failed=false but task_outcome is 'failed'"
        )
    elif agent_run_failed is False and task_outcome == "timeout":
        discrepancies.append(
            "Agent reported run_failed=false but task ended in timeout"
        )

    _check_escalation_discrepancy(result, agent_self_report, discrepancies)

    return discrepancies


def _check_escalation_discrepancy(
    result: dict[str, object],
    agent_self_report: dict[str, Any],
    discrepancies: list[str],
) -> None:
    policy_raw = result.get("policy")
    if not isinstance(policy_raw, dict):
        return
    escalated = policy_raw.get("escalated_to_product_code")
    if escalated is not True:
        return
    agent_read_raw = agent_self_report.get("read")
    if isinstance(agent_read_raw, dict):
        for k, v in agent_read_raw.items():
            if k == "product_code" and v is True:
                return
    discrepancies.append(
        "Agent escalated to product code but did not report read.product_code"
    )


def _build_follow_up_notes(
    result: dict[str, object], evidence: AutomaticEvidence
) -> list[str]:
    notes: list[str] = []
    policy_raw = result.get("policy")
    if isinstance(policy_raw, dict):
        reads_by_cat_raw = policy_raw.get("reads_by_category")
        if isinstance(reads_by_cat_raw, dict):
            examples = reads_by_cat_raw.get("examples", [])
            tests = reads_by_cat_raw.get("tests", [])
            existing_solution_raw = reads_by_cat_raw.get("existing_solution", [])
            if isinstance(examples, (list, tuple)) and examples:
                notes.append(
                    f"Agent read {len(examples)} example file(s); verify whether "
                    "existing_solution applies"
                )
            if isinstance(tests, (list, tuple)) and tests:
                notes.append(
                    f"Agent read {len(tests)} test file(s); verify whether "
                    "existing_solution applies"
                )
            if (
                isinstance(existing_solution_raw, (list, tuple))
                and existing_solution_raw
            ):
                notes.append(
                    f"Agent found {len(existing_solution_raw)} existing solution "
                    "reference(s); verify self-report accuracy"
                )
    if evidence.disallowed_reads:
        notes.append(
            f"Disallowed reads ({len(evidence.disallowed_reads)} path(s)); "
            "review for contamination impact"
        )
    return notes


def _build_manual_audit(
    audit: dict[str, object] | None,
) -> ManualAuditSummary:
    if audit is None:
        return ManualAuditSummary()
    manual = audit.get("manual_audit")
    if isinstance(manual, dict):
        return ManualAuditSummary(
            status="complete",
            official_outcome=_str_none(manual.get("official_outcome")),
            auditor=_str_none(manual.get("auditor")),
            audited_at=_str_none(manual.get("audited_at")),
            corrections=_list_str(manual.get("corrections")),
            notes=_str(manual.get("notes")),
            read_flags=_dict_str_bool(manual.get("read_flags")),
            evidence=_dict_any(manual.get("evidence")),
        )
    return ManualAuditSummary()


def build_trial_report(
    result: dict[str, object],
    *,
    audit: dict[str, object] | None,
    raw_result_path: str | None = None,
    workspace_path: str | None = None,
) -> TrialReport:
    if raw_result_path is None:
        raw_result_path = _str(result.get("result_path"))
    if workspace_path is None:
        workspace_path = _str(result.get("workspace_path"))
    if not raw_result_path:
        raise ValueError("raw_result_path is required")
    if not workspace_path:
        raise ValueError("workspace_path is required")
    return _build_trial_report(
        result,
        audit=audit,
        raw_result_path=raw_result_path,
        workspace_path=workspace_path,
    )


def _str(value: object, *, default: str = "") -> str:
    return value if isinstance(value, str) else default


def _str_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int(value: object, *, default: int = 0) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    return default


def _int_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _float(value: object, *, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _bool_none(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _list_str(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [v for v in value if isinstance(v, str)]
    return []


def _dict_str_str(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            k: str(v)
            for k, v in value.items()
            if isinstance(k, str) and isinstance(v, str)
        }
    return {}


def _dict_str_int(value: object) -> dict[str, int]:
    if isinstance(value, dict):
        return {
            k: int(v)
            for k, v in value.items()
            if isinstance(k, str) and isinstance(v, (int, float))
        }
    return {}


def _dict_str_bool(value: object) -> dict[str, bool]:
    if isinstance(value, dict):
        return {
            k: bool(v)
            for k, v in value.items()
            if isinstance(k, str) and isinstance(v, bool)
        }
    return {}


def _dict_any(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_errors(result: dict[str, object]) -> dict[str, dict[str, str]]:
    errors: dict[str, dict[str, str]] = {}
    parse_error = result.get("parse_error")
    if isinstance(parse_error, dict):
        err_type = parse_error.get("type")
        err_msg = parse_error.get("message")
        if isinstance(err_type, str) and isinstance(err_msg, str):
            errors["parse_error"] = {"type": err_type, "message": err_msg}
    report_parse_error = result.get("report_parse_error")
    if isinstance(report_parse_error, dict):
        err_type = report_parse_error.get("type")
        err_msg = report_parse_error.get("message")
        if isinstance(err_type, str) and isinstance(err_msg, str):
            errors["report_parse_error"] = {"type": err_type, "message": err_msg}
    return errors
