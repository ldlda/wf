from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeResult(BaseModel):
    """Normalized result returned by a node handler after execution."""

    model_config = ConfigDict(extra="allow")

    outcome: str
    output: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
