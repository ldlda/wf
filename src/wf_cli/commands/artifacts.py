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
    version_arg: Annotated[
        int | None,
        typer.Argument(min=1, help="Artifact version."),
    ] = None,
    version_option: Annotated[
        int | None,
        typer.Option("--version", min=1, help="Artifact version."),
    ] = None,
) -> None:
    """Inspect one saved artifact version."""
    version = _resolve_artifact_version(version_arg, version_option)
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.inspect_artifact(artifact_id=artifact_id, version=version),
        )
    )


def _resolve_artifact_version(
    version_arg: int | None,
    version_option: int | None,
) -> int:
    if version_arg is None and version_option is None:
        raise typer.BadParameter("artifact version is required")
    if (
        version_arg is not None
        and version_option is not None
        and version_arg != version_option
    ):
        raise typer.BadParameter("positional VERSION and --version must match")
    if version_option is not None:
        return version_option
    assert version_arg is not None
    return version_arg


@app.command("delete")
def delete_artifact(
    ctx: typer.Context,
    artifact_id: Annotated[str, typer.Argument(help="Artifact id.")],
    version: Annotated[int, typer.Argument(min=1, help="Artifact version.")],
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help="Required confirmation for deleting an artifact version.",
        ),
    ] = False,
) -> None:
    """Delete one unreferenced artifact version."""
    if not confirm:
        raise typer.BadParameter("pass --confirm to delete an artifact version")
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.delete_artifact(
                artifact_id=artifact_id,
                version=version,
            ),
        )
    )
