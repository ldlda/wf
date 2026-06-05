from __future__ import annotations
from pathlib import Path
from typing import Annotated

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.io import CliInputError, emit_json, parse_json_input
from wf_cli.remote_errors import run_cli_operation
from wf_api import TraceRange

app = typer.Typer(
    name="run",
    help="Run workflow deployments and inspect durable runs.",
    no_args_is_help=True,
)


@app.command("start")
def start_run(
    ctx: typer.Context,
    deployment_id: Annotated[str, typer.Argument(help="Deployment id to run.")],
    input_json: Annotated[
        str | None,
        typer.Option("--input", help="Workflow input JSON object."),
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option("--input-file", help="Path to workflow input JSON object."),
    ] = None,
    trace_from: Annotated[
        int | None,
        typer.Option("--trace-from", min=0, help="Optional trace slice start."),
    ] = None,
    trace_limit: Annotated[
        int | None,
        typer.Option(
            "--trace-limit", min=1, max=100, help="Optional trace slice limit."
        ),
    ] = None,
) -> None:
    """Start one workflow deployment."""
    try:
        workflow_input = parse_json_input(input_json=input_json, input_file=input_file)
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    context = load_cli_context_from_typer(ctx)
    trace_range = _optional_trace_range(start=trace_from, limit=trace_limit)
    payload = run_cli_operation(
        context,
        context.handlers.run_deployment(
            deployment_id=deployment_id,
            workflow_input=workflow_input,
            trace_range=trace_range,
        ),
    )
    emit_json(payload)


@app.command("inspect")
def inspect_run(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Durable run id to inspect.")],
) -> None:
    """Inspect a durable run without trace entries."""
    context = load_cli_context_from_typer(ctx)
    emit_json(run_cli_operation(context, context.handlers.inspect_run(run_id=run_id)))


@app.command("resume")
def resume_run(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Interrupted durable run id.")],
    payload_json: Annotated[
        str | None,
        typer.Option("--payload", help="Resume payload JSON object."),
    ] = None,
    payload_file: Annotated[
        Path | None,
        typer.Option("--payload-file", help="Path to resume payload JSON object."),
    ] = None,
    outcome: Annotated[
        str,
        typer.Option("--outcome", help="Interrupt resume outcome."),
    ] = "submitted",
    trace_from: Annotated[
        int | None,
        typer.Option("--trace-from", min=0, help="Optional trace slice start."),
    ] = None,
    trace_limit: Annotated[
        int | None,
        typer.Option(
            "--trace-limit", min=1, max=100, help="Optional trace slice limit."
        ),
    ] = None,
) -> None:
    """Resume an interrupted durable run.

    The target store owns the paused run. With `--local`, this is the local file
    store; with `--url`, this is the long-lived JSON-RPC server's store.
    """
    try:
        resume_payload = parse_json_input(
            input_json=payload_json,
            input_file=payload_file,
        )
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    context = load_cli_context_from_typer(ctx)
    trace_range = _optional_trace_range(start=trace_from, limit=trace_limit)
    payload = run_cli_operation(
        context,
        context.handlers.resume_run(
            run_id=run_id,
            resume_payload=resume_payload,
            resume_outcome=outcome,
            trace_range=trace_range,
        ),
    )
    emit_json(payload)


@app.command("trace")
def trace_run(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Durable run id to trace.")],
    trace_from: Annotated[
        int,
        typer.Option("--from", min=0, help="Zero-based trace start offset."),
    ] = 0,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=100, help="Maximum trace entries."),
    ] = 25,
) -> None:
    """Read a bounded debug trace slice."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.handlers.read_run_trace(
            run_id=run_id,
            trace_range=TraceRange(start=trace_from, limit=limit),
        ),
    )
    emit_json(payload)


def _optional_trace_range(*, start: int | None, limit: int | None) -> TraceRange | None:
    """Build a trace range only when the caller requested trace detail."""
    if start is None and limit is None:
        return None
    return TraceRange(
        start=start if start is not None else 0,
        limit=limit if limit is not None else 25,
    )
