from __future__ import annotations

from typing import Annotated

import typer
from dotenv import load_dotenv

from .commands import (
    admin,
    artifacts,
    caps,
    deployments,
    docs,
    drafts,
    explain,
    runs,
    schema,
    sources,
    status,
)
from .commands import (
    config as config_commands,
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
    ] = "wf.config.json",
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
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Show full tracebacks for unexpected internal errors.",
        ),
    ] = False,
) -> None:
    """Run workflow platform commands."""
    app.pretty_exceptions_short = not verbose
    ctx.obj = CliTyperState(
        config_path=config,
        force_local=local,
        rpc_url=url,
        rpc_timeout_seconds=timeout,
        verbose=verbose,
    )


app.add_typer(caps.app, name="cap")
app.add_typer(drafts.app, name="draft")
app.add_typer(artifacts.app, name="artifact")
app.add_typer(deployments.app, name="deploy")
app.add_typer(runs.app, name="run")
app.add_typer(sources.app, name="source")
app.add_typer(admin.app, name="admin")
app.add_typer(docs.app, name="docs")
app.add_typer(config_commands.app, name="config")
app.command("explain")(explain.explain_command)
app.command("status")(status.status_command)
app.command("schema")(schema.schema_command)

def main() -> None:
    """Console script entrypoint for `wf`."""
    load_dotenv()
    app()
