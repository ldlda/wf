from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class OpenApiOperation:
    """Normalized operation metadata extracted from one OpenAPI document."""

    name: str
    operation_id: str
    method: Literal["get", "post", "put", "patch", "delete", "options", "head"]
    path: str
    summary: str | None
    description: str | None
    effective_parameters: tuple[JsonObject, ...]
    has_request_body: bool
    raw_operation: JsonObject
    document_path: Path
