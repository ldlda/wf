from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, create_model

from wf_authoring import NodeReturn, NodeSpec
from wf_core import RuntimeContext

from ..capabilities import DiscoveredTool
from ..events import McpEvent, make_event
from ..models import AuthRecord, ConnectionConfig
from ..sdk import BackendAdapter


def _model_from_schema(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    properties = cast(dict[str, Any], schema.get("properties", {}))
    required = set(cast(list[str], schema.get("required", [])))
    field_defs: dict[str, tuple[object, object]] = {}

    for field_name in properties:
        default = ... if field_name in required else None
        field_defs[field_name] = (Any, Field(default=default))

    raw_field_defs = cast(dict[str, Any], field_defs)
    model = create_model(
        name,
        __config__=ConfigDict(extra="allow"),
        **raw_field_defs,
    )
    return cast(type[BaseModel], model)


def wrap_discovered_tool(
    *,
    connection: ConnectionConfig,
    auth: AuthRecord | None,
    adapter: BackendAdapter,
    tool: DiscoveredTool,
    emit_event: Callable[[McpEvent], None] | None = None,
) -> NodeSpec[BaseModel, BaseModel]:
    input_model = _model_from_schema(
        f"{connection.id}_{tool.name}_Input",
        tool.input_schema,
    )
    output_model = _model_from_schema(
        f"{connection.id}_{tool.name}_Output",
        tool.output_schema,
    )

    async def invoke_tool(
        payload: BaseModel,
        ctx: RuntimeContext,
    ) -> NodeReturn[BaseModel]:
        if emit_event is not None:
            emit_event(
                make_event(
                    "tool_call_started",
                    connection_id=connection.id,
                    capability_id=f"{connection.id}.{tool.name}",
                    payload={"input": payload.model_dump()},
                )
            )
        result = await adapter.call_tool(
            connection=connection,
            auth=auth,
            tool_name=tool.name,
            payload=payload.model_dump(),
        )
        if emit_event is not None:
            emit_event(
                make_event(
                    "tool_call_completed",
                    connection_id=connection.id,
                    capability_id=f"{connection.id}.{tool.name}",
                    payload={
                        "outcome": result.outcome,
                        "meta": result.meta,
                    },
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
    )
