# wf CLI Explain Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a docs-backed `wf explain` command that explains stable workflow diagnostic/error codes from exact codes or CLI/MCP-style error JSON.

**Architecture:** Keep explanation data in a small protocol-neutral registry under `wf_cli.explain`, then make `src/wf_cli/commands/explain.py` a thin Typer boundary. This slice does not change run/deploy behavior and does not implement fuzzy search, generated prose, or a large FAQ.

**Tech Stack:** Python 3.14, Typer, Pydantic v2, pytest `CliRunner`, existing `wf_cli.io.emit_json`.

---

## File Structure

Create:

```text
src/wf_cli/explain/
  __init__.py        # public exports for the explain registry package
  entries.py         # curated explanation cards; no runtime workflow logic
  models.py          # Pydantic models for cards and list summaries
  parser.py          # extracts stable codes from direct strings and JSON payloads
  registry.py        # exact lookup/list API over curated cards
tests/wf_cli/test_explain.py
```

Modify:

```text
src/wf_cli/commands/explain.py
```

Do not modify:

```text
src/wf_cli/commands/runs.py
src/wf_cli/commands/deployments.py
src/wf_mcp/
src/wf_core/
```

## Behavior Contract

Supported commands:

```bash
wf explain source_missing
wf explain source_missing --format json
wf explain source_missing --format markdown
wf explain source_missing --format compact
wf explain --input-file error.json
wf explain --stdin
wf explain --list
```

Supported initial codes:

```text
source_missing
source_unreachable
binding_missing
capability_missing
schema_changed
deployment_unrunnable
```

JSON output rules:

- `wf explain <code>` returns one full card object.
- `wf explain --input-file error.json` returns `{"entries": [full_card, ...]}` because input JSON can contain multiple diagnostics.
- `wf explain --stdin` follows the same shape as `--input-file`.
- `wf explain --list` returns a lean index: `{"entries": [{"code": "...", "summary": "..."}]}`.

Markdown output rules:

- One card renders as a small markdown document.
- Multiple cards render as multiple markdown documents separated by one blank line.
- List output renders a bullet list.

Compact output rules:

- One line per card: `code: summary`.
- List output uses the same one-line shape.

Input extraction rules:

- Direct string code: `source_missing`
- JSON object with `code`: `{"code": "source_missing"}`
- JSON object with `error.code`: `{"error": {"code": "deployment_unrunnable"}}`
- JSON object with diagnostics: `{"diagnostics": [{"code": "source_missing"}, {"code": "schema_changed"}]}`
- JSON list of diagnostics: `[{"code": "source_missing"}, {"code": "schema_changed"}]`
- Preserve first-seen order and dedupe repeated codes.
- Unknown codes should fail with a Typer error that includes the unknown code.

## Task 1: Add Registry Models And Entries

**Files:**

- Create: `src/wf_cli/explain/models.py`
- Create: `src/wf_cli/explain/entries.py`
- Create: `src/wf_cli/explain/__init__.py`
- Test: `tests/wf_cli/test_explain.py`

- [ ] **Step 1: Write failing model/registry smoke tests**

Create `tests/wf_cli/test_explain.py` with these first tests:

```python
from __future__ import annotations

from wf_cli.explain import DEFAULT_EXPLAIN_REGISTRY


def test_explain_registry_returns_full_card_for_known_code() -> None:
    card = DEFAULT_EXPLAIN_REGISTRY.get("source_missing")

    assert card.code == "source_missing"
    assert "source" in card.summary.lower()
    assert card.why_it_happens
    assert card.how_to_fix
    assert card.related_docs


def test_explain_registry_list_is_lean() -> None:
    entries = DEFAULT_EXPLAIN_REGISTRY.list_entries()

    source_missing = next(entry for entry in entries if entry.code == "source_missing")
    assert source_missing.code == "source_missing"
    assert "source" in source_missing.summary.lower()
    assert not hasattr(source_missing, "how_to_fix")
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
uv run pytest tests/wf_cli/test_explain.py -q
```

Expected: fail because `wf_cli.explain` does not exist.

- [ ] **Step 3: Implement Pydantic models**

Create `src/wf_cli/explain/models.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class ExplainCard(BaseModel):
    """Human-curated help for one stable workflow diagnostic/error code."""

    code: str = Field(min_length=1, description="Stable diagnostic or CLI error code.")
    summary: str = Field(min_length=1, description="One-sentence explanation.")
    why_it_happens: list[str] = Field(
        description="Common causes, ordered from most likely to least likely."
    )
    how_to_fix: list[str] = Field(
        description="Concrete next steps an agent or user can try."
    )
    related_docs: list[str] = Field(
        default_factory=list,
        description="Documentation resource IDs or file references.",
    )


class ExplainSummary(BaseModel):
    """Lean index entry for `wf explain --list`."""

    code: str = Field(min_length=1)
    summary: str = Field(min_length=1)
```

- [ ] **Step 4: Implement curated entries**

Create `src/wf_cli/explain/entries.py`:

```python
from __future__ import annotations

from .models import ExplainCard


EXPLAIN_CARDS: tuple[ExplainCard, ...] = (
    ExplainCard(
        code="source_missing",
        summary="A required logical source is not available or not bound.",
        why_it_happens=[
            "The artifact requires a logical source that the deployment did not bind.",
            "The concrete source was removed, renamed, disabled, or never registered.",
            "A saved wrapper or workflow depends on a source that is absent in this config.",
        ],
        how_to_fix=[
            "Run `wf deploy inspect <deployment_id>` and check the bindings.",
            "Run `wf cap list` to confirm the concrete source is available.",
            "Save the deployment again with the missing logical source bound.",
            "Run `wf deploy validate <deployment_id> --live` after changing bindings.",
        ],
        related_docs=[
            "docs/wf_cli_usage.md#deployment-validation",
            "docs/workflow_capabilities.md",
        ],
    ),
    ExplainCard(
        code="source_unreachable",
        summary="A concrete source exists in config but could not be reached.",
        why_it_happens=[
            "The upstream MCP server or local process failed during liveness checks.",
            "The source command, URL, authentication, or environment is invalid.",
            "The source is slow or hung and exceeded the bounded liveness timeout.",
        ],
        how_to_fix=[
            "Check the source command or URL in the active config.",
            "Start or restart the upstream server.",
            "Run validation without `--live` if you only need static deployment checks.",
            "Run `wf deploy validate <deployment_id> --live` again after fixing the source.",
        ],
        related_docs=[
            "docs/wf_cli_usage.md#deployment-validation",
            "docs/wf_mcp_unified_proxy_plan.md",
        ],
    ),
    ExplainCard(
        code="binding_missing",
        summary="A deployment is missing a required logical-to-concrete source binding.",
        why_it_happens=[
            "The artifact was saved with required capabilities under a logical source.",
            "The deployment was saved without a binding for that logical source.",
            "A binding field was misspelled or placed under the wrong payload key.",
        ],
        how_to_fix=[
            "Inspect the artifact requirements.",
            "Inspect the deployment bindings.",
            "Save the deployment with `bindings` entries that map each logical source.",
            "Use `wf deploy validate <deployment_id>` to confirm the binding set.",
        ],
        related_docs=[
            "docs/wf_cli_usage.md#save-and-validate-a-deployment",
            "docs/workflow_capabilities.md#sources",
        ],
    ),
    ExplainCard(
        code="capability_missing",
        summary="A required capability is not present on the bound source.",
        why_it_happens=[
            "The upstream source no longer exposes the tool or node spec.",
            "The workflow was bound to the wrong account/profile/source.",
            "The capability was renamed after the artifact was saved.",
        ],
        how_to_fix=[
            "Run `wf cap list` and search for the expected capability.",
            "Inspect the deployment bindings for the affected logical source.",
            "Rebind to a concrete source that exposes the capability.",
            "Rebuild or patch the artifact if the capability was intentionally renamed.",
        ],
        related_docs=[
            "docs/workflow_capabilities.md",
            "docs/wf_cli_usage.md#capability-discovery",
        ],
    ),
    ExplainCard(
        code="schema_changed",
        summary="A saved dependency schema no longer matches the live capability.",
        why_it_happens=[
            "The upstream tool or node spec changed its input/output schema.",
            "The deployment is bound to a different source profile than the one used before.",
            "A wrapper assumes fields that the live capability no longer declares.",
        ],
        how_to_fix=[
            "Inspect the live capability.",
            "Compare it with the saved artifact dependency summary.",
            "Patch the draft or wrapper to match the new schema.",
            "Save a new artifact version and deployment after validating the change.",
        ],
        related_docs=[
            "docs/workflow_capabilities.md#dependency-validation",
            "docs/schema_validation.md",
        ],
    ),
    ExplainCard(
        code="deployment_unrunnable",
        summary="The deployment failed validation and should not be run yet.",
        why_it_happens=[
            "One or more required sources, capabilities, schemas, or bindings are invalid.",
            "The deployment points at an artifact version that cannot be resolved.",
            "Live validation found an upstream source or capability problem.",
        ],
        how_to_fix=[
            "Run `wf deploy validate <deployment_id>` and read the diagnostics.",
            "Run `wf explain --input-file <validation-output.json>` for diagnostic details.",
            "Fix source bindings or rebuild the artifact version.",
            "Re-run validation before starting the deployment.",
        ],
        related_docs=[
            "docs/wf_cli_usage.md#deployment-validation",
            "docs/current_roadmap.md",
        ],
    ),
)
```

- [ ] **Step 5: Implement registry**

Create `src/wf_cli/explain/registry.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from .entries import EXPLAIN_CARDS
from .models import ExplainCard, ExplainSummary


class UnknownExplainCode(KeyError):
    """Raised when a diagnostic code is not present in the curated registry."""


class ExplainRegistry:
    """Exact-match registry for docs-backed explanation cards."""

    def __init__(self, entries: Iterable[ExplainCard] = EXPLAIN_CARDS) -> None:
        self._entries = {entry.code: entry for entry in entries}

    def get(self, code: str) -> ExplainCard:
        """Return a full explanation card for one stable code."""
        try:
            return self._entries[code]
        except KeyError as exc:
            raise UnknownExplainCode(code) from exc

    def list_entries(self) -> list[ExplainSummary]:
        """Return lean summaries for discovery output."""
        return [
            ExplainSummary(code=entry.code, summary=entry.summary)
            for entry in self._entries.values()
        ]


DEFAULT_EXPLAIN_REGISTRY = ExplainRegistry()
```

- [ ] **Step 6: Export public API**

Create `src/wf_cli/explain/__init__.py`:

```python
"""Docs-backed explanation registry for workflow CLI diagnostics."""

from .models import ExplainCard, ExplainSummary
from .registry import DEFAULT_EXPLAIN_REGISTRY, ExplainRegistry, UnknownExplainCode

__all__ = [
    "DEFAULT_EXPLAIN_REGISTRY",
    "ExplainCard",
    "ExplainRegistry",
    "ExplainSummary",
    "UnknownExplainCode",
]
```

- [ ] **Step 7: Run tests**

Run:

```bash
uv run pytest tests/wf_cli/test_explain.py -q
```

Expected: pass.

## Task 2: Add JSON/String Code Parser

**Files:**

- Create: `src/wf_cli/explain/parser.py`
- Modify: `src/wf_cli/explain/__init__.py`
- Test: `tests/wf_cli/test_explain.py`

- [ ] **Step 1: Add parser tests**

Replace the import block at the top of `tests/wf_cli/test_explain.py` with:

```python
from __future__ import annotations

import pytest

from wf_cli.explain import (
    DEFAULT_EXPLAIN_REGISTRY,
    ExplainInputError,
    extract_explain_codes,
    parse_explain_input,
)
```

Then append these tests to `tests/wf_cli/test_explain.py`:

```python


def test_parse_explain_input_accepts_direct_code() -> None:
    assert parse_explain_input("source_missing") == ["source_missing"]


def test_parse_explain_input_extracts_error_code() -> None:
    raw = '{"error": {"code": "deployment_unrunnable"}}'

    assert parse_explain_input(raw) == ["deployment_unrunnable"]


def test_parse_explain_input_extracts_diagnostic_codes_in_order() -> None:
    raw = """
    {
      "diagnostics": [
        {"code": "source_missing"},
        {"code": "schema_changed"},
        {"code": "source_missing"}
      ]
    }
    """

    assert parse_explain_input(raw) == ["source_missing", "schema_changed"]


def test_extract_explain_codes_accepts_diagnostic_list() -> None:
    value = [{"code": "binding_missing"}, {"code": "capability_missing"}]

    assert extract_explain_codes(value) == ["binding_missing", "capability_missing"]


def test_parse_explain_input_rejects_json_without_codes() -> None:
    with pytest.raises(ExplainInputError, match="no explainable code"):
        parse_explain_input('{"status": "failed"}')
```

- [ ] **Step 2: Run parser tests to verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_explain.py -q
```

Expected: fail because `parser.py` and exports do not exist.

- [ ] **Step 3: Implement parser**

Create `src/wf_cli/explain/parser.py`:

```python
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
```

- [ ] **Step 4: Export parser helpers**

Modify `src/wf_cli/explain/__init__.py`:

```python
"""Docs-backed explanation registry for workflow CLI diagnostics."""

from .models import ExplainCard, ExplainSummary
from .parser import ExplainInputError, extract_explain_codes, parse_explain_input
from .registry import DEFAULT_EXPLAIN_REGISTRY, ExplainRegistry, UnknownExplainCode

__all__ = [
    "DEFAULT_EXPLAIN_REGISTRY",
    "ExplainCard",
    "ExplainInputError",
    "ExplainRegistry",
    "ExplainSummary",
    "UnknownExplainCode",
    "extract_explain_codes",
    "parse_explain_input",
]
```

- [ ] **Step 5: Run parser tests**

Run:

```bash
uv run pytest tests/wf_cli/test_explain.py -q
```

Expected: pass.

## Task 3: Implement `wf explain` Command And Rendering

**Files:**

- Modify: `src/wf_cli/commands/explain.py`
- Modify: `src/wf_cli/app.py`
- Test: `tests/wf_cli/test_explain.py`
- Test: `tests/wf_cli/test_app.py`

- [ ] **Step 1: Add CLI tests**

Replace the import block at the top of `tests/wf_cli/test_explain.py` with:

```python
from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from wf_cli.app import app
from wf_cli.explain import (
    DEFAULT_EXPLAIN_REGISTRY,
    ExplainInputError,
    extract_explain_codes,
    parse_explain_input,
)
```

Then append these tests to `tests/wf_cli/test_explain.py`:

```python


runner = CliRunner()


def test_wf_explain_code_outputs_full_json_card() -> None:
    result = runner.invoke(app, ["explain", "source_missing"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["code"] == "source_missing"
    assert payload["summary"]
    assert payload["why_it_happens"]
    assert payload["how_to_fix"]


def test_wf_explain_list_outputs_lean_json_index() -> None:
    result = runner.invoke(app, ["explain", "--list"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    first = payload["entries"][0]
    assert first["code"]
    assert first["summary"]
    assert "how_to_fix" not in first


def test_wf_explain_markdown_format() -> None:
    result = runner.invoke(app, ["explain", "source_missing", "--format", "markdown"])

    assert result.exit_code == 0
    assert "# source_missing" in result.output
    assert "## How To Fix" in result.output


def test_wf_explain_compact_format() -> None:
    result = runner.invoke(app, ["explain", "source_missing", "--format", "compact"])

    assert result.exit_code == 0
    assert result.output.strip().startswith("source_missing: ")


def test_wf_explain_input_file_outputs_multiple_cards(tmp_path) -> None:
    error_file = tmp_path / "error.json"
    error_file.write_text(
        json.dumps(
            {
                "diagnostics": [
                    {"code": "source_missing"},
                    {"code": "schema_changed"},
                    {"code": "source_missing"},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["explain", "--input-file", str(error_file)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload["entries"]) == 2
    assert payload["entries"][0]["code"] == "source_missing"
    assert payload["entries"][1]["code"] == "schema_changed"


def test_wf_explain_stdin_outputs_multiple_cards() -> None:
    result = runner.invoke(
        app,
        ["explain", "--stdin"],
        input='{"error": {"code": "deployment_unrunnable"}}',
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["entries"][0]["code"] == "deployment_unrunnable"


def test_wf_explain_unknown_code_fails_clearly() -> None:
    result = runner.invoke(app, ["explain", "not_a_real_code"])

    assert result.exit_code != 0
    assert "not_a_real_code" in result.output


def test_wf_explain_list_rejects_other_input_modes() -> None:
    result = runner.invoke(app, ["explain", "source_missing", "--list"])

    assert result.exit_code != 0
    assert "--list cannot be combined" in result.output
```

Append this test to `tests/wf_cli/test_app.py`:

```python
def test_wf_explain_help_shows_input_modes() -> None:
    result = runner.invoke(app, ["explain", "--help"])

    assert result.exit_code == 0
    assert "--input-file" in result.output
    assert "--stdin" in result.output
    assert "--list" in result.output
```

- [ ] **Step 2: Run CLI tests to verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_explain.py tests/wf_cli/test_app.py -q
```

Expected: fail because `wf explain` has no callback implementation.

- [ ] **Step 3: Implement command**

Replace `src/wf_cli/commands/explain.py` with:

```python
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
        raise ExplainInputError("code, --input-file, and --stdin are mutually exclusive")
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
        lines.extend(["", "## Related Docs", *[f"- {item}" for item in card.related_docs]])
    return "\n".join(lines)


def _card_compact(card: ExplainCard) -> str:
    return f"{card.code}: {card.summary}"


def _error_message(exc: Exception) -> str:
    if isinstance(exc, UnknownExplainCode):
        return f"unknown explain code: {exc.args[0]}"
    return str(exc)
```

Then modify `src/wf_cli/app.py` so `explain` is registered as a direct command,
not as a Typer sub-app:

```python
app.add_typer(caps.app, name="cap")
app.add_typer(drafts.app, name="draft")
app.add_typer(artifacts.app, name="artifact")
app.add_typer(deployments.app, name="deploy")
app.add_typer(runs.app, name="run")
app.add_typer(docs.app, name="docs")
app.add_typer(schema.app, name="schema")
app.command("explain")(explain.explain_command)
```

Reason: `wf explain <code> --format markdown` is a single command with options,
not a command group. The Typer sub-app callback pattern with
`invoke_without_command=True` can misparse callback options as subcommand names
when registered via `add_typer()`.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_explain.py tests/wf_cli/test_app.py -q
```

Expected: pass.

## Task 4: Verify Focused Slice

**Files:**

- No new files unless formatting changes are required.

- [ ] **Step 1: Run focused CLI tests**

Run:

```bash
uv run pytest tests/wf_cli -q
```

Expected: all `tests/wf_cli` tests pass.

- [ ] **Step 2: Run focused lint**

Run:

```bash
uv run ruff check src/wf_cli tests/wf_cli
```

Expected: no lint errors.

- [ ] **Step 3: Run focused format check**

Run:

```bash
uv run ruff format --check src/wf_cli tests/wf_cli
```

Expected: no formatting changes required. If this fails, run:

```bash
uv run ruff format src/wf_cli tests/wf_cli
```

Then rerun the format check.

- [ ] **Step 4: Run type check**

Run:

```bash
uv run basedpyright --level error
```

Expected: `0 errors`.

## Self-Review Checklist

- [ ] `wf explain --list` returns lean summaries, not full cards.
- [ ] `wf explain <code>` returns a full card.
- [ ] `wf explain --input-file` and `wf explain --stdin` support multiple cards.
- [ ] Unknown codes fail clearly and include the unknown code string.
- [ ] No fuzzy matching or generated prose was added.
- [ ] No run/deploy behavior changed.
- [ ] The new package has docstrings around the registry/parser boundary.
