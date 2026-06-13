from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from wf_authoring import NodeReturn, NodeSpec
from wf_core import RuntimeContext
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import DiscoveredTool
from wf_sources_mcp.connections import McpSourceConnection
from wf_sources_mcp.schema_models import model_from_schema
from wf_sources_mcp.sdk import ToolExecutor
from wf_sources_mcp.tool_events import (
    ToolWrapperEventSink,
    tool_call_completed_event,
    tool_call_started_event,
)


def wrap_discovered_tool(
    *,
    connection: McpSourceConnection,
    auth: AuthRecord | None,
    auth_loader: Callable[[], AuthRecord | None] | None = None,
    executor: ToolExecutor,
    tool: DiscoveredTool,
    emit_event: ToolWrapperEventSink | None = None,
) -> NodeSpec[BaseModel, BaseModel]:
    input_model = model_from_schema(
        f"{connection.id}_{tool.name}_Input",
        tool.input_schema,
    )
    output_model = model_from_schema(
        f"{connection.id}_{tool.name}_Output",
        tool.output_schema,
    )

    async def invoke_tool(
        payload: BaseModel,
        ctx: RuntimeContext,
    ) -> NodeReturn[BaseModel]:
        if emit_event is not None:
            emit_event(
                tool_call_started_event(
                    connection_id=connection.id,
                    capability_id=f"{connection.id}.{tool.name}",
                    input_payload=payload.model_dump(exclude_unset=True),
                )
            )
        result = await executor.call_tool(
            connection=connection,
            auth=auth_loader() if auth_loader is not None else auth,
            tool_name=tool.name,
            # Pydantic fills absent optional fields with None, but strict MCP
            # servers such as Playwright distinguish omitted from explicit null.
            payload=payload.model_dump(exclude_unset=True),
        )
        if emit_event is not None:
            emit_event(
                tool_call_completed_event(
                    connection_id=connection.id,
                    capability_id=f"{connection.id}.{tool.name}",
                    outcome=result.outcome,
                    meta=result.meta,
                )
            )
        return NodeReturn(
            outcome=result.outcome,
            output=output_model.model_validate(result.output),
        )

    return NodeSpec(
        name=tool.name,
        input_model=input_model,
        output_model=output_model,
        outcomes=tool.outcomes,
        fn=invoke_tool,
        description=tool.description,
        is_async=True,
        input_schema_contract=tool.input_schema,
        output_schema_contract=tool.output_schema,
    )


__all__ = ["wrap_discovered_tool"]
