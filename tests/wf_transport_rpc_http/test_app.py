from __future__ import annotations

from typing import Any

import httpx

from wf_api.models import RawWorkflowPlan
from wf_config import WorkflowConfigFile
from wf_core import END
from wf_server import build_local_static_workflow_server
from wf_server.config import build_workflow_server_from_workflow_config
from wf_transport_rpc_http.app import create_rpc_app


async def _rpc(
    client: httpx.AsyncClient, method: str, params: dict[str, Any]
) -> dict[str, Any]:
    response = await client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": "test", "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


async def test_rpc_health_and_capability_methods(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health_response = await client.get("/healthz")
        health = await _rpc(client, "workflow.health", {})
        listed = await _rpc(
            client,
            "workflow.capabilities.list",
            {"source_id": "wf.std", "limit": 10},
        )
        inspected = await _rpc(
            client,
            "workflow.capabilities.inspect",
            {"qualified_name": "wf.std.constant"},
        )
        called = await _rpc(
            client,
            "workflow.capabilities.call",
            {
                "qualified_name": "wf.std.constant",
                "payload": {"value": "hello direct rpc"},
            },
        )

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert health["result"]["status"] == "ok"
    assert listed["result"]["capabilities"]
    assert {
        capability["source_id"] for capability in listed["result"]["capabilities"]
    } == {"wf.std"}
    assert inspected["result"]["name"] == "wf.std.constant"
    assert called["result"]["qualified_name"] == "wf.std.constant"
    assert called["result"]["kind"] == "node_spec"
    assert called["result"]["outcome"] == "ok"
    assert called["result"]["output"] == {"value": "hello direct rpc"}


async def test_rpc_unknown_method_returns_json_rpc_error(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(client, "workflow.nope", {})

    assert payload["error"]["code"] == -32601
    assert payload["error"]["message"] == "Method not found"


async def test_rpc_app_mounts_configured_rpc_path(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server, rpc_path="/workflow-rpc")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/workflow-rpc",
            json={
                "jsonrpc": "2.0",
                "id": "test",
                "method": "workflow.health",
                "params": {},
            },
        )

    assert response.status_code == 200
    assert response.json()["result"]["status"] == "ok"


async def test_rpc_draft_artifact_deployment_lifecycle(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        draft_ws = await _rpc(
            client,
            "workflow.drafts.create_from_capability",
            {
                "workspace_id": "constant_ws",
                "capability_name": "wf.std.constant",
                "name": "constant_workflow",
                "title": "Constant Workflow",
                "input_map": {},
                "output_map": {"value": "state.result"},
            },
        )

        draft = {
            "name": "rpc_constant",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "reducer": "wf.std.replace"}
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
            "start": "constant",
            "steps": {
                "constant": {
                    "use": "wf.std.constant",
                    "input": [
                        {
                            "value": "hello over rpc",
                            "target": {"root": "local", "parts": ["value"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["value"]},
                            "target": {"root": "state", "parts": ["result"]},
                        }
                    ],
                }
            },
            "routes": {"constant": {"ok": "__end__"}},
            "output": [
                {
                    "path": {"root": "state", "parts": ["result"]},
                    "target": {"root": "local", "parts": ["result"]},
                }
            ],
        }

        validate_draft = await _rpc(
            client,
            "workflow.drafts.validate",
            {"draft": draft},
        )
        compiled_plan = validate_draft["result"]["compiled_plan"]
        artifact = await _rpc(
            client,
            "workflow.artifacts.save",
            {
                "artifact": {
                    "id": "constant_rpc",
                    "version": 1,
                    "kind": "wrapper",
                    "title": "Constant RPC",
                    "input_schema": {"type": "object", "properties": {}},
                    "output_schema": {
                        "type": "object",
                        "properties": {"result": {"type": "string"}},
                        "required": ["result"],
                    },
                    "outcomes": ["ok"],
                    "required_capabilities": {},
                    "source_bindings": {},
                    "plan": compiled_plan,
                },
            },
        )
        deployment = await _rpc(
            client,
            "workflow.deployments.save",
            {
                "deployment": {
                    "id": "constant_rpc.default",
                    "artifact_id": "constant_rpc",
                    "artifact_version": 1,
                    "bindings": {},
                },
            },
        )
        validate_deployment = await _rpc(
            client,
            "workflow.deployments.validate",
            {"deployment_id": "constant_rpc.default"},
        )

    assert draft_ws["result"]["workspace_id"] == "constant_ws"
    assert validate_draft["result"]["status"] == "valid"
    assert artifact["result"]["artifact_id"] == "constant_rpc"
    assert deployment["result"]["deployment_id"] == "constant_rpc.default"
    assert validate_deployment["result"]["status"] == "runnable"


async def test_rpc_artifact_and_deployment_catalog_methods(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="rpc_lifecycle",
        version=1,
        title="RPC Lifecycle",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={},
    )
    await server.api.save_deployment(
        {
            "id": "rpc_lifecycle.default",
            "artifact_id": "rpc_lifecycle",
            "artifact_version": 1,
            "bindings": {},
        }
    )

    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        listed_artifacts = await _rpc(client, "workflow.artifacts.list", {})
        inspected_artifact = await _rpc(
            client,
            "workflow.artifacts.inspect",
            {"artifact_id": "rpc_lifecycle", "version": 1},
        )
        listed_deployments = await _rpc(client, "workflow.deployments.list", {})
        inspected_deployment = await _rpc(
            client,
            "workflow.deployments.inspect",
            {"deployment_id": "rpc_lifecycle.default"},
        )
        deleted = await _rpc(
            client,
            "workflow.deployments.delete",
            {"deployment_id": "rpc_lifecycle.default"},
        )

    assert listed_artifacts["result"]["nodes"]
    assert inspected_artifact["result"]["id"] == "rpc_lifecycle"
    assert listed_deployments["result"]["deployments"]
    assert inspected_deployment["result"]["id"] == "rpc_lifecycle.default"
    assert deleted["result"]["deployment_id"] == "rpc_lifecycle.default"


async def test_rpc_draft_workspace_methods(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "remote_ws",
                "capability_name": "wf.std.constant",
                "name": "remote_constant",
                "title": "Remote Constant",
                "input_map": {},
                "output_map": {"value": "state.result"},
            },
        )
        listed = await _rpc(client, "workflow.draft_workspaces.list", {})
        fetched = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "remote_ws"},
        )
        validated = await _rpc(
            client,
            "workflow.draft_workspaces.validate",
            {"workspace_id": "remote_ws"},
        )
        patched = await _rpc(
            client,
            "workflow.draft_workspaces.patch",
            {
                "workspace_id": "remote_ws",
                "revision": created["result"]["revision"],
                "patch": [
                    {"op": "replace", "path": "/name", "value": "remote_renamed"}
                ],
            },
        )
        artifact = await _rpc(
            client,
            "workflow.draft_workspaces.create_artifact",
            {
                "workspace_id": "remote_ws",
                "artifact_id": "remote_artifact",
                "version": 1,
                "title": "Remote Artifact",
                "outcomes": ["ok"],
                "kind": "workflow",
                "source_bindings": {},
            },
        )

    assert created["result"]["workspace_id"] == "remote_ws"
    assert listed["result"]["workspaces"]
    assert fetched["result"]["workspace_id"] == "remote_ws"
    assert validated["result"]["status"] in {"valid", "invalid"}
    assert patched["result"]["revision"] == created["result"]["revision"] + 1
    assert artifact["result"]["artifact_id"] == "remote_artifact"


async def test_rpc_draft_workspace_delete(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "delete-me",
                "capability_name": "wf.std.constant",
                "name": "delete_me_ws",
            },
        )
        payload = await _rpc(
            client,
            "workflow.draft_workspaces.delete",
            {"workspace_id": "delete-me"},
        )
        assert payload["result"]["workspace_id"] == "delete-me"
        assert payload["result"]["deleted"] is True


async def test_rpc_artifact_delete(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="delete_artifact",
        version=1,
        title="Delete Me",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={},
    )

    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.artifacts.delete",
            {"artifact_id": "delete_artifact", "version": 1},
        )
        assert payload["result"]["artifact_id"] == "delete_artifact"
        assert payload["result"]["version"] == 1
        assert payload["result"]["deleted"] is True
        assert payload["result"]["blocked_by_deployments"] == []


def _constant_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "rpc_constant",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "reducer": "wf.std.replace"}
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {"result": {"type": "string"}},
                "required": ["result"],
            },
            "outcomes": ["ok"],
            "start": "constant",
            "nodes": [
                {
                    "id": "constant",
                    "type": "node",
                    "node": "wf.std.constant",
                    "input": [
                        {
                            "value": "hello over rpc",
                            "target": {"root": "local", "parts": ["value"]},
                        }
                    ],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["value"]},
                            "target": {"root": "state", "parts": ["result"]},
                        }
                    ],
                }
            ],
            "edges": [{"from": "constant", "outcome": "ok", "to": END}],
            "output": [
                {
                    "path": {"root": "state", "parts": ["result"]},
                    "target": {"root": "local", "parts": ["result"]},
                }
            ],
        }
    )


async def test_rpc_runs_deployment_and_reads_bounded_trace(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="rpc_constant",
        version=1,
        title="RPC Constant",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={},
    )
    await server.api.save_deployment(
        {
            "id": "rpc_constant.default",
            "artifact_id": "rpc_constant",
            "artifact_version": 1,
            "bindings": {},
        }
    )

    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        run = await _rpc(
            client,
            "workflow.runs.start",
            {
                "deployment_id": "rpc_constant.default",
                "workflow_input": {},
                "trace_range": {"start": 0, "limit": 1},
            },
        )
        inspected = await _rpc(
            client,
            "workflow.runs.inspect",
            {"run_id": run["result"]["run_id"]},
        )
        trace = await _rpc(
            client,
            "workflow.runs.trace",
            {
                "run_id": run["result"]["run_id"],
                "trace_range": {"start": 0, "limit": 1},
            },
        )

    assert run["result"]["status"] == "completed"
    assert run["result"]["output"]["result"] == "hello over rpc"
    assert "trace" not in inspected["result"]
    assert inspected["result"]["trace_count"] >= 1
    assert trace["result"]["trace_start"] == 0
    assert trace["result"]["trace_limit"] == 1
    assert len(trace["result"]["trace"]) == 1


async def test_rpc_run_list_method(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="list_runs_rpc",
        version=1,
        title="List Runs RPC",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={},
    )
    await server.api.save_deployment(
        {
            "id": "list_runs_rpc.default",
            "artifact_id": "list_runs_rpc",
            "artifact_version": 1,
            "bindings": {},
        }
    )
    started = await server.api.run_deployment(
        deployment_id="list_runs_rpc.default",
        workflow_input={},
    )

    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.runs.list",
            {"status": "completed", "limit": 10},
        )

    assert payload["result"]["total"] == 1
    assert payload["result"]["runs"][0]["run_id"] == started["run_id"]
    assert payload["result"]["runs"][0]["deployment_id"] == "list_runs_rpc.default"
    assert "trace" not in payload["result"]["runs"][0]


async def test_rpc_calls_python_source_capability(tmp_path) -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "python",
                        "id": "local.ops",
                        "module": "tests.fixtures.python_source_ops",
                        "registry": "registry",
                    }
                ],
            },
        }
    )
    server = build_workflow_server_from_workflow_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await _rpc(
            client,
            "workflow.capabilities.list",
            {"source_id": "local.ops", "limit": 10},
        )
        called = await _rpc(
            client,
            "workflow.capabilities.call",
            {
                "qualified_name": "local.ops.echo",
                "payload": {"text": "hello python"},
            },
        )

    assert listed["result"]["total"] == 2
    assert called["result"]["outcome"] == "ok"
    assert called["result"]["output"] == {"echoed": "hello python"}


async def test_rpc_runs_workflow_from_python_source_capability(tmp_path) -> None:
    config = WorkflowConfigFile.model_validate(
        {
            "version": 1,
            "server": {
                "store": {"kind": "filesystem", "root": str(tmp_path / "store")},
                "sources": [
                    {
                        "kind": "python",
                        "id": "local.ops",
                        "module": "tests.fixtures.python_source_ops",
                        "registry": "registry",
                    }
                ],
            },
        }
    )
    server = build_workflow_server_from_workflow_config(config)
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "python_echo_ws",
                "capability_name": "local.ops.echo",
                "name": "python_echo",
                "title": "Python Echo",
            },
        )
        artifact = await _rpc(
            client,
            "workflow.draft_workspaces.create_artifact",
            {
                "workspace_id": "python_echo_ws",
                "artifact_id": "python_echo",
                "version": 1,
                "title": "Python Echo",
                "outcomes": ["ok"],
                "kind": "workflow",
                "source_bindings": {"local.ops": "local.ops"},
            },
        )
        deployment = await _rpc(
            client,
            "workflow.deployments.save",
            {
                "deployment": {
                    "id": "python_echo.default",
                    "artifact_id": "python_echo",
                    "artifact_version": 1,
                    "bindings": [
                        {"logical_source": "local.ops", "concrete_source": "local.ops"},
                    ],
                }
            },
        )
        run = await _rpc(
            client,
            "workflow.runs.start",
            {
                "deployment_id": "python_echo.default",
                "workflow_input": {"text": "hello workflow"},
                "trace_range": {"start": 0, "limit": 5},
            },
        )

    assert artifact["result"]["artifact_id"] == "python_echo"
    assert deployment["result"]["deployment_id"] == "python_echo.default"
    assert run["result"]["outcome"] == "ok"
    assert run["result"]["output"] == {"echoed": "hello workflow"}


async def test_rpc_create_artifact_from_plan(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.artifacts.create_from_plan",
            {
                "artifact_id": "rpc_plan",
                "version": 1,
                "title": "RPC Plan",
                "plan": _constant_plan().model_dump(mode="json", by_alias=True),
                "outcomes": ["ok"],
                "source_bindings": {},
            },
        )
        inspected = await _rpc(
            client,
            "workflow.artifacts.inspect",
            {"artifact_id": "rpc_plan", "version": 1},
        )

    assert created["result"]["artifact_id"] == "rpc_plan"
    assert created["result"]["version"] == 1
    assert inspected["result"]["id"] == "rpc_plan"
    assert inspected["result"]["plan"]["name"] == "rpc_constant"


async def test_rpc_draft_workspace_focused_edit_methods(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "focused_ws",
                "capability_name": "wf.std.constant",
                "name": "focused_initial",
            },
        )
        assert created["result"]["workspace_id"] == "focused_ws"

        named = await _rpc(
            client,
            "workflow.draft_workspaces.set_name",
            {
                "workspace_id": "focused_ws",
                "revision": 1,
                "name": "focused_renamed",
            },
        )
        routed = await _rpc(
            client,
            "workflow.draft_workspaces.set_route",
            {
                "workspace_id": "focused_ws",
                "revision": 2,
                "step_id": "call",
                "outcome": "ok",
                "target": "__end__",
            },
        )
        input_mapped = await _rpc(
            client,
            "workflow.draft_workspaces.set_step_input_map",
            {
                "workspace_id": "focused_ws",
                "revision": 3,
                "step_id": "call",
                "input_map": {"input.value": "value"},
            },
        )
        output_mapped = await _rpc(
            client,
            "workflow.draft_workspaces.set_step_output_map",
            {
                "workspace_id": "focused_ws",
                "revision": 4,
                "step_id": "call",
                "output_map": {"value": "state.value"},
            },
        )
        fetched = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "focused_ws", "include_draft": True},
        )

    assert named["result"]["revision"] == 2
    assert routed["result"]["revision"] == 3
    assert input_mapped["result"]["revision"] == 4
    assert output_mapped["result"]["revision"] == 5
    draft = fetched["result"]["draft"]
    assert draft["name"] == "focused_renamed"
    assert draft["routes"]["call"]["ok"] == "__end__"
    assert draft["steps"]["call"]["input"] == [
        {
            "target": {"root": "local", "parts": ["value"]},
            "path": {"root": "input", "parts": ["value"]},
        }
    ]
    assert draft["steps"]["call"]["output"] == [
        {
            "source": {"root": "local", "parts": ["value"]},
            "target": {"root": "state", "parts": ["value"]},
        }
    ]


async def test_rpc_diagnoses_source(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.sources.diagnose",
            {"source_id": "wf.std"},
        )

    assert payload["result"]["source_id"] == "wf.std"
    assert payload["result"]["status"] == "unknown"
