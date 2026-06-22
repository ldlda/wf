from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from jsonschema import Draft202012Validator
from typer.testing import CliRunner

from wf_cli.app import app
from wf_cli.schema_catalog import (
    compact_schema_outline,
    schema_catalog,
    verbose_schema_document,
)

runner = CliRunner()


def _json_result(*args: str) -> dict[str, Any]:
    result = runner.invoke(app, ["schema", *args])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, dict)
    return payload


def _local_refs(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str) and item.startswith("#/$defs/"):
                yield item.removeprefix("#/$defs/")
            else:
                yield from _local_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _local_refs(item)


def test_schema_without_name_lists_sorted_catalog() -> None:
    payload = _json_result()
    listed = _json_result("list")

    assert payload == listed
    names = [entry["name"] for entry in payload["schemas"]]
    assert names == sorted(names)
    assert {"WorkflowDraft", "RawWorkflowPlan", "Workflow", "NodeUse"} <= set(names)
    aliases = {
        alias: entry["name"]
        for entry in payload["schemas"]
        for alias in entry["aliases"]
    }
    assert aliases == {
        "core": "Workflow",
        "draft": "WorkflowDraft",
        "raw": "RawWorkflowPlan",
    }


def test_schema_compact_alias_is_json_outline_without_refs() -> None:
    payload = _json_result("raw")

    assert payload["name"] == "RawWorkflowPlan"
    assert payload["kind"] == "schema_outline"
    assert payload["properties"]["nodes"]["items"]["one_of"] == [
        "NodeUse",
        "SubgraphNode",
        "ConditionNode",
        "ForeachNode",
        "JoinNode",
        "EndNode",
        "InterruptNode",
    ]
    assert "$ref" not in json.dumps(payload)
    assert "NodeUse" in payload["related"]
    assert payload["full_schema_command"] == "wf schema raw --verbose"


def test_schema_compact_component_is_queryable() -> None:
    payload = _json_result("NodeUse")

    assert payload["name"] == "NodeUse"
    assert payload["properties"]["input"]["items"]["one_of"] == [
        "InputPathBinding",
        "InputValueBinding",
    ]
    assert "$ref" not in json.dumps(payload)


def test_schema_verbose_root_is_valid_json_schema() -> None:
    payload = _json_result("raw", "--verbose")

    Draft202012Validator.check_schema(payload)
    definitions = payload.get("$defs", {})
    assert set(_local_refs(payload)) <= set(definitions)
    assert payload["title"] == "RawWorkflowPlan"


def test_schema_verbose_component_is_self_contained() -> None:
    payload = _json_result("NodeUse", "--verbose")

    Draft202012Validator.check_schema(payload)
    assert payload["$ref"] == "#/$defs/NodeUse"
    definitions = payload["$defs"]
    assert set(_local_refs(payload)) <= set(definitions)
    Draft202012Validator(payload).validate(
        {"id": "call", "type": "node", "node": "local.report.read_notes"}
    )


def test_schema_unknown_name_fails_with_suggestion() -> None:
    result = runner.invoke(app, ["schema", "Node"])

    assert result.exit_code != 0
    assert "unknown schema 'Node'" in result.output
    assert "NodeUse" in result.output


def test_schema_catalog_resolves_aliases_and_components() -> None:
    catalog = schema_catalog()

    assert catalog.resolve("raw") == "RawWorkflowPlan"
    assert catalog.resolve("RawWorkflowPlan") == "RawWorkflowPlan"
    assert catalog.resolve("NodeUse") == "NodeUse"
    assert catalog.entry("draft").kind == "root"
    assert catalog.entry("NodeUse").kind == "definition"


def test_compact_outline_replaces_local_refs_with_names() -> None:
    payload = compact_schema_outline("NodeUse")

    assert payload["properties"]["input"]["items"]["one_of"] == [
        "InputPathBinding",
        "InputValueBinding",
    ]
    assert "$ref" not in json.dumps(payload)


def test_verbose_component_uses_generated_definitions() -> None:
    payload = verbose_schema_document("NodeUse")

    assert payload["$schema"] == Draft202012Validator.META_SCHEMA["$id"]
    assert payload["$ref"] == "#/$defs/NodeUse"
    assert "InputPathBinding" in payload["$defs"]
