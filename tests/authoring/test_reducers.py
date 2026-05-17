from __future__ import annotations

from pydantic import BaseModel, Field

from wf_authoring import ReducerCatalog, reducer
from wf_core import ReducerRef


class ModuloConfig(BaseModel):
    modulus: int = Field(gt=0)


@reducer(name="wf.std.add")
def add(current: int | None, incoming: int) -> int:
    """Add incoming values into integer state."""
    return (current or 0) + incoming


@reducer(name="wf.std.modulo_add", config_model=ModuloConfig)
def modulo_add(
    current: int | None,
    incoming: int,
    config: ModuloConfig,
) -> int:
    """Add incoming values modulo a configured positive integer."""
    return ((current or 0) + incoming) % config.modulus


def test_reducer_decorator_wraps_plain_callable() -> None:
    assert add.definition.spec.name == "wf.std.add"
    assert add.definition.spec.description == "Add incoming values into integer state."

    result = add.definition.apply(
        reducer=ReducerRef(name="wf.std.add"),
        current_value=2,
        incoming_value=3,
        destination_path="state.total",
    )

    assert result == 5


def test_reducer_decorator_wraps_configured_basemodel_callable() -> None:
    schema = modulo_add.definition.spec.config_schema

    assert schema["properties"]["modulus"]["exclusiveMinimum"] == 0

    result = modulo_add.definition.apply(
        reducer=ReducerRef(name="wf.std.modulo_add", config={"modulus": 10}),
        current_value=8,
        incoming_value=5,
        destination_path="state.total",
    )

    assert result == 3


def test_reducer_catalog_exposes_definitions_and_specs() -> None:
    catalog = ReducerCatalog.from_reducers(add, modulo_add)

    assert set(catalog.definitions) == {"wf.std.add", "wf.std.modulo_add"}
    assert catalog.specs["wf.std.add"].name == "wf.std.add"
    assert catalog.specs["wf.std.modulo_add"].name == "wf.std.modulo_add"
