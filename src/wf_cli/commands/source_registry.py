from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json

app = typer.Typer(
    name="registry",
    help="List and inspect desired persisted source registry entries.",
    no_args_is_help=True,
)


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
    if context.source_registry_admin is None:
        raise typer.BadParameter(
            "source registry admin reads are not available for this server"
        )
    payload = asyncio.run(
        context.source_registry_admin.list_registry_entries(cursor=cursor, limit=limit)
    )
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
    if context.source_registry_admin is None:
        raise typer.BadParameter(
            "source registry admin reads are not available for this server"
        )
    payload = asyncio.run(
        context.source_registry_admin.inspect_registry_entry(source_id=source_id)
    )
    emit_json(payload)
