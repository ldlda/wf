from __future__ import annotations

import asyncio
from typing import Any

import httpx

from wf_api.models import RawWorkflowPlan
from wf_core import END
from wf_server import build_local_static_workflow_server
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


def test_rpc_health_and_capability_methods(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
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

        assert health_response.status_code == 200
        assert health_response.json()["status"] == "ok"
        assert health["result"]["status"] == "ok"
        assert listed["result"]["capabilities"]
        assert inspected["result"]["name"] == "wf.std.constant"

    asyncio.run(scenario())


def test_rpc_unknown_method_returns_json_rpc_error(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = await _rpc(client, "workflow.nope", {})

        assert payload["error"]["code"] == -32601
        assert payload["error"]["message"] == "Method not found"

    asyncio.run(scenario())


def test_rpc_draft_artifact_deployment_lifecycle(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
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
                        "source_bindings": {"wf.std": "wf.std"},
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
                        "bindings": [
                            {"logical_source": "wf.std", "concrete_source": "wf.std"}
                        ],
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

    asyncio.run(scenario())


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


def test_rpc_runs_deployment_and_reads_bounded_trace(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        await server.api.create_artifact_from_plan(
            artifact_id="rpc_constant",
            version=1,
            title="RPC Constant",
            plan=_constant_plan(),
            outcomes=["ok"],
            source_bindings={"wf.std": "wf.std"},
        )
        await server.api.save_deployment(
            {
                "id": "rpc_constant.default",
                "artifact_id": "rpc_constant",
                "artifact_version": 1,
                "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
            }
        )

        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
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

    asyncio.run(scenario())
