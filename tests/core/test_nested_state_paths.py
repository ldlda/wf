from __future__ import annotations

from wf_core import (
    ReducerRef,
    ReducerSpec,
    SchemaRef,
    StateField,
    StateSchema,
    Workflow,
)
from wf_core.models.schemas import StateFieldDecl
from wf_core.paths import StatePath
from wf_core.runtime.ops.merges import ReducerDefinition, apply_reducer
from wf_core.runtime.ops.runs import create_run_state
from wf_core.runtime.ops.state import write_state_value


def test_exact_nested_state_path_uses_declared_reducer() -> None:
    workflow = _workflow(
        fields={
            "person.tags": StateField(
                reducer=ReducerRef(name="wf.std.append"), type="array"
            )
        }
    )
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["seed", "next"]


def test_state_schema_accepts_legacy_field_list_and_dumps_json_schema() -> None:
    schema = StateSchema.model_validate(
        {
            "fields": [
                {"path": "state.person", "type": "object"},
                {
                    "path": "state.person.name",
                    "type": "string",
                    "reducer": "wf.std.replace",
                },
            ]
        }
    )

    assert schema.fields[0].path == StatePath.of("person")
    assert schema.field_map()["person.name"].type == "string"
    dumped = schema.model_dump(mode="json")
    assert dumped["properties"]["person"]["properties"]["name"]["type"] == "string"
    assert "fields" not in dumped


def test_state_schema_uses_json_schema_properties_as_canonical_shape() -> None:
    schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "person": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Display name",
                            "reducer": "wf.std.replace",
                        }
                    },
                },
                "count": {"type": "integer", "reducer": "wf.std.add"},
            },
        }
    )

    fields = schema.field_map()
    assert fields["person.name"].validation_schema.type == "string"
    assert fields["person.name"].reducer == ReducerRef(name="wf.std.replace")
    assert fields["count"].reducer == ReducerRef(name="wf.std.add")


def test_state_schema_preserves_literal_dotted_property_names() -> None:
    schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "person.name": {"type": "string", "reducer": "wf.std.replace"}
            },
        }
    )

    fields = schema.field_index()

    assert set(fields) == {StatePath(("person.name",))}
    assert fields[StatePath(("person.name",))].path == StatePath(("person.name",))


def test_state_schema_field_map_keeps_display_key_for_literal_dotted_property() -> None:
    schema = StateSchema.model_validate(
        {
            "type": "object",
            "properties": {
                "person.name": {"type": "string", "reducer": "wf.std.replace"}
            },
        }
    )

    fields = schema.field_map()

    assert set(fields) == {"person.name"}
    assert fields["person.name"].path == StatePath(("person.name",))


def test_state_schema_rejects_invalid_reducer_extension_keyword() -> None:
    try:
        StateSchema.model_validate(
            {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "reducer": {"bad": True}},
                },
            }
        )
    except ValueError as exc:
        assert "invalid reducer for state field 'count'" in str(exc)
    else:
        raise AssertionError("expected invalid reducer extension keyword to fail")


def test_state_schema_accepts_canonical_schema_field() -> None:
    schema = StateSchema.model_validate(
        {
            "fields": [
                {
                    "path": "state.person.name",
                    "schema": {"type": "string", "title": "Person Name"},
                }
            ]
        }
    )

    field = schema.field_map()["person.name"]
    assert field.validation_schema.type == "string"
    assert field.validation_schema.title == "Person Name"


def test_state_schema_accepts_deprecated_dict_shape_and_dumps_list() -> None:
    schema = StateSchema.model_validate({"fields": {"person.name": {"type": "string"}}})

    dumped = schema.model_dump(mode="json")
    assert dumped["properties"]["person"]["properties"]["name"]["type"] == "string"
    assert "fields" not in dumped


def test_state_schema_accepts_deprecated_dict_value_with_schema_key() -> None:
    schema = StateSchema.model_validate(
        {
            "fields": {
                "person.name": {
                    "schema": {"type": "string", "description": "Display name"},
                }
            }
        }
    )

    assert schema.field_map()["person.name"].validation_schema.type == "string"


def test_state_schema_accepts_json_schema_field_without_type() -> None:
    schema = StateSchema.model_validate({"fields": {"person.name": {"default": "Ada"}}})

    assert schema.field_map()["person.name"].default == "Ada"


def test_state_schema_accepts_deprecated_state_prefixed_dict_keys() -> None:
    schema = StateSchema.model_validate(
        {"fields": {"state.person.name": {"type": "string"}}}
    )

    assert schema.field_map()["person.name"].path == StatePath.of("person.name")


def test_state_field_decl_model_dump_serializes_path_structurally() -> None:
    field = StateFieldDecl.model_validate(
        {
            "path": "state.person.name",
            "type": "string",
        }
    )

    assert field.model_dump()["path"] == {"root": "state", "parts": ["person", "name"]}
    assert field.model_dump(mode="json")["path"] == {
        "root": "state",
        "parts": ["person", "name"],
    }


def test_state_schema_model_dump_serializes_paths_as_strings() -> None:
    schema = StateSchema.model_validate(
        {"fields": [{"path": "state.person.name", "type": "string"}]}
    )

    dumped = schema.model_dump(mode="json")
    assert dumped["properties"]["person"]["properties"]["name"]["type"] == "string"
    assert "fields" not in dumped


def test_state_schema_rejects_duplicate_field_paths() -> None:
    try:
        StateSchema.model_validate(
            {
                "fields": [
                    {"path": "state.person.name", "type": "string"},
                    {"path": "state.person.name", "type": "string"},
                ]
            }
        )
    except ValueError as exc:
        assert "duplicate state field path 'person.name'" in str(exc)
    else:
        raise AssertionError("expected duplicate state field path to fail")


def test_exact_nested_state_path_uses_reducer_from_json_schema_property() -> None:
    workflow = _workflow_from_state_schema(
        StateSchema.model_validate(
            {
                "type": "object",
                "properties": {
                    "person": {
                        "type": "object",
                        "properties": {
                            "tags": {"type": "array", "reducer": "wf.std.append"}
                        },
                    }
                },
            }
        )
    )
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["seed", "next"]


def test_state_schema_field_map_uses_rootless_keys() -> None:
    schema = StateSchema.model_validate(
        {
            "fields": [
                {"path": "state.person.name", "type": "string"},
                {"path": "state.person.tags", "type": "array"},
            ]
        }
    )

    fields = schema.field_map()
    assert fields["person.name"].path == StatePath.of("person.name")
    assert fields["person.tags"].type == "array"


def test_create_run_state_writes_nested_defaults_by_state_path() -> None:
    workflow = _workflow(
        fields={
            "person.name": StateField(type="string", default="Ada"),
        }
    )

    run = create_run_state(workflow, {})

    assert run.state["person"]["name"] == "Ada"
    assert "person.name" not in run.state


def test_parent_state_declaration_does_not_apply_to_nested_write() -> None:
    workflow = _workflow(
        fields={
            "person": StateField(
                reducer=ReducerRef(name="wf.std.merge_object"), type="object"
            )
        }
    )
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["next"]


def test_undeclared_nested_state_path_defaults_to_replace() -> None:
    workflow = _workflow(fields={})
    state = {"person": {"tags": ["seed"]}}

    write_state_value(workflow, state, "state.person.tags", ["next"])

    assert state["person"]["tags"] == ["next"]


def test_state_field_defaults_to_replace_reducer() -> None:
    assert StateField(type="string").reducer == ReducerRef(name="wf.std.replace")


def test_state_field_accepts_string_reducer_shorthand() -> None:
    field = StateField.model_validate({"type": "array", "reducer": "wf.std.set_union"})

    assert field.reducer == ReducerRef(name="wf.std.set_union")


def test_state_field_accepts_configured_reducer_reference() -> None:
    field = StateField(
        type="integer",
        reducer=ReducerRef(name="wf.std.max", config={"sample": True}),
    )

    # PYLINT!!!! what is u on ts is so clear
    assert field.reducer.name == "wf.std.max"  # pylint: disable=no-member
    assert field.reducer.config == {"sample": True}  # pylint: disable=no-member


def test_unknown_state_reducer_fails_clearly() -> None:
    workflow = _workflow(
        fields={
            "person.tags": StateField(reducer=ReducerRef(name="x.nope"), type="array")
        }
    )
    state = {"person": {"tags": ["seed"]}}

    try:
        write_state_value(workflow, state, "state.person.tags", ["next"])
    except Exception as exc:
        assert "unknown reducer 'x.nope'" in str(exc)
    else:
        raise AssertionError("expected unknown reducer to fail")


def test_set_union_reducer_preserves_first_seen_order() -> None:
    workflow = _workflow(
        fields={
            "person.tags": StateField(
                reducer=ReducerRef(name="wf.std.set_union"), type="array"
            )
        }
    )
    state = {"person": {"tags": ["alpha", "beta"]}}

    write_state_value(workflow, state, "state.person.tags", ["beta", "gamma"])

    assert state["person"]["tags"] == ["alpha", "beta", "gamma"]


def test_unexpected_reducer_config_fails_before_state_mutation() -> None:
    workflow = _workflow(
        fields={
            "person.tags": StateField(
                type="array",
                reducer=ReducerRef(name="wf.std.set_union", config={"bad": True}),
            )
        }
    )
    state = {"person": {"tags": ["alpha"]}}

    try:
        write_state_value(workflow, state, "state.person.tags", ["beta"])
    except Exception as exc:
        assert "reducer config for 'wf.std.set_union'" in str(exc)
    else:
        raise AssertionError("expected invalid reducer config to fail")
    assert state["person"]["tags"] == ["alpha"]


def test_max_reducer_keeps_larger_value() -> None:
    workflow = _workflow(
        fields={
            "best_score": StateField(
                reducer=ReducerRef(name="wf.std.max"), type="integer"
            )
        }
    )
    state = {"best_score": 7}

    write_state_value(workflow, state, "state.best_score", 9)

    assert state["best_score"] == 9


def test_add_reducer_sums_numeric_values() -> None:
    workflow = _workflow(
        fields={
            "count": StateField(reducer=ReducerRef(name="wf.std.add"), type="integer")
        }
    )
    state = {"count": 7}

    write_state_value(workflow, state, "state.count", 5)

    assert state["count"] == 12


def test_reducer_definition_can_wrap_plain_two_arg_callable() -> None:
    definition = ReducerDefinition(
        spec=ReducerSpec(name="test.add"),
        fn=lambda current, incoming: (current or 0) + incoming,
    )

    result = apply_reducer(
        reducer=ReducerRef(name="test.add"),
        current_value=2,
        incoming_value=3,
        destination_path="state.total",
        reducers={"test.add": definition},
    )

    assert result == 5


def test_reducer_definition_can_wrap_config_aware_callable() -> None:
    definition = ReducerDefinition(
        spec=ReducerSpec(
            name="test.modulo_add",
            config_schema={
                "type": "object",
                "properties": {"modulus": {"type": "integer"}},
                "required": ["modulus"],
                "additionalProperties": False,
            },
        ),
        fn=lambda current, incoming, config: (
            ((current or 0) + incoming) % config["modulus"]
        ),
        accepts_config=True,
    )

    result = apply_reducer(
        reducer=ReducerRef(name="test.modulo_add", config={"modulus": 10}),
        current_value=8,
        incoming_value=5,
        destination_path="state.total",
        reducers={"test.modulo_add": definition},
    )

    assert result == 3


def _workflow(*, fields: dict[str, StateField]) -> Workflow:
    return _workflow_from_state_schema(StateSchema.from_field_map(fields))


def _workflow_from_state_schema(state_schema: StateSchema) -> Workflow:
    return Workflow(
        name="nested_state_paths",
        input_schema=SchemaRef(type="object", properties={}),
        state_schema=state_schema,
        output_schema=SchemaRef(type="object", properties={}),
        node_defs=[],
        start="unused",
        nodes=[],
        edges=[],
    )
