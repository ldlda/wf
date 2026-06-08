from __future__ import annotations

from typing import Any

import typer

from wf_cli.context import CliContext, CliTyperState, load_cli_context_from_typer
from wf_cli.io import emit_json
from wf_cli.remote_errors import run_cli_operation


def status_command(ctx: typer.Context) -> None:
    """Print a compact read-only summary of the selected workflow target."""
    state = CliTyperState.from_context(ctx)
    context = load_cli_context_from_typer(ctx)
    target_url = _target_url(context, state)
    target: dict[str, Any] = {
        "mode": "remote" if target_url is not None else "local",
        "config_path": str(context.config_path),
        "url": target_url,
    }
    status_data = run_cli_operation(context, _fetch_status_data(context))
    payload: dict[str, Any] = {"target": target, **status_data}
    emit_json(payload)


def _target_url(context: CliContext, state: CliTyperState) -> str | None:
    """Return the resolved RPC URL whether it came from --url or config."""

    if state.rpc_url is not None:
        return state.rpc_url
    url = getattr(context.handlers, "url", None)
    return url if isinstance(url, str) else None


async def _fetch_status_data(context: CliContext) -> dict[str, Any]:
    capabilities = await context.handlers.list_capabilities(limit=20)
    items = capabilities.get("capabilities", [])
    names = [
        item.get("name")
        for item in items
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    workflow = {
        "capability_count": len(items),
        "sample_capabilities": names[:5],
    }

    sources = await _fetch_sources(context)
    admin = await _fetch_admin(context)
    registry = await _fetch_registry(context)

    return {
        "workflow": workflow,
        "sources": sources,
        "admin": admin,
        "registry": registry,
    }


async def _fetch_sources(context: CliContext) -> dict[str, Any]:
    # Intentionally broad: graceful degradation when source admin is unavailable
    try:
        payload = await context.source_admin.list_sources(limit=20)
    except Exception as exc:
        return _unavailable(exc)
    sources = payload.get("sources", [])
    source_ids = [
        item.get("id")
        for item in sources
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    return {
        "available": True,
        "source_count": len(sources),
        "sample_sources": source_ids[:5],
    }


async def _fetch_admin(context: CliContext) -> dict[str, Any]:
    # Intentionally broad: graceful degradation when admin surfaces are unavailable
    try:
        connections = await context.admin.list_connections()
        statuses = await context.admin.get_connection_statuses()
        events = await context.admin.list_events()
    except Exception as exc:
        return _unavailable(exc)
    # Auth is optional - some targets (local/static) don't have auth admin
    auth_count = 0
    try:
        auth = await context.admin.list_auth_records()
        auth_count = len(auth.get("auth_records", []))
    except Exception:
        pass
    return {
        "available": True,
        "connection_count": len(connections.get("connections", [])),
        "status_count": len(statuses.get("statuses", [])),
        "event_count": len(events.get("events", [])),
        "auth_count": auth_count,
    }


async def _fetch_registry(context: CliContext) -> dict[str, Any]:
    admin = context.source_registry_admin
    if admin is None:
        return {"available": False, "reason": "source registry admin is not configured"}
    # Intentionally broad: graceful degradation when registry is unavailable
    try:
        payload = await admin.list_registry_entries(limit=20)
    except Exception as exc:
        return _unavailable(exc)
    return {
        "available": True,
        "entry_count": len(payload.get("entries", [])),
    }


def _unavailable(exc: Exception) -> dict[str, Any]:
    return {
        "available": False,
        "reason": str(exc),
    }
