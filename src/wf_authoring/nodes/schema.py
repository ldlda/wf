from __future__ import annotations

from pydantic import BaseModel

from wf_core import SchemaRef


def schema_ref_for(model_type: type[BaseModel]) -> SchemaRef:
    """Build a core schema reference from a pydantic model class."""
    return SchemaRef.model_validate(model_type.model_json_schema())
