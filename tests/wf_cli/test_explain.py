from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wf_cli.app import app
from wf_cli.explain import (
    DEFAULT_EXPLAIN_REGISTRY,
    ExplainInputError,
    extract_explain_codes,
    parse_explain_input,
)


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


def test_explain_related_docs_do_not_point_to_planning_artifacts() -> None:
    for entry in DEFAULT_EXPLAIN_REGISTRY.list_full_entries():
        for related_doc in entry.related_docs:
            assert "docs/superpowers/" not in related_doc


def test_explain_related_doc_files_exist() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    for entry in DEFAULT_EXPLAIN_REGISTRY.list_full_entries():
        for related_doc in entry.related_docs:
            path_text = related_doc.split("#", 1)[0]
            if path_text.startswith("docs/"):
                assert (repo_root / path_text).exists(), path_text
