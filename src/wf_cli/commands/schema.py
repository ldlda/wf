from __future__ import annotations

import typer

app = typer.Typer(
    name="schema",
    help="Print expected input shapes for wf commands.",
    no_args_is_help=True,
)
