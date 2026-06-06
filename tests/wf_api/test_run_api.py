from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tests.wf_mcp.test_support import echo_tool
from tests.wf_mcp.workflow_surface.conftest import (
    echo_artifact,
    failing_artifact,
    failing_tool,
)
from wf_api.runs import WorkflowRunApi
from wf_artifacts import (
    FileRunStore,
    FileWorkflowArtifactStore,
    WorkflowDeployment,
)
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers


class SimpleTraceRange:
    def __init__(self, start: int, limit: int) -> None:
        self.start = start
        self.limit = limit


def _service_with_echo(
    root: Path,
) -> tuple[WfMcpService, FileWorkflowArtifactStore]:
    artifact_store = FileWorkflowArtifactStore(root)
    artifact_store.save_artifact(echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=artifact_store,
        run_store=FileRunStore(root / "mcp"),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    return service, artifact_store


def _service_with_failing(
    root: Path,
) -> tuple[WfMcpService, FileWorkflowArtifactStore]:
    artifact_store = FileWorkflowArtifactStore(root)
    artifact_store.save_artifact(failing_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="fail.personal",
            artifact_id="fail",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=artifact_store,
        run_store=FileRunStore(root / "mcp"),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", failing_tool)
    return service, artifact_store


def test_run_api_unrunnable_deployment(tmp_path: Path) -> None:
    root = tmp_path / "run_api_unrunnable"
    artifact_store = FileWorkflowArtifactStore(root)
    from tests.wf_mcp.workflow_surface.conftest import artifact

    artifact_store.save_artifact(artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="unbound.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings=[],
        )
    )
    service = WfMcpService(
        store=FileStore(root / "mcp"),
        artifact_store=artifact_store,
    )
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    result = asyncio.run(
        api.run_deployment(
            deployment_id="unbound.personal",
            workflow_input={},
        )
    )

    assert result["status"] == "unrunnable"
    assert result["run_id"] is None
    assert result["trace_count"] == 0
    assert result["diagnostics"][0]["code"]


def test_run_api_completed_run_persists(tmp_path: Path) -> None:
    root = tmp_path / "run_api_completed"
    service, artifact_store = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    result = asyncio.run(
        api.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )

    assert result["status"] == "completed"
    assert isinstance(result["run_id"], str)
    assert result["resume_readiness"] == "not_applicable"
    assert result["trace_count"] >= 1

    assert context.run_store is not None
    stored = context.run_store.get_run(result["run_id"])
    assert stored.id == result["run_id"]


def test_run_api_rejects_resume_for_completed_run(tmp_path: Path) -> None:
    root = tmp_path / "run_api_resume_completed_rejected"
    service, _ = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    result = asyncio.run(
        api.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )

    with pytest.raises(ValueError, match="is not interrupted"):
        asyncio.run(
            api.resume_run(
                run_id=result["run_id"],
                resume_payload={"answer": "ignored"},
            )
        )


def test_run_api_inspect_uses_pinned_environment_after_deployment_deleted(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run_api_inspect_after_deployment_deleted"
    service, artifact_store = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    result = asyncio.run(
        api.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )
    artifact_store.delete_deployment("echo.personal")

    summary = asyncio.run(api.inspect_run(run_id=result["run_id"]))

    assert summary["status"] == "completed"
    assert summary["run_id"] == result["run_id"]
    assert summary["deployment_id"] == "echo.personal"
    assert summary["artifact_id"] == "echo"
    assert summary["output"]["echoed"] == "hello"


def test_run_api_inspect_and_bounded_trace(tmp_path: Path) -> None:
    root = tmp_path / "run_api_inspect_trace"
    service, _ = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    result = asyncio.run(
        api.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )
    run_id = result["run_id"]

    summary = asyncio.run(api.inspect_run(run_id=run_id))
    trace = asyncio.run(
        api.read_run_trace(
            run_id=run_id,
            trace_range=SimpleTraceRange(start=0, limit=1),
        )
    )

    assert "trace" not in summary
    assert trace["trace_start"] == 0
    assert trace["trace_limit"] == 1
    assert len(trace["trace"]) <= 1
    assert trace["trace_count"] == summary["trace_count"]


class ExplodingRunStore(FileRunStore):
    def get_run(self, run_id: str):
        raise AssertionError("run store must not be read before trace_range validation")


def test_run_api_rejects_invalid_trace_range_before_store_lookup(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run_api_invalid_trace_range"
    service, _ = _service_with_echo(root)
    service.run_store = ExplodingRunStore(root / "exploding_runs")
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    with pytest.raises(ValueError, match="trace_range.start"):
        asyncio.run(
            api.read_run_trace(
                run_id="missing",
                trace_range=SimpleTraceRange(start=-1, limit=1),
            )
        )

    with pytest.raises(ValueError, match="trace_range.limit"):
        asyncio.run(
            api.read_run_trace(
                run_id="missing",
                trace_range=SimpleTraceRange(start=0, limit=0),
            )
        )


def test_run_api_handler_delegation_matches(tmp_path: Path) -> None:
    root = tmp_path / "run_api_delegation"
    service, _ = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)
    handlers = WorkflowSurfaceHandlers(service)

    run_result = asyncio.run(
        api.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )
    run_id = run_result["run_id"]

    handler_summary = asyncio.run(handlers.inspect_run(run_id=run_id))
    api_summary = asyncio.run(api.inspect_run(run_id=run_id))

    assert handler_summary["status"] == api_summary["status"]
    assert handler_summary["run_id"] == api_summary["run_id"]
    assert handler_summary["trace_count"] == api_summary["trace_count"]
    assert handler_summary["resume_readiness"] == api_summary["resume_readiness"]
