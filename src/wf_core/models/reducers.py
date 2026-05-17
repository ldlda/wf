from __future__ import annotations

from pydantic import BaseModel


class ReducerSpec(BaseModel):
    """Inspectable metadata for one named pure state reducer."""

    name: str
    description: str | None = None
