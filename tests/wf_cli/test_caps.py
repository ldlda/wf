from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

import wf_cli.commands.caps as caps
from wf_cli.app import app
from wf_cli.commands.caps import (
    CapCallOutputFormat,
    render_cap_call_output,
)
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
        from pathlib import Path
        from typing import cast

        return CliContext(
            config_path=Path("dummy"),
            service=None,
            handlers=_FakeHandlers(result),  # type: ignore[arg-type, ty:invalid-argument-type]
            source_admin=cast(Any, object()),
            admin=cast(Any, object()),
        )

    monkeypatch.setattr(caps, "load_cli_context_from_typer", _load_context)


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
        max_output_chars=100,
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
            "--unwrap-text",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "hello text"


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


def test_cap_call_cli_format_text_requires_unwrap_text(monkeypatch) -> None:
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
            "{}",
            "--format",
            "text",
        ],
    )

    assert result.exit_code != 0
    assert "--format text requires --unwrap-text" in result.output


def test_cap_call_cli_refuses_to_unwrap_multiple_text_blocks(monkeypatch) -> None:
    _patch_context(
        monkeypatch,
        _base_result(
            {"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}
        ),
    )

    result = CliRunner().invoke(
        app,
        [
            "cap",
            "call",
            "everything.default.echo",
            "--input",
            "{}",
            "--format",
            "text",
            "--unwrap-text",
        ],
    )

    assert result.exit_code != 0
    assert "exactly one MCP text content block" in result.output
