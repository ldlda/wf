from __future__ import annotations

from typing import Any, cast

import pytest

from wf_client import App, Run, WorkflowClientPort
from wf_client.errors import DeploymentNotRunnable, InvalidResponse


def _payload(
    *, run_id: str | None = "run-1", status: str = "interrupted"
) -> dict[str, Any]:
    return {
        "artifact_id": "report",
        "artifact_version": 1,
        "deployment_id": "report.production",
        "status": status,
        "run_id": run_id,
        "resume_readiness": "ready" if status == "interrupted" else "not_applicable",
        "interrupt": {
            "id": "interrupt-1",
            "frame_id": "root",
            "node_id": "approve",
            "kind": "approval",
            "payload": {"question": "approve?"},
            "resumable": True,
            "route": None,
            "outcomes": ["submitted"],
            "request_schema": {"type": "object"},
            "resume_schema": {"type": "object"},
            "typed": False,
        }
        if status == "interrupted"
        else None,
        "outcome": None if status == "interrupted" else "ok",
        "error": None,
        "output": None if status == "interrupted" else {"result": "done"},
        "trace_count": 1,
        "diagnostics": [],
        "next_actions": {
            "can_continue": status == "interrupted",
            "can_save_now": None,
            "recommended_next_tool": None,
            "reason": "ready",
            "patch_examples": [],
            "warnings": [],
        },
    }


class _Port:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.resume_payload = _payload(status="completed")
        self.trace_payload = {
            **_payload(status="completed"),
            "trace": [
                {
                    "frame_id": "root",
                    "node_id": "approve",
                    "step_type": "node",
                    "resolved_input": {},
                    "outcome": "ok",
                    "next_node_id": "__end__",
                    "output": {},
                    "state_changes": {},
                }
            ],
            "trace_start": 0,
            "trace_limit": 25,
            "trace_truncated": False,
        }

    async def resume_run(self, **params: Any) -> object:
        self.calls.append(("resume_run", params))
        return self.resume_payload

    async def inspect_run(self, **params: Any) -> object:
        self.calls.append(("inspect_run", params))
        return self.resume_payload

    async def read_run_trace(self, **params: Any) -> object:
        self.calls.append(("read_run_trace", params))
        return self.trace_payload


@pytest.mark.asyncio
async def test_interrupted_run_resumes_and_reads_bounded_trace() -> None:
    port = _Port()
    run = Run.from_payload(cast(WorkflowClientPort, port), _payload())
    completed = await run.resume({"approved": True})
    trace = await completed.trace(limit=25)
    assert completed.status == "completed"
    assert completed.output == {"result": "done"}
    assert trace.start == 0
    assert trace.limit == 25
    assert len(trace.frames) == 1


@pytest.mark.asyncio
async def test_refresh_returns_a_new_snapshot() -> None:
    port = _Port()
    original = Run.from_payload(cast(WorkflowClientPort, port), _payload())
    refreshed = await original.refresh()
    assert refreshed is not original
    assert refreshed.status == "completed"
    assert original.status == "interrupted"


@pytest.mark.asyncio
async def test_app_run_rejects_mismatched_inspection_id() -> None:
    port = _Port()
    port.resume_payload["run_id"] = "different-run"
    app = App._from_port(cast(WorkflowClientPort, port))
    with pytest.raises(InvalidResponse, match="workflow.runs.inspect"):
        await app.run("run-1")


@pytest.mark.asyncio
async def test_refresh_rejects_mismatched_inspection_id() -> None:
    port = _Port()
    port.resume_payload["run_id"] = "different-run"
    run = Run.from_payload(cast(WorkflowClientPort, port), _payload())
    with pytest.raises(InvalidResponse, match="workflow.runs.inspect"):
        await run.refresh()


@pytest.mark.asyncio
async def test_resume_rejects_mismatched_result_id() -> None:
    port = _Port()
    port.resume_payload["run_id"] = "different-run"
    run = Run.from_payload(cast(WorkflowClientPort, port), _payload())
    with pytest.raises(InvalidResponse, match="workflow.runs.resume"):
        await run.resume({"approved": True})


@pytest.mark.asyncio
async def test_malformed_interrupt_route_is_invalid_response() -> None:
    payload = _payload()
    payload["interrupt"]["route"] = {
        "frame_id": "child",
        "node_id": "approve",
        "scope_id": "scope",
        "lineage_id": "lineage",
        "parent_frame_id": "root",
        "workflow_ref": {"name": "local", "artifact_id": "also-invalid", "version": 1},
    }
    with pytest.raises(InvalidResponse, match="workflow.runs.inspect"):
        Run.from_payload(cast(WorkflowClientPort, _Port()), payload)


@pytest.mark.asyncio
async def test_missing_run_id_preserves_server_error() -> None:
    payload = _payload(run_id=None, status="failed")
    payload["error"] = "server refused to start"
    with pytest.raises(DeploymentNotRunnable) as captured:
        Run.from_payload(cast(WorkflowClientPort, _Port()), payload)
    assert captured.value.error == "server refused to start"


@pytest.mark.asyncio
async def test_non_resumable_run_is_rejected_before_io() -> None:
    port = _Port()
    payload = _payload()
    assert payload["interrupt"] is not None
    payload["interrupt"]["resumable"] = False
    run = Run.from_payload(cast(WorkflowClientPort, port), payload)
    with pytest.raises(ValueError, match="not resumable"):
        await run.resume({"approved": True})
    assert port.calls == []


@pytest.mark.asyncio
async def test_trace_rejects_invalid_bounds_before_io() -> None:
    port = _Port()
    run = Run.from_payload(cast(WorkflowClientPort, port), _payload())
    with pytest.raises(ValueError):
        await run.trace(start=-1)
    with pytest.raises(ValueError):
        await run.trace(limit=101)
    assert port.calls == []
