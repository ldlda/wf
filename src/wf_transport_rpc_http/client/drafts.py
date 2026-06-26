from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from .base import RpcCaller


class RpcDraftClientMixin:
    """JSON-RPC implementation of workflow draft workspace surface methods."""

    async def list_draft_workspaces(self: RpcCaller) -> dict[str, Any]:
        return await self._call("workflow.draft_workspaces.list", {})

    async def get_draft_workspace(
        self: RpcCaller,
        *,
        workspace_id: str,
        include_draft: bool = False,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.get",
            {"workspace_id": workspace_id, "include_draft": include_draft},
        )

    async def create_draft_workspace_from_capability(
        self: RpcCaller,
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
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        patch: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.patch",
            {"workspace_id": workspace_id, "revision": revision, "patch": patch},
        )

    async def set_draft_name(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_name",
            {"workspace_id": workspace_id, "revision": revision, "name": name},
        )

    async def set_draft_route(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_route",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "outcome": outcome,
                "target": target,
            },
        )

    async def set_step_input_map(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
        merge: bool = False,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_step_input_map",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "input_map": input_map,
                "merge": merge,
            },
        )

    async def set_step_output_map(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
        merge: bool = False,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_step_output_map",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "output_map": output_map,
                "merge": merge,
            },
        )

    async def add_state_schema_from_output(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.add_state_from_output",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "output_field": output_field,
                "state_path": state_path,
            },
        )

    async def bind_output_to_state(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.bind_output_to_state",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "output_field": output_field,
                "state_path": state_path,
            },
        )

    async def validate_draft_workspace(
        self: RpcCaller,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.validate",
            {"workspace_id": workspace_id},
        )

    async def delete_draft_workspace(
        self: RpcCaller,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.delete",
            {"workspace_id": workspace_id},
        )

    async def create_artifact_from_workspace(
        self: RpcCaller,
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
        self: RpcCaller,
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
