from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal


class RpcDraftClientMixin:
    """JSON-RPC implementation of workflow draft workspace surface methods."""

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]: ...

    async def list_draft_workspaces(self) -> dict[str, Any]:
        return await self._call("workflow.draft_workspaces.list", {})

    async def get_draft_workspace(
        self,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.get",
            {"workspace_id": workspace_id, "include_draft": include_draft},
        )

    async def create_draft_workspace_from_capability(
        self,
        *,
        workspace_id: str,
        capability_name: str,
        name: str | None = None,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        input: Sequence[Any] | None = None,
        output: Sequence[Any] | None = None,
        input_map: dict[str, str] | None = None,
        output_map: dict[str, str] | None = None,
        error_message_source: Any | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": workspace_id,
                "capability_name": capability_name,
                "name": name,
                "title": title,
                "input_schema": input_schema,
                "state_schema": state_schema,
                "output_schema": output_schema,
                "input": input,
                "output": output,
                "input_map": input_map,
                "output_map": output_map,
                "error_message_source": error_message_source,
            },
        )

    async def patch_draft_workspace(
        self,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.patch",
            {"workspace_id": workspace_id, "revision": revision, "patch": patch},
        )

    async def validate_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.validate",
            {"workspace_id": workspace_id},
        )

    async def create_artifact_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        kind: Literal["workflow", "wrapper"] = "workflow",
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.create_artifact",
            {
                "workspace_id": workspace_id,
                "artifact_id": artifact_id,
                "version": version,
                "title": title,
                "outcomes": list(outcomes),
                "kind": kind,
                "description": description,
                "required_capabilities": required_capabilities,
                "source_bindings": source_bindings,
                "created_from_catalog_version": created_from_catalog_version,
            },
        )

    async def create_wrapper_from_workspace(
        self,
        *,
        workspace_id: str,
        artifact_id: str,
        version: int,
        title: str,
        outcomes: Sequence[str],
        description: str | None = None,
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
        created_from_catalog_version: str | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.create_wrapper",
            {
                "workspace_id": workspace_id,
                "artifact_id": artifact_id,
                "version": version,
                "title": title,
                "outcomes": list(outcomes),
                "description": description,
                "required_capabilities": required_capabilities,
                "source_bindings": source_bindings,
                "created_from_catalog_version": created_from_catalog_version,
            },
        )
