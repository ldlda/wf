from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wf_sources_mcp.schema_models import model_from_schema


def test_model_from_schema_maps_basic_json_schema_types() -> None:
    model = model_from_schema(
        "ToolInput",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Display name"},
                "count": {"type": "integer"},
                "ratio": {"type": "number"},
                "enabled": {"type": "boolean"},
                "metadata": {"type": "object"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "count"],
        },
    )

    payload = model.model_validate(
        {
            "name": "demo",
            "count": 2,
            "ratio": 1.5,
            "enabled": True,
            "metadata": {"a": "b"},
            "tags": ["one"],
        }
    )

    assert isinstance(payload, BaseModel)
    assert payload.model_dump(exclude_unset=True) == {
        "name": "demo",
        "count": 2,
        "ratio": 1.5,
        "enabled": True,
        "metadata": {"a": "b"},
        "tags": ["one"],
    }


def test_model_from_schema_omits_unset_optional_fields() -> None:
    model = model_from_schema(
        "OptionalInput",
        {
            "type": "object",
            "properties": {
                "required_name": {"type": "string"},
                "optional_depth": {"type": "integer"},
            },
            "required": ["required_name"],
        },
    )

    payload = model.model_validate({"required_name": "root"})

    assert payload.model_dump(exclude_unset=True) == {"required_name": "root"}


def test_model_from_schema_preserves_explicit_defaults() -> None:
    model = model_from_schema(
        "DefaultInput",
        {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "query": {"type": "string"},
            },
        },
    )

    payload = model.model_validate({})

    assert payload.model_dump() == {"limit": 10, "query": None}
    assert payload.model_dump(exclude_unset=True) == {}


def test_model_from_schema_allows_extra_fields_and_tolerates_unknown_shapes() -> None:
    model = model_from_schema(
        "LooseInput",
        {
            "type": "object",
            "properties": {
                "enum_value": {"enum": ["a", "b"]},
                "union_value": {"type": ["string", "integer"]},
                "unknown_value": {"x-custom": True},
            },
        },
    )

    payload = model.model_validate(
        {
            "enum_value": "a",
            "union_value": 123,
            "unknown_value": {"nested": True},
            "extra": "kept",
        }
    )

    dumped: dict[str, Any] = payload.model_dump(exclude_unset=True)
    assert dumped["enum_value"] == "a"
    assert dumped["union_value"] == 123
    assert dumped["unknown_value"] == {"nested": True}
    assert dumped["extra"] == "kept"


def test_model_from_schema_exports_from_package_root() -> None:
    from wf_sources_mcp import model_from_schema as root_model_from_schema
    from wf_sources_mcp.schema_models import model_from_schema

    assert root_model_from_schema is model_from_schema
