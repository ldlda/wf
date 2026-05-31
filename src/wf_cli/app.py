from __future__ import annotations

from typing import Annotated

import typer

from .commands import artifacts, caps, deployments, docs, drafts, explain, runs, schema

app = typer.Typer(
    name="wf",
    help="Workflow platform CLI.",
    no_args_is_help=True,
)


@app.callback()
def root(
    ctx: typer.Context,
    config: Annotated[
        str,
        typer.Option(
            "--config",
            help="Path to workflow/MCP config JSON.",
        ),
    ] = "wf_mcp.config.json",
) -> None:
    """Run workflow platform commands."""
    ctx.obj = {"config_path": config}


app.add_typer(caps.app, name="cap")
app.add_typer(drafts.app, name="draft")
app.add_typer(artifacts.app, name="artifact")
app.add_typer(deployments.app, name="deploy")
app.add_typer(runs.app, name="run")
app.add_typer(docs.app, name="docs")
app.add_typer(schema.app, name="schema")
app.add_typer(explain.app, name="explain")


def main() -> None:
    """Console script entrypoint for `wf`."""
    app()
