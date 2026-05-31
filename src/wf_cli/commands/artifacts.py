from __future__ import annotations

import typer

app = typer.Typer(
    name="artifact",
    help="List and inspect saved workflow artifacts.",
    no_args_is_help=True,
)
