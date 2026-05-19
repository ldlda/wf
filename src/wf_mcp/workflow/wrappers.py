from __future__ import annotations

from collections.abc import Callable
from types import NoneType, UnionType
from typing import Any, Union, cast, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, create_model

from wf_authoring import NodeReturn, NodeSpec
from wf_core import RuntimeContext
from wf_mcp.broker.events import McpEvent, make_event

from ..capabilities import DiscoveredTool
from ..models import AuthRecord, ConnectionConfig
from ..sdk import BackendAdapter


_JSON_TYPE_MAP: dict[str, object] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict[str, Any],
}


def _python_type_from_schema(schema: object) -> object:
    """Map a small JSON Schema subset into a Pydantic field annotation."""
    if not isinstance(schema, dict):
        return Any

    if "enum" in schema:
        return Any

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null_types = [item for item in schema_type if item != "null"]
        if len(non_null_types) == 1:
            return _optional_type(
                _python_type_from_schema({**schema, "type": non_null_types[0]})
            )
        return Any

    if schema_type == "array":
        item_type = _python_type_from_schema(schema.get("items", {}))
        return list[item_type] if isinstance(item_type, type) else list[Any]

    if not isinstance(schema_type, str):
        return Any
    return _JSON_TYPE_MAP.get(schema_type, Any)


def _optional_type(annotation: object) -> object:
    """Return an optional version of a supported runtime annotation."""
    if annotation is Any:
        return Any
    origin = get_origin(annotation)
    if origin in {Union, UnionType} and NoneType in get_args(annotation):
        return annotation
    return annotation | None if isinstance(annotation, type) else Any


def _field_default(
    field_name: str,
    property_schema: object,
    required: set[str],
) -> object:
    """Return the Pydantic field default for a JSON Schema property."""
    if isinstance(property_schema, dict) and "default" in property_schema:
        return property_schema["default"]
    return ... if field_name in required else None


def _model_from_schema(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    """Create a loose Pydantic adapter model for an MCP JSON Schema object."""
    properties = cast(dict[str, Any], schema.get("properties", {}))
    required = set(cast(list[str], schema.get("required", [])))
    field_defs: dict[str, tuple[object, object]] = {}

    for field_name, property_schema in properties.items():
        annotation = _python_type_from_schema(property_schema)
        default = _field_default(field_name, property_schema, required)
        description = (
            property_schema.get("description")
            if isinstance(property_schema, dict)
            else None
        )
        field_defs[field_name] = (
            annotation,
            Field(default=default, description=description),
        )

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
                    payload={"input": payload.model_dump(exclude_unset=True)},
                )
            )
        result = await adapter.call_tool(
            connection=connection,
            auth=auth,
            tool_name=tool.name,
            # Pydantic fills absent optional fields with None, but strict MCP
            # servers such as Playwright distinguish omitted from explicit null.
            payload=payload.model_dump(exclude_unset=True),
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
        input_schema_contract=tool.input_schema,
        output_schema_contract=tool.output_schema,
    )
