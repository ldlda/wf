from __future__ import annotations

import typer

app = typer.Typer(
    name="run",
    help="Run workflow deployments and inspect durable runs.",
    no_args_is_help=True,
)
