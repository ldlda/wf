from __future__ import annotations

import pytest

from wf_api.schema_projection import (
    project_output_property_to_state_schema,
    project_property_to_schema_path,
    project_schema_path_to_schema_path,
    schema_fragment_at_path,
    schema_path_exists,
    validate_json_value_at_schema_path,
)


def test_project_output_property_copies_schema_and_defs() -> None:
    state_schema = {
        "type": "object",
        "properties": {"before": {"type": "object"}},
    }
    output_schema = {
        "type": "object",
        "properties": {
            "after": {"$ref": "#/$defs/Snapshot"},
        },
        "$defs": {
            "Snapshot": {
                "type": "object",
                "properties": {"clicked": {"type": "boolean"}},
                "required": ["clicked"],
            }
        },
    }

    projected = project_output_property_to_state_schema(
        state_schema=state_schema,
        output_schema=output_schema,
        output_field="after",
        state_field="after",
    )

    assert projected["properties"]["before"] == {"type": "object"}
    assert projected["properties"]["after"] == {"$ref": "#/$defs/Snapshot"}
    assert projected["$defs"]["Snapshot"]["properties"]["clicked"] == {
        "type": "boolean"
    }
    assert "after" not in state_schema["properties"]


def test_project_output_property_rejects_missing_output_field() -> None:
    with pytest.raises(ValueError, match="output field 'after'"):
        project_output_property_to_state_schema(
            state_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            output_field="after",
            state_field="after",
        )


def test_project_output_property_rejects_conflicting_defs() -> None:
    with pytest.raises(ValueError, match=r"conflicting \$defs.Snapshot"):
        project_output_property_to_state_schema(
            state_schema={
                "type": "object",
                "properties": {},
                "$defs": {"Snapshot": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"after": {"$ref": "#/$defs/Snapshot"}},
                "$defs": {"Snapshot": {"type": "object"}},
            },
            output_field="after",
            state_field="after",
        )


def test_project_output_property_rejects_non_object_state_schema() -> None:
    with pytest.raises(ValueError, match="state_schema must be an object schema"):
        project_output_property_to_state_schema(
            state_schema={"type": "array", "items": {"type": "string"}},
            output_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            output_field="after",
            state_field="after",
        )


def test_project_output_property_rejects_existing_state_field() -> None:
    with pytest.raises(ValueError, match="state field 'after' already exists"):
        project_output_property_to_state_schema(
            state_schema={
                "type": "object",
                "properties": {"after": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            output_field="after",
            state_field="after",
        )


def test_project_output_property_allows_equivalent_existing_state_field() -> None:
    state_schema = {
        "type": "object",
        "properties": {"after": {"type": "object"}},
    }

    projected = project_output_property_to_state_schema(
        state_schema=state_schema,
        output_schema={
            "type": "object",
            "properties": {"after": {"type": "object"}},
        },
        output_field="after",
        state_field="after",
        allow_existing_equivalent=True,
    )

    assert projected == state_schema


def test_project_output_property_rejects_invalid_output_schema() -> None:
    with pytest.raises(ValueError, match="output_schema is not valid JSON Schema"):
        project_output_property_to_state_schema(
            state_schema={"type": "object", "properties": {}},
            output_schema={
                "type": "object",
                "properties": {"after": {"type": "definitely-not-jsonschema"}},
            },
            output_field="after",
            state_field="after",
        )


def test_project_schema_property_inserts_nested_path_and_defs() -> None:
    projected = project_property_to_schema_path(
        target_schema={"type": "object", "properties": {}},
        source_schema={
            "type": "object",
            "properties": {"after": {"$ref": "#/$defs/Snapshot"}},
            "$defs": {
                "Snapshot": {
                    "type": "object",
                    "properties": {"clicked": {"type": "boolean"}},
                }
            },
        },
        source_field="after",
        target_parts=("session", "after"),
    )

    assert projected["properties"]["session"]["type"] == "object"
    assert projected["properties"]["session"]["properties"]["after"] == {
        "$ref": "#/$defs/Snapshot"
    }
    assert projected["$defs"]["Snapshot"]["properties"]["clicked"] == {
        "type": "boolean"
    }


def test_project_schema_property_rejects_existing_nested_target() -> None:
    with pytest.raises(ValueError, match="schema path 'session.after' already exists"):
        project_property_to_schema_path(
            target_schema={
                "type": "object",
                "properties": {
                    "session": {
                        "type": "object",
                        "properties": {"after": {"type": "string"}},
                    }
                },
            },
            source_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            source_field="after",
            target_parts=("session", "after"),
        )


def test_project_schema_property_rejects_non_object_ancestor() -> None:
    with pytest.raises(ValueError, match="schema path 'session' is not an object"):
        project_property_to_schema_path(
            target_schema={
                "type": "object",
                "properties": {"session": {"type": "string"}},
            },
            source_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            source_field="after",
            target_parts=("session", "after"),
        )


def test_project_schema_path_copies_inline_nested_source() -> None:
    projected = project_schema_path_to_schema_path(
        target_schema={"type": "object", "properties": {}},
        source_schema={
            "type": "object",
            "properties": {
                "report": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                }
            },
        },
        source_parts=("report", "title"),
        target_parts=("document", "title"),
    )

    assert projected["properties"]["document"]["properties"]["title"] == {
        "type": "string"
    }


def test_schema_fragment_selects_inline_nested_field() -> None:
    fragment = schema_fragment_at_path(
        {
            "type": "object",
            "properties": {
                "request": {
                    "type": "object",
                    "properties": {"format": {"type": "string"}},
                }
            },
        },
        ("request", "format"),
    )

    assert fragment == {"type": "string"}


def test_schema_fragment_preserves_defs_for_selected_reference() -> None:
    fragment = schema_fragment_at_path(
        {
            "type": "object",
            "properties": {"request": {"$ref": "#/$defs/Request"}},
            "$defs": {
                "Request": {
                    "type": "object",
                    "properties": {"format": {"type": "string"}},
                }
            },
        },
        ("request",),
        label="capability input schema",
    )

    assert fragment["$ref"] == "#/$defs/Request"
    assert fragment["$defs"]["Request"]["properties"]["format"] == {"type": "string"}


def test_schema_fragment_accepts_whole_schema() -> None:
    schema = {"type": "object", "properties": {"title": {"type": "string"}}}

    assert schema_fragment_at_path(schema, ()) == schema


def test_schema_fragment_rejects_remote_selected_reference() -> None:
    with pytest.raises(
        ValueError,
        match="unsupported reference 'https://example.com/request.json'",
    ):
        schema_fragment_at_path(
            {
                "type": "object",
                "properties": {"request": {"$ref": "https://example.com/request.json"}},
            },
            ("request",),
        )


@pytest.mark.parametrize(
    ("schema", "value"),
    [
        ({"type": "string"}, "markdown"),
        (
            {
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
            {"title": "Report"},
        ),
        ({"type": "array", "items": {"type": "integer"}}, [1, 2]),
        ({"type": ["string", "null"]}, None),
    ],
)
def test_validate_json_value_accepts_matching_literals(
    schema: dict[str, object],
    value: object,
) -> None:
    validate_json_value_at_schema_path(
        schema={
            "type": "object",
            "properties": {"value": schema},
        },
        parts=("value",),
        value=value,
        label="bindings[0].value",
    )


def test_validate_json_value_at_nested_schema_path() -> None:
    schema = {
        "type": "object",
        "properties": {"request": {"$ref": "#/$defs/Request"}},
        "$defs": {
            "Request": {
                "type": "object",
                "properties": {"format": {"enum": ["markdown", "json"]}},
            }
        },
    }

    validate_json_value_at_schema_path(
        schema=schema,
        parts=("request", "format"),
        value="markdown",
        label="bindings[0].value",
    )

    with pytest.raises(
        ValueError,
        match=r"bindings\[0\]\.value does not satisfy schema at 'request.format'",
    ):
        validate_json_value_at_schema_path(
            schema=schema,
            parts=("request", "format"),
            value="html",
            label="bindings[0].value",
        )


def test_validate_json_value_uses_caller_schema_label() -> None:
    with pytest.raises(ValueError, match="workflow output schema"):
        validate_json_value_at_schema_path(
            schema={
                "type": "object",
                "properties": {"format": {"type": "string"}},
            },
            parts=("missing",),
            value="markdown",
            label="bindings[0].value",
            schema_label="workflow output schema",
        )


@pytest.mark.parametrize(
    ("schema", "value"),
    [
        ({"type": "string"}, 7),
        ({"type": "object"}, []),
        ({"type": "array"}, {}),
        ({"type": "null"}, "not-null"),
    ],
)
def test_validate_json_value_rejects_non_matching_literals(
    schema: dict[str, object],
    value: object,
) -> None:
    with pytest.raises(
        ValueError,
        match=r"bindings\[0\]\.value does not satisfy schema at 'value'",
    ):
        validate_json_value_at_schema_path(
            schema={
                "type": "object",
                "properties": {"value": schema},
            },
            parts=("value",),
            value=value,
            label="bindings[0].value",
        )


def test_project_schema_path_accepts_whole_source_schema() -> None:
    projected = project_schema_path_to_schema_path(
        target_schema={"type": "object", "properties": {}},
        source_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
        source_parts=(),
        target_parts=("payload",),
    )

    assert projected["properties"]["payload"]["required"] == ["title"]


def test_project_schema_path_traverses_pydantic_defs_reference() -> None:
    projected = project_schema_path_to_schema_path(
        target_schema={"type": "object", "properties": {}},
        source_schema={
            "type": "object",
            "properties": {"report": {"$ref": "#/$defs/Report"}},
            "$defs": {
                "Report": {
                    "type": "object",
                    "properties": {"markdown": {"$ref": "#/$defs/Markdown"}},
                },
                "Markdown": {"type": "string", "minLength": 1},
            },
        },
        source_parts=("report", "markdown"),
        target_parts=("report", "markdown"),
    )

    assert projected["properties"]["report"]["properties"]["markdown"] == {
        "$ref": "#/$defs/Markdown"
    }
    assert projected["$defs"]["Markdown"]["minLength"] == 1


def test_project_schema_path_traverses_legacy_definitions_reference() -> None:
    projected = project_schema_path_to_schema_path(
        target_schema={"type": "object", "properties": {}},
        source_schema={
            "type": "object",
            "properties": {"report": {"$ref": "#/definitions/Report"}},
            "definitions": {
                "Report": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                }
            },
        },
        source_parts=("report", "title"),
        target_parts=("title",),
    )

    assert projected["properties"]["title"] == {"type": "string"}
    assert "Report" in projected["definitions"]


def test_project_schema_path_traverses_target_defs_reference() -> None:
    projected = project_schema_path_to_schema_path(
        target_schema={
            "type": "object",
            "properties": {"report": {"$ref": "#/$defs/Report"}},
            "$defs": {
                "Report": {
                    "type": "object",
                    "properties": {},
                }
            },
        },
        source_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}},
        },
        source_parts=("title",),
        target_parts=("report", "title"),
    )

    assert projected["properties"]["report"] == {"$ref": "#/$defs/Report"}
    assert projected["$defs"]["Report"]["properties"]["title"] == {"type": "string"}


def test_schema_path_exists_follows_local_defs() -> None:
    schema = {
        "type": "object",
        "properties": {"report": {"$ref": "#/$defs/Report"}},
        "$defs": {
            "Report": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
            }
        },
    }

    assert schema_path_exists(schema, ("report", "title")) is True
    assert schema_path_exists(schema, ("report", "missing")) is False


def test_project_schema_path_rejects_unresolved_equivalent_target_reference() -> None:
    with pytest.raises(
        ValueError,
        match=r"unresolved reference '#/\$defs/Report'",
    ):
        project_schema_path_to_schema_path(
            target_schema={
                "type": "object",
                "properties": {"report": {"$ref": "#/$defs/Report"}},
            },
            source_schema={
                "type": "object",
                "properties": {"report": {"$ref": "#/$defs/Report"}},
                "$defs": {"Report": {"type": "object", "properties": {}}},
            },
            source_parts=("report",),
            target_parts=("report",),
            allow_existing_equivalent=True,
        )


def test_project_schema_path_rejects_missing_nested_source() -> None:
    with pytest.raises(
        ValueError,
        match="source schema path 'report.missing' is not declared",
    ):
        project_schema_path_to_schema_path(
            target_schema={"type": "object", "properties": {}},
            source_schema={
                "type": "object",
                "properties": {"report": {"type": "object", "properties": {}}},
            },
            source_parts=("report", "missing"),
            target_parts=("value",),
        )


def test_project_schema_path_rejects_scalar_source_ancestor() -> None:
    with pytest.raises(
        ValueError,
        match="source schema path 'report' is not an object",
    ):
        project_schema_path_to_schema_path(
            target_schema={"type": "object", "properties": {}},
            source_schema={
                "type": "object",
                "properties": {"report": {"type": "string"}},
            },
            source_parts=("report", "title"),
            target_parts=("title",),
        )


def test_project_schema_path_rejects_remote_reference() -> None:
    with pytest.raises(
        ValueError,
        match="unsupported reference 'https://example.com/report.json'",
    ):
        project_schema_path_to_schema_path(
            target_schema={"type": "object", "properties": {}},
            source_schema={
                "type": "object",
                "properties": {"report": {"$ref": "https://example.com/report.json"}},
            },
            source_parts=("report", "title"),
            target_parts=("title",),
        )


def test_project_schema_path_rejects_remote_reference_at_selected_leaf() -> None:
    with pytest.raises(
        ValueError,
        match="unsupported reference 'https://example.com/report.json'",
    ):
        project_schema_path_to_schema_path(
            target_schema={"type": "object", "properties": {}},
            source_schema={
                "type": "object",
                "properties": {"report": {"$ref": "https://example.com/report.json"}},
            },
            source_parts=("report",),
            target_parts=("report",),
        )
