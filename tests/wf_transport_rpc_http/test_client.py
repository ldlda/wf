from __future__ import annotations

import asyncio

import httpx

from wf_api.models import RawWorkflowPlan, TraceRange
from wf_core import END
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app


def _constant_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "client_constant",
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
                            "value": "hello from rpc client",
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


def test_rpc_workflow_client_lists_and_inspects_capabilities(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http_client:
            client = RpcWorkflowApiClient(
                url="http://test/rpc",
                timeout_seconds=5,
                http_client=http_client,
            )
            listed = await client.list_capabilities(source_id="wf.std", limit=5)
            inspected = await client.inspect_capability(
                qualified_name="wf.std.constant"
            )

        assert listed["capabilities"]
        assert inspected["name"] == "wf.std.constant"

    asyncio.run(scenario())


def test_rpc_workflow_client_runs_and_reads_trace(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        await server.api.create_artifact_from_plan(
            artifact_id="client_constant",
            version=1,
            title="Client Constant",
            plan=_constant_plan(),
            outcomes=["ok"],
            source_bindings={"wf.std": "wf.std"},
        )
        await server.api.save_deployment(
            {
                "id": "client_constant.default",
                "artifact_id": "client_constant",
                "artifact_version": 1,
                "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
            }
        )
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http_client:
            client = RpcWorkflowApiClient(
                url="http://test/rpc",
                timeout_seconds=5,
                http_client=http_client,
            )
            run = await client.run_deployment(
                deployment_id="client_constant.default",
                workflow_input={},
                trace_range=TraceRange(start=0, limit=1),
            )
            inspected = await client.inspect_run(run_id=run["run_id"])
            trace = await client.read_run_trace(
                run_id=run["run_id"],
                trace_range=TraceRange(start=0, limit=1),
            )

        assert run["status"] == "completed"
        assert run["output"]["result"] == "hello from rpc client"
        assert inspected["trace_count"] >= 1
        assert len(trace["trace"]) == 1

    asyncio.run(scenario())


def test_rpc_workflow_client_raises_for_rpc_error(tmp_path) -> None:
    async def scenario() -> None:
        server = build_local_static_workflow_server(tmp_path / "store")
        app = create_rpc_app(server)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as http_client:
            client = RpcWorkflowApiClient(
                url="http://test/rpc",
                timeout_seconds=5,
                http_client=http_client,
            )
            try:
                await client.inspect_capability(qualified_name="missing.capability")
            except RuntimeError as exc:
                message = str(exc)
            else:
                raise AssertionError("expected RuntimeError")

        assert "Workflow operation failed" in message
        assert "missing.capability" in message

    asyncio.run(scenario())
