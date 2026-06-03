from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json

app = typer.Typer(
    name="cap",
    help="Inspect and call workflow capabilities.",
    no_args_is_help=True,
)


@app.command("list")
def list_capabilities(
    ctx: typer.Context,
    query: Annotated[
        str | None,
        typer.Option("--query", help="Search capability names/descriptions."),
    ] = None,
    source_id: Annotated[
        str | None, typer.Option("--source", help="Filter by source id.")
    ] = None,
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
    """List compact planner-visible workflow capabilities."""
    context = load_cli_context_from_typer(ctx)
    payload = asyncio.run(
        context.handlers.list_capabilities(
            query=query,
            source_id=source_id,
            cursor=cursor,
            limit=limit,
        )
    )
    emit_list_payload(
        payload,
        collection_key="capabilities",
        output_format=output_format,
        id_field="name",
        summary_fields=("source_id", "kind", "description"),
    )


@app.command("inspect")
def inspect_capability(
    ctx: typer.Context,
    qualified_name: Annotated[str, typer.Argument(help="Workflow capability name.")],
) -> None:
    """Inspect one workflow capability contract."""
    context = load_cli_context_from_typer(ctx)
    payload = asyncio.run(
        context.handlers.inspect_capability(qualified_name=qualified_name)
    )
    emit_json(payload)
