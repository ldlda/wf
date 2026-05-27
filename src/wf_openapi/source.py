from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from wf_authoring import NodeReturn, NodeSpec
from wf_core import RuntimeContext
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)

from .executor import (
    OpenApiExecutionConfig,
    OpenApiOperationOutput,
    call_openapi_operation,
)
from .schemas import input_schema_for_operation, output_schema_for_operation
from .spec import load_openapi_operations
from .validation import load_openapi_app

OPENAPI_OUTCOMES = (
    "ok",
    "http_error",
    "unexpected_status",
    "validation_error",
    "transport_error",
)


class OpenApiNodePayload(BaseModel):
    """Loose runtime boundary; public validation remains the JSON Schema contract."""

    model_config = ConfigDict(extra="allow")


def build_openapi_capability_source(
    *,
    source_id: str,
    document_path: Path,
    base_url: str,
) -> CapabilitySource:
    """Build NodeSpecs from public OpenAPI schemas and generic HTTP execution."""
    app = load_openapi_app(document_path)
    operations = load_openapi_operations(document_path)
    specs: dict[str, NodeSpec[OpenApiNodePayload, OpenApiOperationOutput]] = {}
    for operation in operations:
        name = f"{source_id}.{operation.name}"
        config = OpenApiExecutionConfig(
            base_url=base_url,
        )

        async def handler(
            payload: OpenApiNodePayload,
            ctx: RuntimeContext,
            *,
            _app=app,
            _operation=operation,
            _config: OpenApiExecutionConfig = config,
        ) -> NodeReturn[OpenApiOperationOutput]:
            _ = ctx
            return await call_openapi_operation(
                _app,
                _operation,
                _config,
                payload.model_dump(mode="json"),
            )

        specs[name] = NodeSpec(
            name=name,
            input_model=OpenApiNodePayload,
            output_model=OpenApiOperationOutput,
            outcomes=OPENAPI_OUTCOMES,
            fn=handler,
            description=operation.summary or operation.description,
            is_async=True,
            input_schema_contract=input_schema_for_operation(operation),
            output_schema_contract=output_schema_for_operation(operation),
        )

    return CapabilitySource(
        id=source_id,
        kind="connection",
        capabilities=CapabilityBuckets(node_specs=specs),
        enabled=True,
        visibility=SourceVisibility(
            planner=True,
            mcp_client=False,
            admin_dashboard=True,
        ),
        permissions=SourcePermissions(
            calls_upstream=True,
        ),
        description=f"OpenAPI capability source for {document_path.name}.",
    )
