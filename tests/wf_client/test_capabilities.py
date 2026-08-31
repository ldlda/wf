from __future__ import annotations

from typing import Any, cast

import pytest

from wf_client import CapabilityResult, RemoteCapability
from wf_client.errors import InvalidResponse
from wf_client.protocols import WorkflowClientPort
from wf_platform import CapabilityRef, SourceRef


def _inspect_payload() -> dict[str, Any]:
    return {
        "name": "app.default.search",
        "source_id": "app.default",
        "kind": "node_spec",
        "description": "Search things",
        "outcomes": ["ok", "error"],
        "is_async": True,
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {"results": {"type": "array"}},
            "required": ["results"],
        },
        "wrapper_hints": {},
        "accepts_context": False,
    }


class _Port:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result_qualified_name = "app.default.search"
        self.result_source_id = "app.default"
        self.result_kind = "node_spec"
        self.result_deployment_id: str | None = None

    async def call_capability(self, **params: Any) -> object:
        self.calls.append(params)
        return {
            "qualified_name": self.result_qualified_name,
            "source_id": self.result_source_id,
            "kind": self.result_kind,
            "deployment_id": self.result_deployment_id,
            "outcome": "ok",
            "output": {"results": ["one"]},
            "diagnostics": [],
        }


def _port() -> WorkflowClientPort:
    return cast(WorkflowClientPort, _Port())


def test_remote_capability_preserves_dotted_local_key() -> None:
    capability = RemoteCapability(
        _port=_port(),
        ref=CapabilityRef(source=SourceRef.parse("app.default"), name="search.v2"),
        qualified_name="app.default.search.v2",
        description=None,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        outcomes=("ok",),
        is_async=False,
    )

    assert capability.ref.name == "search.v2"
    assert capability.node_def().name == "app.default.search.v2"


@pytest.mark.asyncio
async def test_remote_capability_is_callable_and_validates_result() -> None:
    port = _Port()
    capability = RemoteCapability(
        _port=cast(WorkflowClientPort, port),
        ref=CapabilityRef.parse("app.default.search"),
        qualified_name="app.default.search",
        description=None,
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        output_schema={"type": "object", "required": ["results"]},
        outcomes=("ok",),
        is_async=False,
    )

    result = await capability(query="workflow")

    assert isinstance(result, CapabilityResult)
    assert result.output == {"results": ["one"]}
    assert port.calls == [
        {
            "qualified_name": "app.default.search",
            "payload": {"query": "workflow"},
            "deployment_id": None,
        }
    ]


@pytest.mark.asyncio
async def test_remote_capability_rejects_mixed_payload_forms() -> None:
    capability = RemoteCapability(
        _port=_port(),
        ref=CapabilityRef.parse("app.default.search"),
        qualified_name="app.default.search",
        description=None,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        outcomes=("ok",),
        is_async=False,
    )

    with pytest.raises(TypeError, match="not both"):
        await capability({"query": "workflow"}, query="again")


@pytest.mark.asyncio
async def test_remote_capability_rejects_mismatched_call_source() -> None:
    port = _Port()
    port.result_source_id = "other.source"
    capability = RemoteCapability(
        _port=cast(WorkflowClientPort, port),
        ref=CapabilityRef.parse("app.default.search"),
        qualified_name="app.default.search",
        description=None,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        outcomes=("ok",),
        is_async=False,
    )

    with pytest.raises(InvalidResponse, match="workflow.capabilities.call"):
        await capability({})


@pytest.mark.asyncio
async def test_node_capability_rejects_unexpected_result_deployment() -> None:
    port = _Port()
    port.result_deployment_id = "unexpected"
    capability = RemoteCapability(
        _port=cast(WorkflowClientPort, port),
        ref=CapabilityRef.parse("app.default.search"),
        qualified_name="app.default.search",
        description=None,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        outcomes=("ok",),
        is_async=False,
    )

    with pytest.raises(InvalidResponse, match="workflow.capabilities.call"):
        await capability.call({}, deployment_id="ignored-by-node-spec")


@pytest.mark.asyncio
async def test_wrapper_capability_requires_exact_result_deployment() -> None:
    port = _Port()
    port.result_qualified_name = "workflow.report.v1"
    port.result_source_id = "workflow"
    port.result_kind = "wrapper_artifact"
    port.result_deployment_id = "other.deployment"
    capability = RemoteCapability(
        _port=cast(WorkflowClientPort, port),
        ref=CapabilityRef(source=SourceRef.parse("workflow"), name="report.v1"),
        qualified_name="workflow.report.v1",
        description=None,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        outcomes=("ok",),
        is_async=False,
        _kind="wrapper_artifact",
    )

    with pytest.raises(InvalidResponse, match="workflow.capabilities.call"):
        await capability.call({}, deployment_id="report.production")


def test_remote_capability_rejects_invalid_inspected_schema() -> None:
    with pytest.raises(InvalidResponse, match="invalid JSON Schema"):
        RemoteCapability(
            _port=_port(),
            ref=CapabilityRef.parse("app.default.search"),
            qualified_name="app.default.search",
            description=None,
            input_schema={"type": "not-a-json-schema-type"},
            output_schema={"type": "object"},
            outcomes=("ok",),
            is_async=False,
        )
