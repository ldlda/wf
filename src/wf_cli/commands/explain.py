from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from wf_cli.explain import (
    DEFAULT_EXPLAIN_REGISTRY,
    ExplainCard,
    ExplainInputError,
    ExplainSummary,
    UnknownExplainCode,
    parse_explain_input,
)
from wf_cli.io import emit_json


class ExplainFormat(StrEnum):
    """Output formats supported by `wf explain`."""

    JSON = "json"
    MARKDOWN = "markdown"
    COMPACT = "compact"


def explain_command(
    code: Annotated[
        str | None,
        typer.Argument(help="Diagnostic/error code, or JSON payload containing codes."),
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option("--input-file", help="Read diagnostic/error JSON from a file."),
    ] = None,
    read_stdin: Annotated[
        bool,
        typer.Option("--stdin", help="Read diagnostic/error JSON from standard input."),
    ] = False,
    list_entries: Annotated[
        bool,
        typer.Option("--list", help="List known explanation codes."),
    ] = False,
    output_format: Annotated[
        ExplainFormat,
        typer.Option("--format", help="Output format."),
    ] = ExplainFormat.JSON,
) -> None:
    """Explain exact workflow diagnostic codes without generated prose."""
    try:
        if list_entries:
            if code is not None or input_file is not None or read_stdin:
                raise ExplainInputError(
                    "--list cannot be combined with code, --input-file, or --stdin"
                )
            _emit_summaries(DEFAULT_EXPLAIN_REGISTRY.list_entries(), output_format)
            return
        codes = _read_codes(code=code, input_file=input_file, read_stdin=read_stdin)
        cards = [DEFAULT_EXPLAIN_REGISTRY.get(item) for item in codes]
    except (ExplainInputError, UnknownExplainCode) as exc:
        raise typer.BadParameter(_error_message(exc)) from exc

    if len(cards) == 1 and input_file is None and not read_stdin:
        _emit_card(cards[0], output_format)
    else:
        _emit_cards(cards, output_format)


def _read_codes(
    *,
    code: str | None,
    input_file: Path | None,
    read_stdin: bool,
) -> list[str]:
    """Resolve the mutually exclusive input modes supported by `wf explain`."""
    selected = sum(value is not None for value in (code, input_file)) + int(read_stdin)
    if selected == 0:
        raise ExplainInputError("provide a code, --input-file, --stdin, or --list")
    if selected > 1:
        raise ExplainInputError(
            "code, --input-file, and --stdin are mutually exclusive"
        )
    if code is not None:
        return parse_explain_input(code)
    if input_file is not None:
        try:
            return parse_explain_input(input_file.read_text(encoding="utf-8"))
        except OSError as exc:
            message = f"could not read input file {input_file!s}: {exc}"
            raise ExplainInputError(message) from exc
    return parse_explain_input(typer.get_text_stream("stdin").read())


def _emit_card(card: ExplainCard, output_format: ExplainFormat) -> None:
    if output_format is ExplainFormat.JSON:
        emit_json(card.model_dump(mode="json"))
        return
    if output_format is ExplainFormat.MARKDOWN:
        print(_card_markdown(card))
        return
    print(_card_compact(card))


def _emit_cards(cards: list[ExplainCard], output_format: ExplainFormat) -> None:
    if output_format is ExplainFormat.JSON:
        emit_json({"entries": [card.model_dump(mode="json") for card in cards]})
        return
    if output_format is ExplainFormat.MARKDOWN:
        print("\n\n".join(_card_markdown(card) for card in cards))
        return
    print("\n".join(_card_compact(card) for card in cards))


def _emit_summaries(
    summaries: list[ExplainSummary],
    output_format: ExplainFormat,
) -> None:
    if output_format is ExplainFormat.JSON:
        emit_json(
            {"entries": [summary.model_dump(mode="json") for summary in summaries]}
        )
        return
    if output_format is ExplainFormat.MARKDOWN:
        print("\n".join(f"- `{item.code}`: {item.summary}" for item in summaries))
        return
    print("\n".join(f"{item.code}: {item.summary}" for item in summaries))


def _card_markdown(card: ExplainCard) -> str:
    lines = [
        f"# {card.code}",
        "",
        card.summary,
        "",
        "## Why It Happens",
        *[f"- {item}" for item in card.why_it_happens],
        "",
        "## How To Fix",
        *[f"- {item}" for item in card.how_to_fix],
    ]
    if card.related_docs:
        lines.extend(
            ["", "## Related Docs", *[f"- {item}" for item in card.related_docs]]
        )
    return "\n".join(lines)


def _card_compact(card: ExplainCard) -> str:
    return f"{card.code}: {card.summary}"


def _error_message(exc: Exception) -> str:
    if isinstance(exc, UnknownExplainCode):
        return f"unknown explain code: {exc.args[0]}"
    return str(exc)
