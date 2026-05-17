from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, Field

from wf_core.runtime.ops.merges import DEFAULT_REDUCER_DEFINITIONS
from wf_authoring import (
    NodeReturn,
    NodeSpec,
    coalesce,
    constant,
    default_if_none,
    first_item,
    first_item_maybe,
    first_item_or_none,
    is_empty,
    last_item,
    last_item_or_none,
    length,
    node,
    pick_path,
    pick_key,
    project_fields,
    rename_fields,
    runtime_error,
    truthy,
)

from .capability_sources import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)
from .specs import qualify_spec

if TYPE_CHECKING:
    from wf_core import ReducerSpec

BUILTIN_CONNECTION_ID = "wf.std"
"""Internal source id for workflow standard-library node specs."""

MCP_SOURCE_ID = "wf.mcp"
"""Internal source id for broker MCP utility node specs."""


AUTHORING_STD_SPECS: tuple[NodeSpec[Any, Any], ...] = (
    coalesce,
    default_if_none,
    constant,
    pick_key,
    pick_path,
    project_fields,
    rename_fields,
    truthy,
    runtime_error,
    first_item,
    first_item_or_none,
    first_item_maybe,
    last_item,
    last_item_or_none,
    length,
    is_empty,
)
"""Existing authoring ops that are also exposed through the workflow stdlib."""


class ToolCaller(Protocol):
    """Small service boundary needed by the broker-local MCP utility nodes."""

    async def call_tool(
        self,
        connection_id: str,
        tool_name: str,
        *,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class McpCallToolInput(BaseModel):
    """Input for calling a proxied MCP tool from inside a workflow."""

    connection_id: str = Field(description="Connection id that owns the MCP tool.")
    tool_name: str = Field(description="Local tool name on the upstream MCP server.")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-compatible arguments passed to the upstream tool.",
    )


class McpCallToolOutput(BaseModel):
    """Normalized output returned by a proxied MCP tool call."""

    outcome: str = Field(description="Workflow outcome reported by the upstream tool.")
    output: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-compatible tool result payload.",
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Adapter metadata returned with the tool result.",
    )


def builtin_specs() -> dict[str, NodeSpec[Any, Any]]:
    """Return built-in NodeSpecs available to raw broker workflow plans."""
    specs = [
        node(spec, name=spec.name.removeprefix("authoring."))
        for spec in AUTHORING_STD_SPECS
    ]
    qualified_specs = [qualify_spec(BUILTIN_CONNECTION_ID, spec) for spec in specs]
    return {spec.name: spec for spec in qualified_specs}


def builtin_reducers() -> dict[str, ReducerSpec]:
    """Return built-in reducers owned by the workflow standard library."""
    return {
        definition.spec.name: definition.spec
        for definition in DEFAULT_REDUCER_DEFINITIONS.values()
    }


def mcp_specs(service: ToolCaller) -> dict[str, NodeSpec[Any, Any]]:
    """Return service-bound MCP utility specs available to raw plans."""

    @node(
        name="call_tool",
        outcomes=("ok", "error"),
        input_model=McpCallToolInput,
        output_model=McpCallToolOutput,
        description="Call a tool on a registered MCP connection.",
    )
    async def call_tool(payload: McpCallToolInput) -> NodeReturn[McpCallToolOutput]:
        result = await service.call_tool(
            payload.connection_id,
            payload.tool_name,
            arguments=payload.arguments,
        )
        output = McpCallToolOutput.model_validate(result)
        return NodeReturn(outcome=output.outcome, output=output)

    qualified_specs = [qualify_spec(MCP_SOURCE_ID, call_tool)]
    return {spec.name: spec for spec in qualified_specs}


def builtin_sources(service: ToolCaller) -> dict[str, CapabilitySource]:
    """Return all broker-local capability sources."""
    return {
        BUILTIN_CONNECTION_ID: CapabilitySource(
            id=BUILTIN_CONNECTION_ID,
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs=builtin_specs(),
                reducers=builtin_reducers(),
            ),
            visibility=SourceVisibility(
                planner=True,
                mcp_client=True,
                admin_dashboard=True,
            ),
            permissions=SourcePermissions(safe_for_workflow=True),
            description="Workflow standard-library nodes.",
        ),
        MCP_SOURCE_ID: CapabilitySource(
            id=MCP_SOURCE_ID,
            kind="system",
            capabilities=CapabilityBuckets(node_specs=mcp_specs(service)),
            visibility=SourceVisibility(planner=True, admin_dashboard=True),
            permissions=SourcePermissions(calls_upstream=True),
            description="Broker MCP utility nodes.",
        ),
    }
