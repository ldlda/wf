from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

import pytest

from wf_server import build_local_static_workflow_server
from wf_transport_rpc_http import create_rpc_app


def _method_by_name(document: dict[str, Any], name: str) -> dict[str, Any]:
    return next(method for method in document["methods"] if method["name"] == name)


def _assert_result_component(
    document: dict[str, Any],
    *,
    method_name: str,
    component_name: str,
    properties: Collection[str],
) -> None:
    method = _method_by_name(document, method_name)
    assert method["result"]["schema"] == {
        "$ref": f"#/components/schemas/{component_name}"
    }
    component = document["components"]["schemas"][component_name]
    assert properties <= component["properties"].keys()


@pytest.fixture
def openrpc_document(tmp_path: Path) -> dict[str, Any]:
    app = create_rpc_app(build_local_static_workflow_server(tmp_path / "store"))
    return app.get_openrpc()


def test_openrpc_exposes_typed_health_result(
    openrpc_document: dict[str, Any],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name="workflow.health",
        component_name="HealthResult",
        properties={"status", "store_root"},
    )


@pytest.mark.parametrize(
    ("method_name", "component_name", "properties"),
    [
        (
            "workflow.deployments.list",
            "ListDeploymentsResult",
            {"deployments"},
        ),
        (
            "workflow.deployments.inspect",
            "WorkflowDeploymentPayload",
            {"id", "artifact_id", "artifact_version", "bindings", "drift_policy"},
        ),
        (
            "workflow.deployments.save",
            "SaveDeploymentResult",
            {"deployment_id", "artifact_id", "artifact_version", "saved"},
        ),
        (
            "workflow.deployments.delete",
            "DeleteDeploymentResult",
            {"deployment_id", "deleted"},
        ),
        (
            "workflow.deployments.validate",
            "ValidateDeploymentResult",
            {
                "deployment_id",
                "artifact_id",
                "artifact_version",
                "status",
                "diagnostics",
                "next_actions",
            },
        ),
    ],
)
def test_openrpc_exposes_typed_deployment_results(
    openrpc_document: dict[str, Any],
    method_name: str,
    component_name: str,
    properties: set[str],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name=method_name,
        component_name=component_name,
        properties=properties,
    )


@pytest.mark.parametrize(
    ("method_name", "component_name", "properties"),
    [
        (
            "workflow.runs.list",
            "ListRunsResult",
            {"runs", "total", "cursor", "next_cursor", "limit"},
        ),
        (
            "workflow.runs.start",
            "RunResult",
            {
                "deployment_id",
                "run_id",
                "status",
                "interrupt",
                "output",
                "next_actions",
            },
        ),
        (
            "workflow.runs.inspect",
            "RunResult",
            {"run_id", "status", "resume_readiness", "trace_count"},
        ),
        (
            "workflow.runs.resume",
            "RunResult",
            {"run_id", "status", "resume_readiness", "trace_count"},
        ),
        (
            "workflow.runs.trace",
            "RunTraceResult",
            {
                "run_id",
                "trace",
                "trace_start",
                "trace_limit",
                "trace_truncated",
            },
        ),
    ],
)
def test_openrpc_exposes_typed_run_results(
    openrpc_document: dict[str, Any],
    method_name: str,
    component_name: str,
    properties: set[str],
) -> None:
    _assert_result_component(
        openrpc_document,
        method_name=method_name,
        component_name=component_name,
        properties=properties,
    )
