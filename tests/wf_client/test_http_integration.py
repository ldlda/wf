from __future__ import annotations

import httpx
import pytest

from wf_authoring import input_from, input_value, output_to, state_path
from wf_client import App, ArtifactRef
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app


@pytest.mark.asyncio
async def test_http_app_calls_authors_saves_deploys_and_runs(tmp_path) -> None:
    """Prove the public client lifecycle against the real JSON-RPC ASGI app."""
    server = build_local_static_workflow_server(tmp_path / "store")
    rpc_app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=rpc_app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as http_client:
        app = App._from_port(
            RpcWorkflowApiClient(
                url="http://test/rpc",
                http_client=http_client,
            )
        )
        constant = await app.capability("wf.std.constant")
        graph = app.new_workflow(
            "http_client_proof",
            input_schema={"type": "object", "properties": {}},
            state_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        )
        step = graph.use(
            constant,
            id="constant",
            input=[input_value("value", "hello")],
            output=[output_to("value", state_path("value"))],
        )
        end = graph.end("ok", id="end_ok")
        graph.set_entry_point(step)
        graph.connect(step, "ok", end)
        graph.set_output([input_from(state_path("value"), "value")])

        validation = await graph.validate()
        artifact = await graph.save(version=1, title="HTTP client proof")
        run = await artifact.run({})

    assert validation.ok is True
    assert artifact.ref == ArtifactRef("http_client_proof", 1)
    assert run.status == "completed"
    assert run.output == {"value": "hello"}
