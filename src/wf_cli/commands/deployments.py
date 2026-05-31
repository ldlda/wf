from __future__ import annotations

import typer

app = typer.Typer(
    name="deploy",
    help="Save, inspect, validate, and delete workflow deployments.",
    no_args_is_help=True,
)
