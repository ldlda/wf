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


def test_pydantic_accepts_path_strings_and_serializes_structural_json() -> None:
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
    assert dumped["source"] == {"root": "input", "parts": ["user"]}
    assert dumped["target"] == {"root": "state", "parts": ["person"]}
    assert dumped["local"] == {"root": "local", "parts": ["user"]}

    python_dumped = payload.model_dump()
    assert python_dumped["source"] == {"root": "input", "parts": ["user"]}
    assert python_dumped["target"] == {"root": "state", "parts": ["person"]}
    assert python_dumped["local"] == {"root": "local", "parts": ["user"]}


def test_path_json_schema_advertises_structural_shape() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    schema = Payload.model_json_schema()

    assert schema["properties"]["source"]["type"] == "object"
    assert schema["properties"]["source"]["properties"]["root"]["enum"] == [
        "context",
        "input",
        "state",
    ]
    assert schema["properties"]["target"]["properties"]["root"]["const"] == "state"
    assert schema["properties"]["local"]["properties"]["root"]["const"] == "local"


def test_condition_path_operand_serializes_path_as_structural_json() -> None:
    operand = PathOperand.model_validate({"path": "state.x"})

    assert operand.model_dump()["path"] == {"root": "state", "parts": ["x"]}
    assert operand.model_dump(mode="json")["path"] == {
        "root": "state",
        "parts": ["x"],
    }


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
