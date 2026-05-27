from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import quote

from .models import OpenApiOperation


@dataclass(frozen=True, slots=True)
class HttpRequestParts:
    """OpenAPI-shaped request parts ready for `httpx` execution."""

    method: str
    url: str
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    json: Any | None = None


def build_http_request_parts(
    operation: OpenApiOperation,
    *,
    base_url: str,
    payload: Mapping[str, Any],
) -> HttpRequestParts:
    """Build an HTTP request without renaming public OpenAPI fields."""
    path_values = _mapping(payload, "path")
    path = operation.path
    for parameter in operation.effective_parameters:
        if parameter.get("in") != "path":
            continue
        name = parameter.get("name")
        if not isinstance(name, str):
            raise ValueError(
                f"path parameter metadata for {operation.name!r} is invalid"
            )
        if name not in path_values:
            raise ValueError(f"missing path parameter {name!r}")
        path = path.replace("{" + name + "}", quote(str(path_values[name]), safe=""))

    return HttpRequestParts(
        method=operation.method.upper(),
        url=base_url.rstrip("/") + path,
        params=dict(_mapping(payload, "query")),
        headers={
            str(key): str(value) for key, value in _mapping(payload, "header").items()
        },
        cookies={
            str(key): str(value) for key, value in _mapping(payload, "cookie").items()
        },
        json=payload.get("body"),
    )


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Read one OpenAPI parameter group and reject lossy non-object values."""
    value = payload.get(key, {})
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value
