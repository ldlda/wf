from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload

app = typer.Typer(
    name="admin",
    help="Read workflow server admin and config state.",
    no_args_is_help=True,
)


@app.command("connections")
def list_connections(
    ctx: typer.Context,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List configured upstream connections known to the target."""
    context = load_cli_context_from_typer(ctx)
    payload = asyncio.run(context.admin.list_connections())
    emit_list_payload(
        payload,
        collection_key="connections",
        output_format=output_format,
        id_field="id",
        summary_fields=("server", "account", "enabled"),
    )


@app.command("statuses")
def get_connection_statuses(
    ctx: typer.Context,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List connection catalog/status summaries."""
    context = load_cli_context_from_typer(ctx)
    payload = asyncio.run(context.admin.get_connection_statuses())
    emit_list_payload(
        payload,
        collection_key="statuses",
        output_format=output_format,
        id_field="connection_id",
        summary_fields=("server", "account", "enabled", "has_snapshot"),
    )


@app.command("events")
def list_events(
    ctx: typer.Context,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List recorded workflow platform events."""
    context = load_cli_context_from_typer(ctx)
    payload = asyncio.run(context.admin.list_events())
    emit_list_payload(
        payload,
        collection_key="events",
        output_format=output_format,
        id_field="kind",
        summary_fields=("connection_id", "capability_id", "workflow_name"),
    )
