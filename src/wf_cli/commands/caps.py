from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer

from wf_cli.context import load_cli_context_from_typer
from wf_cli.formats import ListOutputFormat, emit_list_payload
from wf_cli.io import CliInputError, emit_json, parse_json_input
from wf_cli.remote_errors import run_cli_operation


class CapCallOutputFormat(StrEnum):
    JSON = "json"
    COMPACT = "compact"
    TEXT = "text"


app = typer.Typer(
    name="cap",
    help="Inspect and call workflow capabilities.",
    no_args_is_help=True,
)


@app.command("list")
def list_capabilities(
    ctx: typer.Context,
    query: Annotated[
        str | None,
        typer.Option("--query", help="Search capability names/descriptions."),
    ] = None,
    source_id: Annotated[
        str | None, typer.Option("--source", help="Filter by source id.")
    ] = None,
    cursor: Annotated[
        str | None, typer.Option("--cursor", help="Pagination cursor.")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", min=1, max=100, help="Maximum rows.")
    ] = 50,
    output_format: Annotated[
        ListOutputFormat, typer.Option("--format", help="Output format.")
    ] = ListOutputFormat.JSON,
) -> None:
    """List compact planner-visible workflow capabilities."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.handlers.list_capabilities(
            query=query,
            source_id=source_id,
            cursor=cursor,
            limit=limit,
        ),
    )
    emit_list_payload(
        payload,
        collection_key="capabilities",
        output_format=output_format,
        id_field="name",
        summary_fields=("source_id", "kind", "description"),
    )


@app.command("inspect")
def inspect_capability(
    ctx: typer.Context,
    qualified_name: Annotated[str, typer.Argument(help="Workflow capability name.")],
) -> None:
    """Inspect one workflow capability contract."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.handlers.inspect_capability(qualified_name=qualified_name),
    )
    emit_json(payload)


@app.command("call")
def call_capability(
    ctx: typer.Context,
    qualified_name: Annotated[str, typer.Argument(help="Workflow capability name.")],
    input_json: Annotated[
        str | None,
        typer.Option("--input", help="JSON object payload for the capability."),
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option(
            "--input-file",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Read capability JSON object payload from a file.",
        ),
    ] = None,
    deployment_id: Annotated[
        str | None,
        typer.Option(
            "--deployment",
            help="Deployment id for saved wrappers with deployment-bound sources.",
        ),
    ] = None,
    output_format: Annotated[
        CapCallOutputFormat,
        typer.Option("--format", help="Output format for rendered cap-call result."),
    ] = CapCallOutputFormat.JSON,
    max_output_chars: Annotated[
        int | None,
        typer.Option(
            "--max-output-chars",
            min=1,
            help="Maximum characters for compact/text output. JSON output is not truncated.",
        ),
    ] = None,
    unwrap_text: Annotated[
        bool,
        typer.Option(
            "--unwrap-text",
            help="Only with --format text: unwrap one MCP text block.",
        ),
    ] = False,
) -> None:
    """Call one workflow capability once for authoring/runtime smoke tests."""
    try:
        payload = parse_json_input(input_json=input_json, input_file=input_file)
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc

    context = load_cli_context_from_typer(ctx)
    result = run_cli_operation(
        context,
        context.handlers.call_capability(
            qualified_name=qualified_name,
            payload=payload,
            deployment_id=deployment_id,
        ),
    )
    try:
        rendered = render_cap_call_output(
            result,
            output_format=output_format,
            unwrap_text=unwrap_text,
            max_output_chars=max_output_chars,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    print(rendered)


def render_cap_call_output(
    result: dict[str, Any],
    *,
    output_format: CapCallOutputFormat,
    unwrap_text: bool,
    max_output_chars: int | None,
) -> str:
    """Render cap-call output without changing the API/RPC payload."""
    if output_format is CapCallOutputFormat.JSON:
        return json.dumps(result, indent=2, sort_keys=True)
    if output_format is CapCallOutputFormat.TEXT:
        if not unwrap_text:
            raise ValueError("--format text requires --unwrap-text")
        return _truncate_text(
            _unwrap_single_mcp_text_block(result),
            max_output_chars=max_output_chars,
        )
    summary = _compact_cap_call_summary(result)
    return _truncate_text(summary, max_output_chars=max_output_chars)


def _compact_cap_call_summary(result: dict[str, Any]) -> str:
    output = result.get("output")
    output_summary = _summarize_output(output)
    return "\t".join(
        part
        for part in (
            str(result.get("qualified_name", "")),
            f"source={result.get('source_id')}",
            f"kind={result.get('kind')}",
            f"outcome={result.get('outcome')}",
            f"output={output_summary}",
        )
        if part
    )


def _summarize_output(output: object) -> str:
    if isinstance(output, dict):
        content = output.get("content")
        if isinstance(content, list):
            return f"mcp_content_blocks[{len(content)}]"
        return f"object keys={sorted(str(key) for key in output.keys())}"
    if isinstance(output, list):
        return f"array[{len(output)}]"
    return type(output).__name__


def _unwrap_single_mcp_text_block(result: dict[str, Any]) -> str:
    output = result.get("output")
    if not isinstance(output, dict):
        raise ValueError("--unwrap-text requires exactly one MCP text content block")
    content = output.get("content")
    if not isinstance(content, list) or len(content) != 1:
        raise ValueError("--unwrap-text requires exactly one MCP text content block")
    block = content[0]
    if not isinstance(block, dict):
        raise ValueError("--unwrap-text requires exactly one MCP text content block")
    if block.get("type") != "text" or not isinstance(block.get("text"), str):
        raise ValueError("--unwrap-text requires exactly one MCP text content block")
    return block["text"]


def _truncate_text(text: str, *, max_output_chars: int | None) -> str:
    if max_output_chars is None or len(text) <= max_output_chars:
        return text
    remaining = len(text) - max_output_chars
    return f"{text[:max_output_chars]}...<truncated {remaining} chars>"
