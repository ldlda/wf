from __future__ import annotations

import typer

app = typer.Typer(
    name="schema",
    help=(
        "Work in progress: intended to print expected input shapes for wf "
        "commands, but currently has no schema subcommands."
    ),
    no_args_is_help=True,
)
