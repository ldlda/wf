from __future__ import annotations

from typing import Any, NoReturn

from pydantic import BaseModel, Field

from wf_authoring.nodes import NodeReturn, Nothing, node


class CoalesceInput(BaseModel):
    """Input model for selecting the first non-None value."""

    value: Any | None = None
    fallback: Any


class ValueOutput(BaseModel):
    """Output model for ops that emit an arbitrary value."""

    value: Any


class ConstantInput(BaseModel):
    """Input model for passing through a configured value."""

    value: Any


class PickKeyInput(BaseModel):
    """Input model for selecting a value from a mapping by key."""

    mapping: dict[str, Any]
    key: str


class PickPathInput(BaseModel):
    """Input model for selecting a nested mapping value by dotted path."""

    mapping: dict[str, Any]
    path: str


class MappingOutput(BaseModel):
    """Output model for ops that emit a mapping."""

    mapping: dict[str, Any]


class ProjectFieldsInput(BaseModel):
    """Input model for selecting named fields from a mapping."""

    mapping: dict[str, Any]
    fields: list[str]


class RenameFieldsInput(BaseModel):
    """Input model for remapping existing mapping keys."""

    mapping: dict[str, Any]
    renames: dict[str, str]


class TruthyInput(BaseModel):
    """Input model for routing by Python truthiness."""

    value: Any


class RuntimeErrorInput(BaseModel):
    """Input model for intentionally failing a workflow branch."""

    message: str
    details: dict[str, Any] = Field(default_factory=dict)


@node(
    name="authoring.coalesce",
    input_model=CoalesceInput,
    output_model=ValueOutput,
    description="Return value when it is not None, otherwise return fallback.",
)
def coalesce(input: CoalesceInput) -> ValueOutput:
    """Return value when it is not None, otherwise return fallback."""
    return ValueOutput(value=input.value if input.value is not None else input.fallback)


default_if_none = node(
    coalesce,
    name="authoring.default_if_none",
    description="Alias for coalesce: return fallback only when value is None.",
)
"""Alias for coalesce with a more explicit name for None-defaulting workflows."""


@node(
    name="authoring.constant",
    input_model=ConstantInput,
    output_model=ValueOutput,
    description="Return the provided value unchanged.",
)
def constant(input: ConstantInput) -> ValueOutput:
    """Return the provided value unchanged."""
    return ValueOutput(value=input.value)


@node(
    name="authoring.pick_key",
    input_model=PickKeyInput,
    output_model=ValueOutput,
    description="Select a value from a mapping by key, returning None if missing.",
)
def pick_key(input: PickKeyInput) -> ValueOutput:
    """Select a value from a mapping by key, returning None if missing."""
    return ValueOutput(value=input.mapping.get(input.key))


@node(
    name="authoring.pick_path",
    input_model=PickPathInput,
    output_model=ValueOutput,
    description="Select a nested mapping value by dotted path, returning None if missing.",
)
def pick_path(input: PickPathInput) -> ValueOutput:
    """Select a nested mapping value by dotted path, returning None if missing."""
    current: Any = input.mapping
    for part in input.path.split("."):
        if not isinstance(current, dict):
            return ValueOutput(value=None)
        current = current.get(part)
        if current is None:
            return ValueOutput(value=None)
    return ValueOutput(value=current)


@node(
    name="authoring.project_fields",
    input_model=ProjectFieldsInput,
    output_model=MappingOutput,
    description="Return only the requested existing fields from a mapping.",
)
def project_fields(input: ProjectFieldsInput) -> MappingOutput:
    """Return only the requested existing fields from a mapping."""
    return MappingOutput(
        mapping={
            field: input.mapping[field]
            for field in input.fields
            if field in input.mapping
        }
    )


@node(
    name="authoring.rename_fields",
    input_model=RenameFieldsInput,
    output_model=MappingOutput,
    description="Rename existing mapping fields and omit missing source keys.",
)
def rename_fields(input: RenameFieldsInput) -> MappingOutput:
    """Rename existing mapping fields and omit missing source keys."""
    return MappingOutput(
        mapping={
            target: input.mapping[source]
            for source, target in input.renames.items()
            if source in input.mapping
        }
    )


@node(
    name="authoring.truthy",
    input_model=TruthyInput,
    output_model=ValueOutput,
    outcomes=("truthy", "falsey"),
    description="Route based on Python truthiness of a value.",
)
def truthy(input: TruthyInput) -> NodeReturn[ValueOutput]:
    """Route based on Python truthiness of a value."""
    value = bool(input.value)
    outcome = "truthy" if value else "falsey"
    return NodeReturn(outcome=outcome, output=ValueOutput(value=value))


@node(
    name="authoring.runtime_error",
    input_model=RuntimeErrorInput,
    output_model=Nothing,
    description="Raise RuntimeError with the provided message and details.",
)
def runtime_error(input: RuntimeErrorInput) -> NoReturn:
    """Raise RuntimeError with the provided message and details."""
    if input.details:
        raise RuntimeError(f"{input.message}: {input.details!r}")
    raise RuntimeError(input.message)
