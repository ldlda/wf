from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from wf_authoring import (
    NodeReturn,
    ReducerCatalog,
    WorkflowBuilder,
    node,
    output_to,
    reducer,
    state_field,
    state_path,
)
from wf_core import ReducerRef


class ModuloConfig(BaseModel):
    modulus: int = Field(gt=0)


class CounterState(BaseModel):
    total: Annotated[int, state_field(reducer="wf.std.add")] = 0


class EmptyInput(BaseModel):
    pass


class ModuloCounterState(BaseModel):
    total: int = 0


class CounterOutput(BaseModel):
    total: int


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


def test_builder_executes_with_custom_reducer_catalog() -> None:
    @node
    def emit(_: EmptyInput) -> NodeReturn[CounterOutput]:
        return NodeReturn(outcome="ok", output=CounterOutput(total=4))

    builder = WorkflowBuilder(
        name="custom_reducer",
        input_schema=EmptyInput,
        state_schema=CounterState,
        output_schema=CounterOutput,
        reducers=ReducerCatalog.from_reducers(add),
    )
    step = builder.use(
        emit,
        output=[output_to("total", state_path("total"))],
    )
    builder.set_entry_point(step)
    builder.connect(step, "ok", "__end__")

    run = builder.execute({})

    assert run.state["total"] == 4


def test_state_field_accepts_configured_reducer_reference() -> None:
    class State(BaseModel):
        total: Annotated[
            int,
            state_field(
                reducer={"name": "wf.std.modulo_add", "config": {"modulus": 10}}
            ),
        ] = 0

    field = State.model_fields["total"].metadata[0]  # pylint: disable=unsubscriptable-object

    assert field.reducer.name == "wf.std.modulo_add"
    assert field.reducer.config["modulus"] == 10
