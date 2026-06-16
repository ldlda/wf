from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Support direct execution as `python examples/.../run_opencode_trials.py`.
# ruff: noqa: I001 - imports must stay after sys.path.insert
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from examples.agent_challenges.browser_click_challenge.challenge import (  # noqa: E402
    BROWSER_CLICK_DEF,
    CHALLENGE_DIR,
    CHALLENGE_REPORT_ATTEMPT_FIELDS,
    CHALLENGE_REPORT_READ_FIELDS,
    CHALLENGE_REPORT_REQUIRED_FIELDS,
    Classification,
    DEFAULT_PROMPT,
    DEFAULT_RESULTS_DIR,
    DEFAULT_SERVER_PORT,
    DEFAULT_WORKSPACE_TEMPLATE,
    DEFAULT_WORKSPACES_DIR,
    EXAMPLE_CONFIG,
    EXAMPLE_CONFIG_ARG,
    EXAMPLE_SOURCE_ROOT,
    LOCAL_WF_COMMAND_PREFIX,
)
from examples.agent_challenges.browser_click_challenge.classification import (  # noqa: E402
    _contains_bool_marker,
    challenge_report_schema_errors,
    classify_challenge_report,
    classify_output,
    extract_challenge_report,
)
from examples.agent_challenges.opencode_io import (  # noqa: E402
    _event_text,
    _parse_jsonl_tail,
    build_opencode_command,
    parse_opencode_output,
    result_text,
)
from examples.agent_challenges.reports import (  # noqa: E402
    save_report_from_result_payload,
)
from examples.agent_challenges.runner import (  # noqa: E402
    ManagedServer,
    main as _generic_main,
    run_trial as _generic_run_trial,
    start_server as _generic_start_server,
    stop_server as _generic_stop_server,
)
from examples.agent_challenges.workspace import (  # noqa: E402
    TrialConfig,
    TrialWorkspace,
    prepare_trial_workspace as _generic_prepare,
    render_prompt,
    rpc_url_for_port,
    server_command,
    starting_trial_index as _generic_starting_index,
    trial_output_path as _generic_trial_output_path,
    wf_command_prefix_for_config as _generic_wf_prefix,
)

__all__ = [
    "BROWSER_CLICK_DEF",
    "CHALLENGE_DIR",
    "CHALLENGE_REPORT_ATTEMPT_FIELDS",
    "CHALLENGE_REPORT_READ_FIELDS",
    "CHALLENGE_REPORT_REQUIRED_FIELDS",
    "Classification",
    "DEFAULT_PROMPT",
    "DEFAULT_RESULTS_DIR",
    "DEFAULT_SERVER_PORT",
    "DEFAULT_WORKSPACE_TEMPLATE",
    "DEFAULT_WORKSPACES_DIR",
    "EXAMPLE_CONFIG",
    "EXAMPLE_CONFIG_ARG",
    "EXAMPLE_SOURCE_ROOT",
    "LOCAL_WF_COMMAND_PREFIX",
    "ManagedServer",
    "ROOT",
    "TrialConfig",
    "TrialWorkspace",
    "_contains_bool_marker",
    "_event_text",
    "_parse_jsonl_tail",
    "build_opencode_command",
    "challenge_report_schema_errors",
    "classify_challenge_report",
    "classify_output",
    "extract_challenge_report",
    "main",
    "parse_opencode_output",
    "prepare_trial_workspace",
    "render_prompt",
    "result_text",
    "rpc_url_for_port",
    "run_trial",
    "save_report_from_result_payload",
    "server_command",
    "start_server",
    "starting_trial_index",
    "stop_server",
    "trial_output_path",
    "wf_command_prefix_for_config",
]


def main(argv: list[str] | None = None) -> int:
    return _generic_main(BROWSER_CLICK_DEF, classify_output, argv)


def prepare_trial_workspace(
    *,
    model: str,
    index: int,
    workspaces_dir: Path = DEFAULT_WORKSPACES_DIR,
    template_dir: Path = DEFAULT_WORKSPACE_TEMPLATE,
    source_root: Path = EXAMPLE_SOURCE_ROOT,
) -> TrialWorkspace:
    return _generic_prepare(
        BROWSER_CLICK_DEF,
        model=model,
        index=index,
        workspaces_dir=workspaces_dir,
        template_dir=template_dir,
        source_root=source_root,
    )


def run_trial(
    config: TrialConfig,
    *,
    index: int,
    results_dir: Path,
) -> dict:
    return _generic_run_trial(
        config, index=index, results_dir=results_dir, classify_fn=classify_output
    )


def start_server(
    *,
    port: int,
    timeout_seconds: int = 30,
) -> ManagedServer:
    return _generic_start_server(
        BROWSER_CLICK_DEF, port=port, timeout_seconds=timeout_seconds
    )


def stop_server(process: subprocess.Popen[str]) -> None:
    return _generic_stop_server(process)


def starting_trial_index(
    *,
    model: str,
    results_dir: Path,
    workspaces_dir: Path,
) -> int:
    return _generic_starting_index(
        model=model, results_dir=results_dir, workspaces_dir=workspaces_dir
    )


def trial_output_path(results_dir: Path, *, model: str, index: int) -> Path:
    return _generic_trial_output_path(results_dir, model=model, index=index)


def wf_command_prefix_for_config(config_path: Path) -> str:
    return _generic_wf_prefix(config_path)


if __name__ == "__main__":
    raise SystemExit(main())
