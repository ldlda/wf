from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from examples.agent_challenges.classification import extract_challenge_report
from examples.agent_challenges.opencode_io import parse_opencode_output, result_text


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
