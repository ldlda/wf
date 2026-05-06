from __future__ import annotations

from pydantic import BaseModel

from wf_authoring import Nothing, build_registry, node, outcome
from wf_core import RuntimeContext


class AliasInput(BaseModel):
    value: str


class AliasOutput(BaseModel):
    value: str


def test_node_decorator_can_alias_existing_node_spec() -> None:
    @node(name="test.alias", description="Alias spec.")
    @node(name="test.original", description="Original spec.")
    def echo(input: AliasInput) -> AliasOutput:
        """Echo input."""
        return AliasOutput(value=input.value)

    registry = build_registry(echo)
    result = registry["test.alias"](
        {"value": "hello"},
        RuntimeContext(current_node_id="echo"),
    )

    assert echo.name == "test.alias"
    assert echo.description == "Alias spec."
    assert echo.input_model is AliasInput
    assert echo.output_model is AliasOutput
    assert result == {"outcome": "ok", "output": {"value": "hello"}}


def test_node_can_wrap_function_with_direct_metadata_call() -> None:
    def echo(input: AliasInput) -> AliasOutput:
        """Echo input."""
        return AliasOutput(value=input.value)

    spec = node(echo, name="test.direct_fn", description="Direct function spec.")

    assert spec.name == "test.direct_fn"
    assert spec.description == "Direct function spec."
    assert spec.input_model is AliasInput
    assert spec.output_model is AliasOutput


def test_node_can_alias_spec_with_direct_metadata_call() -> None:
    @node(name="test.original")
    def echo(input: AliasInput) -> AliasOutput:
        """Echo input."""
        return AliasOutput(value=input.value)

    alias = node(echo, name="test.direct_alias", description="Direct alias spec.")

    assert alias.name == "test.direct_alias"
    assert alias.description == "Direct alias spec."
    assert alias.fn is echo.fn
    assert alias.input_model is AliasInput
    assert alias.output_model is AliasOutput


def test_outcome_returns_nothing_output_by_default() -> None:
    result = outcome("skip")

    assert result.outcome == "skip"
    assert isinstance(result.output, Nothing)


def test_outcome_can_wrap_explicit_output() -> None:
    output = AliasOutput(value="hello")

    result = outcome("ok", output)

    assert result.outcome == "ok"
    assert result.output is output
