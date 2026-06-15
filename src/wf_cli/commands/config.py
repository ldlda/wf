from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from wf_cli.context import config_path_from_context
from wf_cli.io import emit_json
from wf_config import McpSourceConfig, PythonSourceConfig, StdlibSourceConfig
from wf_config.loader import load_workflow_config
from wf_mcp.broker.config import migrate_broker_config_file
from wf_sources_python import load_python_source

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


@app.command("validate")
def validate_config(
    ctx: typer.Context,
    config_path: Annotated[
        Path | None,
        typer.Argument(
            help="Neutral workflow config JSON path. Defaults to global --config.",
        ),
    ] = None,
) -> None:
    """Validate config shape and trusted static source imports."""
    resolved_config_path = config_path or Path(config_path_from_context(ctx))
    try:
        config = load_workflow_config(resolved_config_path)
        sources = [_validate_source(source) for source in config.server.sources]
    except Exception as exc:
        raise typer.BadParameter(f"invalid workflow config: {exc}") from exc
    emit_json(
        {
            "valid": True,
            "path": str(resolved_config_path),
            "sources": sources,
        }
    )


def _validate_source(
    source: StdlibSourceConfig | PythonSourceConfig | McpSourceConfig,
) -> dict[str, object]:
    """Return a compact source validation summary without live network probes."""
    if isinstance(source, PythonSourceConfig):
        try:
            loaded = load_python_source(
                source_id=source.id,
                path=source.path,
                module=source.module,
                registry=source.registry,
                enabled=source.enabled,
            )
        except Exception as exc:
            raise ValueError(f"source {source.id!r}: {exc}") from exc
        return {
            "id": source.id,
            "kind": source.kind,
            "status": "ok",
            "capability_count": len(loaded.capabilities.node_specs),
        }
    return {
        "id": source.id,
        "kind": source.kind,
        "status": "ok",
    }
