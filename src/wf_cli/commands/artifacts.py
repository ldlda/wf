from __future__ import annotations
from typing import Annotated, Literal

import typer

from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json
from wf_cli.remote_errors import run_cli_operation

app = typer.Typer(
    name="artifact",
    help="List and inspect saved workflow artifacts.",
    no_args_is_help=True,
)


@app.command("list")
def list_artifacts(
    ctx: typer.Context,
    query: Annotated[
        str | None, typer.Option("--query", help="Search artifact summaries.")
    ] = None,
    kind: Annotated[
        Literal["workflow", "wrapper"] | None,
        typer.Option("--kind", help="Filter artifact kind."),
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
    """List compact saved artifact summaries."""
    context = load_cli_context(ctx)
    payload = run_cli_operation(
        context,
        context.handlers.list_artifacts(
            query=query,
            kind=kind,
            cursor=cursor,
            limit=limit,
        ),
    )
    emit_list_payload(
        payload,
        collection_key="nodes",
        output_format=output_format,
        id_field="name",
        summary_fields=("kind", "display_name", "description"),
    )


@app.command("inspect")
def inspect_artifact(
    ctx: typer.Context,
    artifact_id: Annotated[str, typer.Argument(help="Artifact id.")],
    version: Annotated[int, typer.Argument(min=1, help="Artifact version.")],
) -> None:
    """Inspect one saved artifact version."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.inspect_artifact(artifact_id=artifact_id, version=version),
        )
    )
