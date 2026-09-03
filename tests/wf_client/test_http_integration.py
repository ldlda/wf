from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from wf_authoring import input_from, input_path, input_value, output_to, state_path
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
        artifacts = await app.artifacts(query="http_client_proof")
        deployments = await app.deployments()
        runs = await app.runs(status="completed", limit=25)

    assert validation.ok is True
    assert artifact.ref == ArtifactRef("http_client_proof", 1)
    assert run.status == "completed"
    assert run.output == {"value": "hello"}
    assert [(item.artifact_id, item.version) for item in artifacts.items] == [
        ("http_client_proof", 1)
    ]
    assert deployments[0].artifact_id == "http_client_proof"
    assert runs.items[0].run_id == run.run_id


class _ChildInput(BaseModel):
    prompt: str


class _ChildState(BaseModel):
    value: str | None = None


class _ChildOutput(BaseModel):
    value: str


class _ParentInput(BaseModel):
    prompt: str


class _ParentState(BaseModel):
    result: str | None = None


class _ParentOutput(BaseModel):
    result: str


@pytest.mark.asyncio
async def test_http_app_runs_saved_workflow_artifact_as_native_subgraph(
    tmp_path: Path,
) -> None:
    """Catch public-client subgraphs losing exact saved-child resolution."""
    server = build_local_static_workflow_server(tmp_path / "store")
    rpc_app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=rpc_app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as http_client:
        app = App._from_port(
            RpcWorkflowApiClient(url="http://test/rpc", http_client=http_client)
        )
        constant = await app.capability("wf.std.constant")

        child = app.new_workflow(
            "saved_child",
            input_schema=_ChildInput,
            state_schema=_ChildState,
            output_schema=_ChildOutput,
        )
        child_step = child.use(
            constant,
            id="copy_prompt",
            input=[input_from(input_path("prompt"), "value")],
            output=[output_to("value", state_path("value"))],
        )
        child.set_entry_point(child_step)
        child.connect(child_step, "ok", child.end("ok", id="child_done"))
        child.set_output([input_from(state_path("value"), "value")])
        child_artifact = await child.save(version=1, title="Saved child")

        parent = app.new_workflow(
            "saved_parent",
            input_schema=_ParentInput,
            state_schema=_ParentState,
            output_schema=_ParentOutput,
        )
        child_boundary = parent.subgraph(
            child_artifact,
            id="run_child",
            input=[input_from(input_path("prompt"), "prompt")],
            output=[output_to("value", state_path("result"))],
        )
        parent.set_entry_point(child_boundary)
        parent.connect(child_boundary, "ok", parent.end("ok", id="parent_done"))
        parent.set_output([input_from(state_path("result"), "result")])
        parent_artifact = await parent.save(version=1, title="Saved parent")

        deployment = await parent_artifact.deploy("saved_parent.production")
        readiness = await deployment.validate()
        run = await deployment.run({"prompt": "hello from parent"})

    assert readiness.runnable is True
    assert parent_artifact.workflow_dependencies == {"saved_child": 1}
    assert run.status == "completed"
    assert run.output == {"result": "hello from parent"}
