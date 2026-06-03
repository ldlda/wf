from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from wf_api import WorkflowApi
from wf_mcp.broker import build_service_from_config, load_broker_config
from wf_mcp.broker.service import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_config import FilesystemStoreConfig, LocalTargetConfig, RpcHttpTargetConfig, load_workflow_config
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient


@dataclass(frozen=True)
class CliContext:
    """Protocol-neutral CLI handle over local or remote workflow operations."""

    config_path: Path
    service: WfMcpService | None
    handlers: WorkflowApi | RpcWorkflowApiClient


def config_path_from_context(ctx: typer.Context) -> str:
    """Return the root --config path captured by the Typer callback."""
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    value = obj.get("config_path", "wf_mcp.config.json")
    return value if isinstance(value, str) else "wf_mcp.config.json"


def load_cli_context(
    config_path: str | Path,
    *,
    force_local: bool = False,
    rpc_url: str | None = None,
    rpc_timeout_seconds: float | None = None,
) -> CliContext:
    """Load config and build workflow-surface handlers for CLI commands."""
    resolved_config_path = Path(config_path)
    if resolved_config_path.name == "wf_mcp.config.json":
        config = load_broker_config(resolved_config_path)
        service = build_service_from_config(config)
        return CliContext(
            config_path=resolved_config_path,
            service=service,
            handlers=WorkflowApi(context_from_service(service)),
        )

    config = load_workflow_config(resolved_config_path)
    target = config.client.target
    if rpc_url is not None:
        timeout = rpc_timeout_seconds if rpc_timeout_seconds is not None else 30.0
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=RpcWorkflowApiClient(url=rpc_url, timeout_seconds=timeout),
        )
    if force_local or isinstance(target, LocalTargetConfig):
        store = config.server.store
        if not isinstance(store, FilesystemStoreConfig):
            raise ValueError("local CLI target currently requires filesystem store")
        server = build_local_static_workflow_server(store.root)
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=server.api,
        )
    if isinstance(target, RpcHttpTargetConfig):
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=RpcWorkflowApiClient(
                url=target.url,
                timeout_seconds=(
                    rpc_timeout_seconds
                    if rpc_timeout_seconds is not None
                    else target.timeout_seconds
                ),
            ),
        )
    raise ValueError(f"unsupported workflow target {target!r}")


def force_local_from_context(ctx: typer.Context) -> bool:
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    return bool(obj.get("force_local", False))


def rpc_url_from_context(ctx: typer.Context) -> str | None:
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    value = obj.get("rpc_url")
    return value if isinstance(value, str) else None


def rpc_timeout_from_context(ctx: typer.Context) -> float | None:
    obj = ctx.obj if isinstance(ctx.obj, dict) else {}
    value = obj.get("rpc_timeout_seconds")
    return value if isinstance(value, float | int) else None


def load_cli_context_from_typer(ctx: typer.Context) -> CliContext:
    return load_cli_context(
        config_path_from_context(ctx),
        force_local=force_local_from_context(ctx),
        rpc_url=rpc_url_from_context(ctx),
        rpc_timeout_seconds=rpc_timeout_from_context(ctx),
    )
