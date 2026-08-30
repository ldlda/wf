from __future__ import annotations

from typing import Any, cast

import pytest

from wf_authoring import WorkflowBuilder
from wf_client import App, ArtifactRef, EditableWorkflow, RemoteCapability
from wf_client.protocols import WorkflowClientPort
from wf_platform import CapabilityRef


class FakePort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.validate_artifact_plan_result: dict[str, Any] = {
            "status": "valid",
            "diagnostics": [],
            "required_capabilities": [],
            "workflow_dependencies": {},
        }
        self.inspect_artifact_result: dict[str, Any] | None = None

    async def validate_artifact_plan(self, **params: Any) -> object:
        self.calls.append(("validate_artifact_plan", params))
        return self.validate_artifact_plan_result

    async def create_artifact_from_plan(self, **params: Any) -> object:
        self.calls.append(("create_artifact_from_plan", params))
        return {"artifact_id": params["artifact_id"], "version": params["version"], "saved": True}

    async def inspect_artifact(self, **params: Any) -> object:
        self.calls.append(("inspect_artifact", params))
        assert self.inspect_artifact_result is not None
        return self.inspect_artifact_result


def valid_plan(version: int = 1) -> dict[str, Any]:
    return {
        "id": "report",
        "version": version,
        "title": "Report",
        "kind": "workflow",
        "description": None,
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
        "outcomes": ["ok"],
        "plan": {
            "name": "report",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
            "outcomes": ["ok"],
            "output": [{"path": "state.value", "target": "value"}],
            "start": "done",
            "nodes": [{"id": "done", "type": "end", "outcome": "ok"}],
            "edges": [],
        },
        "required_capabilities": [],
        "workflow_dependencies": {},
        "created_from_catalog_version": None,
    }


def remote_plan_without_schema_snapshots(version: int = 1) -> dict[str, Any]:
    payload = valid_plan(version)
    payload["plan"]["nodes"] = [
        {
            "id": "remote",
            "type": "node",
            "node": "app.default.remote",
            "input": [],
            "output": [],
        },
        {"id": "done", "type": "end", "outcome": "ok"},
    ]
    payload["plan"]["start"] = "remote"
    payload["plan"]["edges"] = [
        {"from": "remote", "outcome": "ok", "to": "done"}
    ]
    payload["required_capabilities"] = [
        {
            "ref": {"source": "app.default", "capability_key": "remote"},
            "kind": "node_spec",
            "input_schema_hash": None,
            "input_schema_snapshot": None,
            "output_schema_hash": None,
            "output_schema_snapshot": None,
            "observed_concrete_source": None,
            "observed_at_epoch_ms": None,
        }
    ]
    return payload


def remote_plan_with_real_node_def(version: int = 1) -> dict[str, Any]:
    payload = remote_plan_without_schema_snapshots(version)
    payload["plan"]["node_defs"] = [
        {
            "name": "app.default.remote",
            "input_schema": {
                "type": "object",
                "properties": {"real": {"type": "string"}},
            },
            "output_schema": {"type": "object", "properties": {}},
            "outcomes": ["ok"],
        }
    ]
    return payload


@pytest.mark.asyncio
async def test_validate_stops_before_remote_call_when_local_graph_is_invalid() -> None:
    port = FakePort()
    graph = App._from_port(cast(WorkflowClientPort, port)).new_workflow(
        "invalid",
        input_schema={"type": "object", "properties": {}},
        state_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
    )

    result = await graph.validate()

    assert result.local.ok is False
    assert result.remote_status == "not_run"
    assert port.calls == []


@pytest.mark.asyncio
async def test_validate_runs_local_and_server_validation() -> None:
    port = FakePort()
    graph = App._from_port(cast(WorkflowClientPort, port)).new_workflow(
        "report",
        input_schema={"type": "object", "properties": {}},
        state_schema={"type": "object", "properties": {"value": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"value": {"type": "string"}}},
    )
    done = graph.end("ok", id="done")
    graph.set_entry_point(done)

    result = await graph.validate()

    assert result.ok is True
    assert result.local.ok is True
    assert result.remote_status == "valid"
    assert port.calls[-1][0] == "validate_artifact_plan"


@pytest.mark.asyncio
async def test_edit_and_save_inspects_exact_saved_version() -> None:
    port = FakePort()
    port.inspect_artifact_result = valid_plan(version=1)
    app = App._from_port(cast(WorkflowClientPort, port))

    graph = await app.edit_workflow("report", version=1)
    assert isinstance(graph, WorkflowBuilder)
    assert isinstance(graph, EditableWorkflow)
    assert all(hasattr(graph, name) for name in ("when", "choose", "match", "foreach", "interrupt", "end", "connect", "set_entry_point"))

    port.inspect_artifact_result = valid_plan(version=2)
    saved = await graph.save(version=2)

    create = next(params for operation, params in port.calls if operation == "create_artifact_from_plan")
    assert create["plan"] == valid_plan(version=1)["plan"]
    inspect = [params for operation, params in port.calls if operation == "inspect_artifact"][-1]
    assert inspect == {"artifact_id": "report", "version": 2}
    assert saved.ref == ArtifactRef("report", 2)
    assert str(saved.workflow.output[0].target) == "value"


@pytest.mark.asyncio
async def test_editable_artifact_without_schema_snapshots_remains_saveable() -> None:
    port = FakePort()
    port.inspect_artifact_result = remote_plan_without_schema_snapshots(version=1)
    graph = await App._from_port(cast(WorkflowClientPort, port)).edit_workflow(
        "report", version=1
    )

    result = graph.validate_local()

    assert result.ok is True
    port.inspect_artifact_result = remote_plan_without_schema_snapshots(version=2)
    saved = await graph.save(version=2)
    assert saved.ref == ArtifactRef("report", 2)


@pytest.mark.asyncio
async def test_snapshotless_remote_node_upgrades_to_real_capability_contract() -> None:
    port = FakePort()
    port.inspect_artifact_result = remote_plan_without_schema_snapshots(version=1)
    graph = await App._from_port(cast(WorkflowClientPort, port)).edit_workflow(
        "report", version=1
    )
    capability = RemoteCapability(
        _port=cast(WorkflowClientPort, port),
        ref=CapabilityRef.parse("app.default.remote"),
        qualified_name="app.default.remote",
        description=None,
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("ok",),
        is_async=False,
    )

    replacement = graph.use(capability, id="replacement", input=[], output=[])
    graph.connect(replacement, "ok", "done")

    assert graph.validate_local().ok is True
    assert graph.seeded_node_defs["app.default.remote"].input_schema.properties == {
        "query": {"type": "string"}
    }

    incompatible = RemoteCapability(
        _port=cast(WorkflowClientPort, port),
        ref=CapabilityRef.parse("app.default.remote"),
        qualified_name="app.default.remote",
        description=None,
        input_schema={"type": "object", "properties": {"other": {"type": "string"}}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("ok",),
        is_async=False,
    )
    with pytest.raises(ValueError, match="incompatible duplicate"):
        graph.use(incompatible, id="incompatible", input=[], output=[])


@pytest.mark.asyncio
async def test_real_plan_node_def_remains_authoritative_without_snapshots() -> None:
    port = FakePort()
    port.inspect_artifact_result = remote_plan_with_real_node_def(version=1)
    graph = await App._from_port(cast(WorkflowClientPort, port)).edit_workflow(
        "report", version=1
    )
    incompatible = RemoteCapability(
        _port=cast(WorkflowClientPort, port),
        ref=CapabilityRef.parse("app.default.remote"),
        qualified_name="app.default.remote",
        description=None,
        input_schema={"type": "object", "properties": {"other": {"type": "string"}}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("ok",),
        is_async=False,
    )

    with pytest.raises(ValueError, match="incompatible duplicate"):
        graph.use(incompatible, id="incompatible", input=[], output=[])

    assert graph.seeded_node_defs["app.default.remote"].input_schema.properties == {
        "real": {"type": "string"}
    }
