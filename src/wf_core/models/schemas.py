from __future__ import annotations

from collections.abc import Iterator, Mapping
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
        return StatePath._serialize(path)

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
    """Workflow state JSON Schema plus reducer extension keywords.

    Canonical state schemas are ordinary JSON Schema objects. Field-level
    workflow metadata such as ``reducer`` and ``trace`` lives beside JSON Schema
    keywords inside ``properties`` entries, where JSON Schema validators will
    ignore it and wf_core can compile it into runtime behavior.

    Deprecated ``fields`` inputs are still accepted at parse time and normalized
    into ``properties`` so persisted dumps stay JSON-Schema-shaped.
    """

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    type: str | list[str] | None = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)

    @classmethod
    def from_field_map(cls, fields: Mapping[str, StateField]) -> StateSchema:
        """Build from the deprecated dict shape at typed Python call sites."""
        return cls.model_validate({"fields": fields})

    @property
    def fields(self) -> list[StateFieldDecl]:
        """Return the compiled field declarations for compatibility callers."""
        return list(self.field_index().values())

    def field_index(self) -> dict[StatePath, StateFieldDecl]:
        """Return reducer-aware declarations keyed by exact typed state path."""
        root_schema = self.model_dump(mode="json", exclude_none=True)
        return {
            path: field
            for path, field in _iter_state_field_declarations(
                self.properties,
                root_schema,
                prefix=(),
            )
        }

    def field_map(self) -> dict[str, StateFieldDecl]:
        """Return reducer-aware declarations keyed by rootless dotted path."""
        return {
            ".".join(path.parts): field for path, field in self.field_index().items()
        }

    def root_fields(self) -> set[str]:
        """Return declared top-level state field names."""
        return set(self.properties)

    @model_serializer(mode="wrap")
    def _serialize_without_none_fields(self, handler: Any) -> dict[str, Any]:
        """Persist state schemas as JSON Schema objects without null keywords."""
        data = handler(self)
        return {key: value for key, value in data.items() if value is not None}

    @model_validator(mode="before")
    @classmethod
    def _coerce_deprecated_fields(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value

        data = dict(value)
        fields = data.pop("fields", None)
        if fields is None:
            return data

        if isinstance(fields, list):
            for raw_field in fields:
                field = StateFieldDecl.model_validate(raw_field)
                _set_state_property_schema(
                    data,
                    field.path.parts,
                    _property_schema_from_field(field),
                )
            return data

        if not isinstance(fields, Mapping):
            raise ValueError("state_schema.fields must be a mapping or list")

        for raw_path, raw_field in fields.items():
            if isinstance(raw_field, BaseModel):
                field_data = raw_field.model_dump(mode="python")
            elif isinstance(raw_field, Mapping):
                field_data = dict(raw_field)
            else:
                raise ValueError(
                    "legacy state field map entries must include 'type'; "
                    "use canonical list form for non-legacy declarations"
                )

            path = str(raw_path)
            if not path.startswith("state."):
                path = f"state.{path}"
            field_data["path"] = path
            field = StateFieldDecl.model_validate(field_data)
            _set_state_property_schema(
                data,
                field.path.parts,
                _property_schema_from_field(field),
            )
        return data

    @model_validator(mode="after")
    def _validate_state_json_schema_and_extensions(self) -> StateSchema:
        schema = self.model_dump(mode="json", exclude_none=True)
        validator_cls = (
            validators.validator_for(schema)
            if "$schema" in schema
            else Draft202012Validator
        )
        try:
            validator_cls.check_schema(schema)
        except SchemaError as exc:
            raise ValueError(f"invalid JSON Schema: {exc.message}") from exc

        # JSON Schema permits custom keywords, so wf_core validates reducer
        # metadata separately instead of relying on jsonschema to reject it.
        for path, property_schema in _iter_property_schemas(
            self.properties,
            schema,
        ):
            _validate_state_field_extensions(path, property_schema)
        return self


def _iter_state_field_declarations(
    properties: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    *,
    prefix: tuple[str, ...],
) -> Iterator[tuple[StatePath, StateFieldDecl]]:
    for name, property_schema in properties.items():
        if not isinstance(property_schema, Mapping):
            continue
        path = StatePath((*prefix, name))
        display_path = ".".join(path.parts)
        resolved_schema = _resolve_local_ref(property_schema, root_schema)
        reducer = _reducer_from_property(display_path, property_schema)
        trace = property_schema.get("trace", True)
        default = property_schema.get("default")
        if not isinstance(trace, bool):
            raise ValueError(
                f"invalid trace for state field {display_path!r}: expected bool"
            )
        validation_schema = {
            key: value
            for key, value in resolved_schema.items()
            if key not in {"reducer", "trace"}
        }
        _attach_root_schema_context(validation_schema, root_schema)
        yield (
            path,
            StateFieldDecl.model_validate(
                {
                    "path": path,
                    "schema": SchemaRef.model_validate(validation_schema),
                    "reducer": reducer,
                    "trace": trace,
                    "default": default,
                }
            ),
        )
        child_properties = resolved_schema.get("properties")
        if isinstance(child_properties, Mapping):
            yield from _iter_state_field_declarations(
                child_properties,
                root_schema,
                prefix=path.parts,
            )


def _iter_property_schemas(
    properties: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    *,
    prefix: str = "",
) -> Iterator[tuple[str, Mapping[str, Any]]]:
    for name, property_schema in properties.items():
        if not isinstance(property_schema, Mapping):
            continue
        path = f"{prefix}.{name}" if prefix else name
        yield path, property_schema
        resolved_schema = _resolve_local_ref(property_schema, root_schema)
        child_properties = resolved_schema.get("properties")
        if isinstance(child_properties, Mapping):
            yield from _iter_property_schemas(
                child_properties,
                root_schema,
                prefix=path,
            )


def _validate_state_field_extensions(
    path: str,
    property_schema: Mapping[str, Any],
) -> None:
    _reducer_from_property(path, property_schema)
    trace = property_schema.get("trace", True)
    if not isinstance(trace, bool):
        raise ValueError(f"invalid trace for state field {path!r}: expected bool")


def _reducer_from_property(
    path: str,
    property_schema: Mapping[str, Any],
) -> ReducerRef:
    reducer = property_schema.get("reducer", "wf.std.replace")
    try:
        if isinstance(reducer, str):
            return ReducerRef(name=reducer)
        if isinstance(reducer, Mapping):
            return ReducerRef.model_validate(reducer)
    except ValueError as exc:
        raise ValueError(f"invalid reducer for state field {path!r}: {exc}") from exc
    raise ValueError(
        f"invalid reducer for state field {path!r}: expected string or object"
    )


def _property_schema_from_field(field: StateFieldDecl) -> dict[str, Any]:
    schema = field.validation_schema.model_dump(mode="json", exclude_none=True)
    schema["reducer"] = _dump_reducer_keyword(field.reducer)
    if not field.trace:
        schema["trace"] = False
    if field.default is not None:
        schema["default"] = field.default
    return schema


def _dump_reducer_keyword(reducer: ReducerRef) -> str | dict[str, Any]:
    if not reducer.config:
        return reducer.name
    return reducer.model_dump(mode="json")


def _set_state_property_schema(
    data: dict[str, Any],
    path_parts: tuple[str, ...],
    property_schema: dict[str, Any],
) -> None:
    data.setdefault("type", "object")
    properties = data.setdefault("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("state_schema.properties must be an object")

    current_properties = properties
    for part in path_parts[:-1]:
        current = current_properties.setdefault(
            part,
            {"type": "object", "properties": {}},
        )
        if not isinstance(current, dict):
            raise ValueError(f"state field path {'.'.join(path_parts)!r} overlaps")
        current.setdefault("type", "object")
        next_properties = current.setdefault("properties", {})
        if not isinstance(next_properties, dict):
            raise ValueError(f"state field path {'.'.join(path_parts)!r} overlaps")
        current_properties = next_properties

    leaf = path_parts[-1]
    if leaf in current_properties:
        raise ValueError(f"duplicate state field path {'.'.join(path_parts)!r}")
    current_properties[leaf] = property_schema


def _resolve_local_ref(
    property_schema: Mapping[str, Any],
    root_schema: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Resolve the common Pydantic ``#/$defs/...`` case for internal indexes."""
    ref = property_schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return property_schema
    definitions = root_schema.get("$defs")
    if not isinstance(definitions, Mapping):
        return property_schema
    resolved = definitions.get(ref.removeprefix("#/$defs/"))
    return resolved if isinstance(resolved, Mapping) else property_schema


def _attach_root_schema_context(
    field_schema: dict[str, Any],
    root_schema: Mapping[str, Any],
) -> None:
    """Keep local JSON Schema refs valid after extracting one state field.

    Runtime state writes validate one declared state path at a time. If a field
    schema contains a Pydantic-style local ref such as ``#/$defs/Thing``, the
    extracted subschema still needs the root ``$defs`` table to resolve it.
    """
    definitions = root_schema.get("$defs")
    if isinstance(definitions, Mapping):
        field_schema.setdefault("$defs", dict(definitions))
    schema_dialect = root_schema.get("$schema")
    if isinstance(schema_dialect, str):
        field_schema.setdefault("$schema", schema_dialect)


class NodeDef(BaseModel):
    """Reusable node contract referenced by one or more node uses."""

    name: str
    input_schema: SchemaRef
    output_schema: SchemaRef
    outcomes: list[str] = Field(min_length=1)
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
