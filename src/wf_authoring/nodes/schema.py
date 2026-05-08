from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wf_core import SchemaRef


def schema_ref_for(
    model_type: type[BaseModel],
    schema_override: dict[str, Any] | None = None,
) -> SchemaRef:
    """Build a core schema reference from a Pydantic model or schema override."""
    if schema_override is not None:
        return SchemaRef.model_validate(schema_override)
    return SchemaRef.model_validate(model_type.model_json_schema())
