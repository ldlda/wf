"""Strict identity checks for reconstructing public client snapshots."""

from __future__ import annotations

from collections.abc import Mapping

from .errors import InvalidResponse


def require_response_identity(
    *,
    operation: str,
    actual: Mapping[str, object],
    expected: Mapping[str, object],
) -> None:
    """Reject a validly shaped response that belongs to another resource.

    Shape validation alone cannot prevent a server, proxy, or cache from
    returning the wrong resource. Keeping this check centralized makes every
    public reconstruction boundary report the operation and mismatched field.
    """
    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        if actual_value != expected_value:
            raise InvalidResponse(
                operation=operation,
                details=(
                    f"response {field} {actual_value!r} does not match "
                    f"requested {expected_value!r}"
                ),
            )
