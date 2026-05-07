from __future__ import annotations

from typing import Literal


def normalize_transport(
    transport: str,
) -> Literal["stdio", "sse", "streamable-http"]:
    """Normalize supported CLI transport spellings for FastMCP."""
    match transport:
        case "streamable_http" | "streamable-http":
            return "streamable-http"
        case "stdio":
            return "stdio"
        case "sse":
            return "sse"
        case _:
            raise ValueError(f"we dont support {transport} yet sry")
