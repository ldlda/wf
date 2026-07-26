from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from wf_api import CapabilityStepUpdate
from wf_api.surface import RouteSource
from wf_artifacts.drafts.models import DraftStep
from wf_core.models.steps import InputBinding, OutputBinding

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

    async def create_empty_draft_workspace(
        self: RpcCaller,
        *,
        workspace_id: str,
        name: str,
        title: str | None = None,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        outcomes: Sequence[str] = ("ok",),
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.create_empty",
            {
                "workspace_id": workspace_id,
                "name": name,
                "title": title,
                "input_schema": input_schema,
                "state_schema": state_schema,
                "output_schema": output_schema,
                "outcomes": list(outcomes),
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

    async def set_draft_start(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_start",
            {"workspace_id": workspace_id, "revision": revision, "step_id": step_id},
        )

    async def set_draft_contract(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        input_schema: dict[str, Any] | None = None,
        state_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        outcomes: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_contract",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "input_schema": input_schema,
                "state_schema": state_schema,
                "output_schema": output_schema,
                "outcomes": None if outcomes is None else list(outcomes),
            },
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

    async def set_step_input_bindings(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        bindings: Sequence[InputBinding],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_step_input_bindings",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "bindings": [binding.model_dump(mode="json") for binding in bindings],
            },
        )

    async def set_step_output_bindings(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        bindings: Sequence[OutputBinding],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_step_output_bindings",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "bindings": [binding.model_dump(mode="json") for binding in bindings],
            },
        )

    async def update_capability_step(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        update: CapabilityStepUpdate,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.update_capability_step",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "update": update.model_dump(mode="json", exclude_unset=True),
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

    async def set_workflow_output_map(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        output_map: dict[str, str],
        merge: bool = False,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_workflow_output_map",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "output_map": output_map,
                "merge": merge,
            },
        )

    async def set_workflow_output_bindings(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        bindings: Sequence[InputBinding],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_workflow_output_bindings",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "bindings": [binding.model_dump(mode="json") for binding in bindings],
            },
        )

    async def bind_draft(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        source_path: str,
        target_path: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.bind",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "source_path": source_path,
                "target_path": target_path,
            },
        )

    async def add_step_from_capability(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        capability_name: str,
        route_from_step: str | None = None,
        route_from_outcome: str = "ok",
        routes: dict[str, str] | None = None,
        input_map: dict[str, str] | None = None,
        input_bindings: Sequence[InputBinding] | None = None,
        bind_outputs: dict[str, str] | None = None,
        desc: str | None = None,
        retry: int | None = None,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        if input_map is not None and input_bindings is not None:
            raise ValueError("input_map and input_bindings are mutually exclusive")
        params: dict[str, object] = {
            "workspace_id": workspace_id,
            "revision": revision,
            "step_id": step_id,
            "capability_name": capability_name,
            "route_from_step": route_from_step,
            "route_from_outcome": route_from_outcome,
            "routes": routes,
            "bind_outputs": bind_outputs or {},
        }
        if input_map is not None:
            params["input_map"] = input_map
        if input_bindings is not None:
            params["input_bindings"] = [
                binding.model_dump(mode="json") for binding in input_bindings
            ]
        if desc is not None:
            params["desc"] = desc
        if retry is not None:
            params["retry"] = retry
        if timeout_seconds is not None:
            params["timeout_seconds"] = timeout_seconds
        return await self._call(
            "workflow.draft_workspaces.add_step_from_capability",
            params,
        )

    async def add_step(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        step: DraftStep,
        incoming: RouteSource | None = None,
        routes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.add_step",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "step": step.model_dump(mode="json", by_alias=True),
                "incoming": (
                    None
                    if incoming is None
                    else {"step_id": incoming.step_id, "outcome": incoming.outcome}
                ),
                "routes": routes,
            },
        )

    async def branch_draft(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        routes: dict[str, str],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.branch",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "routes": routes,
            },
        )

    async def handle_draft(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        branches: list[dict[str, str]],
        target: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.handle",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "branches": branches,
                "target": target,
            },
        )

    async def remove_draft_route(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.remove_route",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "outcome": outcome,
            },
        )

    async def remove_draft_step(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.remove_step",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
            },
        )

    async def remove_draft_binding(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        inputs: Sequence[str] = (),
        outputs: Sequence[str] = (),
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.remove_binding",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "inputs": list(inputs),
                "outputs": list(outputs),
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

    async def compile_draft_workspace(
        self: RpcCaller,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.compile",
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
