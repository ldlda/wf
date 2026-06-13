from __future__ import annotations

import ast
from pathlib import Path

from wf_api.models import RawWorkflowPlan
from wf_core import END
from wf_server import build_local_static_workflow_server


def _constant_plan() -> RawWorkflowPlan:
    return RawWorkflowPlan.model_validate(
        {
            "name": "server_constant",
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
                            "value": "hello from server",
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


def test_wf_server_context_imports_no_wfmcp_service() -> None:
    path = Path("src/wf_server/context.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == "wf_mcp.broker" or node.module.endswith(".core"):
                violations.append(f"{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"wf_mcp.broker", "wf_mcp.broker.service.core"}:
                    violations.append(f"{node.lineno}: import {alias.name}")

    assert violations == []


async def test_local_static_server_runs_deployment_and_persists_run(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    api = server.api
    plan = _constant_plan()

    artifact_result = await api.create_artifact_from_plan(
        artifact_id="server_constant",
        version=1,
        title="Server Constant",
        plan=plan,
        outcomes=["ok"],
        source_bindings={"wf.std": "wf.std"},
    )
    deployment_result = await api.save_deployment(
        {
            "id": "server_constant.default",
            "artifact_id": "server_constant",
            "artifact_version": 1,
            "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
        }
    )
    run_result = await api.run_deployment(
        deployment_id="server_constant.default",
        workflow_input={},
    )

    assert artifact_result["artifact_id"] == "server_constant"
    assert deployment_result["deployment_id"] == "server_constant.default"
    assert run_result["status"] == "completed"
    assert run_result["output"]["result"] == "hello from server"
    assert isinstance(run_result["run_id"], str)
    assert (
        server.stores.run_store.get_run(run_result["run_id"]).id == run_result["run_id"]
    )


async def test_local_static_server_inspects_and_reads_bounded_trace(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    api = server.api
    plan = _constant_plan()
    await api.create_artifact_from_plan(
        artifact_id="server_trace",
        version=1,
        title="Server Trace",
        plan=plan.model_copy(update={"name": "server_trace"}),
        outcomes=["ok"],
        source_bindings={"wf.std": "wf.std"},
    )
    await api.save_deployment(
        {
            "id": "server_trace.default",
            "artifact_id": "server_trace",
            "artifact_version": 1,
            "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
        }
    )
    run_result = await api.run_deployment(
        deployment_id="server_trace.default", workflow_input={}
    )

    summary = await api.inspect_run(run_id=run_result["run_id"])
    trace = await api.read_run_trace(
        run_id=run_result["run_id"],
        trace_range=server.trace_range(start=0, limit=1),
    )

    assert "trace" not in summary
    assert summary["trace_count"] >= 1
    assert trace["trace_start"] == 0
    assert trace["trace_limit"] == 1
    assert len(trace["trace"]) == 1


async def test_local_static_wf_std_deployment_runs_without_source_binding(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    api = server.api
    plan = _constant_plan()

    artifact_result = await api.create_artifact_from_plan(
        artifact_id="server_constant_no_binding",
        version=1,
        title="Server Constant No Binding",
        plan=plan.model_copy(update={"name": "server_constant_no_binding"}),
        outcomes=["ok"],
        source_bindings={},
    )
    deployment_result = await api.save_deployment(
        {
            "id": "server_constant_no_binding.default",
            "artifact_id": "server_constant_no_binding",
            "artifact_version": 1,
            "bindings": {},
        }
    )
    run_result = await api.run_deployment(
        deployment_id="server_constant_no_binding.default",
        workflow_input={},
    )

    assert artifact_result["artifact_id"] == "server_constant_no_binding"
    assert deployment_result["deployment_id"] == "server_constant_no_binding.default"
    assert run_result["status"] == "completed"
    assert run_result["output"]["result"] == "hello from server"


def test_local_static_server_has_no_source_registry_admin(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")

    assert server.source_registry_admin is None


def test_local_static_builtins_are_platform_sources(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path)

    wf_std = server.context.specs.capability_sources["wf.std"]

    assert wf_std.policy.platform is True
    assert wf_std.policy.binding_required is False


def test_local_static_server_exposes_wf_source_platform_source(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path)

    source = server.context.specs.capability_sources["wf.source"]

    assert source.policy.platform is True
    assert source.policy.binding_required is False
    assert "wf.source.read_resource" in source.capabilities.node_specs
