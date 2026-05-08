from __future__ import annotations

from pydantic import BaseModel, Field

from wf_authoring import NodeCatalog, NodeReturn, Nothing, build_registry, node, outcome
from wf_core import RuntimeContext


class AliasInput(BaseModel):
    value: str


class AliasOutput(BaseModel):
    value: str


class InferredEchoInput(BaseModel):
    value: str


class InferredEchoOutput(BaseModel):
    echoed: str


class InferredOutcomeInput(BaseModel):
    value: str


class InferredOutcomeOutput(BaseModel):
    echoed: str


class InferredAsyncInput(BaseModel):
    value: str


class InferredAsyncOutput(BaseModel):
    echoed: str


class DocumentedInput(BaseModel):
    message: str = Field(description="Message to echo")


class DocumentedOutput(BaseModel):
    echoed: str = Field(description="Echoed message")


@node()
def inferred_echo(
    payload: InferredEchoInput,
    ctx: RuntimeContext,
) -> InferredEchoOutput:
    return InferredEchoOutput(echoed=payload.value)


@node(outcomes=("done", "retry"))
def inferred_echo_with_outcome(
    payload: InferredOutcomeInput,
    ctx: RuntimeContext,
) -> NodeReturn[InferredOutcomeOutput]:
    return NodeReturn(
        outcome="done",
        output=InferredOutcomeOutput(echoed=payload.value),
    )


@node()
async def inferred_async_echo(
    payload: InferredAsyncInput,
    ctx: RuntimeContext,
) -> InferredAsyncOutput:
    return InferredAsyncOutput(echoed=payload.value)


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


def test_node_decorator_infers_models_from_annotations() -> None:
    assert inferred_echo.input_model is InferredEchoInput
    assert inferred_echo.output_model is InferredEchoOutput
    assert inferred_echo.outcomes == ("ok",)
    assert inferred_echo.is_async is False

    registry = build_registry(inferred_echo)
    result = registry["inferred_echo"](
        {"value": "hello"},
        RuntimeContext(current_node_id="x"),
    )
    assert result == {"outcome": "ok", "output": {"echoed": "hello"}}


def test_node_decorator_infers_nodereturn_output_model() -> None:
    assert inferred_echo_with_outcome.input_model is InferredOutcomeInput
    assert inferred_echo_with_outcome.output_model is InferredOutcomeOutput

    registry = build_registry(inferred_echo_with_outcome)
    result = registry["inferred_echo_with_outcome"](
        {"value": "hello"},
        RuntimeContext(current_node_id="x"),
    )
    assert result == {"outcome": "done", "output": {"echoed": "hello"}}


def test_node_decorator_detects_async_automatically() -> None:
    assert inferred_async_echo.is_async is True


def test_pydantic_field_descriptions_survive_node_catalog_schema() -> None:
    @node(description="Echoes a documented message.")
    def documented_echo(payload: DocumentedInput) -> DocumentedOutput:
        return DocumentedOutput(echoed=payload.message)

    entry = NodeCatalog.from_specs(documented_echo).entries()[0]

    assert entry.description == "Echoes a documented message."
    assert entry.input_schema["type"] == "object"
    assert (
        entry.input_schema["properties"]["message"]["description"] == "Message to echo"
    )
    assert entry.output_schema["type"] == "object"
    assert (
        entry.output_schema["properties"]["echoed"]["description"] == "Echoed message"
    )
