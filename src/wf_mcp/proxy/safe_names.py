from __future__ import annotations

import hashlib
import re
from asyncio import Lock
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from fastmcp.server.transforms import GetToolNext, Transform
from fastmcp.tools.base import Tool
from fastmcp.utilities.versions import VersionSpec

if TYPE_CHECKING:
    from fastmcp import FastMCP

_SAFE_TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_MAX_TOOL_NAME_LENGTH = 64


class SafeToolNames(Transform):
    """Expose MCP tools with client-safe names while preserving internal names.

    Some clients, including Claude Desktop's MCPB frontend path, reject tool
    names outside `^[a-zA-Z0-9_-]{1,64}$`. wf-mcp's native names are dotted
    (`wf.workflow.run_deployment`, `everything.default.echo`) because they are
    better for humans and source ownership. This transform is a boundary
    adapter: `tools/list` shows safe names, and `tools/call` maps them back.

    This is intentionally lookup-backed rather than fully reversible. Claude's
    normal flow is `tools/list` followed by `tools/call` using one listed name,
    so public names should optimize for readability.

    Ambiguous or long mappings receive a deterministic hash suffix. The mapping
    remains one-to-one inside this transform instance, while common names stay
    readable.
    """

    def __init__(self, server: FastMCP[Any] | None = None) -> None:
        self._safe_to_original: dict[str, str] = {}
        self._original_to_safe: dict[str, str] = {}
        self._server = server
        self._primed = False
        self._prime_lock = Lock()

    async def list_tools(self, tools: Sequence[Tool]) -> Sequence[Tool]:
        return [
            tool.model_copy(update={"name": self._safe_name(tool.name)})
            for tool in tools
        ]

    async def get_tool(
        self,
        name: str,
        call_next: GetToolNext,
        *,
        version: VersionSpec | None = None,
    ) -> Tool | None:
        original_name = self._safe_to_original.get(name)
        if original_name is None:
            original_name = await self._prime_lookup(name)
        if original_name is None:
            original_name = decode_safe_tool_name(name)
        tool = await call_next(original_name, version=version)
        return None if tool is None else tool.model_copy(update={"name": name})

    async def _prime_lookup(self, name: str) -> str | None:
        """Populate the reverse map from a live listing on first miss.

        FastMCP v4 resolves `tools/call` through this chain without requiring
        a prior `tools/list`, so the tables built during listing may be empty
        when a directly-called safe name arrives. One live listing primes
        them; a failed prime falls through to the identity fallback so the
        call still ends in a proper unknown-tool error.
        """
        if self._server is None:
            return None
        # A direct-call burst must share the first live listing. Publishing
        # ``_primed`` without this barrier lets siblings observe empty maps.
        async with self._prime_lock:
            if not self._primed:
                self._primed = True
                try:
                    await self._server.list_tools()
                except Exception:
                    return None
            return self._safe_to_original.get(name)

    def _safe_name(self, original_name: str) -> str:
        cached = self._original_to_safe.get(original_name)
        if cached is not None:
            return cached

        candidate = encode_safe_tool_name(original_name)
        if len(candidate) > _MAX_TOOL_NAME_LENGTH:
            candidate = self._hashed_safe_name(original_name)
        if _SAFE_TOOL_NAME_PATTERN.fullmatch(candidate) is None:
            candidate = self._hashed_safe_name(original_name)

        existing = self._safe_to_original.get(candidate)
        if existing is not None and existing != original_name:
            candidate = self._hashed_safe_name(original_name)
            existing = self._safe_to_original.get(candidate)
            if existing is not None and existing != original_name:
                raise ValueError(
                    f"safe tool name collision: {existing!r} and {original_name!r} "
                    f"both project to {candidate!r}"
                )

        self._original_to_safe[original_name] = candidate
        self._safe_to_original[candidate] = original_name
        return candidate

    def _hashed_safe_name(self, original_name: str) -> str:
        digest = hashlib.sha1(original_name.encode("utf-8")).hexdigest()[:10]
        prefix = encode_safe_tool_name(original_name)[: _MAX_TOOL_NAME_LENGTH - 12]
        prefix = prefix.rstrip("_-") or "tool"
        return f"{prefix}_h{digest}"

    def assert_consistent(self) -> None:
        """Fail if the bidirectional lookup tables are not exact inverses."""
        original_to_safe = self._original_to_safe
        safe_to_original = self._safe_to_original
        if len(original_to_safe) != len(safe_to_original):
            raise AssertionError("safe tool name maps have different sizes")
        for original, safe in original_to_safe.items():
            if safe_to_original.get(safe) != original:
                raise AssertionError(
                    f"safe tool name reverse map is stale for {original!r}"
                )
        for safe, original in safe_to_original.items():
            if original_to_safe.get(original) != safe:
                raise AssertionError(
                    f"safe tool name forward map is stale for {safe!r}"
                )


def encode_safe_tool_name(name: str) -> str:
    """Return the preferred readable safe spelling for one runtime tool name."""
    parts: list[str] = []
    for char in name:
        if char.isascii() and (char.isalnum() or char in {"_", "-"}):
            parts.append(char)
        elif char == ".":
            parts.append("_")
        else:
            parts.append("_")
    return "".join(parts) or "tool"


def decode_safe_tool_name(name: str) -> str:
    """Fallback for already-safe names not seen in `tools/list` first."""
    return name
