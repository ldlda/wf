from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wf_authoring.nodes import node


class CoalesceInput(BaseModel):
    value: Any | None = None
    fallback: Any


class ValueOutput(BaseModel):
    value: Any


@node(
    name="authoring.coalesce",
    input_model=CoalesceInput,
    output_model=ValueOutput,
    description="Return value when it is not None, otherwise return fallback.",
)
def coalesce(input: CoalesceInput) -> ValueOutput:
    return ValueOutput(value=input.value if input.value is not None else input.fallback)
