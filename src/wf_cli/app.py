from __future__ import annotations

from typing import Annotated

import typer

from .commands import (
    artifacts,
    caps,
    deployments,
    docs,
    drafts,
    explain,
    runs,
    schema,
    sources,
)
from .context import CliTyperState

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
    local: Annotated[
        bool,
        typer.Option("--local", help="Force same-process local workflow target."),
    ] = False,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Override workflow JSON-RPC target URL."),
    ] = None,
    timeout: Annotated[
        float | None,
        typer.Option("--timeout", min=0.1, help="Override RPC timeout seconds."),
    ] = None,
) -> None:
    """Run workflow platform commands."""
    ctx.obj = CliTyperState(
        config_path=config,
        force_local=local,
        rpc_url=url,
        rpc_timeout_seconds=timeout,
    )


app.add_typer(caps.app, name="cap")
app.add_typer(drafts.app, name="draft")
app.add_typer(artifacts.app, name="artifact")
app.add_typer(deployments.app, name="deploy")
app.add_typer(runs.app, name="run")
app.add_typer(sources.app, name="source")
app.add_typer(docs.app, name="docs")
app.add_typer(schema.app, name="schema")
app.command("explain")(explain.explain_command)


def main() -> None:
    """Console script entrypoint for `wf`."""
    app()
