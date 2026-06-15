from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Classification = Literal[
    "success",
    "workflow_script",
    "workflow_not_used",
    "run_failed",
    "timeout",
    "parse_error",
    "unknown",
]

CHALLENGE_REPORT_REQUIRED_FIELDS = {
    "used_product_path",
    "used_helper_script",
    "workflow_file",
    "deployment_id",
    "run_id",
    "before_clicked",
    "after_clicked",
    "run_failed",
    "leftover_processes",
    "read",
    "attempts",
    "missed_requirements",
    "notes",
}
CHALLENGE_REPORT_READ_FIELDS = {
    "skills",
    "docs",
    "product_code",
    "adjacent_attempts",
    "prior_store",
    "existing_solution",
}
CHALLENGE_REPORT_ATTEMPT_FIELDS = {"total", "failed"}

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_DIR = CHALLENGE_DIR / "results"
DEFAULT_WORKSPACES_DIR = CHALLENGE_DIR / "workspaces"
DEFAULT_WORKSPACE_TEMPLATE = CHALLENGE_DIR / "workspace_template"
DEFAULT_PROMPT = DEFAULT_WORKSPACE_TEMPLATE / "prompt.md"
DEFAULT_SERVER_PORT = 8772
EXAMPLE_CONFIG = ROOT / "examples" / "browser_click_workflow" / "wf.config.json"
EXAMPLE_SOURCE_ROOT = ROOT / "examples" / "browser_click_workflow"
EXAMPLE_CONFIG_ARG = "examples/browser_click_workflow/wf.config.json"
LOCAL_WF_COMMAND_PREFIX = f"uv run wf --config {EXAMPLE_CONFIG_ARG} --local"


@dataclass(frozen=True, slots=True)
class TrialConfig:
    model: str
    variant: str
    prompt_path: Path
    attach_url: str | None
    timeout_seconds: int
    wf_command_prefix: str
    server_context: str


@dataclass(frozen=True, slots=True)
class TrialWorkspace:
    """Per-trial scratch area copied from the challenge workspace template."""

    root: Path
    config_path: Path
    prompt_path: Path


def render_prompt(
    prompt_path: Path,
    *,
    wf_command_prefix: str,
    server_context: str,
) -> str:
    return (
        prompt_path.read_text(encoding="utf-8")
        .replace("{{wf_command_prefix}}", wf_command_prefix)
        .replace("{{server_context}}", server_context)
    )


def rpc_url_for_port(port: int) -> str:
    return f"http://127.0.0.1:{port}/rpc"


def server_command(*, port: int) -> list[str]:
    return [
        "uv",
        "run",
        "wf-rpc-server",
        "--config",
        EXAMPLE_CONFIG_ARG,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
