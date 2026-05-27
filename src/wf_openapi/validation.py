from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from openapi_core import OpenAPI
from openapi_core.datatypes import RequestParameters
from werkzeug.datastructures import Headers, ImmutableMultiDict

from .request import HttpRequestParts


@dataclass(frozen=True, slots=True)
class HttpResponseParts:
    """HTTP response data in the minimal shape `openapi-core` needs."""

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    data: bytes | None = None


@dataclass(frozen=True, slots=True)
class OpenApiValidationResult:
    """Small validation result that keeps `openapi-core` details local."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    data: Any = None


def load_openapi_app(document_path: Path) -> OpenAPI:
    """Load an OpenAPI app used for request/response validation."""
    return OpenAPI.from_file_path(str(document_path))


def validate_openapi_request(
    app: OpenAPI,
    request: HttpRequestParts,
) -> OpenApiValidationResult:
    """Validate and unmarshal one outgoing request."""
    try:
        result = app.unmarshal_request(_OpenApiCoreRequest(request))
    except Exception as exc:
        return OpenApiValidationResult(valid=False, errors=[str(exc)])
    errors = _error_messages(getattr(result, "errors", []))
    if errors:
        return OpenApiValidationResult(valid=False, errors=errors)
    return OpenApiValidationResult(valid=True, data=result)


def validate_openapi_response(
    app: OpenAPI,
    request: HttpRequestParts,
    response: HttpResponseParts,
) -> OpenApiValidationResult:
    """Validate and unmarshal one incoming response."""
    try:
        result = app.unmarshal_response(
            _OpenApiCoreRequest(request),
            _OpenApiCoreResponse(response),
        )
    except Exception as exc:
        return OpenApiValidationResult(valid=False, errors=[str(exc)])
    errors = _error_messages(getattr(result, "errors", []))
    if errors:
        return OpenApiValidationResult(valid=False, errors=errors)
    return OpenApiValidationResult(valid=True, data=result.data)


def _error_messages(errors: object) -> list[str]:
    """Normalize `openapi-core` result errors without exporting its classes."""
    if not errors:
        return []
    if not isinstance(errors, list):
        return [str(errors)]
    return [str(error) for error in errors]


class _OpenApiCoreRequest:
    """Protocol shim from local request parts to `openapi-core`.

    The rest of `wf_openapi` should talk in terms of `HttpRequestParts`; this
    adapter is the only place that knows `openapi-core`'s protocol attributes.
    """

    def __init__(self, request: HttpRequestParts) -> None:
        self._request = request
        self._url = urlparse(request.url, allow_fragments=False)
        self.parameters = RequestParameters(
            query=ImmutableMultiDict(request.params.items()),
            header=Headers(request.headers),
            cookie=ImmutableMultiDict(request.cookies.items()),
        )

    @property
    def host_url(self) -> str:
        return f"{self._url.scheme}://{self._url.netloc}"

    @property
    def path(self) -> str:
        return self._url.path

    @property
    def method(self) -> str:
        return self._request.method.lower()

    @property
    def body(self) -> bytes | None:
        if self._request.json is None:
            return None
        return json.dumps(self._request.json).encode()

    @property
    def content_type(self) -> str:
        if self._request.json is not None:
            return "application/json"
        return self._request.headers.get("content-type", "")


class _OpenApiCoreResponse:
    """Protocol shim from local response parts to `openapi-core`."""

    def __init__(self, response: HttpResponseParts) -> None:
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def content_type(self) -> str:
        return self._response.headers.get("content-type", "")

    @property
    def headers(self) -> Headers:
        return Headers(self._response.headers)

    @property
    def data(self) -> bytes | None:
        return self._response.data
