from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from wf_cli.io import emit_json
from wf_mcp.broker.config import migrate_broker_config_file

app = typer.Typer(
    name="config",
    help="Inspect and migrate workflow config files.",
    no_args_is_help=True,
)


@app.command("migrate-mcp")
def migrate_mcp_config(
    input_path: Annotated[
        Path,
        typer.Argument(help="Legacy wf_mcp.config.json path."),
    ],
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write neutral workflow config JSON here."),
    ] = None,
) -> None:
    """Convert legacy MCP broker config into neutral workflow config."""
    config = migrate_broker_config_file(input_path)
    payload = config.model_dump(mode="json")
    if output_path is None:
        emit_json(payload)
        return
    output_path.write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8",
    )
    emit_json({"status": "written", "path": str(output_path)})
