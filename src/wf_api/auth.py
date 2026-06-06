from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

AUTH_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"


def validate_auth_id(value: str) -> str:
    """Validate auth refs that are safe as store keys and path segments.

    Auth refs deliberately carry no provider semantics. Source providers decide
    how a resolved auth record is interpreted.
    """

    if not re.fullmatch(AUTH_ID_PATTERN, value):
        raise ValueError(
            "auth id must start with alphanumeric or underscore and contain "
            "only [A-Za-z0-9_.-]"
        )
    return value


@dataclass(frozen=True, slots=True)
class AuthRecord:
    """Neutral credential record resolved by auth ref.

    `scheme + payload` is a compatibility bridge, not the long-term taxonomy.
    Keep payload interpretation inside provider adapters so a future
    discriminated union can replace this without touching workflow/config code.
    """

    id: str
    scheme: str
    payload: Mapping[str, object]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_auth_id(self.id)
        if not self.scheme:
            raise ValueError("auth scheme must be non-empty")


class AuthStore(Protocol):
    """Read-only runtime credential lookup by auth ref."""

    def load_auth(self, auth_ref: str) -> AuthRecord | None: ...


__all__ = [
    "AUTH_ID_PATTERN",
    "AuthRecord",
    "AuthStore",
    "validate_auth_id",
]
