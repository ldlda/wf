# cap call Output Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `wf cap call` safer and more useful for humans by adding explicit compact/truncated/text output modes without changing the default JSON contract.

**Architecture:** Keep the API and RPC payload unchanged. All shaping happens in `wf_cli.commands.caps` after `call_capability` returns. JSON remains default and lossless; compact/text modes are opt-in and must avoid dumping large MCP content/resource/blob payloads.

**Tech Stack:** Python 3.14, Typer, pytest, pytest-asyncio, existing `wf_cli` formatting helpers, ruff, basedpyright.

---

## Product Rules

- Default `wf cap call` output stays full JSON.
- `--format compact` prints a bounded one-line summary.
- `--max-output-chars N` applies only to non-JSON rendered output.
- `--unwrap-text` is explicit and safe only when the output is exactly one MCP text content block.
- `--unwrap-text` must not unwrap image/resource/blob/base64 content.
- Help text for `--unwrap-text` must explain the exact safe case.

## Files

- Modify `src/wf_cli/commands/caps.py`.
- Add or modify tests in `tests/wf_cli/test_remote_target.py` or create `tests/wf_cli/test_caps.py`.
- Update `docs/wf_cli.md`.
- Update `docs/current_roadmap.md`.
- Move this plan to `docs/historical/superpowers/plans/` after implementation.

## Task 1: Renderer Unit Tests

**Files:**
- Test: `tests/wf_cli/test_caps.py`
- Modify: `src/wf_cli/commands/caps.py`

- [ ] **Step 1: Add renderer tests first**

Create `tests/wf_cli/test_caps.py` with tests for pure rendering helpers. Import the helpers even if they are private; this is acceptable because the behavior is CLI safety-critical.

```python
from __future__ import annotations

import json

import pytest

from wf_cli.commands.caps import (
    CapCallOutputFormat,
    render_cap_call_output,
)


def _base_result(output: object) -> dict[str, object]:
    return {
        "qualified_name": "everything.default.echo",
        "source_id": "everything.default",
        "kind": "node_spec",
        "deployment_id": None,
        "outcome": "ok",
        "output": output,
        "diagnostics": [],
    }


def test_render_cap_call_json_is_lossless() -> None:
    result = _base_result({"value": "hello"})

    rendered = render_cap_call_output(
        result,
        output_format=CapCallOutputFormat.JSON,
        unwrap_text=False,
        max_output_chars=10,
    )

    assert json.loads(rendered) == result


def test_render_cap_call_compact_summarizes_without_dumping_payload() -> None:
    result = _base_result({"content": [{"type": "image", "data": "x" * 5000}]})

    rendered = render_cap_call_output(
        result,
        output_format=CapCallOutputFormat.COMPACT,
        unwrap_text=False,
        max_output_chars=40,
    )

    assert "everything.default.echo" in rendered
    assert "outcome=ok" in rendered
    assert "output=" in rendered
    assert "x" * 100 not in rendered
    assert len(rendered) < 200


def test_render_cap_call_unwrap_text_for_single_text_block() -> None:
    result = _base_result(
        {
            "content": [
                {
                    "type": "text",
                    "text": "hello from mcp",
                }
            ]
        }
    )

    rendered = render_cap_call_output(
        result,
        output_format=CapCallOutputFormat.TEXT,
        unwrap_text=True,
        max_output_chars=100,
    )

    assert rendered == "hello from mcp"


def test_render_cap_call_unwrap_text_rejects_non_text_blocks() -> None:
    result = _base_result(
        {
            "content": [
                {
                    "type": "image",
                    "data": "BASE64",
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="exactly one MCP text content block"):
        render_cap_call_output(
            result,
            output_format=CapCallOutputFormat.TEXT,
            unwrap_text=True,
            max_output_chars=100,
        )


def test_render_cap_call_text_truncates_unwrapped_text() -> None:
    result = _base_result({"content": [{"type": "text", "text": "abcdef"}]})

    rendered = render_cap_call_output(
        result,
        output_format=CapCallOutputFormat.TEXT,
        unwrap_text=True,
        max_output_chars=3,
    )

    assert rendered == "abc...<truncated 3 chars>"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_caps.py -q
```

Expected: FAIL because `CapCallOutputFormat` and `render_cap_call_output` do not exist.

- [ ] **Step 3: Add enum and renderer**

In `src/wf_cli/commands/caps.py`, add imports:

```python
import json
from enum import StrEnum
from typing import Any
```

Add near the top:

```python
class CapCallOutputFormat(StrEnum):
    JSON = "json"
    COMPACT = "compact"
    TEXT = "text"
```

Add helpers near the bottom:

```python
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
```

- [ ] **Step 4: Run renderer tests**

Run:

```bash
uv run pytest tests/wf_cli/test_caps.py -q
```

Expected: PASS.

## Task 2: CLI Flags And Help Text

**Files:**
- Modify: `src/wf_cli/commands/caps.py`
- Test: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add CLI behavior tests**

In `tests/wf_cli/test_remote_target.py`, extend or add tests around `test_wf_cap_commands_use_rpc_url_override`.

Add compact mode assertion:

```python
compact = runner.invoke(
    app,
    [
        *base_args,
        "cap",
        "call",
        "wf.std.constant",
        "--input",
        '{"value": "hello cap call"}',
        "--format",
        "compact",
    ],
)
assert compact.exit_code == 0, compact.output
assert "wf.std.constant" in compact.output
assert "outcome=ok" in compact.output
assert "hello cap call" not in compact.output
```

Add help text assertion:

```python
help_result = runner.invoke(app, ["cap", "call", "--help"])
assert help_result.exit_code == 0
assert "--unwrap-text" in help_result.output
assert "exactly one MCP text content block" in help_result.output
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_cap_commands_use_rpc_url_override -q
```

Expected: FAIL because flags do not exist.

- [ ] **Step 3: Add command options**

In `call_capability`, add parameters:

```python
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
            help=(
                "Only with --format text: print exactly one MCP text content block; "
                "refuses images, resources, blobs, multiple blocks, and non-MCP output."
            ),
        ),
    ] = False,
```

- [ ] **Step 4: Use renderer in command**

Replace `emit_json(result)` with:

```python
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
```

- [ ] **Step 5: Run focused CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_caps.py tests/wf_cli/test_remote_target.py::test_wf_cap_commands_use_rpc_url_override -q
```

Expected: PASS.

## Task 3: MCP Text And Blob Safety Tests

**Files:**
- Test: `tests/wf_cli/test_caps.py`

- [ ] **Step 1: Add command-level fake-handler tests**

Add a small fake handler/context test in `tests/wf_cli/test_caps.py` so MCP-shaped output is tested without needing a real MCP server:

```python
from typing import Any

from typer.testing import CliRunner

import wf_cli.commands.caps as caps
from wf_cli.app import app
from wf_cli.context import CliContext


class _FakeHandlers:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> dict[str, Any]:
        return self.result


def _patch_context(monkeypatch, result: dict[str, Any]) -> None:
    def _load_context(ctx: object) -> CliContext:
        return CliContext(handlers=_FakeHandlers(result))

    monkeypatch.setattr(caps, "load_cli_context_from_typer", _load_context)
```

Add text unwrap success:

```python
def test_cap_call_cli_unwraps_single_mcp_text_block(monkeypatch) -> None:
    _patch_context(
        monkeypatch,
        _base_result({"content": [{"type": "text", "text": "hello text"}]}),
    )

    result = CliRunner().invoke(
        app,
        [
            "cap",
            "call",
            "everything.default.echo",
            "--input",
            '{"message": "hello"}',
            "--format",
            "text",
            "--unwrap-text",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "hello text"
```

Add blob rejection:

```python
def test_cap_call_cli_refuses_to_unwrap_blob_content(monkeypatch) -> None:
    _patch_context(
        monkeypatch,
        _base_result({"content": [{"type": "image", "data": "BASE64"}]}),
    )

    result = CliRunner().invoke(
        app,
        [
            "cap",
            "call",
            "everything.default.image",
            "--input",
            "{}",
            "--format",
            "text",
            "--unwrap-text",
        ],
    )

    assert result.exit_code != 0
    assert "exactly one MCP text content block" in result.output
```

- [ ] **Step 2: Run tests**

Run:

```bash
uv run pytest tests/wf_cli/test_caps.py -q
```

Expected: PASS.

## Task 4: Docs And Roadmap

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/runbooks/rpc-cli-smoke.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update CLI docs**

In `docs/wf_cli.md`, extend the `cap call` section:

```bash
wf cap call wf.std.constant --input '{"value": "hello"}' --format compact
wf cap call everything.default.echo --input '{"message": "hello"}' --format text --unwrap-text
```

Document:

- JSON is default and lossless.
- Compact/text output is opt-in.
- `--unwrap-text` only prints exactly one MCP text content block.
- Images/resources/blobs/multiple content blocks are refused by text mode.
- Use `--max-output-chars` for compact/text terminal safety.

- [ ] **Step 2: Update smoke runbook**

In `docs/runbooks/rpc-cli-smoke.md`, keep the default JSON `wf.std.constant`
smoke command and add one optional small-output command:

```bash
uv run wf --config wf.config.json cap call wf.std.constant --input '{"value":"smoke"}' --format compact
```

Do not add arbitrary MCP tool calls to the smoke runbook.

- [ ] **Step 3: Update roadmap**

In `docs/current_roadmap.md`, mark the `cap call` output safety cleanup complete after implementation.

## Task 5: Final Verification

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_cli/test_caps.py tests/wf_cli/test_remote_target.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint and type checks on changed files**

Run:

```bash
uv run ruff check src/wf_cli/commands/caps.py tests/wf_cli/test_caps.py tests/wf_cli/test_remote_target.py docs/wf_cli.md docs/runbooks/rpc-cli-smoke.md docs/current_roadmap.md
uv run basedpyright --level error src/wf_cli/commands/caps.py tests/wf_cli/test_caps.py tests/wf_cli/test_remote_target.py
```

Expected: PASS.

- [ ] **Step 3: Optional manual smoke**

Against a running RPC server:

```bash
uv run wf --config wf.config.json cap call wf.std.constant --input '{"value":"smoke"}' --format compact
```

Expected: one bounded line with `outcome=ok`.

