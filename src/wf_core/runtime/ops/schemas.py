from __future__ import annotations

from typing import Any

from jsonschema import ValidationError, SchemaError, validators

from wf_core.errors import WorkflowExecutionError
from wf_core.models.schemas import SchemaRef


def validate_payload_against_schema(
    schema: SchemaRef | dict[str, Any],
    payload: Any,
    label: str,
) -> None:
    """Validate a runtime payload against the schema declared at a boundary.

    The runtime delegates JSON Schema semantics to `jsonschema` instead of
    maintaining hand-written type checks. Errors are wrapped in
    `WorkflowExecutionError` so callers keep one execution-failure surface.
    """
    schema_dict = _schema_dict(schema)
    validator_cls = validators.validator_for(schema_dict)
    try:
        validator_cls.check_schema(schema_dict)
        validator_cls(schema_dict).validate(payload)
    except SchemaError as exc:
        raise WorkflowExecutionError(
            f"{label} has invalid schema: {exc.message}"
        ) from exc
    except ValidationError as exc:
        path = _format_error_path(exc)
        raise WorkflowExecutionError(f"{label}{path}: {exc.message}") from exc


def _schema_dict(schema: SchemaRef | dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-Schema-compatible dictionary for validation."""
    if isinstance(schema, SchemaRef):
        return schema.model_dump(exclude_none=True)
    return schema


def _format_error_path(exc: ValidationError) -> str:
    """Render a compact JSON-path-like suffix for a validation error."""
    if not exc.path:
        return ""
    return "".join(f"[{part!r}]" for part in exc.path)
