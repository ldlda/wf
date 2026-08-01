from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from wf_api.models import RawWorkflowPlan
from wf_config import WorkflowConfigFile
from wf_core import END
from wf_server import build_local_static_workflow_server
from wf_server.config import build_workflow_server_from_workflow_config
from wf_transport_rpc_http.app import create_rpc_app
from wf_transport_rpc_http.models import (
    AddDraftStepParams,
    AddStepFromCapabilityParams,
    SetDraftContractParams,
    UpdateCapabilityStepParams,
)


async def _rpc(
    client: httpx.AsyncClient, method: str, params: dict[str, Any]
) -> dict[str, Any]:
    response = await client.post(
        "/rpc",
        json={"jsonrpc": "2.0", "id": "test", "method": method, "params": params},
    )
    assert response.status_code == 200
    return response.json()


def _rpc_constant_draft() -> dict[str, Any]:
    """Return the canonical keyed draft shared by stateless RPC tests."""
    return {
        "name": "rpc_constant",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {
            "type": "object",
            "properties": {"result": {"type": "string", "reducer": "wf.std.replace"}},
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


def test_update_capability_step_params_preserve_nested_field_presence() -> None:
    params = UpdateCapabilityStepParams.model_validate(
        {
            "workspace_id": "report",
            "revision": 4,
            "step_id": "publish",
            "update": {"desc": None, "retry": 0},
        }
    )

    assert params.update.model_fields_set == {"desc", "retry"}
    assert params.update.desc is None
    assert params.update.retry == 0


@pytest.mark.parametrize(
    "update",
    [
        {},
        {"input": None},
        {"retry": -1},
        {"timeout_seconds": 0},
        {"unknown": True},
    ],
)
def test_update_capability_step_params_reject_invalid_update(
    update: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        UpdateCapabilityStepParams.model_validate(
            {
                "workspace_id": "report",
                "revision": 4,
                "step_id": "publish",
                "update": update,
            }
        )


def test_add_step_from_capability_params_preserve_canonical_inputs() -> None:
    params = AddStepFromCapabilityParams.model_validate(
        {
            "workspace_id": "report",
            "revision": 1,
            "step_id": "publish",
            "capability_name": "demo.report",
            "desc": "Publish report",
            "retry": 0,
            "timeout_seconds": 30,
            "input_bindings": [
                {"path": "state.report.title", "target": "request.title"},
                {"value": "markdown", "target": "request.format"},
            ],
        }
    )

    assert params.desc == "Publish report"
    assert params.retry == 0
    assert params.timeout_seconds == 30
    assert [
        binding.model_dump(mode="json") for binding in params.input_bindings or []
    ] == [
        {"path": "state.report.title", "target": "request.title"},
        {"value": "markdown", "target": "request.format"},
    ]


def test_add_step_from_capability_params_reject_both_input_forms() -> None:
    with pytest.raises(ValidationError, match="mutually exclusive"):
        AddStepFromCapabilityParams.model_validate(
            {
                "workspace_id": "report",
                "revision": 1,
                "step_id": "publish",
                "capability_name": "demo.report",
                "input_map": {},
                "input_bindings": [],
            }
        )


def test_set_draft_contract_params_reject_whitespace_duplicate_outcomes() -> None:
    with pytest.raises(ValidationError, match="unique"):
        SetDraftContractParams.model_validate(
            {
                "workspace_id": "report",
                "revision": 1,
                "outcomes": ["ok", " ok "],
            }
        )


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


async def test_rpc_source_discovery_preserves_inventory_contracts(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await _rpc(client, "workflow.sources.list", {"limit": 10})
        inspected = await _rpc(
            client,
            "workflow.sources.inspect",
            {"source_id": "wf.std"},
        )
        diagnosed = await _rpc(
            client,
            "workflow.sources.diagnose",
            {"source_id": "wf.std"},
        )

    source = next(row for row in listed["result"]["sources"] if row["id"] == "wf.std")
    assert source["kind"] == "system"
    assert source["preview"]["node_specs"]
    inventory = inspected["result"]["capabilities"]
    assert inventory["node_spec_details"][0]["input_schema"]["type"] == "object"
    assert inventory["reducer_details"][0]["ref"] == {
        "source": "wf.std",
        "capability_key": "add",
    }
    assert diagnosed["result"]["source_id"] == "wf.std"
    assert diagnosed["result"]["status"] == "unknown"


async def test_rpc_stateless_draft_methods_preserve_result_variants(tmp_path) -> None:
    app = create_rpc_app(build_local_static_workflow_server(tmp_path / "store"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        validated = await _rpc(
            client,
            "workflow.drafts.validate",
            {"draft": {}},
        )
        patched_valid = await _rpc(
            client,
            "workflow.drafts.patch",
            {
                "draft": _rpc_constant_draft(),
                "patch": [
                    {
                        "op": "replace",
                        "path": "/name",
                        "value": "renamed_rpc_constant",
                    }
                ],
            },
        )
        patched_invalid = await _rpc(
            client,
            "workflow.drafts.patch",
            {
                "draft": _rpc_constant_draft(),
                "patch": [
                    {
                        "op": "replace",
                        "path": "/routes/constant/ok",
                        "value": "missing_step",
                    }
                ],
            },
        )
        patched_malformed = await _rpc(
            client,
            "workflow.drafts.patch",
            {
                "draft": {},
                "patch": [{"op": "remove", "path": "/missing"}],
            },
        )

    assert validated["result"]["status"] == "invalid"
    assert validated["result"]["diagnostics"]
    assert patched_valid["result"]["status"] == "valid"
    assert patched_valid["result"]["draft"]["name"] == "renamed_rpc_constant"
    assert patched_valid["result"]["compiled_plan"]["name"] == "renamed_rpc_constant"
    assert patched_invalid["result"]["status"] == "invalid"
    assert patched_invalid["result"]["diagnostics"]
    assert patched_invalid["result"]["draft"]["routes"]["constant"]["ok"] == (
        "missing_step"
    )
    assert patched_malformed["result"]["status"] == "invalid"
    assert patched_malformed["result"]["diagnostics"][0]["code"] == "patch_invalid"
    assert "draft" not in patched_malformed["result"]


async def test_rpc_capability_methods_preserve_saved_wrapper_fields(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="rpc_wrapper",
        version=1,
        title="RPC Wrapper",
        kind="wrapper",
        plan=_constant_plan(),
        outcomes=["ok"],
    )
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await _rpc(
            client,
            "workflow.capabilities.list",
            {"source_id": "workflow", "limit": 10},
        )
        inspected = await _rpc(
            client,
            "workflow.capabilities.inspect",
            {"qualified_name": "workflow.rpc_wrapper.v1"},
        )
        called = await _rpc(
            client,
            "workflow.capabilities.call",
            {
                "qualified_name": "workflow.rpc_wrapper.v1",
                "payload": {},
            },
        )

    wrapper = listed["result"]["capabilities"][0]
    assert wrapper["kind"] == "wrapper_artifact"
    assert wrapper["artifact_id"] == "rpc_wrapper"
    assert wrapper["version"] == 1
    assert wrapper["title"] == "RPC Wrapper"
    assert inspected["result"]["kind"] == "wrapper_artifact"
    assert inspected["result"]["artifact_id"] == "rpc_wrapper"
    assert "required_capabilities" in inspected["result"]
    assert called["result"]["kind"] == "wrapper_artifact"
    assert called["result"]["output"] == {"result": "hello over rpc"}


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

        draft = _rpc_constant_draft()

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
                "output_map": {},
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


async def test_rpc_replace_document_replaces_complete_draft_workspace(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_empty",
            {"workspace_id": "report", "name": "initial"},
        )
        initial = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "report", "include_draft": True},
        )
        replacement = {**initial["result"]["draft"], "name": "replacement"}

        replaced = await _rpc(
            client,
            "workflow.draft_workspaces.replace_document",
            {
                "workspace_id": "report",
                "revision": 1,
                "draft": replacement,
            },
        )
        inspected = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "report", "include_draft": True},
        )
        malformed = await _rpc(
            client,
            "workflow.draft_workspaces.replace_document",
            {
                "workspace_id": "report",
                "revision": 2,
                "draft": [],
            },
        )
        after_malformed = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "report", "include_draft": True},
        )

    assert replaced["result"]["revision"] == 2
    assert inspected["result"]["draft"] == replacement
    assert malformed["error"]["code"] == -32602
    assert after_malformed["result"] == inspected["result"]


async def test_rpc_replace_document_rejects_invalid_object_without_mutation(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_empty",
            {"workspace_id": "report", "name": "initial"},
        )
        before = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "report", "include_draft": True},
        )
        malformed = await _rpc(
            client,
            "workflow.draft_workspaces.replace_document",
            {
                "workspace_id": "report",
                "revision": 1,
                "draft": {"name": "missing-required-fields"},
            },
        )
        after = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "report", "include_draft": True},
        )

    assert malformed["error"]["code"] == -32602
    assert after["result"] == before["result"]


async def test_rpc_replace_document_persists_semantically_invalid_draft(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_empty",
            {"workspace_id": "report", "name": "initial"},
        )
        initial = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "report", "include_draft": True},
        )
        replacement = {**initial["result"]["draft"], "start": "missing_step"}
        replaced = await _rpc(
            client,
            "workflow.draft_workspaces.replace_document",
            {
                "workspace_id": "report",
                "revision": 1,
                "draft": replacement,
            },
        )
        after = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "report", "include_draft": True},
        )

    assert replaced["result"]["status"] == "invalid"
    assert replaced["result"]["diagnostics"]
    assert after["result"]["draft"]["start"] == "missing_step"
    assert after["result"]["diagnostics"] == replaced["result"]["diagnostics"]


async def test_rpc_draft_workspace_lifecycle_methods(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.draft_workspaces.create_empty",
            {
                "workspace_id": "rpc_control",
                "name": "rpc_control",
                "title": "RPC Control",
            },
        )
        started = await _rpc(
            client,
            "workflow.draft_workspaces.set_start",
            {
                "workspace_id": "rpc_control",
                "revision": 1,
                "step_id": "gate",
            },
        )
        contracted = await _rpc(
            client,
            "workflow.draft_workspaces.set_contract",
            {
                "workspace_id": "rpc_control",
                "revision": 2,
                "state_schema": {"type": "object", "properties": {}},
                "outcomes": ["error"],
            },
        )
        inspected = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "rpc_control", "include_draft": True},
        )

    assert created["result"]["revision"] == 1
    assert created["result"]["status"] == "invalid"
    assert started["result"]["revision"] == 2
    assert started["result"]["status"] == "invalid"
    assert contracted["result"]["revision"] == 3
    assert inspected["result"]["title"] == "RPC Control"
    assert inspected["result"]["draft"]["start"] == "gate"
    assert inspected["result"]["draft"]["state_schema"] == {
        "type": "object",
        "properties": {},
    }
    assert inspected["result"]["draft"]["outcomes"] == ["error"]


@pytest.mark.parametrize(
    ("method", "params"),
    [
        (
            "workflow.draft_workspaces.set_contract",
            {"workspace_id": "rpc_control", "revision": 1},
        ),
        (
            "workflow.draft_workspaces.set_contract",
            {"workspace_id": "rpc_control", "revision": 1, "outcomes": []},
        ),
        (
            "workflow.draft_workspaces.set_contract",
            {
                "workspace_id": "rpc_control",
                "revision": 1,
                "outcomes": ["ok", "ok"],
            },
        ),
        (
            "workflow.draft_workspaces.set_contract",
            {
                "workspace_id": "rpc_control",
                "revision": 1,
                "outcomes": ["ok", " ok "],
            },
        ),
        (
            "workflow.draft_workspaces.set_start",
            {"workspace_id": "rpc_control", "revision": 1, "step_id": " "},
        ),
        (
            "workflow.draft_workspaces.set_contract",
            {
                "workspace_id": "rpc_control",
                "revision": 1,
                "state_schema": [],
            },
        ),
    ],
)
async def test_rpc_draft_lifecycle_rejects_invalid_envelope_without_mutation(
    tmp_path,
    method: str,
    params: dict[str, Any],
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_empty_draft_workspace(
        workspace_id="rpc_control",
        name="rpc_control",
    )
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        rejected = await _rpc(client, method, params)
        inspected = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "rpc_control", "include_draft": True},
        )

    assert rejected["error"]["code"] == -32602
    assert inspected["result"]["revision"] == 1
    assert inspected["result"]["draft"]["start"] == ""
    assert inspected["result"]["draft"]["outcomes"] == ["ok"]


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
                "input_map": {"input.value": "payload.value"},
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
        input_merged = await _rpc(
            client,
            "workflow.draft_workspaces.set_step_input_map",
            {
                "workspace_id": "focused_ws",
                "revision": 5,
                "step_id": "call",
                "input_map": {"input.extra": "extra"},
                "merge": True,
            },
        )
        output_merged = await _rpc(
            client,
            "workflow.draft_workspaces.set_step_output_map",
            {
                "workspace_id": "focused_ws",
                "revision": 6,
                "step_id": "call",
                "output_map": {"extra": "state.extra"},
                "merge": True,
            },
        )
        state_bound = await _rpc(
            client,
            "workflow.draft_workspaces.bind",
            {
                "workspace_id": "focused_ws",
                "revision": 7,
                "step_id": "call",
                "source_path": "local.value",
                "target_path": "state.extra_value",
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
    assert input_merged["result"]["revision"] == 6
    assert output_merged["result"]["revision"] == 7
    assert state_bound["result"]["revision"] == 8
    draft = fetched["result"]["draft"]
    assert draft["name"] == "focused_renamed"
    assert draft["routes"]["call"]["ok"] == "__end__"
    assert draft["steps"]["call"]["input"] == [
        {
            "target": "payload.value",
            "path": "input.value",
        },
        {
            "target": "extra",
            "path": "input.extra",
        },
    ]
    assert draft["steps"]["call"]["output"] == [
        {
            "source": "value",
            "target": "state.extra_value",
        },
        {
            "source": "extra",
            "target": "state.extra",
        },
    ]
    assert (
        draft["state_schema"]["properties"]["extra_value"]
        == draft["state_schema"]["properties"]["value"]
    )


async def test_rpc_set_step_input_bindings_preserves_canonical_order(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "binding_ws",
                "capability_name": "wf.std.concat",
                "name": "binding_transport",
            },
        )
        result = await _rpc(
            client,
            "workflow.draft_workspaces.set_step_input_bindings",
            {
                "workspace_id": "binding_ws",
                "revision": 1,
                "step_id": "call",
                "bindings": [
                    {"path": "input.items", "target": "items"},
                    {"value": "\n", "target": "separator"},
                ],
            },
        )
        inspected = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "binding_ws", "include_draft": True},
        )

    assert result["result"]["revision"] == 2
    assert inspected["result"]["draft"]["steps"]["call"]["input"] == [
        {"target": "items", "path": "input.items"},
        {"target": "separator", "value": "\n"},
    ]


async def test_rpc_set_step_output_bindings_preserves_order_and_source_fan_out(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "draft-rpc-output-bindings",
                "capability_name": "wf.std.constant",
                "name": "output_bindings",
            },
        )
        response = await _rpc(
            client,
            "workflow.draft_workspaces.set_step_output_bindings",
            {
                "workspace_id": "draft-rpc-output-bindings",
                "revision": 1,
                "step_id": "call",
                "bindings": [
                    {"source": "value", "target": "state.report.title"},
                    {"source": "value", "target": "state.audit.title"},
                ],
            },
        )
        inspected = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "draft-rpc-output-bindings", "include_draft": True},
        )

    assert response["result"]["revision"] == 2
    assert inspected["result"]["draft"]["steps"]["call"]["output"] == [
        {"source": "value", "target": "state.report.title"},
        {"source": "value", "target": "state.audit.title"},
    ]


@pytest.mark.parametrize(
    "binding",
    [
        {"target": "state.report.title"},
        {"source": "value", "target": "state"},
        {"source": "value", "target": "state.report.title", "extra": True},
        {
            "source": {"root": "state", "parts": ["value"]},
            "target": "state.report.title",
        },
    ],
)
async def test_rpc_set_step_output_bindings_rejects_malformed_binding(
    tmp_path,
    binding: dict[str, Any],
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "valid_ws",
                "capability_name": "wf.std.constant",
                "name": "valid",
            },
        )
        rejected = await _rpc(
            client,
            "workflow.draft_workspaces.set_step_output_bindings",
            {
                "workspace_id": "valid_ws",
                "revision": 1,
                "step_id": "call",
                "bindings": [binding],
            },
        )

    assert rejected["error"]["code"] == -32602


@pytest.mark.parametrize(
    "binding",
    [
        {"path": "input.items", "value": [], "target": "items"},
        {"target": "items"},
    ],
)
async def test_rpc_set_step_input_bindings_rejects_malformed_union(
    tmp_path,
    binding: dict[str, Any],
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "valid_ws",
                "capability_name": "wf.std.constant",
                "name": "valid",
            },
        )
        rejected = await _rpc(
            client,
            "workflow.draft_workspaces.set_step_input_bindings",
            {
                "workspace_id": "valid_ws",
                "revision": 1,
                "step_id": "call",
                "bindings": [binding],
            },
        )

    assert rejected["error"]["code"] == -32602


async def test_rpc_draft_workspace_set_workflow_output_map(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "output_ws",
                "capability_name": "wf.std.constant",
                "name": "output_test",
            },
        )

        result = await _rpc(
            client,
            "workflow.draft_workspaces.set_workflow_output_map",
            {
                "workspace_id": "output_ws",
                "revision": created["result"]["revision"],
                "output_map": {"state.value": "value"},
            },
        )
        fetched = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "output_ws", "include_draft": True},
        )

    assert result["result"]["revision"] == 2
    assert fetched["result"]["draft"]["output"] == [
        {"path": "state.value", "target": "value"},
    ]


async def test_rpc_set_workflow_output_bindings_preserves_union_and_order(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "output_bindings_ws",
                "capability_name": "wf.std.constant",
                "name": "output_bindings_test",
            },
        )
        contracted = await _rpc(
            client,
            "workflow.draft_workspaces.set_contract",
            {
                "workspace_id": "output_bindings_ws",
                "revision": created["result"]["revision"],
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "format": {"type": "string"},
                    },
                },
            },
        )
        result = await _rpc(
            client,
            "workflow.draft_workspaces.set_workflow_output_bindings",
            {
                "workspace_id": "output_bindings_ws",
                "revision": contracted["result"]["revision"],
                "bindings": [
                    {"path": "state.value", "target": "value"},
                    {"value": "markdown", "target": "format"},
                ],
            },
        )
        fetched = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "output_bindings_ws", "include_draft": True},
        )

    assert "result" in result, result
    assert result["result"]["revision"] == 3
    assert fetched["result"]["draft"]["output"] == [
        {"path": "state.value", "target": "value"},
        {"value": "markdown", "target": "format"},
    ]


@pytest.mark.parametrize(
    "binding",
    [
        {"path": "state.value", "value": "duplicate", "target": "value"},
        {"path": "state.value"},
        {"path": "state.value", "target": "value", "extra": True},
        {"path": "local.value", "target": "value"},
    ],
)
async def test_rpc_set_workflow_output_bindings_rejects_malformed_binding(
    tmp_path,
    binding: dict[str, Any],
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "valid_ws",
                "capability_name": "wf.std.constant",
                "name": "valid",
            },
        )
        rejected = await _rpc(
            client,
            "workflow.draft_workspaces.set_workflow_output_bindings",
            {
                "workspace_id": "valid_ws",
                "revision": 1,
                "bindings": [binding],
            },
        )

    assert rejected["error"]["code"] == -32602


async def test_rpc_draft_workspace_remove_route(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "remove_route_ws",
                "capability_name": "wf.std.constant",
                "name": "remove_route_test",
                "output_map": {"value": "state.result"},
            },
        )
        assert created["result"]["workspace_id"] == "remove_route_ws"

        removed = await _rpc(
            client,
            "workflow.draft_workspaces.remove_route",
            {
                "workspace_id": "remove_route_ws",
                "revision": 1,
                "step_id": "call",
                "outcome": "ok",
            },
        )

        assert removed["result"]["revision"] == 2
        assert removed["result"]["status"] == "invalid"

        inspected = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "remove_route_ws", "include_draft": True},
        )
        assert inspected["result"]["draft"]["routes"]["call"] == {}


async def test_rpc_draft_workspace_add_step_from_capability(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "add_step_ws",
                "capability_name": "wf.std.constant",
                "name": "add_step",
            },
        )

        response = await _rpc(
            client,
            "workflow.draft_workspaces.add_step_from_capability",
            {
                "workspace_id": "add_step_ws",
                "revision": 1,
                "step_id": "second",
                "capability_name": "wf.std.constant",
                "route_from_step": "call",
                "route_from_outcome": "ok",
                "routes": {"ok": "__end__"},
                "input_map": {"input.value": "value"},
                "bind_outputs": {"value": "state.second_value"},
            },
        )

    result = response["result"]
    assert result["revision"] == 2
    assert result["status"] == "valid"


async def test_rpc_draft_workspace_updates_capability_step_atomically(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "update_step_ws",
                "capability_name": "wf.std.constant",
                "name": "update_step",
            },
        )
        before = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "update_step_ws", "include_draft": True},
        )

        updated = await _rpc(
            client,
            "workflow.draft_workspaces.update_capability_step",
            {
                "workspace_id": "update_step_ws",
                "revision": 1,
                "step_id": "call",
                "update": {
                    "desc": "Return the prepared value",
                    "retry": 0,
                    "input": [{"value": "prepared", "target": "value"}],
                },
            },
        )
        inspected = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "update_step_ws", "include_draft": True},
        )

    assert updated["result"]["revision"] == 2
    step = inspected["result"]["draft"]["steps"]["call"]
    assert step["use"] == "wf.std.constant"
    assert step["desc"] == "Return the prepared value"
    assert step["retry"] == 0
    assert step["input"] == [{"value": "prepared", "target": "value"}]
    assert step["output"] == before["result"]["draft"]["steps"]["call"]["output"]
    assert inspected["result"]["draft"]["routes"] == before["result"]["draft"]["routes"]


async def test_rpc_add_step_from_capability_accepts_canonical_inputs(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "canonical_add_ws",
                "capability_name": "wf.std.constant",
                "name": "canonical_add",
            },
        )
        added = await _rpc(
            client,
            "workflow.draft_workspaces.add_step_from_capability",
            {
                "workspace_id": "canonical_add_ws",
                "revision": 1,
                "step_id": "second",
                "capability_name": "wf.std.constant",
                "routes": {"ok": "__end__"},
                "desc": "Return another prepared value",
                "retry": 0,
                "timeout_seconds": 30,
                "input_bindings": [{"value": "second", "target": "value"}],
            },
        )
        inspected = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "canonical_add_ws", "include_draft": True},
        )

    assert added["result"]["revision"] == 2
    step = inspected["result"]["draft"]["steps"]["second"]
    assert step["desc"] == "Return another prepared value"
    assert step["retry"] == 0
    assert step["timeout_seconds"] == 30
    assert step["input"] == [{"value": "second", "target": "value"}]


def test_add_draft_step_params_preserve_typed_step_json() -> None:
    foreach = AddDraftStepParams.model_validate(
        {
            "workspace_id": "ws",
            "revision": 1,
            "step_id": "each",
            "step": {"foreach": {"over": "state.items", "as": "item"}},
            "incoming": {"step_id": "call"},
        }
    )
    foreach_dump = foreach.model_dump(mode="json", by_alias=True)

    assert foreach_dump["step"]["foreach"]["as"] == "item"
    assert "as_" not in foreach_dump["step"]["foreach"]
    assert foreach_dump["incoming"] == {"step_id": "call", "outcome": "ok"}

    when = AddDraftStepParams.model_validate(
        {
            "workspace_id": "ws",
            "revision": 1,
            "step_id": "decide",
            "step": {
                "when": {
                    "if": {"op": "exists", "path": "state.ready"},
                    "then": "next",
                }
            },
        }
    )
    assert when.model_dump(mode="json", by_alias=True)["step"]["when"]["if"] == {
        "op": "exists",
        "path": "state.ready",
    }

    interrupt = AddDraftStepParams.model_validate(
        {
            "workspace_id": "ws",
            "revision": 1,
            "step_id": "review",
            "step": {
                "interrupt": {
                    "kind": "issue_review",
                    "request_schema": {
                        "type": "object",
                        "properties": {"issues": {"type": "array"}},
                    },
                    "resume_schema": {
                        "type": "object",
                        "properties": {"selected": {"type": "array"}},
                    },
                },
            },
        }
    )
    interrupt_dump = interrupt.model_dump(mode="json", by_alias=True)
    assert interrupt_dump["step"]["interrupt"]["request_schema"]["type"] == "object"
    assert interrupt_dump["step"]["interrupt"]["resume_schema"]["type"] == "object"

    subgraph = AddDraftStepParams.model_validate(
        {
            "workspace_id": "ws",
            "revision": 1,
            "step_id": "child",
            "step": {"subgraph": {"workflow": {"artifact_id": "child", "version": 2}}},
        }
    )
    assert subgraph.model_dump(mode="json", by_alias=True)["step"]["subgraph"][
        "workflow"
    ] == {"artifact_id": "child", "version": 2}


def test_add_draft_step_params_reject_invalid_kind_and_route_source() -> None:
    with pytest.raises(ValidationError):
        AddDraftStepParams.model_validate(
            {
                "workspace_id": "ws",
                "revision": 1,
                "step_id": "bad",
                "step": {"unknown": {}},
            }
        )

    with pytest.raises(ValidationError):
        AddDraftStepParams.model_validate(
            {
                "workspace_id": "ws",
                "revision": 1,
                "step_id": "bad",
                "step": {"use": "demo.echo", "join": {}},
            }
        )

    for incoming in (
        {"step_id": "", "outcome": "ok"},
        {"step_id": "call", "outcome": ""},
    ):
        with pytest.raises(ValidationError):
            AddDraftStepParams.model_validate(
                {
                    "workspace_id": "ws",
                    "revision": 1,
                    "step_id": "new",
                    "step": {"join": {}},
                    "incoming": incoming,
                }
            )


async def test_rpc_draft_workspace_add_typed_step_round_trip(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "typed_step_ws",
                "capability_name": "wf.std.constant",
                "name": "typed_step",
            },
        )
        added = await _rpc(
            client,
            "workflow.draft_workspaces.add_step",
            {
                "workspace_id": "typed_step_ws",
                "revision": created["result"]["revision"],
                "step_id": "review",
                "step": {
                    "interrupt": {
                        "kind": "issue_review",
                        "request_schema": {
                            "type": "object",
                            "properties": {"issues": {"type": "array"}},
                        },
                        "resume_schema": {
                            "type": "object",
                            "properties": {"selected": {"type": "array"}},
                        },
                        "outcomes": ["submitted", "cancelled"],
                    }
                },
                "incoming": {"step_id": "call", "outcome": "ok"},
                "routes": {"submitted": "__end__", "cancelled": "__end__"},
            },
        )
        malformed = await _rpc(
            client,
            "workflow.draft_workspaces.add_step",
            {
                "workspace_id": "typed_step_ws",
                "revision": added["result"]["revision"],
                "step_id": "bad",
                "step": {"unknown": {}},
            },
        )
        fetched = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "typed_step_ws", "include_draft": True},
        )

    assert added["result"]["revision"] == created["result"]["revision"] + 1
    assert added["result"]["status"] == "valid"
    assert "error" in malformed
    assert fetched["result"]["revision"] == added["result"]["revision"]
    assert "bad" not in fetched["result"]["draft"]["steps"]
    review = fetched["result"]["draft"]["steps"]["review"]["interrupt"]
    assert review["request_schema"]["type"] == "object"
    assert review["resume_schema"]["properties"]["selected"] == {"type": "array"}


async def test_rpc_draft_workspace_add_untyped_interrupt_preserves_null_schemas(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "untyped_interrupt_ws",
                "capability_name": "wf.std.constant",
                "name": "untyped_interrupt",
            },
        )
        added = await _rpc(
            client,
            "workflow.draft_workspaces.add_step",
            {
                "workspace_id": "untyped_interrupt_ws",
                "revision": created["result"]["revision"],
                "step_id": "pause",
                "step": {
                    "interrupt": {
                        "kind": "approval",
                        "request_schema": None,
                        "resume_schema": None,
                    }
                },
            },
        )
        fetched = await _rpc(
            client,
            "workflow.draft_workspaces.get",
            {"workspace_id": "untyped_interrupt_ws", "include_draft": True},
        )

    assert added["result"]["revision"] == created["result"]["revision"] + 1
    interrupt = fetched["result"]["draft"]["steps"]["pause"]["interrupt"]
    assert interrupt["request_schema"] is None
    assert interrupt["resume_schema"] is None
    assert fetched["result"]["draft"]["steps"]["pause"] == {"interrupt": interrupt}


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
