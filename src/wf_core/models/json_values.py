from __future__ import annotations

from math import isfinite

from pydantic import FiniteFloat

# Keep literal JSON values recursive at the canonical model seam so every
# downstream contract generator sees the same JSON scalar/container union.
type JsonValue = (
    None | bool | int | FiniteFloat | str | list[JsonValue] | dict[str, JsonValue]
)


def validate_strict_json_value(value: object) -> JsonValue:
    """Reject Python containers and scalar types that JSON would coerce."""

    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [validate_strict_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: validate_strict_json_value(item) for key, item in value.items()}
    raise ValueError("value must be a finite JSON value")
