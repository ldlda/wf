from __future__ import annotations

import httpx

from wf_api.models import RawWorkflowPlan, TraceRange
from wf_api.surface import WorkflowDraftSurface
from wf_core import END
from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import RpcWorkflowApiClient, create_rpc_app
from wf_transport_rpc_http.client.sources import RpcSourceAdminClientMixin


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


async def test_rpc_workflow_client_lists_and_inspects_capabilities(tmp_path) -> None:
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
        inspected = await client.inspect_capability(qualified_name="wf.std.constant")
        called = await client.call_capability(
            qualified_name="wf.std.constant",
            payload={"value": "hello rpc client"},
        )

    assert listed["capabilities"]
    assert {capability["source_id"] for capability in listed["capabilities"]} == {
        "wf.std"
    }
    assert inspected["name"] == "wf.std.constant"
    assert called["qualified_name"] == "wf.std.constant"
    assert called["outcome"] == "ok"
    assert called["output"] == {"value": "hello rpc client"}


async def test_rpc_workflow_client_lists_and_inspects_sources(tmp_path) -> None:
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
        listed = await client.list_sources(limit=10)
        inspected = await client.inspect_source(source_id="wf.std")

    source_ids = {source["id"] for source in listed["sources"]}
    assert "wf.std" in source_ids
    assert inspected["id"] == "wf.std"


async def test_rpc_workflow_client_reads_admin_state(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    server.events.record_workflow_event(
        "workflow_test_event",
        capability_id="workflow.demo.v1",
        payload={"ok": True},
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
        connections = await client.list_connections()
        statuses = await client.get_connection_statuses()
        events = await client.list_events()

    assert connections == {"connections": [], "total": 0}
    assert statuses == {"statuses": [], "total": 0}
    assert events["total"] == 1
    assert events["events"][0]["kind"] == "workflow_test_event"


async def test_rpc_workflow_client_runs_and_reads_trace(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="client_constant",
        version=1,
        title="Client Constant",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={},
    )
    await server.api.save_deployment(
        {
            "id": "client_constant.default",
            "artifact_id": "client_constant",
            "artifact_version": 1,
            "bindings": {},
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


async def test_rpc_workflow_client_raises_for_rpc_error(tmp_path) -> None:
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


async def test_rpc_workflow_client_lists_and_inspects_artifacts(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="client_art",
        version=1,
        title="Client Art",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={},
    )
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc", timeout_seconds=5, http_client=http_client
        )
        listed = await client.list_artifacts()
        inspected = await client.inspect_artifact(artifact_id="client_art", version=1)

    assert listed["nodes"]
    assert inspected["id"] == "client_art"


async def test_rpc_workflow_client_lists_inspects_validates_and_deletes_deployments(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="client_deploy_art",
        version=1,
        title="Client Deploy Art",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={},
    )
    await server.api.save_deployment(
        {
            "id": "client_deploy_art.default",
            "artifact_id": "client_deploy_art",
            "artifact_version": 1,
            "bindings": {},
        }
    )
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc", timeout_seconds=5, http_client=http_client
        )
        listed = await client.list_deployments()
        inspected = await client.inspect_deployment(
            deployment_id="client_deploy_art.default"
        )
        validated = await client.validate_deployment(
            deployment_id="client_deploy_art.default"
        )
        deleted = await client.delete_deployment(
            deployment_id="client_deploy_art.default"
        )

    assert listed["deployments"]
    assert inspected["id"] == "client_deploy_art.default"
    assert validated["status"] == "runnable"
    assert deleted["deployment_id"] == "client_deploy_art.default"


async def test_rpc_workflow_client_draft_workspace_lifecycle(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc", timeout_seconds=5, http_client=http_client
        )
        created = await client.create_draft_workspace_from_capability(
            workspace_id="client_ws",
            capability_name="wf.std.constant",
            name="client_constant",
            title="Client Constant",
            input_map={},
            output_map={"value": "state.result"},
        )
        listed = await client.list_draft_workspaces()
        fetched = await client.get_draft_workspace(workspace_id="client_ws")
        validated = await client.validate_draft_workspace(workspace_id="client_ws")
        patched = await client.patch_draft_workspace(
            workspace_id="client_ws",
            revision=created["revision"],
            patch=[{"op": "replace", "path": "/name", "value": "client_renamed"}],
        )
        artifact = await client.create_artifact_from_workspace(
            workspace_id="client_ws",
            artifact_id="client_ws_art",
            version=1,
            title="Client WS Art",
            outcomes=("ok",),
            kind="workflow",
            source_bindings={},
        )

    assert created["workspace_id"] == "client_ws"
    assert listed["workspaces"]
    assert fetched["workspace_id"] == "client_ws"
    assert validated["status"] in {"valid", "invalid"}
    assert patched["revision"] == created["revision"] + 1
    assert artifact["artifact_id"] == "client_ws_art"


def test_rpc_client_satisfies_draft_surface_static_shape() -> None:
    _: type[WorkflowDraftSurface] = RpcWorkflowApiClient


async def test_rpc_workflow_client_deletes_draft_workspace(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc", timeout_seconds=5, http_client=http_client
        )
        await client.create_draft_workspace_from_capability(
            workspace_id="delete-me",
            capability_name="wf.std.constant",
            name="delete_me_ws",
        )
        deleted = await client.delete_draft_workspace(workspace_id="delete-me")
        assert deleted["workspace_id"] == "delete-me"
        assert deleted["deleted"] is True

        deleted_again = await client.delete_draft_workspace(workspace_id="delete-me")
        assert deleted_again["workspace_id"] == "delete-me"
        assert deleted_again["deleted"] is False


async def test_rpc_workflow_client_deletes_artifact(tmp_path) -> None:
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
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc", timeout_seconds=5, http_client=http_client
        )
        deleted = await client.delete_artifact(artifact_id="delete_artifact", version=1)

    assert deleted["deleted"] is True
    assert deleted["artifact_id"] == "delete_artifact"
    assert deleted["version"] == 1


async def test_rpc_client_lists_runs(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="client_list_runs",
        version=1,
        title="Client List Runs",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={},
    )
    await server.api.save_deployment(
        {
            "id": "client_list_runs.default",
            "artifact_id": "client_list_runs",
            "artifact_version": 1,
            "bindings": {},
        }
    )
    started = await server.api.run_deployment(
        deployment_id="client_list_runs.default",
        workflow_input={},
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
        listed = await client.list_runs(status="completed", limit=5)

    assert listed["total"] == 1
    assert listed["runs"][0]["run_id"] == started["run_id"]


async def test_rpc_client_creates_artifact_from_plan(tmp_path) -> None:
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
        created = await client.create_artifact_from_plan(
            artifact_id="client_plan",
            version=1,
            title="Client Plan",
            plan=_constant_plan().model_dump(mode="json", by_alias=True),
            outcomes=("ok",),
            source_bindings={},
        )
        inspected = await client.inspect_artifact(
            artifact_id="client_plan",
            version=1,
        )

    assert created["artifact_id"] == "client_plan"
    assert inspected["id"] == "client_plan"


async def test_rpc_client_draft_workspace_focused_edit_methods(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        client = RpcWorkflowApiClient(
            url="http://test/rpc",
            timeout_seconds=5,
            http_client=http_client,
        )
        await client.create_draft_workspace_from_capability(
            workspace_id="client_focused_ws",
            capability_name="wf.std.constant",
            name="client_initial",
        )

        named = await client.set_draft_name(
            workspace_id="client_focused_ws",
            revision=1,
            name="client_renamed",
        )
        routed = await client.set_draft_route(
            workspace_id="client_focused_ws",
            revision=2,
            step_id="call",
            outcome="ok",
            target="__end__",
        )
        input_mapped = await client.set_step_input_map(
            workspace_id="client_focused_ws",
            revision=3,
            step_id="call",
            input_map={"input.value": "value"},
        )
        output_mapped = await client.set_step_output_map(
            workspace_id="client_focused_ws",
            revision=4,
            step_id="call",
            output_map={"value": "state.value"},
        )
        input_merged = await client.set_step_input_map(
            workspace_id="client_focused_ws",
            revision=5,
            step_id="call",
            input_map={"input.extra": "extra"},
            merge=True,
        )
        output_merged = await client.set_step_output_map(
            workspace_id="client_focused_ws",
            revision=6,
            step_id="call",
            output_map={"extra": "state.extra"},
            merge=True,
        )

    assert named["revision"] == 2
    assert routed["revision"] == 3
    assert input_mapped["revision"] == 4
    assert output_mapped["revision"] == 5
    assert input_merged["revision"] == 6
    assert output_merged["revision"] == 7


async def test_rpc_client_diagnoses_source(tmp_path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class Client(RpcSourceAdminClientMixin):
        async def _call(self, method: str, params: dict[str, object]):
            calls.append((method, params))
            return {"source_id": params["source_id"], "status": "ok"}

    payload = await Client().diagnose_source(source_id="demo.personal")

    assert payload == {"source_id": "demo.personal", "status": "ok"}
    assert calls == [("workflow.sources.diagnose", {"source_id": "demo.personal"})]
