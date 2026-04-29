from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, create_model

from wf_authoring import NodeReturn, NodeSpec
from wf_core import RuntimeContext

from .adapters import BackendAdapter, DiscoveredTool
from .models import AuthRecord, ConnectionConfig


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
        result = await adapter.call_tool(
            connection=connection,
            auth=auth,
            tool_name=tool.name,
            payload=payload.model_dump(),
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
