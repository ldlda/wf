from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import CliInputError, emit_json, parse_json_input
from wf_cli.remote_errors import run_cli_operation

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
    payload = run_cli_operation(
        context,
        context.handlers.list_capabilities(
            query=query,
            source_id=source_id,
            cursor=cursor,
            limit=limit,
        ),
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
    payload = run_cli_operation(
        context,
        context.handlers.inspect_capability(qualified_name=qualified_name),
    )
    emit_json(payload)


@app.command("call")
def call_capability(
    ctx: typer.Context,
    qualified_name: Annotated[str, typer.Argument(help="Workflow capability name.")],
    input_json: Annotated[
        str | None,
        typer.Option("--input", help="JSON object payload for the capability."),
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option(
            "--input-file",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Read capability JSON object payload from a file.",
        ),
    ] = None,
    deployment_id: Annotated[
        str | None,
        typer.Option(
            "--deployment",
            help="Deployment id for saved wrappers with deployment-bound sources.",
        ),
    ] = None,
) -> None:
    """Call one workflow capability once for authoring/runtime smoke tests."""
    try:
        payload = parse_json_input(input_json=input_json, input_file=input_file)
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc

    context = load_cli_context_from_typer(ctx)
    result = run_cli_operation(
        context,
        context.handlers.call_capability(
            qualified_name=qualified_name,
            payload=payload,
            deployment_id=deployment_id,
        ),
    )
    emit_json(result)
