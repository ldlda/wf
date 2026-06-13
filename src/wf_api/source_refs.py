from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SourceResourceRef(BaseModel):
    """Workflow-safe resource handle.

    The ref is inert pass-by-value data. Only explicit source-aware helper nodes
    dereference it through deployment source bindings and platform context.
    """

    kind: Literal["source_resource_ref"] = "source_resource_ref"
    logical_source: str = Field(min_length=1)
    uri: str = Field(min_length=1)
    mime_type: str | None = None
    name: str | None = None
