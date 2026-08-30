from __future__ import annotations

from typing import Any, cast

import httpx
import pytest

from wf_client import App, CapabilitySummary, Page
from wf_client.errors import InvalidResponse
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
