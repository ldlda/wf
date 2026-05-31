from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from wf_mcp.broker import build_service_from_config, load_broker_config
from wf_mcp.broker.service import WfMcpService
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers


@dataclass(frozen=True)
class CliContext:
    """Protocol-neutral CLI handle over the current workflow service stack.

    V1 intentionally reuses wf_mcp service construction because that is where
    config, store, source, artifact, draft, and run wiring currently lives. Keep
    this dependency behind context.py so later extraction does not affect every
    command module.
    """

    config_path: Path
    service: WfMcpService
    handlers: WorkflowSurfaceHandlers


def config_path_from_context(ctx: typer.Context) -> str:
    """Return the root --config path captured by the Typer callback."""
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    value = obj.get("config_path", "wf_mcp.config.json")
    return value if isinstance(value, str) else "wf_mcp.config.json"


def load_cli_context(config_path: str | Path) -> CliContext:
    """Load config and build workflow-surface handlers for CLI commands."""
    resolved_config_path = Path(config_path)
    config = load_broker_config(resolved_config_path)
    service = build_service_from_config(config)
    return CliContext(
        config_path=resolved_config_path,
        service=service,
        handlers=WorkflowSurfaceHandlers(service),
    )
