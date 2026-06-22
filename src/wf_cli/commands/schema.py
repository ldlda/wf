from __future__ import annotations

import typer

from wf_cli.io import emit_json
from wf_cli.schema_catalog import (
    compact_schema_outline,
    schema_catalog,
    schema_catalog_payload,
    verbose_schema_document,
)


def schema_command(
    name: str | None = typer.Argument(
        None,
        help="Schema name or alias (e.g. draft, raw, core, NodeUse). Omit it, or use `list`, to list names.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print complete valid JSON Schema; output may be large.",
    ),
) -> None:
    """Print a compact workflow schema outline or full JSON Schema."""
    if name is None or name == "list":
        emit_json(schema_catalog_payload())
        return
    try:
        schema_catalog().resolve(name)
    except KeyError as exc:
        message = exc.args[0] if exc.args else str(exc)
        raise typer.BadParameter(message, param_hint="NAME") from exc
    emit_json(
        verbose_schema_document(name) if verbose else compact_schema_outline(name)
    )
