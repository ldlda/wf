from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReducerRef(BaseModel):
    """Reference to one reducer plus JSON-compatible configuration."""

    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class ReducerSpec(BaseModel):
    """Inspectable metadata for one named pure state reducer."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    config_schema: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
    )
