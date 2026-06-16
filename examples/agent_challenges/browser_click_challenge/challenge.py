from __future__ import annotations

from pathlib import Path
from typing import Literal

from examples.agent_challenges.workspace import (  # noqa: F401 - re-exported for backward compat
    ChallengeDef,
    TrialConfig,
    TrialWorkspace,
    render_prompt,
    rpc_url_for_port,
    server_command,
)

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

BROWSER_CLICK_DEF = ChallengeDef(
    name="browser_click",
    source_root=ROOT / "examples" / "browser_click_workflow",
    source_id="local.browser_click",
    source_module="ops",
    source_registry="registry",
    store_root=".wf_browser_click_store",
    default_workspace_template=CHALLENGE_DIR / "workspace_template",
    default_workspaces_dir=CHALLENGE_DIR / "workspaces",
    default_results_dir=CHALLENGE_DIR / "results",
    default_prompt=CHALLENGE_DIR / "workspace_template" / "prompt.md",
    default_server_port=8772,
    server_config_arg="examples/browser_click_workflow/wf.config.json",
)

EXAMPLE_CONFIG_ARG = BROWSER_CLICK_DEF.server_config_arg
EXAMPLE_CONFIG = ROOT / EXAMPLE_CONFIG_ARG
EXAMPLE_SOURCE_ROOT = BROWSER_CLICK_DEF.source_root
LOCAL_WF_COMMAND_PREFIX = f"uv run wf --config {EXAMPLE_CONFIG_ARG} --local"
DEFAULT_PROMPT = BROWSER_CLICK_DEF.default_prompt
DEFAULT_RESULTS_DIR = BROWSER_CLICK_DEF.default_results_dir
DEFAULT_WORKSPACES_DIR = BROWSER_CLICK_DEF.default_workspaces_dir
DEFAULT_WORKSPACE_TEMPLATE = BROWSER_CLICK_DEF.default_workspace_template
DEFAULT_SERVER_PORT = BROWSER_CLICK_DEF.default_server_port
