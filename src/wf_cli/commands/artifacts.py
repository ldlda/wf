from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import CliInputError, emit_json, parse_bindings, parse_structured_file
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


@app.command("create-from-plan")
def create_artifact_from_plan(
    ctx: typer.Context,
    plan_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    artifact_id: Annotated[str, typer.Option("--artifact", help="Artifact id.")],
    version: Annotated[int, typer.Option("--version", min=1, help="Artifact version.")],
    title: Annotated[str, typer.Option("--title", help="Artifact title.")],
    outcome: Annotated[
        list[str] | None,
        typer.Option("--outcome", help="Artifact outcome. Repeatable."),
    ] = None,
    kind: Annotated[
        Literal["workflow", "wrapper"], typer.Option("--kind", help="Artifact kind.")
    ] = "workflow",
    description: Annotated[
        str | None, typer.Option("--description", help="Artifact description.")
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option("--binding", help="Logical=concrete source binding. Repeatable."),
    ] = None,
) -> None:
    """Create an artifact from a raw JSON/YAML workflow plan file."""
    try:
        plan = parse_structured_file(plan_file)
        source_bindings = parse_bindings(binding or [])
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.create_artifact_from_plan(
                artifact_id=artifact_id,
                version=version,
                title=title,
                plan=plan,
                outcomes=tuple(outcome or ["ok"]),
                kind=kind,
                description=description,
                source_bindings=source_bindings or None,
            ),
        )
    )


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
