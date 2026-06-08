from __future__ import annotations

from typing import Any, Literal

from .base import RpcCaller


class RpcArtifactClientMixin:
    """JSON-RPC implementation of workflow artifact surface methods."""

    async def list_artifacts(
        self: RpcCaller,
        *,
        query: str | None = None,
        kind: Literal["workflow", "wrapper"] | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.artifacts.list",
            {
                "query": query,
                "kind": kind,
                "cursor": cursor,
                "limit": limit,
            },
        )

    async def inspect_artifact(
        self: RpcCaller, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.artifacts.inspect",
            {"artifact_id": artifact_id, "version": version},
        )

    async def save_artifact(
        self: RpcCaller, artifact: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._call("workflow.artifacts.save", {"artifact": artifact})

    async def delete_artifact(
        self: RpcCaller, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.artifacts.delete",
            {"artifact_id": artifact_id, "version": version},
        )
