from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SchemaRef(BaseModel):
    """JSON-schema-like shape used at workflow boundaries."""

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    type: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class StateField(BaseModel):
    """Declared state path plus its runtime merge behavior."""

    type: str
    reducer: str = "wf.std.replace"
    trace: bool = True
    default: Any = None


class StateSchema(BaseModel):
    """Workflow state schema keyed by declared exact state path."""

    model_config = ConfigDict(extra="allow")

    fields: dict[str, StateField] = Field(default_factory=dict)


class NodeDef(BaseModel):
    """Reusable node contract referenced by one or more node uses."""

    name: str
    input_schema: SchemaRef
    output_schema: SchemaRef
    outcomes: list[str] = Field(min_length=1)
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
