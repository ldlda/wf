from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from wf_core.models.conditions import PathOperand
from wf_core.paths import (
    GraphSourcePath,
    LocalPath,
    PathResolutionError,
    StatePath,
    is_valid_destination_path,
    is_valid_source_path,
    path_parts_overlap,
    set_nested_value,
)


def test_graph_source_path_accepts_root_and_nested_paths() -> None:
    assert str(GraphSourcePath.parse("state")) == "state"
    assert str(GraphSourcePath.parse("input")) == "input"
    assert str(GraphSourcePath.parse("context")) == "context"
    assert str(GraphSourcePath.parse("input.user")) == "input.user"
    assert str(GraphSourcePath.parse("state.person.name")) == "state.person.name"
    assert str(GraphSourcePath.context("loop_item")) == "context.loop_item"


def test_structural_path_parts_preserve_literal_field_names() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    payload = Payload.model_validate(
        {
            "source": {"root": "input", "parts": ["user.name"]},
            "target": {"root": "state", "parts": ["person name"]},
            "local": {"root": "local", "parts": ["payload.text"]},
        }
    )

    assert payload.source == GraphSourcePath("input", ("user.name",))
    assert payload.target == StatePath(("person name",))
    assert payload.local == LocalPath(("payload.text",))


def test_state_path_serializes_with_state_prefix() -> None:
    assert str(StatePath.of("person.name")) == "state.person.name"
    assert str(StatePath.parse("state.person.name")) == "state.person.name"


def test_state_path_rejects_bare_state_write_target() -> None:
    with pytest.raises(PathResolutionError, match="state path"):
        StatePath.parse("state")


def test_local_path_supports_root_marker_and_fragments() -> None:
    assert str(LocalPath.root()) == "."
    assert str(LocalPath.of("user.name")) == "user.name"
    assert str(LocalPath.of("user", "name")) == "user.name"
    assert LocalPath.parse(".") == LocalPath.root()


@pytest.mark.parametrize(
    "raw",
    [
        "",
        ".",
        "state.",
        "state..name",
        "output.foo",
    ],
)
def test_graph_source_paths_reject_invalid_segments(raw: str) -> None:
    with pytest.raises(PathResolutionError):
        GraphSourcePath.parse(raw)


@pytest.mark.parametrize(
    "factory",
    [
        LocalPath.parse,
        StatePath.parse,
        GraphSourcePath.parse,
    ],
)
@pytest.mark.parametrize(
    "raw",
    [
        "state.",
        "state..name",
    ],
)
def test_all_path_types_reject_invalid_segments(factory, raw: str) -> None:
    with pytest.raises(PathResolutionError):
        factory(raw)


def test_path_objects_are_immutable_and_hashable() -> None:
    paths = {StatePath.of("person.name"), StatePath.of("person.name")}
    assert len(paths) == 1

    with pytest.raises(Exception):
        StatePath.of("person.name").parts = ("other",)  # type: ignore[misc, ty:invalid-assignment]


@pytest.mark.parametrize(
    ("factory", "args"),
    [
        (GraphSourcePath, ("output", ("user",))),
        (StatePath, (("",),)),
        (LocalPath, ((" ",),)),
    ],
)
def test_direct_constructors_enforce_path_invariants(
    factory, args: tuple[object, ...]
) -> None:
    with pytest.raises(PathResolutionError):
        factory(*args)


def test_pydantic_revalidates_existing_path_objects() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    # Bypass constructors to simulate stale or malicious objects that predate
    # constructor validation. Pydantic must not blindly trust existing instances.
    source = object.__new__(GraphSourcePath)
    object.__setattr__(source, "root", "output")
    object.__setattr__(source, "parts", ("user",))
    target = object.__new__(StatePath)
    object.__setattr__(target, "parts", ("",))
    local = object.__new__(LocalPath)
    object.__setattr__(local, "parts", (" ",))

    with pytest.raises(ValidationError):
        Payload.model_validate(
            {
                "source": source,
                "target": StatePath.of("person"),
                "local": LocalPath.root(),
            }
        )
    with pytest.raises(ValidationError):
        Payload.model_validate(
            {
                "source": GraphSourcePath.input("user"),
                "target": target,
                "local": LocalPath.root(),
            }
        )
    with pytest.raises(ValidationError):
        Payload.model_validate(
            {
                "source": GraphSourcePath.input("user"),
                "target": StatePath.of("person"),
                "local": local,
            }
        )


def test_pydantic_accepts_path_strings_and_serializes_path_strings() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    payload = Payload.model_validate(
        {
            "source": "input.user",
            "target": "state.person",
            "local": "user",
        }
    )

    assert payload.source == GraphSourcePath.input("user")
    assert payload.target == StatePath.of("person")
    assert payload.local == LocalPath.of("user")

    dumped = payload.model_dump(mode="json")
    assert dumped["source"] == "input.user"
    assert dumped["target"] == "state.person"
    assert dumped["local"] == "user"

    python_dumped = payload.model_dump()
    assert python_dumped["source"] == "input.user"
    assert python_dumped["target"] == "state.person"
    assert python_dumped["local"] == "user"


def test_path_json_schema_advertises_strings_and_structural_objects() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    schema = Payload.model_json_schema()

    assert schema["properties"]["source"]["oneOf"][0]["type"] == "string"
    assert schema["properties"]["source"]["oneOf"][1]["properties"]["root"]["enum"] == [
        "input",
        "state",
        "context",
    ]
    assert schema["properties"]["target"]["oneOf"][0]["type"] == "string"
    assert (
        schema["properties"]["target"]["oneOf"][1]["properties"]["root"]["const"]
        == "state"
    )
    assert schema["properties"]["local"]["oneOf"][0]["type"] == "string"
    assert (
        schema["properties"]["local"]["oneOf"][1]["properties"]["root"]["const"]
        == "local"
    )


def test_condition_path_operand_serializes_path_as_string() -> None:
    operand = PathOperand.model_validate({"path": "state.x"})

    assert operand.model_dump()["path"] == "state.x"
    assert operand.model_dump(mode="json")["path"] == "state.x"


def test_pydantic_accepts_existing_path_objects() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    payload = Payload.model_validate(
        {
            "source": GraphSourcePath.state("person"),
            "target": StatePath.of("person.name"),
            "local": LocalPath.root(),
        }
    )

    assert str(payload.source) == "state.person"
    assert str(payload.target) == "state.person.name"
    assert str(payload.local) == "."


def test_pydantic_rejects_bad_path_string() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath

    with pytest.raises(ValidationError):
        Payload.model_validate({"source": "output.foo"})


def test_existing_source_and_destination_validation_helpers_use_new_parsers() -> None:
    assert is_valid_source_path("state", set(), set()) is True
    assert is_valid_source_path("input", set(), set()) is True
    assert is_valid_source_path("context", set(), set(), allow_context=True) is True
    assert is_valid_source_path("state.person", {"person"}, set()) is True
    assert is_valid_source_path("input.person", set(), {"person"}) is True
    assert is_valid_source_path("state.person-name", {"person-name"}, set()) is True

    assert is_valid_destination_path("state") is False
    assert is_valid_destination_path("state.person") is True
    assert is_valid_destination_path("input.person") is False


def test_set_nested_value_rejects_empty_path() -> None:
    with pytest.raises(PathResolutionError, match="empty path"):
        set_nested_value({}, [], "value")


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (("person",), ("person", "name"), True),
        (("person", "name"), ("person",), True),
        (("person", "name"), ("person", "email"), False),
        (("person",), ("job",), False),
        ((), ("person",), True),
    ],
)
def test_path_parts_overlap_detects_equality_and_ancestry(
    left: tuple[str, ...],
    right: tuple[str, ...],
    expected: bool,
) -> None:
    assert path_parts_overlap(left, right) is expected


def test_toml_path_strings_round_trip_literal_segments() -> None:
    source = GraphSourcePath.parse('input."customer.name"."display name"')
    target = StatePath.parse('state."report.title"')
    local = LocalPath.parse('payload."raw.value"')

    assert source.parts == ("customer.name", "display name")
    assert target.parts == ("report.title",)
    assert local.parts == ("payload", "raw.value")
    assert str(source) == 'input."customer.name"."display name"'
    assert str(target) == 'state."report.title"'
    assert str(local) == 'payload."raw.value"'


def test_toml_path_strings_bare_keys_round_trip() -> None:
    source = GraphSourcePath.parse("input.user.name")
    assert source.parts == ("user", "name")
    assert str(source) == "input.user.name"


def test_local_path_parse_root_marker() -> None:
    local = LocalPath.parse(".")
    assert local.parts == ()
    assert str(local) == "."


def test_toml_path_strings_reject_malformed_toml() -> None:
    with pytest.raises(PathResolutionError, match="invalid TOML path"):
        GraphSourcePath.parse('input."unclosed')


@pytest.mark.parametrize("raw", ["[input]\nname", "[input.user]\nname"])
def test_toml_path_strings_reject_document_table_syntax(raw: str) -> None:
    with pytest.raises(PathResolutionError, match="invalid TOML path"):
        GraphSourcePath.parse(raw)


def test_toml_path_strings_reject_inline_table_breakout_syntax() -> None:
    with pytest.raises(PathResolutionError, match="invalid TOML path"):
        LocalPath.parse("uhh = 1}\nfoo={bar")


def test_toml_path_strings_reject_control_characters_in_segments() -> None:
    with pytest.raises(PathResolutionError, match="control characters"):
        LocalPath.parse('"uhh = 1}\\nfoo={bar"')


def test_toml_path_strings_allow_brackets_inside_quoted_segments() -> None:
    assert GraphSourcePath.parse('input."[name]"') == GraphSourcePath(
        "input", ("[name]",)
    )


def test_toml_path_strings_reject_invalid_root() -> None:
    with pytest.raises(PathResolutionError, match="unknown path root"):
        GraphSourcePath.parse('output."foo"')


def test_state_path_rejects_bare_state_without_segments() -> None:
    with pytest.raises(PathResolutionError, match="state path"):
        StatePath.parse("state")


def test_path_models_serialize_strings_but_accept_structural_compat() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    payload = Payload.model_validate(
        {
            "source": {"root": "input", "parts": ["user.name"]},
            "target": {"root": "state", "parts": ["person name"]},
            "local": {"root": "local", "parts": ["payload.text"]},
        }
    )

    assert payload.model_dump(mode="json") == {
        "source": 'input."user.name"',
        "target": 'state."person name"',
        "local": '"payload.text"',
    }
    assert (
        Payload.model_json_schema()["properties"]["source"]["oneOf"][0]["type"]
        == "string"
    )


def test_json_encoded_structural_path_string_is_invalid() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath

    with pytest.raises(ValidationError, match="invalid TOML path"):
        Payload.model_validate({"source": '{"root":"input","parts":["button_label"]}'})
