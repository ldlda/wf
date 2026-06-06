from __future__ import annotations

from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import emit_json
from wf_cli.remote_errors import run_cli_operation

app = typer.Typer(
    name="auth",
    help="Read auth record status without exposing secret payload values.",
    no_args_is_help=True,
)


@app.command("list")
def list_auth_records(
    ctx: typer.Context,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List auth records known to the target."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(context, context.admin.list_auth_records())
    emit_list_payload(
        payload,
        collection_key="auth_records",
        output_format=output_format,
        id_field="id",
        summary_fields=("scheme", "payload_keys"),
    )


@app.command("inspect")
def inspect_auth_record(
    ctx: typer.Context,
    auth_ref: Annotated[str, typer.Argument(help="Auth record id/ref.")],
) -> None:
    """Inspect one auth record summary without secret payload values."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.admin.inspect_auth_record(auth_ref),
    )
    emit_json(payload)
