from __future__ import annotations

import re

CONNECTION_ID_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$"

RESERVED_CONNECTION_IDS = frozenset({"wf.admin", "wf.mcp"})
"""Source ids reserved by built-in workflow/MCP control surfaces."""


def parse_connection_id(connection_id: str) -> tuple[str, str]:
    """Validate and split one MCP source id into provider/account parts.

    Source ids also key persisted auth, registry, and catalog files. Keep this
    conservative so unsafe ids are rejected before reaching store boundaries.
    """

    if not re.fullmatch(CONNECTION_ID_PATTERN, connection_id):
        raise ValueError(
            "connection id must start with alphanumeric or underscore and contain "
            "only [A-Za-z0-9_.-]"
        )
    if "." not in connection_id:
        raise ValueError("connection id must look like '<server>.<account>'")
    server, account = connection_id.split(".", 1)
    if not server or not account:
        raise ValueError("connection id must look like '<server>.<account>'")
    return server, account


__all__ = [
    "CONNECTION_ID_PATTERN",
    "RESERVED_CONNECTION_IDS",
    "parse_connection_id",
]
