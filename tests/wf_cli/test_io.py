from __future__ import annotations

import json

import pytest

from wf_cli.io import CliInputError, emit_json, parse_json_input


def test_parse_json_input_reads_inline_json() -> None:
    payload = parse_json_input(input_json='{"text": "hello"}', input_file=None)

    assert payload["text"] == "hello"


def test_parse_json_input_reads_file(tmp_path) -> None:
    path = tmp_path / "payload.json"
    path.write_text('{"text": "from file"}', encoding="utf-8")

    payload = parse_json_input(input_json=None, input_file=path)

    assert payload["text"] == "from file"


def test_parse_json_input_rejects_both_inline_and_file(tmp_path) -> None:
    path = tmp_path / "payload.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(CliInputError, match="mutually exclusive"):
        parse_json_input(input_json="{}", input_file=path)


def test_parse_json_input_rejects_invalid_json() -> None:
    with pytest.raises(CliInputError, match="invalid JSON"):
        parse_json_input(input_json="{", input_file=None)


def test_emit_json_writes_pretty_json(capsys) -> None:
    emit_json({"ok": True, "items": [1]})
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["ok"] is True
    assert payload["items"][0] == 1
