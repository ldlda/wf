from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from examples.agent_challenges.classification import extract_challenge_report
from examples.agent_challenges.opencode_io import parse_opencode_output, result_text
from examples.agent_challenges.report_models import TrialReport


def save_report(
    *,
    workspace: Path,
    report_text: str,
    output_name: str = "final-report.md",
) -> Path:
    if not workspace.is_dir():
        raise ValueError(f"workspace does not exist or is not a directory: {workspace}")
    output_path = workspace / output_name
    output_path.write_text(report_text.rstrip() + "\n", encoding="utf-8")
    return output_path


def report_from_result(result_path: Path) -> tuple[Path, str]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("result file must contain a JSON object")
    report_text = _report_text_from_result(result)
    workspace = _workspace_from_result(result, report_text)
    return workspace, report_text


def save_report_from_result_payload(
    result: dict[str, object],
    *,
    output_name: str = "final-report.md",
) -> Path:
    report_text = _report_text_from_result(result)
    workspace = _workspace_from_result(result, report_text)
    return save_report(
        workspace=workspace,
        report_text=report_text,
        output_name=output_name,
    )


def _report_text_from_result(result: dict[str, object]) -> str:
    parsed = result.get("parsed")
    if isinstance(parsed, dict):
        return result_text(parsed)

    stdout = result.get("stdout")
    if isinstance(stdout, str) and stdout.strip():
        try:
            recovered = parse_opencode_output(stdout)
        except ValueError as exc:
            raise ValueError(
                "result file is missing parsed output and stdout has no report text"
            ) from exc
        return result_text(recovered)

    raise ValueError("result file is missing parsed output")


def _workspace_from_result(result: dict[str, object], report_text: str) -> Path:
    config = result.get("config")
    if isinstance(config, dict):
        prompt_path = config.get("prompt_path")
        if isinstance(prompt_path, str) and prompt_path:
            return Path(prompt_path).parent

    report = extract_challenge_report(report_text)
    if report is not None:
        workflow_file = report.get("workflow_file")
        if isinstance(workflow_file, str) and workflow_file:
            return Path(workflow_file).parent

    raise ValueError("could not infer trial workspace from result")


def _read_report_text(input_file: Path | None) -> str:
    if input_file is None:
        if sys.stdin.isatty():
            raise ValueError(
                "manual report mode needs piped stdin, --input-file, or --from-result"
            )
        return sys.stdin.read()
    return input_file.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path, nargs="?")
    parser.add_argument("--from-result", type=Path, default=None)
    parser.add_argument("--input-file", type=Path, default=None)
    parser.add_argument("--output-name", default="final-report.md")
    args = parser.parse_args(argv)

    try:
        if args.from_result is not None:
            if args.workspace is not None or args.input_file is not None:
                parser.error("--from-result cannot be combined with workspace/input")
            workspace, report_text = report_from_result(args.from_result)
        else:
            if args.workspace is None:
                parser.error("workspace is required unless --from-result is used")
            workspace = args.workspace
            report_text = _read_report_text(args.input_file)
        output_path = save_report(
            workspace=workspace,
            report_text=report_text,
            output_name=args.output_name,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(output_path.as_posix())
    return 0


def _format_tokens(tokens: dict[str, object]) -> str:
    parts = []
    for key in ("total", "input", "output", "reasoning", "cache_read", "cache_write"):
        val = tokens.get(key)
        if val is not None:
            parts.append(f"{key}: {val}")
    return ", ".join(parts)


def report_from_v2_result(result: dict[str, object]) -> str:
    lines: list[str] = []

    profile = result.get("instruction_profile", "unknown")
    lines.append(f"Instruction profile: {profile}")
    lines.append("")

    task_outcome = result.get("task_outcome", "unknown")
    evaluation_validity = result.get("evaluation_validity", "unknown")
    lines.append(f"Task outcome: {task_outcome}")
    lines.append(f"Evaluation validity: {evaluation_validity}")
    lines.append("")

    duration = result.get("duration_seconds", 0)
    lines.append(f"Duration: {duration}s")
    lines.append("")

    metrics = result.get("metrics", {})
    if isinstance(metrics, dict):
        tokens = metrics.get("tokens", {})
        if isinstance(tokens, dict):
            lines.append("Observed token metrics:")
            lines.append(f"  {_format_tokens(tokens)}")
        cost = metrics.get("cost")
        if cost is not None:
            lines.append(f"  cost: {cost}")
        tool_counts = metrics.get("tool_counts", {})
        if isinstance(tool_counts, dict) and tool_counts:
            lines.append("")
            lines.append("Tool calls by tool:")
            for tool, count in sorted(tool_counts.items()):
                lines.append(f"  {tool}: {count}")
        tool_calls = metrics.get("tool_calls", [])
        if isinstance(tool_calls, list) and tool_calls:
            lines.append("")
            lines.append("Tool call details:")
            for tc in tool_calls:
                if isinstance(tc, dict):
                    tool = tc.get("tool", "unknown")
                    status = tc.get("status", "unknown")
                    preview = tc.get("output_preview", "")
                    lines.append(f"  [{tc.get('ordinal', '?')}] {tool} ({status})")
                    if preview:
                        lines.append(f"    preview: {preview[:200]}")
    lines.append("")

    policy = result.get("policy", {})
    if isinstance(policy, dict):
        disallowed = policy.get("disallowed_reads", [])
        if disallowed:
            lines.append("Disallowed reads:")
            for path in disallowed:
                lines.append(f"  - {path}")
            lines.append("")

    lines.append("Agent self-report discrepancies:")
    lines.append("  (pending manual audit)")
    lines.append("")

    parsed = result.get("parsed")
    if isinstance(parsed, dict):
        text = parsed.get("text", "")
        if text:
            lines.append("Final agent answer:")
            lines.append(text)
            lines.append("")

    lines.append("Manual audit: pending")
    lines.append("")

    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class TrialReportPaths:
    markdown: Path
    machine: Path


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def render_trial_report_markdown(report: TrialReport) -> str:
    lines: list[str] = []

    lines.append("# Trial Report")
    lines.append("")

    lines.append("## Outcome")
    lines.append("")
    o = report.outcome
    lines.append(f"- Task outcome: {o.task_outcome}")
    lines.append(f"- Evaluation validity: {o.evaluation_validity}")
    lines.append(f"- Duration: {o.duration_seconds}s")
    if o.returncode is not None:
        lines.append(f"- Return code: {o.returncode}")
    if o.assertion_failures:
        lines.append("- Assertion failures:")
        for af in o.assertion_failures:
            lines.append(f"  - {af}")
    if o.parse_errors:
        for key, err in o.parse_errors.items():
            lines.append(
                f"- Parse error ({key}): {err.get('type', '')} - {err.get('message', '')}"
            )
    lines.append("")

    lines.append("## Agent Self-Report")
    lines.append("")
    if report.agent_self_report is not None:
        lines.append("```yaml")
        for key, value in report.agent_self_report.items():
            lines.append(f"{key}: {value}")
        lines.append("```")
    else:
        lines.append("No agent self-report captured.")
    if report.final_agent_answer:
        lines.append("")
        lines.append("Final agent answer:")
        lines.append("")
        lines.append(report.final_agent_answer)
    lines.append("")

    lines.append("## Commands And Tool Calls")
    lines.append("")
    if report.commands_and_tools:
        for cmd in report.commands_and_tools:
            marker = f"{cmd.ordinal}. "
            indent = " " * len(marker)
            parts = [
                f"{marker}**{cmd.tool}** ({cmd.status})",
                f"{indent}- Title: {cmd.title}",
            ]
            if cmd.detail:
                parts.append(f"{indent}- Detail: `{cmd.detail}`")
            parts.append(
                f"{indent}- Output: {cmd.output_chars} chars, sha256: `{cmd.output_sha256}`"
            )
            lines.extend(parts)
            lines.append("")
    else:
        lines.append("No commands or tool calls recorded.")
    lines.append("")

    lines.append("## Automatic Evidence")
    lines.append("")
    ev = report.automatic_evidence
    lines.append(f"- Steps: {ev.step_count}")
    lines.append(
        f"- Tool calls: {ev.tool_call_count} ({ev.failed_tool_call_count} failed)"
    )
    if ev.tool_counts:
        for tool, count in sorted(ev.tool_counts.items()):
            lines.append(f"  - {tool}: {count}")
    lines.append(
        f"- Tokens: total={ev.tokens.total}, input={ev.tokens.input}, output={ev.tokens.output}, reasoning={ev.tokens.reasoning}, cache_read={ev.tokens.cache_read}, cache_write={ev.tokens.cache_write}"
    )
    lines.append(f"- Cost: {ev.cost}")
    lines.append(f"- Policy coverage: {ev.policy_coverage}")
    if ev.unknown_event_count:
        lines.append(f"- Unknown events: {ev.unknown_event_count}")
    if ev.reads_by_category:
        for category, paths in sorted(ev.reads_by_category.items()):
            lines.append(f"- {category}: {len(paths)} path(s)")
    if ev.disallowed_reads:
        lines.append(f"- Disallowed reads: {len(ev.disallowed_reads)} path(s)")
    if ev.opaque_shell_commands:
        lines.append(
            f"- Opaque shell commands: {len(ev.opaque_shell_commands)} command(s)"
        )
    if ev.escalated_to_product_code:
        lines.append("- Escalated to product code: yes")
    lines.append("")

    lines.append("## Policy Findings")
    lines.append("")
    if report.policy_findings:
        for pf in report.policy_findings:
            lines.append(f"- {pf}")
    else:
        lines.append("No policy findings.")
    lines.append("")

    lines.append("## Self-Report Discrepancies")
    lines.append("")
    if report.self_report_discrepancies:
        for sd in report.self_report_discrepancies:
            lines.append(f"- {sd}")
    else:
        lines.append("No discrepancies detected.")
    lines.append("")

    lines.append("## Manual Audit")
    lines.append("")
    ma = report.manual_audit
    lines.append(f"- Status: {ma.status}")
    if ma.official_outcome is not None:
        lines.append(f"- Official outcome: {ma.official_outcome}")
    if ma.auditor is not None:
        lines.append(f"- Auditor: {ma.auditor}")
    if ma.audited_at is not None:
        lines.append(f"- Audited at: {ma.audited_at}")
    if ma.corrections:
        for c in ma.corrections:
            lines.append(f"- Correction: {c}")
    if ma.notes:
        lines.append(f"- Notes: {ma.notes}")
    if ma.read_flags:
        for key, val in ma.read_flags.items():
            lines.append(f"- read.{key}: {val}")
    lines.append("")

    lines.append("## Follow-Up Notes")
    lines.append("")
    if report.follow_up_notes:
        for fn in report.follow_up_notes:
            lines.append(f"- {fn}")
    else:
        lines.append("No follow-up notes.")
    lines.append("")

    return "\n".join(lines)


def write_trial_report_projections(
    report: TrialReport,
    *,
    markdown_path: Path,
    machine_path: Path,
) -> TrialReportPaths:
    machine = (
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    )
    markdown = render_trial_report_markdown(report).rstrip() + "\n"
    _atomic_write_text(machine_path, machine)
    _atomic_write_text(markdown_path, markdown)
    return TrialReportPaths(markdown=markdown_path, machine=machine_path)
