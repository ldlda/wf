from __future__ import annotations

from typing import Any, Literal


class RpcArtifactClientMixin:
    """JSON-RPC implementation of workflow artifact surface methods."""

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...

    async def list_artifacts(
        self,
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
        self, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.artifacts.inspect",
            {"artifact_id": artifact_id, "version": version},
        )

    async def save_artifact(self, artifact: dict[str, Any]) -> dict[str, Any]:
        return await self._call("workflow.artifacts.save", {"artifact": artifact})
