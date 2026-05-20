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
)


def test_graph_source_path_accepts_root_and_nested_paths() -> None:
    assert str(GraphSourcePath.parse("state")) == "state"
    assert str(GraphSourcePath.parse("input")) == "input"
    assert str(GraphSourcePath.parse("context")) == "context"
    assert str(GraphSourcePath.parse("input.user")) == "input.user"
    assert str(GraphSourcePath.parse("state.person.name")) == "state.person.name"
    assert str(GraphSourcePath.context("loop_item")) == "context.loop_item"


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
        "state.items.0",
        "state.user-name",
        "state.items[0]",
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
        "state.items.0",
        "state.user-name",
        "state.items[0]",
    ],
)
def test_all_path_types_reject_invalid_segments(factory, raw: str) -> None:
    with pytest.raises(PathResolutionError):
        factory(raw)


def test_path_objects_are_immutable_and_hashable() -> None:
    paths = {StatePath.of("person.name"), StatePath.of("person.name")}
    assert len(paths) == 1

    with pytest.raises(Exception):
        StatePath.of("person.name").parts = ("other",)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("factory", "args"),
    [
        (GraphSourcePath, ("output", ("user-name",))),
        (StatePath, (("0",),)),
        (LocalPath, (("items[0]",),)),
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
    object.__setattr__(source, "parts", ("user-name",))
    target = object.__new__(StatePath)
    object.__setattr__(target, "parts", ("0",))
    local = object.__new__(LocalPath)
    object.__setattr__(local, "parts", ("items[0]",))

    with pytest.raises(ValidationError):
        Payload.model_validate({
            "source": source,
            "target": StatePath.of("person"),
            "local": LocalPath.root(),
        })
    with pytest.raises(ValidationError):
        Payload.model_validate({
            "source": GraphSourcePath.input("user"),
            "target": target,
            "local": LocalPath.root(),
        })
    with pytest.raises(ValidationError):
        Payload.model_validate({
            "source": GraphSourcePath.input("user"),
            "target": StatePath.of("person"),
            "local": local,
        })


def test_pydantic_accepts_path_strings_and_serializes_strings() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    payload = Payload.model_validate({
        "source": "input.user",
        "target": "state.person",
        "local": "user",
    })

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


def test_condition_path_operand_serializes_path_as_string_in_all_dump_modes() -> None:
    operand = PathOperand.model_validate({"path": "state.x"})

    assert operand.model_dump()["path"] == "state.x"
    assert operand.model_dump(mode="json")["path"] == "state.x"


def test_pydantic_accepts_existing_path_objects() -> None:
    class Payload(BaseModel):
        source: GraphSourcePath
        target: StatePath
        local: LocalPath

    payload = Payload.model_validate({
        "source": GraphSourcePath.state("person"),
        "target": StatePath.of("person.name"),
        "local": LocalPath.root(),
    })

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
    assert is_valid_source_path("state.person-name", {"person-name"}, set()) is False

    assert is_valid_destination_path("state") is False
    assert is_valid_destination_path("state.person") is True
    assert is_valid_destination_path("input.person") is False
