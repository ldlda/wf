from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Any

import typer

from wf_cli.context import CliContext, load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json

app = typer.Typer(
    name="registry",
    help="List, inspect, and mutate desired persisted source registry entries.",
    no_args_is_help=True,
)


def _require_registry_admin(context: CliContext) -> Any:
    """Return the source registry admin surface or raise if unavailable."""
    if context.source_registry_admin is None:
        raise typer.BadParameter(
            "source registry admin operations are not available for this server"
        )
    return context.source_registry_admin


@app.command("list")
def list_registry_entries(
    ctx: typer.Context,
    cursor: Annotated[
        str | None, typer.Option("--cursor", help="Pagination cursor.")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", min=1, max=100, help="Maximum rows.")
    ] = 50,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List desired persisted source registry entries."""
    context = load_cli_context_from_typer(ctx)
    admin = _require_registry_admin(context)
    payload = asyncio.run(admin.list_registry_entries(cursor=cursor, limit=limit))
    emit_list_payload(
        payload,
        collection_key="entries",
        output_format=output_format,
        id_field="id",
        summary_fields=("kind", "enabled", "provider", "account", "transport_kind"),
    )


@app.command("inspect")
def inspect_registry_entry(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Source registry entry id.")],
) -> None:
    """Inspect one desired persisted source registry entry."""
    context = load_cli_context_from_typer(ctx)
    admin = _require_registry_admin(context)
    payload = asyncio.run(admin.inspect_registry_entry(source_id=source_id))
    emit_json(payload)


@app.command("add")
def add_registry_entry(
    ctx: typer.Context,
    input_json: Annotated[
        str | None, typer.Option("--input", help="JSON payload for the new entry.")
    ] = None,
    input_file: Annotated[
        str | None,
        typer.Option("--input-file", help="Path to JSON file for the new entry."),
    ] = None,
) -> None:
    """Add a new desired source registry entry."""
    context = load_cli_context_from_typer(ctx)
    admin = _require_registry_admin(context)
    entry = _read_json_arg(input_json, input_file, "--input/--input-file")
    payload = asyncio.run(admin.add_registry_entry(entry=entry))
    emit_json(payload)


@app.command("update")
def update_registry_entry(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Source ID to update.")],
    patch_json: Annotated[
        str | None, typer.Option("--patch", help="JSON patch to apply.")
    ] = None,
    patch_file: Annotated[
        str | None, typer.Option("--patch-file", help="Path to JSON patch file.")
    ] = None,
) -> None:
    """Update an existing desired source registry entry."""
    context = load_cli_context_from_typer(ctx)
    admin = _require_registry_admin(context)
    patch = _read_json_arg(patch_json, patch_file, "--patch/--patch-file")
    payload = asyncio.run(admin.update_registry_entry(source_id=source_id, patch=patch))
    emit_json(payload)


@app.command("enable")
def enable_registry_entry(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Source ID to enable.")],
) -> None:
    """Enable a desired source registry entry."""
    context = load_cli_context_from_typer(ctx)
    admin = _require_registry_admin(context)
    payload = asyncio.run(admin.enable_registry_entry(source_id=source_id))
    emit_json(payload)


@app.command("disable")
def disable_registry_entry(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Source ID to disable.")],
) -> None:
    """Disable a desired source registry entry."""
    context = load_cli_context_from_typer(ctx)
    admin = _require_registry_admin(context)
    payload = asyncio.run(admin.disable_registry_entry(source_id=source_id))
    emit_json(payload)


@app.command("remove")
def remove_registry_entry(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Source ID to remove.")],
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Confirm removal.")
    ] = False,
) -> None:
    """Remove a desired source registry entry (requires --confirm)."""
    context = load_cli_context_from_typer(ctx)
    admin = _require_registry_admin(context)
    if not confirm:
        raise typer.BadParameter("removal requires --confirm flag")
    payload = asyncio.run(admin.remove_registry_entry(source_id=source_id))
    emit_json(payload)


def _read_json_arg(
    inline: str | None,
    file_path: str | None,
    flag_names: str,
) -> dict[str, Any]:
    """Resolve JSON from either inline text or a file path."""
    if inline and file_path:
        raise typer.BadParameter(f"provide exactly one of {flag_names}")
    if inline:
        try:
            value = json.loads(inline)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"invalid JSON: {exc}") from exc
        return _require_json_object(value, flag_names)
    if file_path:
        try:
            value = json.loads(Path(file_path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise typer.BadParameter(f"file not found: {file_path}")
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"invalid JSON in file: {exc}") from exc
        return _require_json_object(value, flag_names)
    raise typer.BadParameter(f"{flag_names} is required")


def _require_json_object(value: Any, flag_names: str) -> dict[str, Any]:
    """Registry add/update payloads must be JSON objects, not arrays/scalars."""
    if not isinstance(value, dict):
        raise typer.BadParameter(f"{flag_names} must be a JSON object")
    return value
