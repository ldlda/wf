from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any

import httpx
from openapi_core import OpenAPI
from pydantic import BaseModel, ConfigDict

from wf_authoring import NodeReturn

from .models import OpenApiOperation
from .request import HttpRequestParts, build_http_request_parts
from .validation import (
    HttpResponseParts,
    validate_openapi_request,
    validate_openapi_response,
)


@dataclass(frozen=True, slots=True)
class OpenApiExecutionConfig:
    """Runtime config for spec-driven OpenAPI HTTP execution."""

    base_url: str
    timeout_seconds: float = 30.0


class OpenApiOperationOutput(BaseModel):
    """Generic transport output for raw OpenAPI operation nodes."""

    model_config = ConfigDict(extra="allow")

    status_code: int
    headers: dict[str, str]
    body: Any
    validation_errors: list[str] = []


async def call_openapi_operation(
    app: OpenAPI,
    operation: OpenApiOperation,
    config: OpenApiExecutionConfig,
    payload: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> NodeReturn[OpenApiOperationOutput]:
    """Execute one raw OpenAPI operation through generic HTTP machinery."""
    request = build_http_request_parts(
        operation,
        base_url=config.base_url,
        payload=payload,
    )
    request_validation = validate_openapi_request(app, request)
    if not request_validation.valid:
        return NodeReturn(
            outcome="validation_error",
            output=OpenApiOperationOutput(
                status_code=0,
                headers={},
                body=None,
                validation_errors=request_validation.errors,
            ),
        )

    close_client = client is None
    active_client = client or httpx.AsyncClient(timeout=config.timeout_seconds)
    try:
        try:
            response = await _send_request(active_client, request)
        except httpx.HTTPError as exc:
            return NodeReturn(
                outcome="transport_error",
                output=OpenApiOperationOutput(
                    status_code=0,
                    headers={},
                    body=None,
                    validation_errors=[str(exc)],
                ),
            )
    finally:
        if close_client:
            await active_client.aclose()

    body, body_errors = _response_body(response)
    headers = {str(key): str(value) for key, value in response.headers.items()}
    output = OpenApiOperationOutput(
        status_code=response.status_code,
        headers=headers,
        body=body,
        validation_errors=body_errors,
    )
    if body_errors:
        return NodeReturn(outcome="validation_error", output=output)

    if not _status_declared(operation, response.status_code):
        output.validation_errors = [
            f"response status {response.status_code} is not declared"
        ]
        return NodeReturn(outcome="unexpected_status", output=output)

    response_validation = validate_openapi_response(
        app,
        request,
        HttpResponseParts(
            status_code=response.status_code,
            headers=headers,
            data=response.content,
        ),
    )
    if not response_validation.valid:
        output.validation_errors = response_validation.errors
        return NodeReturn(outcome="validation_error", output=output)

    if 200 <= response.status_code < 300:
        return NodeReturn(outcome="ok", output=output)
    return NodeReturn(outcome="http_error", output=output)


async def _send_request(
    client: httpx.AsyncClient,
    request: HttpRequestParts,
) -> httpx.Response:
    kwargs: dict[str, Any] = {
        "method": request.method,
        "url": request.url,
    }
    if request.params:
        kwargs["params"] = request.params
    if request.headers:
        kwargs["headers"] = request.headers
    if request.cookies:
        kwargs["cookies"] = request.cookies
    if request.json is not None:
        kwargs["json"] = request.json
    return await client.request(**kwargs)


def _response_body(response: httpx.Response) -> tuple[Any, list[str]]:
    """Parse response body while keeping malformed JSON in validation flow."""
    content_type = response.headers.get("content-type", "").lower()
    if not response.content:
        return None, []
    if "json" in content_type:
        try:
            return response.json(), []
        except JSONDecodeError as exc:
            return response.text, [str(exc)]
    return response.text, []


def _status_declared(operation: OpenApiOperation, status_code: int) -> bool:
    responses = operation.raw_operation.get("responses", {})
    if not isinstance(responses, dict):
        return False
    status = str(status_code)
    if status in responses or "default" in responses:
        return True
    status_range = f"{status[0]}XX"
    return status_range in responses
