from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from wf_cli.context import config_path_from_context, load_cli_context
from wf_cli.io import emit_json

app = typer.Typer(
    name="deploy",
    help="Save, inspect, validate, and delete workflow deployments.",
    no_args_is_help=True,
)


@app.command("validate")
def validate_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment id to validate.")],
    live: Annotated[
        bool,
        typer.Option(
            "--live",
            help="Also perform opt-in upstream liveness checks.",
        ),
    ] = False,
) -> None:
    """Validate one saved workflow deployment."""
    context = load_cli_context(config_path_from_context(ctx))
    payload = asyncio.run(
        context.handlers.validate_deployment(
            deployment_id=deployment_id,
            live_check=live,
        )
    )
    emit_json(payload)
