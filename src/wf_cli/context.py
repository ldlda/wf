from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from collections.abc import Mapping

import typer
from pydantic import ValidationError

from wf_api import (
    WorkflowApi,
    WorkflowAdminApi,
    WorkflowAdminSurface,
    WorkflowApiSurface,
    WorkflowSourceAdminApi,
    WorkflowSourceAdminSurface,
    WorkflowSourceRegistrySurface,
)
from wf_config import (
    FilesystemStoreConfig,
    LocalTargetConfig,
    RpcHttpTargetConfig,
    load_workflow_config,
)
from wf_mcp.broker import build_service_from_config, load_broker_config
from wf_mcp.broker.service import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient


@dataclass(frozen=True)
class CliContext:
    """Protocol-neutral CLI handle over local or remote workflow operations."""

    config_path: Path
    service: WfMcpService | None
    handlers: WorkflowApiSurface
    source_admin: WorkflowSourceAdminSurface
    admin: WorkflowAdminSurface
    source_registry_admin: WorkflowSourceRegistrySurface | None = None


@dataclass(frozen=True)
class LocalCliContext:
    """CLI context for commands that still require same-process WorkflowApi."""

    config_path: Path
    service: WfMcpService | None
    handlers: WorkflowApi


@dataclass(frozen=True, slots=True)
class CliTyperState:
    """Typed boundary for Typer's untyped `Context.obj` payload.

    Typer/Click do not make `Context.obj` generic, so every command should read
    root CLI options through this adapter instead of spelling dict keys locally.
    """

    config_path: str = "wf_mcp.config.json"
    force_local: bool = False
    rpc_url: str | None = None
    rpc_timeout_seconds: float | None = None

    @classmethod
    def from_context(cls, ctx: typer.Context) -> CliTyperState:
        obj = ctx.obj
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, Mapping):
            return cls.from_mapping(obj)
        return cls()

    @classmethod
    def from_mapping(cls, obj: Mapping[object, object]) -> CliTyperState:
        config_path = obj.get("config_path", cls.config_path)
        rpc_url = obj.get("rpc_url")
        timeout = obj.get("rpc_timeout_seconds")
        return cls(
            config_path=(
                config_path if isinstance(config_path, str) else cls.config_path
            ),
            force_local=bool(obj.get("force_local", cls.force_local)),
            rpc_url=rpc_url if isinstance(rpc_url, str) else None,
            rpc_timeout_seconds=(
                float(timeout) if isinstance(timeout, float | int) else None
            ),
        )


def config_path_from_context(ctx: typer.Context) -> str:
    """Return the root --config path captured by the Typer callback."""
    return CliTyperState.from_context(ctx).config_path


def load_cli_context(
    config_path: str | Path,
    *,
    force_local: bool = False,
    rpc_url: str | None = None,
    rpc_timeout_seconds: float | None = None,
) -> CliContext:
    """Load config and build workflow-surface handlers for CLI commands."""
    resolved_config_path = Path(config_path)
    if force_local and rpc_url is not None:
        raise ValueError("--local and --url are mutually exclusive")

    if rpc_url is not None:
        _validate_rpc_url(rpc_url)
        client = RpcWorkflowApiClient(
            url=rpc_url,
            timeout_seconds=_rpc_timeout_from_optional_config(
                resolved_config_path,
                override=rpc_timeout_seconds,
            ),
        )
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=client,
            source_admin=client,
            admin=client,
            source_registry_admin=client,
        )

    if _is_legacy_mcp_config(resolved_config_path):
        config = load_broker_config(resolved_config_path)
        service = build_service_from_config(config)
        return CliContext(
            config_path=resolved_config_path,
            service=service,
            handlers=WorkflowApi(context_from_service(service)),
            source_admin=WorkflowSourceAdminApi(context_from_service(service)),
            admin=WorkflowAdminApi(
                connections=service.connection_service,
                events=service.events,
            ),
        )

    config = load_workflow_config(resolved_config_path)
    target = config.client.target
    if force_local or isinstance(target, LocalTargetConfig):
        store = config.server.store
        if not isinstance(store, FilesystemStoreConfig):
            raise ValueError("local CLI target currently requires filesystem store")
        server = build_local_static_workflow_server(store.root)
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=server.api,
            source_admin=server.source_admin,
            admin=server.admin,
        )
    if isinstance(target, RpcHttpTargetConfig):
        client = RpcWorkflowApiClient(
            url=str(target.url),
            timeout_seconds=(
                rpc_timeout_seconds
                if rpc_timeout_seconds is not None
                else target.timeout_seconds
            ),
        )
        return CliContext(
            config_path=resolved_config_path,
            service=None,
            handlers=client,
            source_admin=client,
            admin=client,
            source_registry_admin=client,
        )
    raise ValueError(f"unsupported workflow target {target!r}")


def load_local_cli_context(
    config_path: str | Path,
    *,
    force_local: bool = False,
    rpc_url: str | None = None,
    rpc_timeout_seconds: float | None = None,
) -> LocalCliContext:
    """Load a local WorkflowApi context for commands not remote-enabled yet."""
    context = load_cli_context(
        config_path,
        force_local=force_local,
        rpc_url=rpc_url,
        rpc_timeout_seconds=rpc_timeout_seconds,
    )
    if not isinstance(context.handlers, WorkflowApi):
        raise ValueError(
            "this CLI command is not available for rpc_http targets yet; "
            "use --local or run a cap/run command"
        )
    return LocalCliContext(
        config_path=context.config_path,
        service=context.service,
        handlers=context.handlers,
    )


def force_local_from_context(ctx: typer.Context) -> bool:
    return CliTyperState.from_context(ctx).force_local


def rpc_url_from_context(ctx: typer.Context) -> str | None:
    return CliTyperState.from_context(ctx).rpc_url


def rpc_timeout_from_context(ctx: typer.Context) -> float | None:
    return CliTyperState.from_context(ctx).rpc_timeout_seconds


def load_cli_context_from_typer(ctx: typer.Context) -> CliContext:
    try:
        return load_cli_context(
            config_path_from_context(ctx),
            force_local=force_local_from_context(ctx),
            rpc_url=rpc_url_from_context(ctx),
            rpc_timeout_seconds=rpc_timeout_from_context(ctx),
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def load_local_cli_context_from_typer(ctx: typer.Context) -> LocalCliContext:
    try:
        return load_local_cli_context(
            config_path_from_context(ctx),
            force_local=force_local_from_context(ctx),
            rpc_url=rpc_url_from_context(ctx),
            rpc_timeout_seconds=rpc_timeout_from_context(ctx),
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _is_legacy_mcp_config(path: Path) -> bool:
    """Detect legacy broker config by content, not filename.

    This keeps `wf_mcp.config.json` compatibility without making the filename a
    load-bearing part of the neutral workflow config migration.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False
    if any(key in data for key in ("version", "client", "server")):
        return False
    return any(key in data for key in ("store_root", "connections"))


def _rpc_timeout_from_optional_config(
    path: Path,
    *,
    override: float | None,
) -> float:
    if override is not None:
        return override
    try:
        config = load_workflow_config(path)
    except FileNotFoundError, json.JSONDecodeError, ValidationError:
        return 30.0
    target = config.client.target
    if isinstance(target, RpcHttpTargetConfig):
        return target.timeout_seconds
    return 30.0


def _validate_rpc_url(url: str) -> None:
    if not url.startswith(("http://", "https://")):
        raise ValueError("rpc url must start with http:// or https://")
