from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CliInputError(ValueError):
    """Raised when CLI JSON/file input cannot be parsed safely."""


def parse_json_value(
    *,
    input_json: str | None,
    input_file: Path | None,
) -> Any:
    """Parse exactly one JSON value from inline JSON or a file path."""
    if input_json is not None and input_file is not None:
        raise CliInputError("--input and --input-file are mutually exclusive")
    if input_json is None and input_file is None:
        raise CliInputError("--input or --input-file is required")
    raw = input_json if input_json is not None else _read_input_file(input_file)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliInputError(f"invalid JSON input: {exc.msg}") from exc


def parse_json_input(
    *,
    input_json: str | None,
    input_file: Path | None,
) -> dict[str, Any]:
    """Parse exactly one JSON object from inline JSON or a file path."""
    if input_json is None and input_file is None:
        return {}
    payload = parse_json_value(input_json=input_json, input_file=input_file)
    if not isinstance(payload, dict):
        raise CliInputError("JSON input must be an object")
    return payload


def emit_json(payload: Any) -> None:
    """Write JSON output in the CLI default machine-readable format."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_bindings(bindings: list[str]) -> dict[str, str]:
    """Parse repeatable logical=concrete source binding flags."""
    parsed: dict[str, str] = {}
    for item in bindings:
        logical, separator, concrete = item.partition("=")
        if separator != "=" or not logical or not concrete:
            raise CliInputError("--binding must use logical=concrete")
        if logical in parsed:
            raise CliInputError(f"duplicate --binding for {logical!r}")
        parsed[logical] = concrete
    return parsed


def _read_input_file(path: Path | None) -> str:
    """Read a required JSON input file."""
    if path is None:
        raise CliInputError("input file path is required")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliInputError(f"could not read input file {path!s}: {exc}") from exc
