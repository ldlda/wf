from __future__ import annotations

from typing import Any, cast

import httpx
import pytest

import wf_client
from wf_client import App, CapabilitySummary, Page, WorkflowClientError
from wf_client.errors import (
    CapabilityNotFound,
    InvalidResponse,
    ProtocolError,
    TransportError,
)
from wf_client.protocols import WorkflowClientPort
from wf_platform import CapabilityRef


def _inspect_payload() -> dict[str, Any]:
    return {
        "name": "app.default.search",
        "source_id": "app.default",
        "kind": "node_spec",
        "description": "Search things",
        "outcomes": ["ok"],
        "is_async": False,
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "wrapper_hints": {
            "capability_name": "app.default.search",
            "confidence": "high",
            "declared_outcomes": ["ok"],
            "suggested_wrapper_outcomes": ["ok"],
            "outcome_policy": "preserve_declared",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "input_map": {},
            "output_map": {},
            "outcome_candidates": [],
            "missing_decisions": [],
            "notes": [],
        },
        "accepts_context": False,
    }


class _Port:
    def __init__(self, *, capability_name: str = "app.default.search") -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.capability_name = capability_name

    async def inspect_capability(self, **params: Any) -> object:
        self.calls.append(("inspect", params))
        payload = _inspect_payload()
        payload["name"] = self.capability_name
        payload["wrapper_hints"]["capability_name"] = self.capability_name
        return payload

    async def list_capabilities(self, **params: Any) -> object:
        self.calls.append(("list", params))
        return {
            "next_cursor": None,
            "total": 1,
            "capabilities": [
                {
                    "name": "app.default.search",
                    "source_id": "app.default",
                    "kind": "node_spec",
                    "description": "Search things",
                    "outcomes": ["ok"],
                    "is_async": False,
                    "input_fields": [],
                    "output_fields": [],
                }
            ],
        }


def _app(*, capability_name: str = "app.default.search") -> App:
    return App._from_port(
        cast(WorkflowClientPort, _Port(capability_name=capability_name))
    )


def test_from_http_jsonrpc_is_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        httpx.AsyncClient,
        "post",
        lambda *args, **kwargs: calls.append("post"),
    )

    app = App.from_http_jsonrpc("http://localhost:8765/rpc")

    assert app.endpoint == "http://localhost:8765/rpc"
    assert calls == []


def test_package_does_not_export_internal_port_or_codecs() -> None:
    assert not hasattr(wf_client, "WorkflowClientPort")
    assert not hasattr(wf_client, "DecodedRunResult")
    assert not hasattr(wf_client, "decode_run_result")


@pytest.mark.asyncio
async def test_http_app_translates_connection_failure_to_public_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_post(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_post)
    app = App.from_http_jsonrpc("http://unreachable.test/rpc")

    with pytest.raises(WorkflowClientError) as raised:
        await app.capability("app.default.search")

    assert isinstance(raised.value, TransportError)
    assert "connection refused" in str(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http", "json", "json-array"])
async def test_http_app_translates_http_and_json_failures(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    async def fail_post(*args: object, **kwargs: object) -> httpx.Response:
        request = httpx.Request("POST", "http://test/rpc")
        if failure == "http":
            return httpx.Response(503, request=request)
        if failure == "json-array":
            return httpx.Response(200, request=request, json=[])
        return httpx.Response(200, request=request, content=b"not-json")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_post)
    app = App.from_http_jsonrpc("http://test/rpc")

    with pytest.raises(WorkflowClientError) as raised:
        await app.capability("app.default.search")

    expected_type = ProtocolError if failure == "json-array" else TransportError
    assert isinstance(raised.value, expected_type)
    assert "workflow.capabilities.inspect" in str(raised.value)


@pytest.mark.asyncio
async def test_http_app_translates_known_workflow_protocol_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def error_post(
        _client: object,
        _url: object,
        *,
        json: dict[str, object],
        **_kwargs: object,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://test/rpc"),
            json={
                "jsonrpc": "2.0",
                "id": json["id"],
                "error": {
                    "code": 5000,
                    "message": "Workflow operation failed",
                    "data": {
                        "code": "KeyError",
                        "message": "unknown workflow capability 'app.default.search'",
                    },
                },
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", error_post)
    app = App.from_http_jsonrpc("http://test/rpc")

    with pytest.raises(WorkflowClientError) as raised:
        await app.capability("app.default.search")

    assert isinstance(raised.value, CapabilityNotFound)
    assert "unknown workflow capability" in str(raised.value)
    assert raised.value.code == 5000
    assert raised.value.data == {
        "code": "KeyError",
        "message": "unknown workflow capability 'app.default.search'",
    }


@pytest.mark.asyncio
async def test_http_app_preserves_unknown_protocol_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = {"code": "future_workflow_error", "message": "future detail", "retry": 3}

    async def error_post(
        _client: object,
        _url: object,
        *,
        json: dict[str, object],
        **_kwargs: object,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://test/rpc"),
            json={
                "jsonrpc": "2.0",
                "id": json["id"],
                "error": {
                    "code": 5999,
                    "message": "Future workflow error",
                    "data": data,
                },
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", error_post)
    app = App.from_http_jsonrpc("http://test/rpc")

    with pytest.raises(ProtocolError) as raised:
        await app.capability("app.default.search")

    assert raised.value.code == 5999
    assert raised.value.message == "Future workflow error"
    assert raised.value.data == data


@pytest.mark.asyncio
async def test_workflow_rejects_mismatched_inspected_artifact_identity() -> None:
    class ArtifactPort(_Port):
        async def inspect_artifact(self, **params: Any) -> object:
            return {
                "id": "other",
                "version": 2,
                "title": "Other",
                "kind": "workflow",
                "description": None,
                "input_schema": {"type": "object", "properties": {}},
                "output_schema": {"type": "object", "properties": {}},
                "outcomes": ["ok"],
                "plan": {
                    "name": "other",
                    "input_schema": {"type": "object", "properties": {}},
                    "state_schema": {"type": "object", "properties": {}},
                    "output_schema": {"type": "object", "properties": {}},
                    "outcomes": ["ok"],
                    "start": "done",
                    "nodes": [{"id": "done", "type": "end", "outcome": "ok"}],
                    "edges": [],
                },
                "required_capabilities": [],
                "workflow_dependencies": {},
                "created_from_catalog_version": None,
            }

    app = App._from_port(cast(WorkflowClientPort, ArtifactPort()))

    with pytest.raises(InvalidResponse, match="workflow.artifacts.inspect"):
        await app.workflow("report", version=1)


@pytest.mark.asyncio
async def test_capability_discovery_returns_rich_page() -> None:
    page = await _app().capabilities(query="search", limit=10)

    assert isinstance(page, Page)
    assert page.total == 1
    assert page.next_cursor is None
    assert isinstance(page.items[0], CapabilitySummary)
    assert page.items[0].qualified_name == "app.default.search"
    assert page.items[0].outcomes == ("ok",)


@pytest.mark.asyncio
async def test_app_discovers_existing_artifacts_deployments_and_runs() -> None:
    """Catch collection methods disappearing while exact loaders still work."""

    class ExistingObjectsPort(_Port):
        async def list_artifacts(self, **params: Any) -> object:
            self.calls.append(("artifacts", params))
            return {
                "nodes": [
                    {
                        "name": "report.v3",
                        "artifact_id": "report",
                        "version": 3,
                        "kind": "workflow",
                        "display_name": "Report",
                        "description": None,
                        "outcomes": ["ok"],
                        "input_schema": {"type": "object", "properties": {}},
                        "output_schema": {"type": "object", "properties": {}},
                        "required_sources": ["app.default"],
                        "diagnostics": [],
                    }
                ],
                "cursor": "0",
                "next_cursor": None,
                "limit": 10,
                "total": 1,
            }

        async def list_deployments(self) -> object:
            self.calls.append(("deployments", {}))
            return {
                "deployments": [
                    {
                        "id": "report.production",
                        "artifact_id": "report",
                        "artifact_version": 3,
                        "binding_count": 1,
                        "drift_policy": "block",
                    }
                ]
            }

        async def list_runs(self, **params: Any) -> object:
            self.calls.append(("runs", params))
            return {
                "runs": [
                    {
                        "run_id": "run-123",
                        "deployment_id": "report.production",
                        "artifact_id": "report",
                        "artifact_version": 3,
                        "status": "interrupted",
                        "resume_readiness": "ready",
                        "diagnostic_count": 0,
                        "created_at": "2026-09-02T00:00:00Z",
                        "updated_at": "2026-09-02T00:01:00Z",
                    }
                ],
                "cursor": None,
                "next_cursor": "next",
                "limit": 25,
                "total": 1,
            }

    port = ExistingObjectsPort()
    app = App._from_port(cast(WorkflowClientPort, port))

    artifacts = await app.artifacts(query="report", kind="workflow", limit=10)
    deployments = await app.deployments()
    runs = await app.runs(status="interrupted", limit=25)

    assert artifacts.items[0].artifact_id == "report"
    assert artifacts.items[0].version == 3
    assert artifacts.total == 1
    assert deployments[0].deployment_id == "report.production"
    assert deployments[0].artifact_version == 3
    assert runs.items[0].run_id == "run-123"
    assert runs.items[0].status == "interrupted"
    assert runs.next_cursor == "next"
    assert port.calls == [
        (
            "artifacts",
            {"query": "report", "kind": "workflow", "cursor": None, "limit": 10},
        ),
        ("deployments", {}),
        ("runs", {"status": "interrupted", "cursor": None, "limit": 25}),
    ]


@pytest.mark.asyncio
async def test_app_rejects_malformed_existing_object_discovery() -> None:
    """Catch unvalidated wire dictionaries leaking through collection methods."""

    class MalformedPort(_Port):
        async def list_runs(self, **params: Any) -> object:
            return {"runs": [{"run_id": "missing-the-rest"}]}

    app = App._from_port(cast(WorkflowClientPort, MalformedPort()))

    with pytest.raises(InvalidResponse, match="workflow.runs.list"):
        await app.runs()


@pytest.mark.asyncio
async def test_capability_reconstructs_structural_reference() -> None:
    capability = await _app().capability("app.default.search")

    assert capability.ref == CapabilityRef.parse("app.default.search")
    assert capability.ref.source.parts == ("app", "default")


@pytest.mark.asyncio
async def test_capability_reference_keeps_dotted_local_key() -> None:
    capability = await _app(capability_name="app.default.search.v2").capability(
        "app.default.search.v2"
    )

    assert capability.ref.source.parts == ("app", "default")
    assert capability.ref.name == "search.v2"


@pytest.mark.asyncio
async def test_capability_rejects_mismatched_inspection_name() -> None:
    app = _app(capability_name="app.default.other")

    with pytest.raises(InvalidResponse, match="workflow.capabilities.inspect"):
        await app.capability("app.default.search")
