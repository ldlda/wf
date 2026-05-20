from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator, SchemaError, validators
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from wf_core.models.reducers import ReducerRef
from wf_core.paths import StatePath


class SchemaRef(BaseModel):
    """JSON Schema object used at workflow and node boundaries."""

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    type: str | list[str] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _serialize_without_none_fields(self, handler: Any) -> dict[str, Any]:
        """Persist JSON Schema objects without null-valued optional keywords."""
        data = handler(self)
        return {key: value for key, value in data.items() if value is not None}

    @model_validator(mode="before")
    @classmethod
    def _validate_json_schema_definition(cls, value: object) -> object:
        if isinstance(value, SchemaRef):
            schema = value.model_dump(mode="json", exclude_none=True)
        elif isinstance(value, Mapping):
            schema = dict(value)
        else:
            return value

        validator_cls = (
            validators.validator_for(schema)
            if "$schema" in schema
            else Draft202012Validator
        )
        try:
            validator_cls.check_schema(schema)
        except SchemaError as exc:
            raise ValueError(f"invalid JSON Schema: {exc.message}") from exc
        return value


class StateField(BaseModel):
    """Declared state path plus its runtime merge behavior."""

    type: str
    reducer: ReducerRef = Field(
        default_factory=lambda: ReducerRef(name="wf.std.replace")
    )
    trace: bool = True
    default: Any = None

    @field_validator("reducer", mode="before")
    @classmethod
    def _coerce_reducer(cls, value: object) -> object:
        if isinstance(value, str):
            return {"name": value}
        return value


class StateFieldDecl(BaseModel):
    """One declared state path plus validation and reducer metadata."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    path: StatePath
    validation_schema: SchemaRef = Field(
        default_factory=lambda: SchemaRef(type="object"),
        alias="schema",
        serialization_alias="schema",
    )
    reducer: ReducerRef = Field(
        default_factory=lambda: ReducerRef(name="wf.std.replace")
    )
    trace: bool = True
    default: Any = None

    @property
    def type(self) -> str | None:
        """Compatibility accessor for callers migrating from StateField.type."""
        schema_type = self.validation_schema.type
        return schema_type if isinstance(schema_type, str) else None

    @field_serializer("path")
    def _serialize_path(self, path: StatePath) -> str:
        return str(path)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_type(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value

        data = dict(value)
        if "schema" not in data and "type" in data:
            data["schema"] = {"type": data.pop("type")}
        return data

    @field_validator("reducer", mode="before")
    @classmethod
    def _coerce_reducer(cls, value: object) -> object:
        if isinstance(value, str):
            return {"name": value}
        return value


class StateSchema(BaseModel):
    """Workflow state schema with canonical list fields.

    Deprecated dict-shaped input is still accepted at parse time and normalized
    so runtime and serialization only deal with list-of-struct declarations.
    """

    model_config = ConfigDict(extra="allow")

    fields: list[StateFieldDecl] = Field(default_factory=list)

    @classmethod
    def from_field_map(cls, fields: Mapping[str, StateField]) -> StateSchema:
        """Build from the deprecated dict shape at typed Python call sites."""
        return cls.model_validate({"fields": fields})

    def field_map(self) -> dict[str, StateFieldDecl]:
        """Return declarations keyed by rootless dotted path."""
        return {".".join(field.path.parts): field for field in self.fields}

    def root_fields(self) -> set[str]:
        """Return declared top-level state field names."""
        return {field.path.parts[0] for field in self.fields}

    @model_validator(mode="before")
    @classmethod
    def _coerce_deprecated_field_map(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value

        data = dict(value)
        fields = data.get("fields")
        if not isinstance(fields, Mapping):
            return data

        normalized_fields: list[object] = []
        for raw_path, raw_field in fields.items():
            path = str(raw_path)
            if not path.startswith("state."):
                path = f"state.{path}"

            if isinstance(raw_field, BaseModel):
                field_data = raw_field.model_dump(mode="python")
            elif isinstance(raw_field, Mapping):
                field_data = dict(raw_field)
                if "schema" in field_data or "type" not in field_data:
                    raise ValueError(
                        "legacy state field map entries must include 'type'; "
                        "use canonical list form for entries with 'schema'"
                    )
            else:
                raise ValueError(
                    "legacy state field map entries must include 'type'; "
                    "use canonical list form for non-legacy declarations"
                )

            field_data["path"] = path
            normalized_fields.append(field_data)

        data["fields"] = normalized_fields
        return data

    @model_validator(mode="after")
    def _reject_duplicate_field_paths(self) -> StateSchema:
        seen: set[str] = set()
        for field in self.fields:
            key = ".".join(field.path.parts)
            if key in seen:
                raise ValueError(f"duplicate state field path {key!r}")
            seen.add(key)
        return self


class NodeDef(BaseModel):
    """Reusable node contract referenced by one or more node uses."""

    name: str
    input_schema: SchemaRef
    output_schema: SchemaRef
    outcomes: list[str] = Field(min_length=1)
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
