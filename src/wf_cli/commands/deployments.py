from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer as load_cli_context
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import CliInputError, emit_json, parse_bindings, parse_json_input
from wf_cli.remote_errors import run_cli_operation

app = typer.Typer(
    name="deploy",
    help="Save, inspect, validate, and delete workflow deployments.",
    no_args_is_help=True,
)


@app.command("validate")
def validate_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment id to validate.")],
    live: Annotated[
        bool,
        typer.Option(
            "--live",
            help="Also perform opt-in upstream liveness checks.",
        ),
    ] = False,
) -> None:
    """Validate one saved workflow deployment."""
    context = load_cli_context(ctx)
    payload = run_cli_operation(
        context,
        context.handlers.validate_deployment(
            deployment_id=deployment_id,
            live_check=live,
        ),
    )
    emit_json(payload)


@app.command("list")
def list_deployments(
    ctx: typer.Context,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List saved workflow deployments."""
    context = load_cli_context(ctx)
    payload = run_cli_operation(context, context.handlers.list_deployments())
    emit_list_payload(
        payload,
        collection_key="deployments",
        output_format=output_format,
        id_field="id",
        summary_fields=("artifact_id", "artifact_version", "drift_policy"),
    )


@app.command("inspect")
def inspect_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment id.")],
) -> None:
    """Inspect one saved deployment."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.inspect_deployment(deployment_id=deployment_id),
        )
    )


@app.command("save")
def save_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str | None, typer.Argument(help="Deployment id.")] = None,
    artifact_id: Annotated[
        str | None, typer.Option("--artifact", help="Artifact id.")
    ] = None,
    version: Annotated[
        int | None, typer.Option("--version", min=1, help="Artifact version.")
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option("--binding", help="Logical=concrete source binding. Repeatable."),
    ] = None,
    input_json: Annotated[
        str | None, typer.Option("--input", help="Full deployment JSON object.")
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option("--input-file", help="Path to full deployment JSON object."),
    ] = None,
) -> None:
    """Save a workflow deployment from flags or a JSON object."""
    _save_deployment_command(
        ctx,
        deployment_id=deployment_id,
        artifact_id=artifact_id,
        version=version,
        binding=binding,
        input_json=input_json,
        input_file=input_file,
    )


@app.command("create")
def create_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str | None, typer.Argument(help="Deployment id.")] = None,
    artifact_id: Annotated[
        str | None, typer.Option("--artifact", help="Artifact id.")
    ] = None,
    version: Annotated[
        int | None, typer.Option("--version", min=1, help="Artifact version.")
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option("--binding", help="Logical=concrete source binding. Repeatable."),
    ] = None,
    input_json: Annotated[
        str | None, typer.Option("--input", help="Full deployment JSON object.")
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option("--input-file", help="Path to full deployment JSON object."),
    ] = None,
) -> None:
    """Alias for `deploy save`; creates or updates a deployment record."""
    _save_deployment_command(
        ctx,
        deployment_id=deployment_id,
        artifact_id=artifact_id,
        version=version,
        binding=binding,
        input_json=input_json,
        input_file=input_file,
    )


def _save_deployment_command(
    ctx: typer.Context,
    *,
    deployment_id: str | None,
    artifact_id: str | None,
    version: int | None,
    binding: list[str] | None,
    input_json: str | None,
    input_file: Path | None,
) -> None:
    try:
        if input_json is not None or input_file is not None:
            payload = parse_json_input(input_json=input_json, input_file=input_file)
        else:
            payload = _deployment_payload_from_flags(
                deployment_id=deployment_id,
                artifact_id=artifact_id,
                version=version,
                bindings=binding or [],
            )
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    context = load_cli_context(ctx)
    emit_json(run_cli_operation(context, context.handlers.save_deployment(payload)))


@app.command("delete")
def delete_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment id.")],
) -> None:
    """Delete one saved deployment."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.delete_deployment(deployment_id=deployment_id),
        )
    )


def _deployment_payload_from_flags(
    *,
    deployment_id: str | None,
    artifact_id: str | None,
    version: int | None,
    bindings: list[str],
) -> dict[str, object]:
    """Build deployment JSON from ergonomic flags without hiding the model shape."""
    if deployment_id is None or artifact_id is None or version is None:
        raise CliInputError(
            "deployment_id, --artifact, and --version are required without --input"
        )
    return {
        "deployment_id": deployment_id,
        "artifact_id": artifact_id,
        "artifact_version": version,
        "bindings": parse_bindings(bindings),
    }
