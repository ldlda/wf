from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json
from wf_cli.remote_errors import run_cli_operation

app = typer.Typer(
    name="source",
    help="List and inspect workflow capability sources.",
    no_args_is_help=True,
)


class SourceInventoryOutputFormat(StrEnum):
    """Output formats for source resource and prompt names."""

    NAMES = "names"
    JSON = "json"


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
    payload = run_cli_operation(
        context,
        context.source_admin.list_sources(cursor=cursor, limit=limit),
    )
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
    payload = run_cli_operation(
        context,
        context.source_admin.inspect_source(source_id=source_id),
    )
    emit_json(payload)


@app.command("resources")
def list_source_resources(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Workflow source id.")],
    output_format: Annotated[
        SourceInventoryOutputFormat,
        typer.Option("--format", help="Output format."),
    ] = SourceInventoryOutputFormat.NAMES,
) -> None:
    """List resource names owned by one workflow source."""
    _list_source_inventory_names(
        ctx,
        source_id=source_id,
        capability_key="resources",
        output_key="resources",
        output_format=output_format,
    )


@app.command("prompts")
def list_source_prompts(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Workflow source id.")],
    output_format: Annotated[
        SourceInventoryOutputFormat,
        typer.Option("--format", help="Output format."),
    ] = SourceInventoryOutputFormat.NAMES,
) -> None:
    """List prompt names owned by one workflow source."""
    _list_source_inventory_names(
        ctx,
        source_id=source_id,
        capability_key="prompts",
        output_key="prompts",
        output_format=output_format,
    )


@app.command("diagnose")
def diagnose_source(
    ctx: typer.Context,
    source_id: Annotated[str, typer.Argument(help="Workflow source id.")],
) -> None:
    """Diagnose source transport, auth, and catalog state."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.source_admin.diagnose_source(source_id=source_id),
    )
    emit_json(payload)


def _list_source_inventory_names(
    ctx: typer.Context,
    *,
    source_id: str,
    capability_key: str,
    output_key: str,
    output_format: SourceInventoryOutputFormat,
) -> None:
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.source_admin.inspect_source(source_id=source_id),
    )
    names = _source_capability_names(payload, capability_key=capability_key)
    if output_format is SourceInventoryOutputFormat.JSON:
        emit_json({"source_id": source_id, output_key: names})
        return
    print("\n".join(names))


def _source_capability_names(
    payload: dict[str, object],
    *,
    capability_key: str,
) -> list[str]:
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValueError("source inventory missing capabilities object")
    value = capabilities.get(capability_key)
    if not isinstance(value, list):
        raise ValueError(
            f"source inventory capabilities.{capability_key} must be a list"
        )
    return [str(item) for item in value]
