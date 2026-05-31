from __future__ import annotations

import json
from typing import Any


class ExplainInputError(ValueError):
    """Raised when `wf explain` input cannot be reduced to stable codes."""


def parse_explain_input(raw: str) -> list[str]:
    """Parse a direct code or JSON payload into first-seen unique codes."""
    stripped = raw.strip()
    if not stripped:
        raise ExplainInputError("explain input is empty")
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ExplainInputError(f"invalid JSON explain input: {exc.msg}") from exc
        return extract_explain_codes(value)
    return [stripped]


def extract_explain_codes(value: Any) -> list[str]:
    """Extract known diagnostic-code shapes without guessing or fuzzy matching."""
    codes: list[str] = []
    _collect_codes(value, codes)
    deduped = _dedupe(codes)
    if not deduped:
        raise ExplainInputError("no explainable code found in input")
    return deduped


def _collect_codes(value: Any, codes: list[str]) -> None:
    if isinstance(value, str):
        codes.append(value)
        return
    if isinstance(value, list):
        for item in value:
            _collect_codes(item, codes)
        return
    if not isinstance(value, dict):
        return

    code = value.get("code")
    if isinstance(code, str):
        codes.append(code)

    error = value.get("error")
    if isinstance(error, dict):
        error_code = error.get("code")
        if isinstance(error_code, str):
            codes.append(error_code)

    diagnostics = value.get("diagnostics")
    if isinstance(diagnostics, list):
        for diagnostic in diagnostics:
            _collect_codes(diagnostic, codes)


def _dedupe(codes: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        result.append(code)
    return result
