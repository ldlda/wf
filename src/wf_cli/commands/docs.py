from __future__ import annotations

import typer

app = typer.Typer(
    name="docs",
    help="List and read workflow documentation resources.",
    no_args_is_help=True,
)
