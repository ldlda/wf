from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json

app = typer.Typer(
    name="source",
    help="List and inspect workflow capability sources.",
    no_args_is_help=True,
)


@app.command("list")
def list_sources(
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
    """List compact workflow source summaries."""
    context = load_cli_context_from_typer(ctx)
    payload = asyncio.run(context.source_admin.list_sources(cursor=cursor, limit=limit))
    emit_list_payload(
        payload,
        collection_key="sources",
        output_format=output_format,
        id_field="id",
        summary_fields=("kind", "enabled", "description"),
    )


@app.command("inspect")
def inspect_source(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Workflow source id.")],
) -> None:
    """Inspect one workflow source inventory."""
    context = load_cli_context_from_typer(ctx)
    payload = asyncio.run(context.source_admin.inspect_source(source_id=source_id))
    emit_json(payload)
