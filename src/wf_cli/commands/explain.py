from __future__ import annotations

import typer

app = typer.Typer(
    name="explain",
    help="Explain workflow diagnostic and CLI error codes.",
    no_args_is_help=True,
)
