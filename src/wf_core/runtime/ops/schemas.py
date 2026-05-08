from __future__ import annotations

from typing import Any

from wf_core.errors import WorkflowExecutionError


def validate_payload_against_schema(schema: Any, payload: Any, label: str) -> None:
    if schema.type == "object":
        if not isinstance(payload, dict):
            raise WorkflowExecutionError(f"{label} must be an object")
        for required_key in schema.required:
            if required_key not in payload:
                raise WorkflowExecutionError(
                    f"{label} is missing required field {required_key!r}"
                )
