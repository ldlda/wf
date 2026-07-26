from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from tests.wf_mcp.test_support import echo_tool
from wf_api.draft_authoring import RouteSource, WorkflowDraftAuthoringApi
from wf_api.draft_updates import CapabilityStepUpdate
from wf_api.drafts import WorkflowDraftApi
from wf_api.models import RawWorkflowPlan
from wf_api.service import WorkflowApi
from wf_artifacts import FileDraftWorkspaceStore, FileWorkflowArtifactStore
from wf_artifacts.drafts.models import DraftStep
from wf_authoring import node
from wf_core.models.steps import (
    InputBinding,
    InputPathBinding,
    InputValueBinding,
    OutputBinding,
)
from wf_core.paths import GraphSourcePath, LocalPath, StatePath
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.workflow_operation_context import context_from_service
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers


def test_capability_step_update_preserves_field_presence() -> None:
    update = CapabilityStepUpdate.model_validate(
        {"desc": None, "retry": 0, "input": []}
    )

    assert update.model_fields_set == {"desc", "retry", "input"}
    assert update.desc is None
    assert update.retry == 0
    assert update.input == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"input": None},
        {"desc": ""},
        {"retry": -1},
        {"timeout_seconds": 0},
        {"unknown": True},
    ],
)
def test_capability_step_update_rejects_invalid_patch(payload: object) -> None:
    with pytest.raises(ValidationError):
        CapabilityStepUpdate.model_validate(payload)


@pytest.mark.asyncio
async def test_update_capability_step_changes_metadata_and_inputs_atomically(
    tmp_path: Path,
) -> None:
    draft_api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "update_capability"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["steps"]["echo"].update(
        {
            "desc": "Old description",
            "retry": 1,
            "timeout_seconds": 10,
        }
    )
    await draft_api.create_draft_workspace(workspace_id="echo", draft=draft)

    result = await authoring.update_capability_step(
        workspace_id="echo",
        revision=1,
        step_id="echo",
        update=CapabilityStepUpdate.model_validate(
            {
                "desc": "New description",
                "retry": 0,
                "timeout_seconds": None,
                "input": [{"value": "fixed", "target": "text"}],
            }
        ),
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )
    step = inspected["draft"]["steps"]["echo"]

    assert result["revision"] == 2
    assert step["use"] == "demo.personal.echo_tool"
    assert step["desc"] == "New description"
    assert step["retry"] == 0
    assert "timeout_seconds" not in step
    assert step["input"] == [{"value": "fixed", "target": "text"}]
    assert step["output"] == [{"source": "echoed", "target": "state.echoed"}]
    assert inspected["draft"]["routes"]["echo"] == {"ok": "__end__"}

    compiled = await draft_api.compile_draft_workspace(workspace_id="echo")
    run = await service.run_workflow_from_plan(
        RawWorkflowPlan.model_validate(compiled["compiled_plan"]),
        {"text": "ignored"},
    )
    assert run.error is None
    assert run.output == {"echoed": "fixed"}


@pytest.mark.asyncio
async def test_update_capability_step_preserves_omitted_fields_and_exact_noop(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "update_capability_noop"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["steps"]["echo"].update({"desc": "Keep", "retry": 2, "timeout_seconds": 15})
    await draft_api.create_draft_workspace(workspace_id="echo", draft=draft)

    first = await authoring.update_capability_step(
        workspace_id="echo",
        revision=1,
        step_id="echo",
        update=CapabilityStepUpdate(
            retry=2,
            input=[
                InputPathBinding(
                    path=GraphSourcePath.input("text"),
                    target=LocalPath.of("text"),
                )
            ],
        ),
    )
    second = await authoring.update_capability_step(
        workspace_id="echo",
        revision=first["revision"],
        step_id="echo",
        update=CapabilityStepUpdate(desc=None),
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )

    assert first["revision"] == 1
    assert second["revision"] == 2
    step = inspected["draft"]["steps"]["echo"]
    assert "desc" not in step
    assert step["retry"] == 2
    assert step["timeout_seconds"] == 15


@pytest.mark.asyncio
async def test_update_capability_step_removes_stored_null_metadata(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "update_capability_null_noop"),
        register_echo=True,
    )
    await draft_api.create_draft_workspace(workspace_id="echo", draft=_echo_draft())
    before = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )
    assert before["draft"]["steps"]["echo"]["retry"] is None

    result = await authoring.update_capability_step(
        workspace_id="echo",
        revision=1,
        step_id="echo",
        update=CapabilityStepUpdate(retry=None),
    )
    after = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )

    assert result["revision"] == 2
    assert "retry" not in after["draft"]["steps"]["echo"]


@pytest.mark.asyncio
async def test_update_capability_step_input_preserves_omitted_null_metadata(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "update_capability_null_metadata"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["steps"]["echo"].update(
        {
            "desc": None,
            "retry": None,
            "timeout_seconds": None,
        }
    )
    await draft_api.create_draft_workspace(workspace_id="echo", draft=draft)

    result = await authoring.update_capability_step(
        workspace_id="echo",
        revision=1,
        step_id="echo",
        update=CapabilityStepUpdate(
            input=[
                InputValueBinding(
                    target=LocalPath.of("text"),
                    value="replacement",
                )
            ]
        ),
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )
    step = inspected["draft"]["steps"]["echo"]

    assert result["revision"] == 2
    assert step["desc"] is None
    assert step["retry"] is None
    assert step["timeout_seconds"] is None
    assert step["input"] == [{"value": "replacement", "target": "text"}]


@pytest.mark.asyncio
async def test_update_capability_step_metadata_does_not_resolve_capability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "update_capability_metadata"),
        register_echo=True,
    )
    await draft_api.create_draft_workspace(workspace_id="echo", draft=_echo_draft())

    def fail_lookup(_provider: object, _capability_name: str) -> None:
        raise AssertionError("metadata-only update resolved the capability")

    monkeypatch.setattr(
        type(authoring.context.specs),
        "get_qualified_spec",
        fail_lookup,
    )
    result = await authoring.update_capability_step(
        workspace_id="echo",
        revision=1,
        step_id="echo",
        update=CapabilityStepUpdate(desc="Metadata only"),
    )

    assert result["revision"] == 2


@pytest.mark.asyncio
async def test_update_capability_step_metadata_preserves_invalid_draft_shape(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "update_invalid_draft_shape"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["routes"]["echo"]["ok"] = "missing"
    await draft_api.create_draft_workspace(workspace_id="echo", draft=draft)
    before = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )

    result = await authoring.update_capability_step(
        workspace_id="echo",
        revision=1,
        step_id="echo",
        update=CapabilityStepUpdate(desc="Explain the invalid draft"),
    )
    after = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )

    assert result["revision"] == 2
    assert after["draft"]["steps"]["echo"]["desc"] == "Explain the invalid draft"
    assert (
        after["draft"]["steps"]["echo"]["input"]
        == before["draft"]["steps"]["echo"]["input"]
    )
    assert (
        after["draft"]["steps"]["echo"]["output"]
        == before["draft"]["steps"]["echo"]["output"]
    )
    assert after["draft"]["routes"] == before["draft"]["routes"]


@pytest.mark.asyncio
async def test_update_capability_step_stale_revision_wins_over_semantic_errors(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "update_capability_stale"),
        register_echo=True,
    )
    await draft_api.create_draft_workspace(workspace_id="echo", draft=_echo_draft())

    result = await authoring.update_capability_step(
        workspace_id="echo",
        revision=2,
        step_id="missing",
        update=CapabilityStepUpdate(
            input=[InputValueBinding(target=LocalPath.of("missing"), value="bad")]
        ),
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"


@pytest.mark.asyncio
async def test_update_capability_step_rejects_wrong_kind_and_invalid_input_atomically(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "update_capability_invalid"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["steps"]["joined"] = {"join": ["echo"]}
    await draft_api.create_draft_workspace(workspace_id="echo", draft=draft)
    before = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )

    with pytest.raises(ValueError, match="not capability-backed"):
        await authoring.update_capability_step(
            workspace_id="echo",
            revision=1,
            step_id="joined",
            update=CapabilityStepUpdate(desc="No"),
        )
    with pytest.raises(ValueError, match=r"bindings\[0\]\.target"):
        await authoring.update_capability_step(
            workspace_id="echo",
            revision=1,
            step_id="echo",
            update=CapabilityStepUpdate(
                desc="Must not persist",
                input=[
                    InputValueBinding(
                        target=LocalPath.of("missing"),
                        value="bad",
                    )
                ],
            ),
        )

    after = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
async def test_add_step_from_capability_accepts_metadata_and_canonical_inputs(
    tmp_path: Path,
) -> None:
    draft_api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "add_capability_parity"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _structured_report)
    draft = _structured_report_draft()
    draft["steps"] = {}
    draft["routes"] = {}
    await draft_api.create_draft_workspace(workspace_id="report", draft=draft)

    result = await authoring.add_step_from_capability(
        workspace_id="report",
        revision=1,
        step_id="report",
        capability_name="demo.personal.structured_report",
        routes={"ok": "__end__"},
        desc="Publish report",
        retry=0,
        timeout_seconds=30,
        input_bindings=[
            InputPathBinding(
                path=GraphSourcePath.state("report", "title"),
                target=LocalPath.of("request", "title"),
            ),
            InputValueBinding(
                target=LocalPath.of("request", "format"),
                value="markdown",
            ),
        ],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )
    step = inspected["draft"]["steps"]["report"]

    assert result["revision"] == 2
    assert step["desc"] == "Publish report"
    assert step["retry"] == 0
    assert step["timeout_seconds"] == 30
    assert step["input"] == [
        {"path": "state.report.title", "target": "request.title"},
        {"value": "markdown", "target": "request.format"},
    ]
    assert (
        inspected["draft"]["state_schema"]["properties"]["report"]["properties"][
            "title"
        ]["type"]
        == "string"
    )


@pytest.mark.asyncio
async def test_add_step_from_capability_rejects_both_input_forms(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "add_capability_exclusive"),
        register_echo=True,
    )
    await draft_api.create_draft_workspace(workspace_id="echo", draft=_echo_draft())

    with pytest.raises(ValueError, match="mutually exclusive"):
        await authoring.add_step_from_capability(
            workspace_id="echo",
            revision=1,
            step_id="other",
            capability_name="demo.personal.echo_tool",
            routes={"ok": "__end__"},
            input_map={},
            input_bindings=[],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("desc", "retry", "timeout_seconds"),
    [
        ("", None, None),
        (None, -1, None),
        (None, None, 0),
    ],
)
async def test_add_step_from_capability_rejects_invalid_metadata_atomically(
    tmp_path: Path,
    desc: str | None,
    retry: int | None,
    timeout_seconds: int | None,
) -> None:
    workspace_id = f"invalid_add_metadata_{desc}_{retry}_{timeout_seconds}"
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / workspace_id),
        register_echo=True,
    )
    await draft_api.create_draft_workspace(
        workspace_id=workspace_id,
        draft=_echo_draft(),
    )
    before = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )

    with pytest.raises(ValidationError):
        await authoring.add_step_from_capability(
            workspace_id=workspace_id,
            revision=1,
            step_id="other",
            capability_name="demo.personal.echo_tool",
            routes={"ok": "__end__"},
            desc=desc,
            retry=retry,
            timeout_seconds=timeout_seconds,
        )

    after = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )
    assert after == before


def _echo_draft() -> dict[str, Any]:
    return {
        "name": "echo",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "state_schema": {"fields": {"echoed": {"type": "string"}}},
        "output_schema": {
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        "start": "echo",
        "steps": {
            "echo": {
                "use": "demo.personal.echo_tool",
                "input": [
                    {
                        "target": {"root": "local", "parts": ["text"]},
                        "path": {"root": "input", "parts": ["text"]},
                    }
                ],
                "output": [
                    {
                        "source": {"root": "local", "parts": ["echoed"]},
                        "target": {"root": "state", "parts": ["echoed"]},
                    }
                ],
            }
        },
        "routes": {"echo": {"ok": "__end__"}},
    }


class _Snapshot(BaseModel):
    clicked: bool


class _SnapshotOutput(BaseModel):
    after: _Snapshot


class _SnapshotInput(BaseModel):
    pass


@node(name="snapshot_tool", outcomes=("ok", "skipped"))
def _snapshot_tool(payload: _SnapshotInput) -> _SnapshotOutput:
    return _SnapshotOutput(after=_Snapshot(clicked=True))


class _ReportInputValue(BaseModel):
    title: str


class _NestedReportInput(BaseModel):
    report: _ReportInputValue


class _ReportOutputValue(BaseModel):
    title: str
    markdown: str


class _NestedReportOutput(BaseModel):
    report: _ReportOutputValue


@node(name="nested_report", outcomes=("ok",))
def _nested_report(payload: _NestedReportInput) -> _NestedReportOutput:
    return _NestedReportOutput(
        report=_ReportOutputValue(
            title=payload.report.title,
            markdown=f"# {payload.report.title}",
        )
    )


def _nested_report_draft() -> dict[str, Any]:
    return {
        "name": "nested_report",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "start": "render",
        "steps": {
            "render": {
                "use": "demo.personal.nested_report",
                "input": [],
                "output": [],
            }
        },
        "routes": {"render": {"ok": "__end__"}},
    }


class _StructuredRequest(BaseModel):
    title: str
    body: str
    format: Literal["markdown", "json"]
    note: str | None = None


class _StructuredAudit(BaseModel):
    title: str = ""


class _StructuredReportInput(BaseModel):
    request: _StructuredRequest
    audit: _StructuredAudit = Field(default_factory=_StructuredAudit)


class _StructuredReportOutput(BaseModel):
    rendered: str


@node(name="structured_report", outcomes=("ok",))
def _structured_report(payload: _StructuredReportInput) -> _StructuredReportOutput:
    return _StructuredReportOutput(
        rendered=(
            f"{payload.request.title}|{payload.request.body}|{payload.request.format}"
        )
    )


def _structured_report_draft(
    capability_name: str = "demo.personal.structured_report",
) -> dict[str, Any]:
    return {
        "name": "structured_report",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "start": "report",
        "steps": {
            "report": {
                "use": capability_name,
                "input": [],
                "output": [],
            }
        },
        "routes": {"report": {"ok": "__end__"}},
    }


def _draft_api(
    artifact_store: FileWorkflowArtifactStore,
    *,
    register_echo: bool = False,
) -> tuple[WorkflowDraftApi, WfMcpService, WorkflowDraftAuthoringApi]:
    mcp_root = artifact_store.root / "drafts_mcp" / str(id(artifact_store))
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(mcp_root),
    )
    if register_echo:
        service.register_connection(
            ConnectionConfig(id="demo.personal", server="demo", account="personal")
        )
        service.register_specs("demo.personal", echo_tool)
    context = context_from_service(service)
    return (
        WorkflowDraftApi(context),
        service,
        WorkflowDraftAuthoringApi(context, WorkflowDraftApi(context)),
    )


async def _create_structured_binding_api(
    tmp_path: Path,
    workspace_id: str,
) -> tuple[WorkflowDraftApi, WfMcpService, WorkflowApi]:
    draft_api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / workspace_id),
        register_echo=True,
    )
    service.register_specs("demo.personal", _structured_report)
    await draft_api.create_draft_workspace(
        workspace_id=workspace_id,
        draft=_structured_report_draft(),
    )
    return draft_api, service, WorkflowApi(authoring.context)


async def _create_nested_output_binding_api(
    tmp_path: Path,
    workspace_id: str,
) -> tuple[WorkflowDraftApi, WfMcpService, WorkflowApi]:
    draft_api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / workspace_id),
        register_echo=True,
    )
    service.register_specs(
        "demo.personal",
        replace(
            _nested_report,
            output_schema_contract={
                "type": "object",
                "properties": {
                    "report": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "markdown": {"type": "string"},
                        },
                        "required": ["title", "markdown"],
                    }
                },
                "required": ["report"],
            },
        ),
    )
    await draft_api.create_draft_workspace(
        workspace_id=workspace_id,
        draft=_nested_report_draft(),
    )
    return draft_api, service, WorkflowApi(authoring.context)


@pytest.mark.asyncio
async def test_patch_draft_applies_json_patch(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)

    result = await api.patch_draft(
        draft=_echo_draft(),
        patch=[
            {
                "op": "replace",
                "path": "/steps/echo/input/0/target/parts/0",
                "value": "message",
            }
        ],
    )

    assert result["status"] == "invalid"
    assert result["draft"]["steps"]["echo"]["input"][0]["target"] == {
        "root": "local",
        "parts": ["message"],
    }


@pytest.mark.asyncio
async def test_create_draft_workspace_creates_workspace(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_create_workspace")
    api, _service, _authoring = _draft_api(artifact_store)

    result = await api.create_draft_workspace(
        workspace_id="echo_ws",
        title="Echo Workspace",
        draft=_echo_draft(),
    )

    assert result["workspace_id"] == "echo_ws"
    assert result["revision"] == 1
    fetched = await api.get_draft_workspace(workspace_id="echo_ws", include_draft=True)

    assert fetched["workspace_id"] == "echo_ws"
    assert fetched["title"] == "Echo Workspace"
    assert fetched["draft"]["steps"]["echo"]["use"] == "demo.personal.echo_tool"


@pytest.mark.asyncio
async def test_create_empty_draft_workspace_persists_invalid_skeleton(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_create_empty")
    _drafts, _service, authoring = _draft_api(artifact_store)
    facade = WorkflowApi(authoring.context)

    created = await facade.create_empty_draft_workspace(
        workspace_id="control_first",
        name="control_first",
        title="Control First",
    )
    stored = await facade.get_draft_workspace(
        workspace_id="control_first",
        include_draft=True,
    )

    assert created["revision"] == 1
    assert created["status"] == "invalid"
    assert created["diagnostics"]
    assert stored["title"] == "Control First"
    assert stored["draft"] == {
        "name": "control_first",
        "input_schema": {"type": "object", "properties": {}},
        "state_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "outcomes": ["ok"],
        "output": [],
        "start": "",
        "steps": {},
        "routes": {},
    }


@pytest.mark.asyncio
async def test_create_empty_draft_workspace_preserves_custom_contract(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_create_contract")
    _drafts, _service, authoring = _draft_api(artifact_store)
    facade = WorkflowApi(authoring.context)
    input_schema = {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
    }
    state_schema = {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "x-reducer": "append",
            }
        },
    }
    output_schema = {
        "type": "object",
        "properties": {"report": {"type": "string"}},
    }

    await facade.create_empty_draft_workspace(
        workspace_id="custom_contract",
        name="custom_contract",
        title="Custom Contract",
        input_schema=input_schema,
        state_schema=state_schema,
        output_schema=output_schema,
        outcomes=("submitted", "cancelled"),
    )
    input_schema["properties"]["late"] = {"type": "boolean"}
    stored = await facade.get_draft_workspace(
        workspace_id="custom_contract",
        include_draft=True,
    )

    assert stored["title"] == "Custom Contract"
    assert stored["draft"]["input_schema"] == {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
    }
    assert stored["draft"]["state_schema"] == state_schema
    assert stored["draft"]["output_schema"] == output_schema
    assert stored["draft"]["outcomes"] == ["submitted", "cancelled"]


@pytest.mark.asyncio
async def test_create_empty_draft_workspace_isolates_default_schemas(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_schema_isolation")
    _drafts, _service, authoring = _draft_api(artifact_store)
    facade = WorkflowApi(authoring.context)
    input_schema = {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
    }

    await facade.create_empty_draft_workspace(
        workspace_id="isolated",
        name="isolated",
        input_schema=input_schema,
    )
    input_schema["properties"]["late"] = {"type": "boolean"}
    stored = await facade.get_draft_workspace(
        workspace_id="isolated",
        include_draft=True,
    )
    stored["draft"]["state_schema"]["properties"]["state_only"] = {"type": "string"}

    assert stored["draft"]["input_schema"] == {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
    }
    assert stored["draft"]["output_schema"] == {
        "type": "object",
        "properties": {},
    }


@pytest.mark.asyncio
async def test_create_empty_draft_workspace_reports_duplicate_conflict(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_create_conflict")
    _drafts, _service, authoring = _draft_api(artifact_store)
    facade = WorkflowApi(authoring.context)
    await facade.create_empty_draft_workspace(
        workspace_id="control_first",
        name="control_first",
    )

    duplicate = await facade.create_empty_draft_workspace(
        workspace_id="control_first",
        name="replacement",
    )

    assert duplicate["status"] == "conflict"
    assert duplicate["diagnostics"][0]["code"] == "workspace_exists"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "contract",
    [
        {"input_schema": cast(Any, [])},
        {"outcomes": ()},
        {"outcomes": cast(Any, (1,))},
        {"outcomes": ("ok", " ")},
        {"outcomes": ("ok", "ok")},
    ],
)
async def test_create_empty_draft_workspace_rejects_invalid_contract_before_mutation(
    tmp_path: Path,
    contract: dict[str, Any],
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_create_rejected")
    _drafts, _service, authoring = _draft_api(artifact_store)
    facade = WorkflowApi(authoring.context)

    with pytest.raises(ValueError):
        await facade.create_empty_draft_workspace(
            workspace_id="rejected",
            name="rejected",
            **contract,
        )

    assert await facade.list_draft_workspaces() == {"workspaces": []}


@pytest.mark.asyncio
async def test_set_draft_start_and_contract_replace_top_level_fields_atomically(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_set_lifecycle")
    _drafts, _service, authoring = _draft_api(artifact_store)
    facade = WorkflowApi(authoring.context)
    await facade.create_empty_draft_workspace(
        workspace_id="control_first",
        name="control_first",
        input_schema={
            "type": "object",
            "properties": {"topic": {"type": "string"}},
        },
    )
    state_schema = {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "x-reducer": "append",
            }
        },
    }
    output_schema = {
        "type": "object",
        "properties": {"report": {"type": "string"}},
    }

    forward = await facade.set_draft_start(
        workspace_id="control_first",
        revision=1,
        step_id="gate",
    )
    contract = await facade.set_draft_contract(
        workspace_id="control_first",
        revision=2,
        state_schema=state_schema,
        output_schema=output_schema,
        outcomes=("submitted", "cancelled"),
    )
    stored = await facade.get_draft_workspace(
        workspace_id="control_first",
        include_draft=True,
    )

    assert forward["revision"] == 2
    assert forward["status"] == "invalid"
    assert contract["revision"] == 3
    assert stored["draft"]["start"] == "gate"
    assert stored["draft"]["input_schema"] == {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
    }
    assert stored["draft"]["state_schema"] == state_schema
    assert stored["draft"]["output_schema"] == output_schema
    assert stored["draft"]["outcomes"] == ["submitted", "cancelled"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "arguments"),
    [
        ("start", {"step_id": " "}),
        ("start", {"step_id": cast(Any, 1)}),
        ("contract", {}),
        ("contract", {"state_schema": cast(Any, [])}),
        ("contract", {"outcomes": ()}),
        ("contract", {"outcomes": cast(Any, (1,))}),
        ("contract", {"outcomes": ("ok", " ")}),
        ("contract", {"outcomes": ("ok", "ok")}),
    ],
)
async def test_lifecycle_edits_reject_invalid_envelopes_without_mutation(
    tmp_path: Path,
    operation: str,
    arguments: dict[str, Any],
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / f"drafts_lifecycle_rejected_{operation}"
    )
    _drafts, _service, authoring = _draft_api(artifact_store)
    facade = WorkflowApi(authoring.context)
    await facade.create_empty_draft_workspace(
        workspace_id="control_first",
        name="control_first",
    )
    before = await facade.get_draft_workspace(
        workspace_id="control_first",
        include_draft=True,
    )

    with pytest.raises(ValueError):
        if operation == "start":
            await facade.set_draft_start(
                workspace_id="control_first",
                revision=2,
                **arguments,
            )
        else:
            await facade.set_draft_contract(
                workspace_id="control_first",
                revision=2,
                **arguments,
            )

    after = await facade.get_draft_workspace(
        workspace_id="control_first",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["start", "contract"])
async def test_lifecycle_edits_report_stale_revision_without_mutation(
    tmp_path: Path,
    operation: str,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / f"drafts_lifecycle_stale_{operation}"
    )
    _drafts, _service, authoring = _draft_api(artifact_store)
    facade = WorkflowApi(authoring.context)
    await facade.create_empty_draft_workspace(
        workspace_id="control_first",
        name="control_first",
    )
    before = await facade.get_draft_workspace(
        workspace_id="control_first",
        include_draft=True,
    )

    if operation == "start":
        result = await facade.set_draft_start(
            workspace_id="control_first",
            revision=2,
            step_id="gate",
        )
    else:
        result = await facade.set_draft_contract(
            workspace_id="control_first",
            revision=2,
            outcomes=("submitted", "cancelled"),
        )

    after = await facade.get_draft_workspace(
        workspace_id="control_first",
        include_draft=True,
    )
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert after == before


@pytest.mark.asyncio
async def test_list_draft_workspaces_returns_sorted_summaries_without_drafts(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_list_workspaces")
    api, _service, _authoring = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="b_draft",
        title="B Draft",
        draft=_echo_draft(),
    )

    await api.create_draft_workspace(
        workspace_id="a_draft",
        title="A Draft",
        draft=_echo_draft(),
    )

    result = await api.list_draft_workspaces()

    assert [workspace["workspace_id"] for workspace in result["workspaces"]] == [
        "a_draft",
        "b_draft",
    ]
    assert result["workspaces"][0]["title"] == "A Draft"
    assert "draft" not in result["workspaces"][0]


@pytest.mark.asyncio
async def test_delete_draft_workspace_is_idempotent(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_delete_workspace")
    api, _service, _authoring = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    deleted = await api.delete_draft_workspace(workspace_id="echo_ws")
    deleted_again = await api.delete_draft_workspace(workspace_id="echo_ws")
    listed = await api.list_draft_workspaces()

    assert deleted["workspace_id"] == "echo_ws"
    assert deleted["deleted"] is True
    assert deleted["status"] == "deleted"
    assert deleted_again["workspace_id"] == "echo_ws"
    assert deleted_again["deleted"] is False
    assert deleted_again["status"] == "not_found"
    assert listed["workspaces"] == []


@pytest.mark.asyncio
async def test_patch_draft_workspace_updates_revision(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch_workspace")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    patched = await api.patch_draft_workspace(
        workspace_id="echo_ws",
        revision=1,
        patch=[{"op": "replace", "path": "/name", "value": "echo_v2"}],
    )

    assert patched["revision"] == 2
    assert patched["status"] == "valid"


@pytest.mark.asyncio
async def test_patch_draft_workspace_stale_revision_does_not_mutate(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_patch_workspace_stale"
    )
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )
    before = await api.get_draft_workspace(
        workspace_id="echo_ws",
        include_draft=True,
    )

    result = await api.patch_draft_workspace(
        workspace_id="echo_ws",
        revision=2,
        patch=[{"op": "replace", "path": "/name", "value": "must_not_apply"}],
    )

    after = await api.get_draft_workspace(
        workspace_id="echo_ws",
        include_draft=True,
    )
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert after == before


@pytest.mark.asyncio
async def test_draft_workspace_patch_helpers_update_revision_and_bindings(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch_helpers")
    api, _service, _authoring = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    named = await api.set_draft_name(
        workspace_id="echo_ws",
        revision=1,
        name="echo_v2",
    )
    routed = await api.set_draft_route(
        workspace_id="echo_ws",
        revision=2,
        step_id="echo",
        outcome="error",
        target="__end__",
    )
    input_mapped = await api.set_step_input_map(
        workspace_id="echo_ws",
        revision=3,
        step_id="echo",
        input_map={"input.text": "message"},
    )

    output_mapped = await api.set_step_output_map(
        workspace_id="echo_ws",
        revision=4,
        step_id="echo",
        output_map={"echoed": "state.echoed"},
    )
    fetched = await api.get_draft_workspace(workspace_id="echo_ws", include_draft=True)

    assert named["revision"] == 2
    assert routed["revision"] == 3
    assert input_mapped["revision"] == 4
    assert output_mapped["revision"] == 5
    assert fetched["draft"]["name"] == "echo_v2"
    assert fetched["draft"]["routes"]["echo"]["error"] == "__end__"
    assert fetched["draft"]["steps"]["echo"]["input"] == [
        {
            "target": "message",
            "path": "input.text",
        }
    ]
    assert fetched["draft"]["steps"]["echo"]["output"] == [
        {
            "source": "echoed",
            "target": "state.echoed",
        }
    ]


@pytest.mark.asyncio
async def test_step_map_helpers_merge_with_existing_bindings(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch_helper_merge")
    api, _service, _authoring = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    input_mapped = await api.set_step_input_map(
        workspace_id="echo_ws",
        revision=1,
        step_id="echo",
        input_map={"input.extra": "extra"},
        merge=True,
    )
    output_mapped = await api.set_step_output_map(
        workspace_id="echo_ws",
        revision=2,
        step_id="echo",
        output_map={"extra": "state.extra"},
        merge=True,
    )
    replaced = await api.set_step_input_map(
        workspace_id="echo_ws",
        revision=3,
        step_id="echo",
        input_map={"input.final": "final"},
    )
    fetched = await api.get_draft_workspace(workspace_id="echo_ws", include_draft=True)

    assert input_mapped["revision"] == 2
    assert output_mapped["revision"] == 3
    assert replaced["revision"] == 4
    assert fetched["draft"]["steps"]["echo"]["input"] == [
        {
            "target": "final",
            "path": "input.final",
        }
    ]
    assert fetched["draft"]["steps"]["echo"]["output"] == [
        {
            "source": "echoed",
            "target": "state.echoed",
        },
        {
            "source": "extra",
            "target": "state.extra",
        },
    ]


@pytest.mark.asyncio
async def test_validate_draft_workspace_refreshes_status(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_validate_workspace")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=draft,
    )

    payload = await api.validate_draft_workspace(workspace_id="echo_ws")
    fetched = await api.get_draft_workspace(workspace_id="echo_ws")

    assert payload["revision"] == 1
    assert payload["status"] == "invalid"
    assert payload["diagnostics"][0]["code"] in (
        "unknown_outcome",
        "undeclared_edge_outcome",
    )
    assert fetched["status"] == "invalid"


@pytest.mark.asyncio
async def test_validate_draft_workspace_suggests_bind(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_repair_hint")
    api, service, authoring = _draft_api(artifact_store)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="snapshot_ws",
        draft={
            "name": "snapshot",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "snap",
            "steps": {
                "snap": {
                    "use": "demo.personal.snapshot_tool",
                    "input": [],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["after"]},
                            "target": {"root": "state", "parts": ["after"]},
                        }
                    ],
                }
            },
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    payload = await api.validate_draft_workspace(workspace_id="snapshot_ws")

    diagnostic = payload["diagnostics"][0]
    assert diagnostic["code"] == "invalid_destination_path"
    assert diagnostic["step_id"] == "snap"
    assert diagnostic["repair_hint"] == (
        "wf draft bind snapshot_ws --revision 1 "
        "--step snap --from local.after --to state.after"
    )


@pytest.mark.asyncio
async def test_patch_draft_workspace_validates_new_use_step_with_context_specs(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_patch_new_use")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    patched = await api.patch_draft_workspace(
        workspace_id="echo_ws",
        revision=1,
        patch=[
            {
                "op": "add",
                "path": "/steps/snap",
                "value": {
                    "use": "demo.personal.snapshot_tool",
                    "input": [],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["after"]},
                            "target": {"root": "state", "parts": ["after"]},
                        }
                    ],
                },
            },
            {
                "op": "replace",
                "path": "/routes/echo/ok",
                "value": "snap",
            },
            {
                "op": "add",
                "path": "/routes/snap",
                "value": {"ok": "__end__"},
            },
        ],
    )

    diagnostic = patched["diagnostics"][0]
    assert patched["status"] == "invalid"
    assert diagnostic["code"] == "invalid_destination_path"
    assert diagnostic["step_id"] == "snap"
    assert diagnostic["details"] == {
        "output_field": "after",
        "state_path": "state.after",
    }


@pytest.mark.asyncio
async def test_create_minimal_draft_workspace_minimal_success_path(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_minimal_workspace")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)

    result = await authoring.create_minimal_draft_workspace(
        workspace_id="echo_minimal",
        name="echo",
        capability_name="demo.personal.echo_tool",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        state_schema={"fields": {"echoed": {"type": "string"}}},
        output_schema={
            "type": "object",
            "properties": {"echoed": {"type": "string"}},
            "required": ["echoed"],
        },
        input_map={"input.text": "text"},
        output_map={"echoed": "state.echoed"},
    )

    assert result["workspace_id"] == "echo_minimal"
    fetched = await api.get_draft_workspace(
        workspace_id="echo_minimal", include_draft=True
    )
    assert fetched["draft"]["routes"]["call"]["ok"] == "__end__"
    assert fetched["draft"]["steps"]["call"]["use"] == "demo.personal.echo_tool"


@pytest.mark.asyncio
async def test_delegation_smoke_validate_draft_equivalence(tmp_path: Path) -> None:
    """WorkflowSurfaceHandlers.validate_draft delegates to WorkflowDraftApi."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_delegation_smoke")
    mcp_root = artifact_store.root / "delegation_mcp"
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(mcp_root),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    h = WorkflowSurfaceHandlers(service)
    context = context_from_service(service)
    api = WorkflowDraftApi(context)
    draft = _echo_draft()

    handler_result = await h.validate_draft(draft=draft)
    api_result = await api.validate_draft(draft=draft)

    assert handler_result["status"] == api_result["status"]
    assert handler_result["diagnostics"] == api_result["diagnostics"]
    assert (
        handler_result["compiled_plan"]["nodes"] == api_result["compiled_plan"]["nodes"]
    )


@pytest.mark.asyncio
async def test_facade_delegates_semantic_authoring_to_authoring_service(
    tmp_path: Path,
) -> None:
    """WorkflowApi constructs a sibling WorkflowDraftAuthoringApi."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_facade_delegation")
    mcp_root = artifact_store.root / "facade_mcp"
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(mcp_root),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)

    context = context_from_service(service)
    facade = WorkflowApi(context)

    assert facade.draft_authoring is not None
    assert isinstance(facade.draft_authoring, WorkflowDraftAuthoringApi)

    await facade.create_draft_workspace(
        workspace_id="ws1",
        draft=_echo_draft(),
    )
    result = await facade.bind_draft(
        workspace_id="ws1",
        revision=1,
        step_id="echo",
        source_path="local.echoed",
        target_path="state.echoed",
    )
    assert result["revision"] == 2


@pytest.mark.asyncio
async def test_bind_draft_workflow_input_to_step_input_projects_input_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_input")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = {**_echo_draft(), "input_schema": {"type": "object", "properties": {}}}
    await api.create_draft_workspace(
        workspace_id="bind_ws",
        draft=draft,
    )

    result = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=1,
        step_id="echo",
        source_path="input.text",
        target_path="local.text",
    )
    workspace = await api.get_draft_workspace(
        workspace_id="bind_ws", include_draft=True
    )

    assert result["revision"] == 2
    assert workspace["draft"]["input_schema"]["properties"]["text"]["type"] == "string"
    assert workspace["draft"]["steps"]["echo"]["input"] == [
        {"target": "text", "path": "input.text"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_workflow_input_to_step_input_reuses_existing_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_bind_existing_input_schema"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="bind_ws",
        draft=_echo_draft(),
    )

    result = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=1,
        step_id="echo",
        source_path="input.text",
        target_path="local.text",
    )
    workspace = await api.get_draft_workspace(
        workspace_id="bind_ws", include_draft=True
    )

    assert result["status"] == "valid", result["diagnostics"]
    assert result["revision"] == 2
    assert workspace["draft"]["steps"]["echo"]["input"] == [
        {"target": "text", "path": "input.text"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_workflow_input_to_step_input_can_repeat(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_repeat")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(workspace_id="bind_ws", draft=_echo_draft())

    first = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=1,
        step_id="echo",
        source_path="input.text",
        target_path="local.text",
    )
    second = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=first["revision"],
        step_id="echo",
        source_path="input.text",
        target_path="local.text",
    )
    workspace = await api.get_draft_workspace(
        workspace_id="bind_ws", include_draft=True
    )

    assert first["status"] == "valid"
    assert second["status"] == "valid"
    assert second["revision"] == 3
    assert workspace["draft"]["steps"]["echo"]["input"] == [
        {"target": "text", "path": "input.text"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_workflow_state_to_step_input_reuses_existing_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_bind_existing_state_schema"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = {
        **_echo_draft(),
        "state_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
        "steps": {
            "echo": {
                "use": "demo.personal.echo_tool",
                "input": [],
                "output": [],
            }
        },
    }
    await api.create_draft_workspace(workspace_id="bind_ws", draft=draft)

    result = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=1,
        step_id="echo",
        source_path="state.text",
        target_path="local.text",
    )
    workspace = await api.get_draft_workspace(
        workspace_id="bind_ws", include_draft=True
    )

    assert result["status"] == "valid", result["diagnostics"]
    assert result["revision"] == 2
    assert workspace["draft"]["steps"]["echo"]["input"] == [
        {"target": "text", "path": "state.text"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_output_to_nested_state_projects_state_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_output_nested")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="snapshot_ws",
        draft={
            "name": "snapshot",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "snap",
            "steps": {
                "snap": {
                    "use": "demo.personal.snapshot_tool",
                    "input": [],
                    "output": [],
                }
            },
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    result = await authoring.bind_draft(
        workspace_id="snapshot_ws",
        revision=1,
        step_id="snap",
        source_path="local.after",
        target_path="state.session.after",
    )
    workspace = await api.get_draft_workspace(
        workspace_id="snapshot_ws", include_draft=True
    )

    assert result["revision"] == 2
    assert (
        workspace["draft"]["state_schema"]["properties"]["session"]["properties"][
            "after"
        ]["$ref"]
        == "#/$defs/_Snapshot"
    )
    assert workspace["draft"]["steps"]["snap"]["output"] == [
        {"source": "after", "target": "state.session.after"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_projects_nested_local_input_schema(tmp_path: Path) -> None:
    api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "nested_local_input"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _nested_report)
    await api.create_draft_workspace(
        workspace_id="nested",
        draft=_nested_report_draft(),
    )

    result = await authoring.bind_draft(
        workspace_id="nested",
        revision=1,
        step_id="render",
        source_path="input.title",
        target_path="local.report.title",
    )
    workspace = await api.get_draft_workspace(workspace_id="nested", include_draft=True)
    draft = workspace["draft"]

    assert result["revision"] == 2
    assert draft["input_schema"]["properties"]["title"]["type"] == "string"
    assert draft["steps"]["render"]["input"] == [
        {"target": "report.title", "path": "input.title"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_reuses_nested_state_for_nested_local_input(
    tmp_path: Path,
) -> None:
    api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "nested_local_state_input"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _nested_report)
    draft = _nested_report_draft()
    draft["state_schema"] = {
        "type": "object",
        "properties": {
            "report": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
            }
        },
    }
    await api.create_draft_workspace(workspace_id="nested", draft=draft)

    result = await authoring.bind_draft(
        workspace_id="nested",
        revision=1,
        step_id="render",
        source_path="state.report.title",
        target_path="local.report.title",
    )
    workspace = await api.get_draft_workspace(workspace_id="nested", include_draft=True)

    assert result["revision"] == 2
    assert workspace["draft"]["steps"]["render"]["input"] == [
        {"target": "report.title", "path": "state.report.title"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_projects_nested_local_output_to_state(tmp_path: Path) -> None:
    api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "nested_local_output_state"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _nested_report)
    await api.create_draft_workspace(
        workspace_id="nested",
        draft=_nested_report_draft(),
    )

    result = await authoring.bind_draft(
        workspace_id="nested",
        revision=1,
        step_id="render",
        source_path="local.report.markdown",
        target_path="state.report.markdown",
    )
    workspace = await api.get_draft_workspace(workspace_id="nested", include_draft=True)
    draft = workspace["draft"]

    assert result["revision"] == 2
    assert draft["steps"]["render"]["output"] == [
        {"source": "report.markdown", "target": "state.report.markdown"}
    ]
    assert (
        draft["state_schema"]["properties"]["report"]["properties"]["markdown"]["type"]
        == "string"
    )


@pytest.mark.asyncio
async def test_bind_draft_lowers_nested_local_output_to_public_output(
    tmp_path: Path,
) -> None:
    api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "nested_local_public_output"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _nested_report)
    await api.create_draft_workspace(
        workspace_id="nested",
        draft=_nested_report_draft(),
    )

    result = await authoring.bind_draft(
        workspace_id="nested",
        revision=1,
        step_id="render",
        source_path="local.report.markdown",
        target_path="output.report.markdown",
    )
    workspace = await api.get_draft_workspace(workspace_id="nested", include_draft=True)
    draft = workspace["draft"]

    assert result["revision"] == 2
    assert draft["steps"]["render"]["output"] == [
        {"source": "report.markdown", "target": "state.report.markdown"}
    ]
    assert draft["output"] == [
        {"path": "state.report.markdown", "target": "report.markdown"}
    ]
    assert (
        draft["state_schema"]["properties"]["report"]["properties"]["markdown"]["type"]
        == "string"
    )
    assert (
        draft["output_schema"]["properties"]["report"]["properties"]["markdown"]["type"]
        == "string"
    )


@pytest.mark.asyncio
async def test_bind_draft_rebinds_nested_local_public_output(tmp_path: Path) -> None:
    api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "rebind_nested_local_public_output"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _nested_report)
    await api.create_draft_workspace(
        workspace_id="nested",
        draft=_nested_report_draft(),
    )
    first = await authoring.bind_draft(
        workspace_id="nested",
        revision=1,
        step_id="render",
        source_path="local.report.markdown",
        target_path="output.report.markdown",
    )

    second = await authoring.bind_draft(
        workspace_id="nested",
        revision=first["revision"],
        step_id="render",
        source_path="local.report.markdown",
        target_path="output.published.markdown",
    )
    workspace = await api.get_draft_workspace(workspace_id="nested", include_draft=True)

    assert second["revision"] == 3
    assert workspace["draft"]["steps"]["render"]["output"] == [
        {"source": "report.markdown", "target": "state.published.markdown"}
    ]
    assert workspace["draft"]["output"] == [
        {"path": "state.published.markdown", "target": "published.markdown"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_rejects_missing_nested_local_output_without_mutation(
    tmp_path: Path,
) -> None:
    api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "missing_nested_local_output"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _nested_report)
    await api.create_draft_workspace(
        workspace_id="nested",
        draft=_nested_report_draft(),
    )

    with pytest.raises(
        ValueError,
        match="source schema path 'report.missing' is not declared",
    ):
        await authoring.bind_draft(
            workspace_id="nested",
            revision=1,
            step_id="render",
            source_path="local.report.missing",
            target_path="state.report.missing",
        )
    workspace = await api.get_draft_workspace(workspace_id="nested", include_draft=True)

    assert workspace["revision"] == 1
    assert workspace["draft"]["steps"]["render"]["output"] == []


@pytest.mark.asyncio
async def test_bind_draft_stale_revision_precedes_nested_local_path_error(
    tmp_path: Path,
) -> None:
    api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "stale_nested_local_output"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _nested_report)
    await api.create_draft_workspace(
        workspace_id="nested",
        draft=_nested_report_draft(),
    )
    await api.patch_draft_workspace(
        workspace_id="nested",
        revision=1,
        patch=[{"op": "replace", "path": "/name", "value": "nested_v2"}],
    )

    result = await authoring.bind_draft(
        workspace_id="nested",
        revision=1,
        step_id="render",
        source_path="local.report.missing",
        target_path="state.report.missing",
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"


@pytest.mark.asyncio
async def test_set_step_input_bindings_replaces_structured_inputs_in_order(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_structured_binding_api(
        tmp_path,
        "structured_input",
    )

    result = await api.set_step_input_bindings(
        workspace_id="structured_input",
        revision=1,
        step_id="report",
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.state("report", "title"),
                target=LocalPath.of("request", "title"),
            ),
            InputPathBinding(
                path=GraphSourcePath.state("report", "markdown"),
                target=LocalPath.of("request", "body"),
            ),
            InputValueBinding(
                target=LocalPath.of("request", "format"),
                value="markdown",
            ),
        ],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="structured_input",
        include_draft=True,
    )

    assert result["revision"] == 2
    assert inspected["draft"]["steps"]["report"]["input"] == [
        {"target": "request.title", "path": "state.report.title"},
        {"target": "request.body", "path": "state.report.markdown"},
        {"target": "request.format", "value": "markdown"},
    ]


@pytest.mark.asyncio
async def test_set_step_input_bindings_preserves_source_fan_out(tmp_path: Path) -> None:
    draft_api, _service, api = await _create_structured_binding_api(
        tmp_path,
        "input_fan_out",
    )

    await api.set_step_input_bindings(
        workspace_id="input_fan_out",
        revision=1,
        step_id="report",
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.state("report", "title"),
                target=LocalPath.of("request", "title"),
            ),
            InputPathBinding(
                path=GraphSourcePath.state("report", "title"),
                target=LocalPath.of("audit", "title"),
            ),
        ],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="input_fan_out",
        include_draft=True,
    )

    assert inspected["draft"]["steps"]["report"]["input"] == [
        {"target": "request.title", "path": "state.report.title"},
        {"target": "audit.title", "path": "state.report.title"},
    ]


@pytest.mark.asyncio
async def test_set_step_output_bindings_replaces_in_order_and_preserves_source_fan_out(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "draft-output-bindings",
    )

    result = await api.set_step_output_bindings(
        workspace_id="draft-output-bindings",
        revision=1,
        step_id="render",
        bindings=[
            OutputBinding(
                source=LocalPath.parse("report.title"),
                target=StatePath.parse("state.report.title"),
            ),
            OutputBinding(
                source=LocalPath.parse("report.title"),
                target=StatePath.parse("state.audit.title"),
            ),
        ],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="draft-output-bindings",
        include_draft=True,
    )

    assert result["revision"] == 2
    assert inspected["draft"]["steps"]["render"]["output"] == [
        {"source": "report.title", "target": "state.report.title"},
        {"source": "report.title", "target": "state.audit.title"},
    ]
    state_schema = inspected["draft"]["state_schema"]
    assert state_schema["properties"]["report"]["properties"]["title"] == {
        "type": "string"
    }
    assert state_schema["properties"]["audit"]["properties"]["title"] == {
        "type": "string"
    }


@pytest.mark.asyncio
async def test_set_step_output_bindings_projects_whole_capability_payload(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "whole-output-binding",
    )

    await api.set_step_output_bindings(
        workspace_id="whole-output-binding",
        revision=1,
        step_id="render",
        bindings=[
            OutputBinding(
                source=LocalPath.root(),
                target=StatePath.parse("state.raw_result"),
            )
        ],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="whole-output-binding",
        include_draft=True,
    )

    raw_result_schema = inspected["draft"]["state_schema"]["properties"]["raw_result"]
    assert raw_result_schema["type"] == "object"
    assert raw_result_schema["properties"]["report"]["properties"]["title"] == {
        "type": "string"
    }


@pytest.mark.asyncio
async def test_set_step_output_bindings_accepts_exact_existing_target_and_is_noop(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "equivalent-output-binding",
    )
    binding = OutputBinding(
        source=LocalPath.parse("report.title"),
        target=StatePath.parse("state.report.title"),
    )
    first = await api.set_step_output_bindings(
        workspace_id="equivalent-output-binding",
        revision=1,
        step_id="render",
        bindings=[binding],
    )
    second = await api.set_step_output_bindings(
        workspace_id="equivalent-output-binding",
        revision=first["revision"],
        step_id="render",
        bindings=[binding],
    )

    assert first["revision"] == 2
    assert second["revision"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bindings", "message"),
    [
        (
            [
                OutputBinding(
                    source=LocalPath.parse("report.missing"),
                    target=StatePath.parse("state.report.missing"),
                )
            ],
            r"bindings\[0\]\.source 'report\.missing' is not declared",
        ),
        (
            [
                OutputBinding(
                    source=LocalPath.parse("report.title"),
                    target=StatePath.parse("state.report.title"),
                ),
                OutputBinding(
                    source=LocalPath.parse("report.markdown"),
                    target=StatePath.parse("state.report.title"),
                ),
            ],
            r"bindings\[0\]\.target 'state\.report\.title' overlaps "
            r"bindings\[1\]\.target 'state\.report\.title'",
        ),
        (
            [
                OutputBinding(
                    source=LocalPath.parse("report.title"),
                    target=StatePath.parse("state.report"),
                ),
                OutputBinding(
                    source=LocalPath.parse("report.markdown"),
                    target=StatePath.parse("state.report.title"),
                ),
            ],
            r"bindings\[0\]\.target 'state\.report' overlaps "
            r"bindings\[1\]\.target 'state\.report\.title'",
        ),
    ],
)
async def test_set_step_output_bindings_rejects_semantic_errors_without_mutation(
    tmp_path: Path,
    bindings: list[OutputBinding],
    message: str,
) -> None:
    workspace_id = f"invalid_output_bindings_{len(message)}"
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        workspace_id,
    )
    before = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )

    with pytest.raises(ValueError, match=message):
        await api.set_step_output_bindings(
            workspace_id=workspace_id,
            revision=1,
            step_id="render",
            bindings=bindings,
        )

    after = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
async def test_set_step_output_bindings_reports_invalid_source_before_overlap(
    tmp_path: Path,
) -> None:
    _draft_api_instance, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "invalid_source_before_overlap",
    )

    with pytest.raises(
        ValueError,
        match=r"bindings\[0\]\.source 'report\.missing' is not declared",
    ):
        await api.set_step_output_bindings(
            workspace_id="invalid_source_before_overlap",
            revision=1,
            step_id="render",
            bindings=[
                OutputBinding(
                    source=LocalPath.parse("report.missing"),
                    target=StatePath.parse("state.report.title"),
                ),
                OutputBinding(
                    source=LocalPath.parse("report.title"),
                    target=StatePath.parse("state.report.title"),
                ),
            ],
        )


@pytest.mark.asyncio
async def test_set_step_output_bindings_rejects_incompatible_existing_target(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "incompatible-output-binding",
    )
    await draft_api.patch_draft_workspace(
        workspace_id="incompatible-output-binding",
        revision=1,
        patch=[
            {
                "op": "replace",
                "path": "/state_schema",
                "value": {
                    "type": "object",
                    "properties": {
                        "report": {
                            "type": "object",
                            "properties": {"title": {"type": "integer"}},
                        }
                    },
                },
            }
        ],
    )
    before = await draft_api.get_draft_workspace(
        workspace_id="incompatible-output-binding",
        include_draft=True,
    )

    with pytest.raises(
        ValueError,
        match=(
            r"bindings\[0\]\.target 'state\.report\.title' cannot receive "
            r"source 'report\.title'"
        ),
    ):
        await api.set_step_output_bindings(
            workspace_id="incompatible-output-binding",
            revision=2,
            step_id="render",
            bindings=[
                OutputBinding(
                    source=LocalPath.parse("report.title"),
                    target=StatePath.parse("state.report.title"),
                )
            ],
        )

    after = await draft_api.get_draft_workspace(
        workspace_id="incompatible-output-binding",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
async def test_set_step_output_bindings_clears_outputs_without_removing_projection(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "clear-output-bindings",
    )
    first = await api.set_step_output_bindings(
        workspace_id="clear-output-bindings",
        revision=1,
        step_id="render",
        bindings=[
            OutputBinding(
                source=LocalPath.parse("report.title"),
                target=StatePath.parse("state.report.title"),
            )
        ],
    )
    cleared = await api.set_step_output_bindings(
        workspace_id="clear-output-bindings",
        revision=first["revision"],
        step_id="render",
        bindings=[],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="clear-output-bindings",
        include_draft=True,
    )

    assert cleared["revision"] == 3
    assert inspected["draft"]["steps"]["render"]["output"] == []
    assert (
        inspected["draft"]["state_schema"]["properties"]["report"]["properties"][
            "title"
        ]["type"]
        == "string"
    )
    assert set(
        inspected["draft"]["state_schema"]["properties"]["report"]["properties"][
            "title"
        ]
    ) == {"type"}


@pytest.mark.asyncio
async def test_set_step_output_bindings_rejects_missing_step_without_mutation(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "missing-output-step",
    )
    before = await draft_api.get_draft_workspace(
        workspace_id="missing-output-step",
        include_draft=True,
    )

    with pytest.raises(KeyError, match="missing"):
        await api.set_step_output_bindings(
            workspace_id="missing-output-step",
            revision=1,
            step_id="missing",
            bindings=[],
        )

    after = await draft_api.get_draft_workspace(
        workspace_id="missing-output-step",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
async def test_set_step_output_bindings_rejects_non_capability_step_without_mutation(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "non-capability-output-step",
    )
    await draft_api.patch_draft_workspace(
        workspace_id="non-capability-output-step",
        revision=1,
        patch=[{"op": "replace", "path": "/steps/render", "value": {"join": {}}}],
    )
    before = await draft_api.get_draft_workspace(
        workspace_id="non-capability-output-step",
        include_draft=True,
    )

    with pytest.raises(ValueError, match="does not declare a capability use"):
        await api.set_step_output_bindings(
            workspace_id="non-capability-output-step",
            revision=2,
            step_id="render",
            bindings=[],
        )

    after = await draft_api.get_draft_workspace(
        workspace_id="non-capability-output-step",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bindings",
    [
        [
            OutputBinding(
                source=LocalPath.parse("report.missing"),
                target=StatePath.parse("state.report.missing"),
            )
        ],
        [
            OutputBinding(
                source=LocalPath.parse("report.title"),
                target=StatePath.parse("state.report"),
            ),
            OutputBinding(
                source=LocalPath.parse("report.markdown"),
                target=StatePath.parse("state.report.title"),
            ),
        ],
    ],
)
async def test_set_step_output_bindings_stale_revision_precedes_semantic_errors(
    tmp_path: Path,
    bindings: list[OutputBinding],
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        f"stale-output-binding-{len(bindings)}",
    )
    workspace_id = f"stale-output-binding-{len(bindings)}"

    result = await api.set_step_output_bindings(
        workspace_id=workspace_id,
        revision=2,
        step_id="render",
        bindings=bindings,
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    inspected = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )
    assert inspected["revision"] == 1


@pytest.mark.asyncio
async def test_set_step_output_bindings_stale_revision_precedes_missing_step(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "stale-output-missing-step",
    )
    before = await draft_api.get_draft_workspace(
        workspace_id="stale-output-missing-step",
        include_draft=True,
    )

    result = await api.set_step_output_bindings(
        workspace_id="stale-output-missing-step",
        revision=2,
        step_id="missing",
        bindings=[],
    )

    after = await draft_api.get_draft_workspace(
        workspace_id="stale-output-missing-step",
        include_draft=True,
    )
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert after == before


@pytest.mark.asyncio
async def test_set_step_output_bindings_stale_revision_precedes_non_capability_step(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "stale-output-non-capability",
    )
    await draft_api.patch_draft_workspace(
        workspace_id="stale-output-non-capability",
        revision=1,
        patch=[{"op": "replace", "path": "/steps/render", "value": {"join": {}}}],
    )
    before = await draft_api.get_draft_workspace(
        workspace_id="stale-output-non-capability",
        include_draft=True,
    )

    result = await api.set_step_output_bindings(
        workspace_id="stale-output-non-capability",
        revision=1,
        step_id="render",
        bindings=[],
    )

    after = await draft_api.get_draft_workspace(
        workspace_id="stale-output-non-capability",
        include_draft=True,
    )
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert after == before


@pytest.mark.asyncio
async def test_set_step_output_bindings_stale_revision_precedes_duplicate_target(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "stale-output-duplicate-target",
    )
    before = await draft_api.get_draft_workspace(
        workspace_id="stale-output-duplicate-target",
        include_draft=True,
    )

    result = await api.set_step_output_bindings(
        workspace_id="stale-output-duplicate-target",
        revision=2,
        step_id="render",
        bindings=[
            OutputBinding(
                source=LocalPath.parse("report.title"),
                target=StatePath.parse("state.report.title"),
            ),
            OutputBinding(
                source=LocalPath.parse("report.markdown"),
                target=StatePath.parse("state.report.title"),
            ),
        ],
    )

    after = await draft_api.get_draft_workspace(
        workspace_id="stale-output-duplicate-target",
        include_draft=True,
    )
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert after == before


@pytest.mark.asyncio
async def test_set_step_output_bindings_stale_revision_precedes_incompatible_schema(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_nested_output_binding_api(
        tmp_path,
        "stale-output-incompatible-schema",
    )
    await draft_api.patch_draft_workspace(
        workspace_id="stale-output-incompatible-schema",
        revision=1,
        patch=[
            {
                "op": "replace",
                "path": "/state_schema",
                "value": {
                    "type": "object",
                    "properties": {
                        "report": {
                            "type": "object",
                            "properties": {"title": {"type": "integer"}},
                        }
                    },
                },
            }
        ],
    )
    before = await draft_api.get_draft_workspace(
        workspace_id="stale-output-incompatible-schema",
        include_draft=True,
    )

    result = await api.set_step_output_bindings(
        workspace_id="stale-output-incompatible-schema",
        revision=1,
        step_id="render",
        bindings=[
            OutputBinding(
                source=LocalPath.parse("report.title"),
                target=StatePath.parse("state.report.title"),
            )
        ],
    )

    after = await draft_api.get_draft_workspace(
        workspace_id="stale-output-incompatible-schema",
        include_draft=True,
    )
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bindings", "message"),
    [
        (
            [
                InputValueBinding(
                    target=LocalPath.of("request", "missing"),
                    value="value",
                )
            ],
            r"bindings\[0\]\.target 'request.missing' is not declared",
        ),
        (
            [
                InputValueBinding(
                    target=LocalPath.of("request", "title"),
                    value="first",
                ),
                InputValueBinding(
                    target=LocalPath.of("request", "title"),
                    value="second",
                ),
            ],
            r"bindings\[0\]\.target 'request.title' overlaps bindings\[1\]",
        ),
        (
            [
                InputValueBinding(
                    target=LocalPath.of("request"),
                    value={
                        "title": "Report",
                        "body": "Body",
                        "format": "markdown",
                    },
                ),
                InputValueBinding(
                    target=LocalPath.of("request", "title"),
                    value="Report",
                ),
            ],
            r"bindings\[0\]\.target 'request' overlaps bindings\[1\]",
        ),
        (
            [
                InputValueBinding(
                    target=LocalPath.of("request", "format"),
                    value="html",
                )
            ],
            r"bindings\[0\]\.value does not satisfy schema at 'request.format'",
        ),
        (
            [InputValueBinding(target=LocalPath.root(), value="not-an-object")],
            r"bindings\[0\]\.value for target '\.' must be a JSON object",
        ),
    ],
)
async def test_set_step_input_bindings_rejects_semantic_errors_without_mutation(
    tmp_path: Path,
    bindings: list[InputPathBinding | InputValueBinding],
    message: str,
) -> None:
    workspace_id = f"invalid_bindings_{len(message)}"
    draft_api, _service, api = await _create_structured_binding_api(
        tmp_path,
        workspace_id,
    )
    before = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )

    with pytest.raises(ValueError, match=message):
        await api.set_step_input_bindings(
            workspace_id=workspace_id,
            revision=1,
            step_id="report",
            bindings=bindings,
        )

    after = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
async def test_set_step_input_bindings_rejects_remote_target_reference_without_mutation(
    tmp_path: Path,
) -> None:
    draft_api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "remote_binding_target"),
        register_echo=True,
    )
    remote_spec = replace(
        _structured_report,
        name="remote_structured_report",
        input_schema_contract={
            "type": "object",
            "properties": {"request": {"$ref": "https://example.com/request.json"}},
        },
    )
    service.register_specs("demo.personal", remote_spec)
    await draft_api.create_draft_workspace(
        workspace_id="remote_target",
        draft=_structured_report_draft("demo.personal.remote_structured_report"),
    )
    api = WorkflowApi(authoring.context)
    before = await draft_api.get_draft_workspace(
        workspace_id="remote_target",
        include_draft=True,
    )

    with pytest.raises(ValueError, match="unsupported reference"):
        await api.set_step_input_bindings(
            workspace_id="remote_target",
            revision=1,
            step_id="report",
            bindings=[
                InputValueBinding(
                    target=LocalPath.of("request"),
                    value={},
                )
            ],
        )

    after = await draft_api.get_draft_workspace(
        workspace_id="remote_target",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
async def test_set_step_input_bindings_rejects_non_capability_step_without_mutation(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "non_capability_binding"),
        register_echo=True,
    )
    draft = _structured_report_draft()
    draft["steps"]["report"] = {"join": {}}
    await draft_api.create_draft_workspace(workspace_id="non_capability", draft=draft)
    api = WorkflowApi(authoring.context)
    before = await draft_api.get_draft_workspace(
        workspace_id="non_capability",
        include_draft=True,
    )

    with pytest.raises(ValueError, match="does not declare a capability use"):
        await api.set_step_input_bindings(
            workspace_id="non_capability",
            revision=1,
            step_id="report",
            bindings=[],
        )

    after = await draft_api.get_draft_workspace(
        workspace_id="non_capability",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "binding",
    [
        InputValueBinding(target=LocalPath.of("missing"), value="value"),
        InputValueBinding(
            target=LocalPath.of("request", "format"),
            value="html",
        ),
    ],
)
async def test_set_step_input_bindings_stale_revision_wins_over_semantic_errors(
    tmp_path: Path,
    binding: InputValueBinding,
) -> None:
    draft_api, _service, api = await _create_structured_binding_api(
        tmp_path,
        f"stale_binding_{len(str(binding.target))}",
    )
    workspace_id = f"stale_binding_{len(str(binding.target))}"

    result = await api.set_step_input_bindings(
        workspace_id=workspace_id,
        revision=2,
        step_id="report",
        bindings=[binding],
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    inspected = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )
    assert inspected["revision"] == 1


@pytest.mark.asyncio
async def test_set_step_input_bindings_projects_whole_capability_payload(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_structured_binding_api(
        tmp_path,
        "whole_payload_binding",
    )

    await api.set_step_input_bindings(
        workspace_id="whole_payload_binding",
        revision=1,
        step_id="report",
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.input("payload"),
                target=LocalPath.root(),
            )
        ],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="whole_payload_binding",
        include_draft=True,
    )

    payload_schema = inspected["draft"]["input_schema"]["properties"]["payload"]
    assert payload_schema["properties"]["request"]["$ref"].endswith(
        "/_StructuredRequest"
    )
    assert inspected["draft"]["steps"]["report"]["input"] == [
        {"target": ".", "path": "input.payload"}
    ]


@pytest.mark.asyncio
async def test_set_step_input_bindings_projects_input_and_state_but_not_context(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_structured_binding_api(
        tmp_path,
        "multi_schema_binding",
    )

    await api.set_step_input_bindings(
        workspace_id="multi_schema_binding",
        revision=1,
        step_id="report",
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.input("title"),
                target=LocalPath.of("request", "title"),
            ),
            InputPathBinding(
                path=GraphSourcePath.state("body"),
                target=LocalPath.of("request", "body"),
            ),
            InputValueBinding(
                target=LocalPath.of("request", "format"),
                value="markdown",
            ),
            InputPathBinding(
                path=GraphSourcePath.context("prior_outcome"),
                target=LocalPath.of("request", "note"),
            ),
        ],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="multi_schema_binding",
        include_draft=True,
    )
    draft = inspected["draft"]

    assert draft["input_schema"]["properties"]["title"]["type"] == "string"
    assert draft["state_schema"]["properties"]["body"]["type"] == "string"
    assert set(draft["input_schema"]["properties"]) == {"title"}
    assert set(draft["state_schema"]["properties"]) == {"body"}


@pytest.mark.asyncio
async def test_set_step_input_bindings_accepts_explicit_null_and_exact_noop(
    tmp_path: Path,
) -> None:
    draft_api, _service, api = await _create_structured_binding_api(
        tmp_path,
        "null_and_noop_binding",
    )
    bindings = [
        InputValueBinding(
            target=LocalPath.of("request", "note"),
            value=None,
        )
    ]

    first = await api.set_step_input_bindings(
        workspace_id="null_and_noop_binding",
        revision=1,
        step_id="report",
        bindings=bindings,
    )
    second = await api.set_step_input_bindings(
        workspace_id="null_and_noop_binding",
        revision=first["revision"],
        step_id="report",
        bindings=bindings,
    )

    assert first["revision"] == 2
    assert second["revision"] == 2
    inspected = await draft_api.get_draft_workspace(
        workspace_id="null_and_noop_binding",
        include_draft=True,
    )
    assert inspected["draft"]["steps"]["report"]["input"] == [
        {"target": "request.note", "value": None}
    ]


@pytest.mark.asyncio
async def test_set_step_input_bindings_compiles_and_assembles_nested_payload(
    tmp_path: Path,
) -> None:
    draft_api, service, api = await _create_structured_binding_api(
        tmp_path,
        "execute_structured_binding",
    )
    bindings = [
        InputPathBinding(
            path=GraphSourcePath.input("title"),
            target=LocalPath.of("request", "title"),
        ),
        InputPathBinding(
            path=GraphSourcePath.input("body"),
            target=LocalPath.of("request", "body"),
        ),
        InputValueBinding(
            target=LocalPath.of("request", "format"),
            value="markdown",
        ),
    ]
    await api.set_step_input_bindings(
        workspace_id="execute_structured_binding",
        revision=1,
        step_id="report",
        bindings=bindings,
    )

    compiled = await draft_api.compile_draft_workspace(
        workspace_id="execute_structured_binding"
    )
    plan = RawWorkflowPlan.model_validate(compiled["compiled_plan"])
    run = await service.run_workflow_from_plan(
        plan,
        {"title": "Thesis", "body": "Evidence"},
    )

    assert run.error is None
    assert run.trace[0].output == {"rendered": "Thesis|Evidence|markdown"}


@pytest.mark.asyncio
async def test_set_step_output_bindings_compile_and_execute_source_fan_out(
    tmp_path: Path,
) -> None:
    draft_api, service, api = await _create_structured_binding_api(
        tmp_path,
        "execute_output_fan_out",
    )
    input_result = await api.set_step_input_bindings(
        workspace_id="execute_output_fan_out",
        revision=1,
        step_id="report",
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.input("title"),
                target=LocalPath.of("request", "title"),
            ),
            InputPathBinding(
                path=GraphSourcePath.input("body"),
                target=LocalPath.of("request", "body"),
            ),
            InputValueBinding(
                target=LocalPath.of("request", "format"),
                value="markdown",
            ),
        ],
    )
    await api.set_step_output_bindings(
        workspace_id="execute_output_fan_out",
        revision=input_result["revision"],
        step_id="report",
        bindings=[
            OutputBinding(
                source=LocalPath.parse("rendered"),
                target=StatePath.parse("state.report"),
            ),
            OutputBinding(
                source=LocalPath.parse("rendered"),
                target=StatePath.parse("state.audit"),
            ),
        ],
    )

    compiled = await draft_api.compile_draft_workspace(
        workspace_id="execute_output_fan_out"
    )
    plan = RawWorkflowPlan.model_validate(compiled["compiled_plan"])
    run = await service.run_workflow_from_plan(
        plan,
        {"title": "Thesis", "body": "Evidence"},
    )

    assert run.error is None
    assert run.state["report"] == "Thesis|Evidence|markdown"
    assert run.state["audit"] == "Thesis|Evidence|markdown"


@pytest.mark.asyncio
async def test_bind_draft_rejects_unsupported_direction(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_bad_direction")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(workspace_id="bind_ws", draft=_echo_draft())

    with pytest.raises(ValueError, match="unsupported bind direction"):
        await authoring.bind_draft(
            workspace_id="bind_ws",
            revision=1,
            step_id="echo",
            source_path="input.message",
            target_path="state.message",
        )


@pytest.mark.asyncio
async def test_add_step_from_capability_wires_route_inputs_and_state_outputs(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_add_step")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    result = await authoring.add_step_from_capability(
        workspace_id="echo_ws",
        revision=1,
        step_id="snap",
        capability_name="demo.personal.snapshot_tool",
        route_from_step="echo",
        route_from_outcome="ok",
        routes={"ok": "__end__", "skipped": "__end__"},
        input_map={},
        bind_outputs={"after": "state.after"},
    )

    assert result["revision"] == 2
    assert result["status"] == "valid"
    fetched = await api.get_draft_workspace(workspace_id="echo_ws", include_draft=True)
    draft = fetched["draft"]
    assert draft["steps"]["snap"]["use"] == "demo.personal.snapshot_tool"
    assert draft["routes"]["echo"]["ok"] == "snap"
    assert draft["routes"]["snap"]["ok"] == "__end__"
    assert draft["steps"]["snap"]["output"] == [
        {
            "source": "after",
            "target": "state.after",
        }
    ]
    assert draft["state_schema"]["properties"]["after"]["$ref"] == "#/$defs/_Snapshot"
    assert draft["state_schema"]["$defs"]["_Snapshot"]["properties"]["clicked"] == {
        "title": "Clicked",
        "type": "boolean",
    }


@pytest.mark.asyncio
async def test_add_step_from_capability_projects_nested_local_input(
    tmp_path: Path,
) -> None:
    api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "nested_capability_input"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _nested_report)
    draft = _nested_report_draft()
    draft["steps"] = {}
    draft["routes"] = {}
    await api.create_draft_workspace(workspace_id="nested_add", draft=draft)

    result = await authoring.add_step_from_capability(
        workspace_id="nested_add",
        revision=1,
        step_id="render",
        capability_name="demo.personal.nested_report",
        routes={"ok": "__end__"},
        input_map={"input.title": "report.title"},
        bind_outputs={},
    )
    workspace = await api.get_draft_workspace(
        workspace_id="nested_add", include_draft=True
    )
    validated = await api.validate_draft_workspace(workspace_id="nested_add")

    assert result["revision"] == 2
    assert workspace["draft"]["input_schema"]["properties"]["title"]["type"] == (
        "string"
    )
    assert workspace["draft"]["steps"]["render"]["input"] == [
        {"target": "report.title", "path": "input.title"}
    ]
    assert validated["status"] == "valid", validated["diagnostics"]


@pytest.mark.asyncio
async def test_add_step_from_capability_preserves_whole_payload_input(
    tmp_path: Path,
) -> None:
    api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "whole_payload_capability_input"),
        register_echo=True,
    )
    service.register_specs("demo.personal", _nested_report)
    draft = _nested_report_draft()
    draft["steps"] = {}
    draft["routes"] = {}
    await api.create_draft_workspace(workspace_id="whole_payload", draft=draft)

    result = await authoring.add_step_from_capability(
        workspace_id="whole_payload",
        revision=1,
        step_id="render",
        capability_name="demo.personal.nested_report",
        routes={"ok": "__end__"},
        input_map={"input.payload": "."},
        bind_outputs={},
    )
    workspace = await api.get_draft_workspace(
        workspace_id="whole_payload", include_draft=True
    )

    assert result["revision"] == 2
    assert workspace["draft"]["steps"]["render"]["input"] == [
        {"target": ".", "path": "input.payload"}
    ]


@pytest.mark.asyncio
async def test_add_step_from_capability_rejects_existing_step_id(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_add_step_duplicate")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError, match="draft step 'echo' already exists"):
        await authoring.add_step_from_capability(
            workspace_id="echo_ws",
            revision=1,
            step_id="echo",
            capability_name="demo.personal.echo_tool",
            route_from_step=None,
            route_from_outcome="ok",
            routes={"ok": "__end__"},
            input_map={},
            bind_outputs={},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step_name", "step_payload"),
    [
        (
            "use",
            {
                "use": "demo.personal.echo_tool",
                "input": [],
                "output": [],
            },
        ),
        (
            "foreach",
            {"foreach": {"over": "state.items", "as": "item"}},
        ),
        (
            "interrupt",
            {"interrupt": {"kind": "review", "outcomes": ["submitted"]}},
        ),
        ("join", {"join": {}}),
        ("end", {"end": {"outcome": "ok"}}),
        (
            "when",
            {
                "when": {
                    "if": {"op": "exists", "path": "state.ready"},
                    "then": "echo",
                }
            },
        ),
        (
            "choose",
            {
                "choose": {
                    "clauses": [
                        {
                            "if": {"op": "exists", "path": "state.ready"},
                            "then": "echo",
                        }
                    ]
                }
            },
        ),
        (
            "match",
            {
                "match": {
                    "value": "state.status",
                    "cases": [{"equals": "ready", "then": "echo"}],
                }
            },
        ),
        (
            "subgraph",
            {
                "subgraph": {
                    "workflow": {"name": "child"},
                    "outcomes": ["ok"],
                }
            },
        ),
    ],
)
async def test_add_step_accepts_every_typed_draft_step(
    tmp_path: Path,
    step_name: str,
    step_payload: dict[str, Any],
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / f"draft_add_{step_name}")
    draft_api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    api = WorkflowApi(authoring.context)
    await draft_api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())

    step = TypeAdapter(DraftStep).validate_python(step_payload)
    result = await api.add_step(
        workspace_id="draft_ws",
        revision=1,
        step_id="new_step",
        step=step,
    )

    assert result["revision"] == 2
    workspace = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert workspace["draft"]["steps"]["new_step"] == step.model_dump(
        mode="json", by_alias=True
    )


@pytest.mark.asyncio
async def test_add_step_routes_incoming_and_outgoing_edges_atomically(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "draft_add_routes")
    draft_api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    api = WorkflowApi(authoring.context)
    await draft_api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())

    step = TypeAdapter(DraftStep).validate_python(
        {"use": "demo.personal.echo_tool", "input": [], "output": []}
    )
    result = await api.add_step(
        workspace_id="draft_ws",
        revision=1,
        step_id="new_step",
        step=step,
        incoming=RouteSource("echo", "ok"),
        routes={"ok": "__end__"},
    )

    assert result["revision"] == 2
    workspace = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert workspace["draft"]["routes"]["echo"]["ok"] == "new_step"
    assert workspace["draft"]["routes"]["new_step"] == {"ok": "__end__"}


@pytest.mark.asyncio
async def test_add_step_stale_revision_wins_over_content_preflight(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "draft_add_stale")
    draft_api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    api = WorkflowApi(authoring.context)
    await draft_api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())
    before = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    step = TypeAdapter(DraftStep).validate_python({"join": {}})

    result = await api.add_step(
        workspace_id="draft_ws",
        revision=2,
        step_id="echo",
        step=step,
    )

    after = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["bind", "capability_add"])
async def test_capability_aware_edits_stale_revision_wins_over_semantic_errors(
    tmp_path: Path,
    operation: str,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / f"draft_capability_stale_{operation}"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="draft_ws",
        draft=_echo_draft(),
    )
    before = await api.get_draft_workspace(
        workspace_id="draft_ws",
        include_draft=True,
    )

    if operation == "bind":
        result = await authoring.bind_draft(
            workspace_id="draft_ws",
            revision=2,
            step_id="missing",
            source_path="input.text",
            target_path="local.text",
        )
    else:
        result = await authoring.add_step_from_capability(
            workspace_id="draft_ws",
            revision=2,
            step_id="new_step",
            capability_name="missing.connection.unknown_tool",
        )

    after = await api.get_draft_workspace(
        workspace_id="draft_ws",
        include_draft=True,
    )
    assert result["status"] == "conflict"
    assert result["revision"] == before["revision"]
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert after == before


@pytest.mark.asyncio
async def test_add_step_adds_missing_incoming_route_parent_atomically(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "draft_add_missing_parent")
    draft_api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    api = WorkflowApi(authoring.context)
    draft = _echo_draft()
    draft["routes"] = {}
    await draft_api.create_draft_workspace(workspace_id="draft_ws", draft=draft)

    step = TypeAdapter(DraftStep).validate_python(
        {"use": "demo.personal.echo_tool", "input": [], "output": []}
    )
    result = await api.add_step(
        workspace_id="draft_ws",
        revision=1,
        step_id="new_step",
        step=step,
        incoming=RouteSource("echo", "ok"),
    )

    assert result["revision"] == 2
    workspace = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert workspace["draft"]["routes"]["echo"] == {"ok": "new_step"}


@pytest.mark.asyncio
async def test_add_step_distinguishes_missing_and_explicit_empty_routes(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "draft_add_empty_routes")
    draft_api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    api = WorkflowApi(authoring.context)
    await draft_api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())

    step_adapter = TypeAdapter(DraftStep)
    step_without_routes = step_adapter.validate_python(
        {"use": "demo.personal.echo_tool", "input": [], "output": []}
    )
    first = await api.add_step(
        workspace_id="draft_ws",
        revision=1,
        step_id="no_routes",
        step=step_without_routes,
        routes=None,
    )
    assert first["revision"] == 2
    after_none = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert "no_routes" not in after_none["draft"]["routes"]

    step_with_empty_routes = step_adapter.validate_python(
        {"use": "demo.personal.echo_tool", "input": [], "output": []}
    )
    second = await api.add_step(
        workspace_id="draft_ws",
        revision=2,
        step_id="empty_routes",
        step=step_with_empty_routes,
        routes={},
    )
    assert second["revision"] == 3
    after_empty = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert after_empty["draft"]["routes"]["empty_routes"] == {}


@pytest.mark.asyncio
async def test_add_step_rejects_unknown_incoming_outcome_without_mutation(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "draft_add_bad_incoming")
    draft_api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    api = WorkflowApi(authoring.context)
    await draft_api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())

    draft_store = authoring.drafts._draft_store()
    assert isinstance(draft_store, FileDraftWorkspaceStore)
    workspace_path = draft_store._workspace_path("draft_ws")
    before_bytes = workspace_path.read_bytes()
    before = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    step = TypeAdapter(DraftStep).validate_python(
        {"use": "demo.personal.echo_tool", "input": [], "output": []}
    )

    with pytest.raises(ValueError, match="unknown incoming route outcome"):
        await api.add_step(
            workspace_id="draft_ws",
            revision=1,
            step_id="new_step",
            step=step,
            incoming=RouteSource("echo", "missing"),
        )

    after = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert workspace_path.read_bytes() == before_bytes
    assert after["revision"] == before["revision"]
    assert after["draft"] == before["draft"]


async def _assert_add_step_rejected_without_mutation(
    api: WorkflowApi,
    draft_api: WorkflowDraftApi,
    *,
    step_id: str = "new_step",
    incoming: RouteSource | None = None,
    routes: dict[str, str] | None = None,
    message: str,
) -> None:
    before = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )

    step = TypeAdapter(DraftStep).validate_python(
        {"use": "demo.personal.echo_tool", "input": [], "output": []}
    )
    with pytest.raises(ValueError, match=message):
        await api.add_step(
            workspace_id="draft_ws",
            revision=1,
            step_id=step_id,
            step=step,
            incoming=incoming,
            routes=routes,
        )

    after = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert after["revision"] == before["revision"]
    assert after["draft"] == before["draft"]


@pytest.mark.asyncio
async def test_add_step_rejects_invalid_routing_inputs_atomically(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "draft_add_errors")
    draft_api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    api = WorkflowApi(authoring.context)
    await draft_api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())

    await _assert_add_step_rejected_without_mutation(
        api,
        draft_api,
        incoming=RouteSource("missing", "ok"),
        message="unknown incoming source",
    )

    await _assert_add_step_rejected_without_mutation(
        api,
        draft_api,
        step_id="echo",
        routes={"ok": "__end__"},
        message="already exists",
    )

    await _assert_add_step_rejected_without_mutation(
        api,
        draft_api,
        routes={"typo": "__end__"},
        message="unknown route outcome",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "step_payload",
    [
        {"end": {"outcome": "ok"}},
        {
            "when": {
                "if": {"op": "exists", "path": "state.ready"},
                "then": "echo",
            }
        },
        {
            "choose": {
                "clauses": [
                    {
                        "if": {"op": "exists", "path": "state.ready"},
                        "then": "echo",
                    }
                ]
            }
        },
        {
            "match": {
                "value": "state.status",
                "cases": [{"equals": "ready", "then": "echo"}],
            }
        },
    ],
)
async def test_add_step_rejects_routes_for_non_routable_steps_atomically(
    tmp_path: Path,
    step_payload: dict[str, Any],
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "draft_add_forbidden_routes")
    draft_api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    api = WorkflowApi(authoring.context)
    await draft_api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())

    before = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    step = TypeAdapter(DraftStep).validate_python(step_payload)
    with pytest.raises(ValueError, match="routes are not allowed"):
        await api.add_step(
            workspace_id="draft_ws",
            revision=1,
            step_id="new_step",
            step=step,
            routes={"ok": "__end__"},
        )
    after = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert after["revision"] == before["revision"]
    assert after["draft"] == before["draft"]


@pytest.mark.asyncio
async def test_add_step_accepts_incomplete_declared_route_subset(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "draft_add_partial_routes")
    draft_api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)
    api = WorkflowApi(authoring.context)
    await draft_api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())

    step = TypeAdapter(DraftStep).validate_python(
        {"use": "demo.personal.snapshot_tool", "input": [], "output": []}
    )
    result = await api.add_step(
        workspace_id="draft_ws",
        revision=1,
        step_id="new_step",
        step=step,
        routes={"ok": "__end__"},
    )

    assert result["revision"] == 2
    workspace = await draft_api.get_draft_workspace(
        workspace_id="draft_ws", include_draft=True
    )
    assert workspace["draft"]["routes"]["new_step"] == {"ok": "__end__"}


@pytest.mark.asyncio
async def test_branch_draft_updates_routes_atomically(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_branch")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="branching",
        draft={
            "name": "branching",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "classify",
            "steps": {
                "classify": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [],
                },
                "tool_error": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [],
                },
            },
            "routes": {
                "classify": {"ok": "classify"},
                "tool_error": {"ok": "__end__"},
            },
        },
    )

    result = await authoring.branch_draft(
        workspace_id="branching",
        revision=1,
        step_id="classify",
        routes={"ok": "classify", "error": "tool_error"},
    )
    assert result["revision"] == 2
    workspace = await api.get_draft_workspace(
        workspace_id="branching", include_draft=True
    )
    assert workspace["draft"]["routes"]["classify"] == {
        "ok": "classify",
        "error": "tool_error",
    }
    assert "tool_error" in workspace["draft"]["steps"]


@pytest.mark.asyncio
async def test_handle_draft_updates_multiple_source_outcomes(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_handle")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="handling",
        draft={
            "name": "handling",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "lookup",
            "steps": {
                "lookup": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [],
                },
                "transform": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [],
                },
            },
            "routes": {
                "lookup": {"ok": "transform", "error": "lookup"},
                "transform": {"ok": "__end__", "error": "transform"},
            },
        },
    )

    result = await authoring.handle_draft(
        workspace_id="handling",
        revision=1,
        branches=[
            RouteSource(step_id="lookup", outcome="error"),
            RouteSource(step_id="transform", outcome="error"),
        ],
        target="__end__",
    )
    assert result["revision"] == 2
    workspace = await api.get_draft_workspace(
        workspace_id="handling", include_draft=True
    )
    assert workspace["draft"]["routes"]["lookup"]["error"] == "__end__"
    assert workspace["draft"]["routes"]["transform"]["error"] == "__end__"
    assert workspace["draft"]["routes"]["lookup"]["ok"] == "transform"
    assert workspace["draft"]["routes"]["transform"]["ok"] == "__end__"


@pytest.mark.asyncio
async def test_branch_draft_no_change_when_routes_unchanged(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_branch_noop")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft=_echo_draft(),
    )
    before = await api.get_draft_workspace(workspace_id="noop_ws", include_draft=True)

    result = await authoring.branch_draft(
        workspace_id="noop_ws",
        revision=1,
        step_id="echo",
        routes={"ok": "__end__"},
    )
    after = await api.get_draft_workspace(workspace_id="noop_ws", include_draft=True)
    assert result["revision"] == 1
    assert after == before


@pytest.mark.asyncio
async def test_branch_draft_no_change_still_checks_revision(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_branch_noop_stale")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft=_echo_draft(),
    )

    result = await authoring.branch_draft(
        workspace_id="noop_ws",
        revision=2,
        step_id="echo",
        routes={"ok": "__end__"},
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"


@pytest.mark.asyncio
async def test_handle_draft_empty_branches_noop(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_handle_noop")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft=_echo_draft(),
    )
    before = await api.get_draft_workspace(workspace_id="noop_ws", include_draft=True)

    result = await authoring.handle_draft(
        workspace_id="noop_ws",
        revision=1,
        branches=[],
        target="fail",
    )
    after = await api.get_draft_workspace(workspace_id="noop_ws", include_draft=True)
    assert result["revision"] == 1
    assert after == before


@pytest.mark.asyncio
async def test_handle_draft_no_change_still_checks_revision(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_handle_noop_stale")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft=_echo_draft(),
    )

    result = await authoring.handle_draft(
        workspace_id="noop_ws",
        revision=2,
        branches=[],
        target="fail",
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    ["branch", "handle", "remove_route", "remove_step", "remove_binding"],
)
async def test_route_and_remove_edits_stale_revision_wins_over_semantic_errors(
    tmp_path: Path,
    operation: str,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / f"draft_route_remove_stale_{operation}"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    if operation in {"branch", "handle", "remove_route"}:
        draft["routes"] = "not-an-object"
    elif operation == "remove_step":
        draft["steps"] = "not-an-object"
    await api.create_draft_workspace(workspace_id="draft_ws", draft=draft)
    before = await api.get_draft_workspace(
        workspace_id="draft_ws",
        include_draft=True,
    )

    if operation == "branch":
        result = await authoring.branch_draft(
            workspace_id="draft_ws",
            revision=2,
            step_id="echo",
            routes={"error": "__end__"},
        )
    elif operation == "handle":
        result = await authoring.handle_draft(
            workspace_id="draft_ws",
            revision=2,
            branches=[RouteSource(step_id="echo", outcome="error")],
            target="__end__",
        )
    elif operation == "remove_route":
        result = await authoring.remove_draft_route(
            workspace_id="draft_ws",
            revision=2,
            step_id="echo",
            outcome="ok",
        )
    elif operation == "remove_step":
        result = await authoring.remove_draft_step(
            workspace_id="draft_ws",
            revision=2,
            step_id="echo",
        )
    else:
        result = await authoring.remove_draft_binding(
            workspace_id="draft_ws",
            revision=2,
            step_id="missing",
            inputs=("text",),
        )

    after = await api.get_draft_workspace(
        workspace_id="draft_ws",
        include_draft=True,
    )
    assert result["status"] == "conflict"
    assert result["revision"] == before["revision"]
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    assert after == before


@pytest.mark.asyncio
async def test_add_step_from_capability_infers_single_outcome_route(
    tmp_path: Path,
) -> None:
    """One declared outcome named 'done', no routes supplied -> routes to __end__."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_single_outcome")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool)
    await api.create_draft_workspace(
        workspace_id="single",
        draft=_echo_draft(),
    )

    result = await authoring.add_step_from_capability(
        workspace_id="single",
        revision=1,
        step_id="done_step",
        capability_name="demo.personal.echo_tool",
    )
    assert result["revision"] == 2
    workspace = await api.get_draft_workspace(workspace_id="single", include_draft=True)
    assert workspace["draft"]["routes"]["done_step"] == {"ok": "__end__"}


@pytest.mark.asyncio
async def test_add_step_from_capability_requires_complete_routes_for_multi_outcome(
    tmp_path: Path,
) -> None:
    """Multiple declared outcomes with incomplete explicit routes raises ValueError."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_multi_outcome")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="multi",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError, match="missing routes"):
        await authoring.add_step_from_capability(
            workspace_id="multi",
            revision=1,
            step_id="snap",
            capability_name="demo.personal.snapshot_tool",
            routes={"ok": "__end__"},
        )


@pytest.mark.asyncio
async def test_add_step_from_capability_rejects_unknown_routes_for_multi_outcome(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_unknown_outcome")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="unknown_multi",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError, match="unknown routes") as exc_info:
        await authoring.add_step_from_capability(
            workspace_id="unknown_multi",
            revision=1,
            step_id="snap",
            capability_name="demo.personal.snapshot_tool",
            routes={"ok": "__end__", "skipped": "__end__", "typo": "__end__"},
        )

    message = str(exc_info.value)
    assert "declares outcomes ('ok', 'skipped')" in message
    assert "unknown routes ['typo']" in message
    assert "remove --route entries for ['typo']" in message


@pytest.mark.asyncio
async def test_add_step_rejects_unknown_single_outcome_route_with_repair(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_unknown_single_outcome"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="unknown_single",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError) as exc_info:
        await authoring.add_step_from_capability(
            workspace_id="unknown_single",
            revision=1,
            step_id="second",
            capability_name="demo.personal.echo_tool",
            routes={"ok": "__end__", "error": "fail"},
        )

    message = str(exc_info.value)
    assert "declares outcomes ('ok',)" in message
    assert "unknown routes ['error']" in message
    assert "remove --route entries for ['error']" in message


@pytest.mark.asyncio
async def test_add_step_rejects_missing_outcomes_only_with_repair(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_missing_outcome_only")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="missing_single",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError) as exc_info:
        await authoring.add_step_from_capability(
            workspace_id="missing_single",
            revision=1,
            step_id="snap",
            capability_name="demo.personal.snapshot_tool",
            routes={"ok": "__end__"},
        )

    message = str(exc_info.value)
    assert "declares outcomes ('ok', 'skipped')" in message
    assert "missing routes ['skipped']" in message
    assert "add --route OUTCOME=TARGET for ['skipped']" in message


# -- Draft remove helpers --


@pytest.mark.asyncio
async def test_remove_draft_route_persists_invalid_workspace(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "remove_route")
    api, _service, authoring = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="route_ws",
        draft={
            "name": "route_ws",
            "start": "echo",
            "steps": {
                "echo": {"use": "demo.personal.echo_tool", "input": [], "output": []}
            },
            "routes": {"echo": {"ok": "__end__"}},
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
        },
    )

    result = await authoring.remove_draft_route(
        workspace_id="route_ws",
        revision=1,
        step_id="echo",
        outcome="ok",
    )

    assert result["revision"] == 2
    assert result["status"] == "invalid"
    fetched = await api.get_draft_workspace(
        workspace_id="route_ws",
        include_draft=True,
    )
    assert fetched["draft"]["routes"]["echo"] == {}


@pytest.mark.asyncio
async def test_remove_draft_step_removes_outgoing_routes_not_inbound_routes(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "remove_step")
    api, _service, authoring = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="step_ws",
        draft={
            "name": "step_ws",
            "start": "first",
            "steps": {
                "first": {"use": "demo.personal.echo_tool", "input": [], "output": []},
                "second": {"use": "demo.personal.echo_tool", "input": [], "output": []},
            },
            "routes": {
                "first": {"ok": "second"},
                "second": {"ok": "__end__"},
            },
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
        },
    )

    result = await authoring.remove_draft_step(
        workspace_id="step_ws",
        revision=1,
        step_id="second",
    )

    assert result["revision"] == 2
    assert result["status"] == "invalid"
    assert any(
        item["code"] == "unknown_edge_destination" for item in result["diagnostics"]
    )
    fetched = await api.get_draft_workspace(
        workspace_id="step_ws",
        include_draft=True,
    )
    assert "second" not in fetched["draft"]["steps"]
    assert "second" not in fetched["draft"]["routes"]
    assert fetched["draft"]["routes"]["first"]["ok"] == "second"


@pytest.mark.asyncio
async def test_remove_draft_binding_removes_input_and_output_bindings(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "remove_binding")
    api, _service, authoring = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="binding_ws",
        draft={
            "name": "binding_ws",
            "start": "echo",
            "steps": {
                "echo": {
                    "use": "demo.personal.echo_tool",
                    "input": [
                        {"path": "input.message", "target": "message"},
                        {"path": "input.extra", "target": "extra"},
                    ],
                    "output": [
                        {"source": "echoed", "target": "state.echoed"},
                        {"source": "debug", "target": "state.debug"},
                    ],
                }
            },
            "routes": {"echo": {"ok": "__end__"}},
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
        },
    )

    result = await authoring.remove_draft_binding(
        workspace_id="binding_ws",
        revision=1,
        step_id="echo",
        inputs=("message",),
        outputs=("debug",),
    )

    assert result["revision"] == 2
    fetched = await api.get_draft_workspace(
        workspace_id="binding_ws",
        include_draft=True,
    )
    assert fetched["draft"]["steps"]["echo"]["input"] == [
        {"path": "input.extra", "target": "extra"}
    ]
    assert fetched["draft"]["steps"]["echo"]["output"] == [
        {"source": "echoed", "target": "state.echoed"}
    ]


@pytest.mark.asyncio
async def test_remove_draft_binding_envelope_error_precedes_revision_check(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "draft_remove_binding_envelope_precedence"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(workspace_id="draft_ws", draft=_echo_draft())
    before = await api.get_draft_workspace(
        workspace_id="draft_ws",
        include_draft=True,
    )

    with pytest.raises(
        ValueError,
        match="pass at least one input or output binding to remove",
    ):
        await authoring.remove_draft_binding(
            workspace_id="draft_ws",
            revision=2,
            step_id="echo",
        )

    after = await api.get_draft_workspace(
        workspace_id="draft_ws",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
async def test_remove_missing_draft_element_is_noop(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "remove_noop")
    api, _service, authoring = _draft_api(artifact_store)
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft={
            "name": "noop_ws",
            "start": "echo",
            "steps": {
                "echo": {"use": "demo.personal.echo_tool", "input": [], "output": []}
            },
            "routes": {"echo": {"ok": "__end__"}},
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
        },
    )

    result = await authoring.remove_draft_route(
        workspace_id="noop_ws",
        revision=1,
        step_id="echo",
        outcome="missing",
    )

    assert result["revision"] == 1


@pytest.mark.asyncio
async def test_compile_draft_workspace_returns_compiled_plan(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_compile")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="compile_me",
        draft=_echo_draft(),
    )
    before = await api.get_draft_workspace(
        workspace_id="compile_me", include_draft=True
    )
    result = await api.compile_draft_workspace(workspace_id="compile_me")
    after = await api.get_draft_workspace(workspace_id="compile_me", include_draft=True)
    assert result["compiled_plan"]["name"] == "echo"
    assert result["required_capabilities"]
    assert after == before


@pytest.mark.asyncio
async def test_compile_draft_workspace_invalid_returns_diagnostics(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_compile_invalid")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}
    await api.create_draft_workspace(
        workspace_id="invalid_ws",
        draft=draft,
    )
    result = await api.compile_draft_workspace(workspace_id="invalid_ws")
    assert result["status"] == "invalid"
    assert "compiled_plan" not in result
    assert result["diagnostics"]


def _workflow_output_binding_draft() -> dict[str, Any]:
    draft = _echo_draft()
    draft["state_schema"] = {
        "type": "object",
        "properties": {
            "report": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
            },
            "items": {"type": "array", "items": {"type": "string"}},
        },
    }
    draft["output_schema"] = {
        "type": "object",
        "properties": {
            "format": {"type": "string"},
            "metadata": {
                "type": "object",
                "properties": {"reviewed": {"type": "boolean"}},
                "required": ["reviewed"],
            },
            "tags": {"type": "array", "items": {"type": "string"}},
            "note": {"type": ["string", "null"]},
            "context_value": {},
        },
    }
    draft["output"] = []
    return draft


@pytest.mark.asyncio
async def test_set_workflow_output_bindings_projects_nested_paths_and_literals(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "workflow_outputs"),
        register_echo=True,
    )
    draft = _workflow_output_binding_draft()
    await draft_api.create_draft_workspace(workspace_id="report", draft=draft)
    bindings: list[InputBinding] = [
        InputPathBinding(
            path=GraphSourcePath.state("report", "title"),
            target=LocalPath.of("report", "title"),
        ),
        InputPathBinding(
            path=GraphSourcePath.state("report", "title"),
            target=LocalPath.of("audit", "title"),
        ),
        InputValueBinding(target=LocalPath.of("format"), value="markdown"),
    ]

    first = await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=1,
        bindings=bindings,
    )
    second = await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=first["revision"],
        bindings=bindings,
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )

    assert first["revision"] == 2
    assert second["revision"] == 2
    assert inspected["draft"]["output"] == [
        {"path": "state.report.title", "target": "report.title"},
        {"path": "state.report.title", "target": "audit.title"},
        {"value": "markdown", "target": "format"},
    ]
    assert inspected["draft"]["output_schema"]["properties"]["report"]["properties"][
        "title"
    ] == {"type": "string"}
    assert inspected["draft"]["output_schema"]["properties"]["audit"]["properties"][
        "title"
    ] == {"type": "string"}

    cleared = await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=2,
        bindings=[],
    )
    cleared_workspace = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )
    assert cleared["revision"] == 3
    assert cleared_workspace["draft"]["output"] == []
    assert (
        cleared_workspace["draft"]["output_schema"]
        == inspected["draft"]["output_schema"]
    )


@pytest.mark.asyncio
async def test_set_workflow_output_bindings_projects_input_and_whole_state(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "workflow_output_sources"),
        register_echo=True,
    )
    draft = _workflow_output_binding_draft()
    draft["input_schema"]["properties"]["request"] = {
        "type": "object",
        "properties": {"title": {"type": "string"}},
    }
    await draft_api.create_draft_workspace(workspace_id="report", draft=draft)

    await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=1,
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.input("request", "title"),
                target=LocalPath.of("input_title"),
            ),
            InputPathBinding(
                path=GraphSourcePath.state(),
                target=LocalPath.of("snapshot"),
            ),
        ],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )

    output_schema = inspected["draft"]["output_schema"]["properties"]
    assert output_schema["input_title"] == {"type": "string"}
    assert output_schema["snapshot"]["properties"]["report"]["properties"]["title"] == {
        "type": "string"
    }


@pytest.mark.asyncio
async def test_set_workflow_output_bindings_accepts_declared_context_and_literals(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "workflow_output_values"),
        register_echo=True,
    )
    await draft_api.create_draft_workspace(
        workspace_id="report",
        draft=_workflow_output_binding_draft(),
    )
    bindings: list[InputBinding] = [
        InputPathBinding(
            path=GraphSourcePath.context("prior_outcome"),
            target=LocalPath.of("context_value"),
        ),
        InputValueBinding(
            target=LocalPath.of("metadata"),
            value={"reviewed": True},
        ),
        InputValueBinding(target=LocalPath.of("tags"), value=["thesis"]),
        InputValueBinding(target=LocalPath.of("note"), value=None),
    ]

    result = await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=1,
        bindings=bindings,
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )

    assert result["revision"] == 2
    assert inspected["draft"]["output"] == [
        {"path": "context.prior_outcome", "target": "context_value"},
        {"value": {"reviewed": True}, "target": "metadata"},
        {"value": ["thesis"], "target": "tags"},
        {"value": None, "target": "note"},
    ]


@pytest.mark.asyncio
async def test_set_workflow_output_bindings_accepts_strict_root_bindings(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "workflow_output_root"),
        register_echo=True,
    )
    schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    draft = _echo_draft()
    draft["input_schema"] = schema
    draft["output_schema"] = schema
    draft["output"] = []
    await draft_api.create_draft_workspace(workspace_id="report", draft=draft)

    path_result = await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=1,
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.input(),
                target=LocalPath.root(),
            )
        ],
    )
    literal_result = await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=path_result["revision"],
        bindings=[
            InputValueBinding(
                target=LocalPath.root(),
                value={"text": "Thesis"},
            )
        ],
    )

    assert path_result["revision"] == 2
    assert literal_result["revision"] == 3


@pytest.mark.asyncio
async def test_set_workflow_output_bindings_validates_root_literal_complete_schema(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "workflow_output_root_literal"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["output_schema"] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }
    draft["output"] = []
    await draft_api.create_draft_workspace(workspace_id="report", draft=draft)
    before = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )

    with pytest.raises(
        ValueError,
        match=r"bindings\[0\]\.value does not satisfy schema at '\.'",
    ):
        await authoring.set_workflow_output_bindings(
            workspace_id="report",
            revision=1,
            bindings=[
                InputValueBinding(
                    target=LocalPath.root(),
                    value={"wrong": "field"},
                )
            ],
        )

    after = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bindings", "message"),
    [
        (
            [
                InputPathBinding(
                    path=GraphSourcePath.state("missing"),
                    target=LocalPath.of("missing"),
                )
            ],
            r"bindings\[0\]\.path 'state\.missing' is not declared",
        ),
        (
            [
                InputPathBinding(
                    path=GraphSourcePath.context("prior_outcome"),
                    target=LocalPath.of("missing"),
                )
            ],
            r"bindings\[0\]\.path 'context\.prior_outcome' requires a declared "
            "output target",
        ),
        (
            [InputValueBinding(target=LocalPath.of("missing"), value="x")],
            r"bindings\[0\]\.target 'missing' is not declared",
        ),
        (
            [
                InputPathBinding(
                    path=GraphSourcePath.state("report"),
                    target=LocalPath.of("report"),
                ),
                InputValueBinding(
                    target=LocalPath.of("report", "format"),
                    value="markdown",
                ),
            ],
            r"bindings\[0\]\.target 'report' overlaps bindings\[1\]",
        ),
        (
            [
                InputValueBinding(
                    target=LocalPath.of("format"),
                    value="markdown",
                ),
                InputValueBinding(
                    target=LocalPath.of("format"),
                    value="json",
                ),
            ],
            r"bindings\[0\]\.target 'format' overlaps bindings\[1\]",
        ),
        (
            [
                InputPathBinding(
                    path=GraphSourcePath.state(),
                    target=LocalPath.root(),
                ),
                InputValueBinding(
                    target=LocalPath.of("format"),
                    value="markdown",
                ),
            ],
            r"bindings\[0\]\.target '\.' overlaps bindings\[1\]",
        ),
        (
            [
                InputPathBinding(
                    path=GraphSourcePath.state("missing"),
                    target=LocalPath.of("report"),
                ),
                InputValueBinding(
                    target=LocalPath.of("report", "format"),
                    value="markdown",
                ),
            ],
            r"bindings\[0\]\.path 'state\.missing' is not declared",
        ),
        (
            [
                InputPathBinding(
                    path=GraphSourcePath.state("report"),
                    target=LocalPath.of("format"),
                )
            ],
            r"bindings\[0\]\.target 'format' cannot receive source "
            r"'state\.report'",
        ),
        (
            [
                InputPathBinding(
                    path=GraphSourcePath.state("report"),
                    target=LocalPath.root(),
                )
            ],
            r"bindings\[0\]\.target '\.' already has an incompatible schema",
        ),
        (
            [InputValueBinding(target=LocalPath.root(), value="not-an-object")],
            r"bindings\[0\]\.value for root target must be an object",
        ),
    ],
)
async def test_set_workflow_output_bindings_rejects_without_mutation(
    tmp_path: Path,
    bindings: list[InputBinding],
    message: str,
) -> None:
    workspace_id = f"invalid_output_{abs(hash(message))}"
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / workspace_id),
        register_echo=True,
    )
    await draft_api.create_draft_workspace(
        workspace_id=workspace_id,
        draft=_workflow_output_binding_draft(),
    )
    before = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )

    with pytest.raises(ValueError, match=message):
        await authoring.set_workflow_output_bindings(
            workspace_id=workspace_id,
            revision=1,
            bindings=bindings,
        )

    after = await draft_api.get_draft_workspace(
        workspace_id=workspace_id,
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
async def test_set_workflow_output_bindings_stale_revision_wins_without_mutation(
    tmp_path: Path,
) -> None:
    draft_api, _service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "stale_workflow_output"),
        register_echo=True,
    )
    await draft_api.create_draft_workspace(
        workspace_id="report",
        draft=_workflow_output_binding_draft(),
    )
    before = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )

    result = await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=2,
        bindings=[
            InputValueBinding(target=LocalPath.of("missing"), value="x"),
            InputValueBinding(target=LocalPath.of("missing", "child"), value="y"),
        ],
    )

    assert result["status"] == "conflict"
    assert result["diagnostics"][0]["code"] == "revision_conflict"
    after = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )
    assert after == before


@pytest.mark.asyncio
async def test_set_workflow_output_bindings_compile_and_execute(
    tmp_path: Path,
) -> None:
    draft_api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "execute_workflow_output"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["state_schema"] = {
        "type": "object",
        "properties": {
            "report": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
            }
        },
    }
    draft["steps"]["echo"]["output"] = [
        {"source": "echoed", "target": "state.report.title"}
    ]
    draft["output_schema"] = {
        "type": "object",
        "properties": {"format": {"type": "string"}},
    }
    draft["output"] = []
    await draft_api.create_draft_workspace(workspace_id="report", draft=draft)

    await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=1,
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.state("report", "title"),
                target=LocalPath.of("report", "title"),
            ),
            InputPathBinding(
                path=GraphSourcePath.state("report", "title"),
                target=LocalPath.of("audit", "title"),
            ),
            InputValueBinding(target=LocalPath.of("format"), value="markdown"),
        ],
    )
    compiled = await draft_api.compile_draft_workspace(workspace_id="report")
    run = await service.run_workflow_from_plan(
        RawWorkflowPlan.model_validate(compiled["compiled_plan"]),
        {"text": "Thesis"},
    )

    assert run.error is None
    assert run.output == {
        "report": {"title": "Thesis"},
        "audit": {"title": "Thesis"},
        "format": "markdown",
    }


@pytest.mark.asyncio
async def test_cleared_workflow_output_bindings_preserve_state_fallback(
    tmp_path: Path,
) -> None:
    draft_api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "execute_workflow_output_fallback"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["output"] = []
    await draft_api.create_draft_workspace(workspace_id="report", draft=draft)

    first = await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=1,
        bindings=[InputValueBinding(target=LocalPath.of("echoed"), value="explicit")],
    )
    await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=first["revision"],
        bindings=[],
    )
    compiled = await draft_api.compile_draft_workspace(workspace_id="report")
    run = await service.run_workflow_from_plan(
        RawWorkflowPlan.model_validate(compiled["compiled_plan"]),
        {"text": "Thesis"},
    )

    assert run.error is None
    assert run.output == {"echoed": "Thesis"}


@pytest.mark.asyncio
async def test_set_workflow_output_map_replaces_top_level_output(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_out_replace")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(workspace_id="report", draft=_echo_draft())

    result = await api.set_workflow_output_map(
        workspace_id="report",
        revision=1,
        output_map={"state.echoed": "echoed"},
    )

    assert result["revision"] == 2
    assert result["status"] == "valid", result["diagnostics"]
    fetched = await api.get_draft_workspace(workspace_id="report", include_draft=True)
    assert fetched["draft"]["output"] == [{"path": "state.echoed", "target": "echoed"}]


@pytest.mark.asyncio
async def test_set_workflow_output_map_merges_top_level_output(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_out_merge")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    draft = {
        **_echo_draft(),
        "state_schema": {
            "fields": {
                "echoed": {"type": "string"},
                "other": {"type": "string"},
            }
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "echoed": {"type": "string"},
                "kind": {"type": "string"},
                "other": {"type": "string"},
            },
        },
        "output": [
            {"path": "state.echoed", "target": "echoed"},
            {"value": "report", "target": "kind"},
        ],
    }
    await api.create_draft_workspace(workspace_id="report", draft=draft)

    result = await api.set_workflow_output_map(
        workspace_id="report",
        revision=1,
        output_map={"state.other": "other"},
        merge=True,
    )

    assert result["status"] == "valid", result["diagnostics"]
    fetched = await api.get_draft_workspace(workspace_id="report", include_draft=True)
    assert fetched["draft"]["output"] == [
        {"path": "state.echoed", "target": "echoed"},
        {"value": "report", "target": "kind"},
        {"path": "state.other", "target": "other"},
    ]


@pytest.mark.asyncio
async def test_set_workflow_output_map_projects_missing_output_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_out_project")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    draft = {
        **_echo_draft(),
        "state_schema": {
            "type": "object",
            "properties": {
                "echoed": {"type": "string"},
                "after": {"type": "object"},
            },
        },
        "output_schema": {"type": "object", "properties": {}},
        "output": [],
    }
    await api.create_draft_workspace(workspace_id="report", draft=draft)

    result = await api.set_workflow_output_map(
        workspace_id="report",
        revision=1,
        output_map={"state.after": "after"},
        merge=True,
    )

    assert result["status"] == "valid", result["diagnostics"]
    fetched = await api.get_draft_workspace(workspace_id="report", include_draft=True)
    assert fetched["draft"]["output"] == [{"path": "state.after", "target": "after"}]
    assert fetched["draft"]["output_schema"]["properties"]["after"] == {
        "type": "object"
    }


# -- Browser-click test helpers for forward-route tests --


class _OpenClickPageInput(BaseModel):
    open_browser: bool = False


class _OpenClickPageOutput(BaseModel):
    before: dict = {}
    session_id: str = ""


class _WaitForClickInput(BaseModel):
    session_id: str
    simulate: dict
    timeout_seconds: int


class _WaitForClickOutput(BaseModel):
    after: dict = {}


class _CollectSnapshotsInput(BaseModel):
    session_id: str
    before: dict
    after: dict


class _CollectSnapshotsOutput(BaseModel):
    before: dict = {}
    after: dict = {}


@node(name="open_click_page", outcomes=("ok",))
def _open_click_page(payload: _OpenClickPageInput) -> _OpenClickPageOutput:
    return _OpenClickPageOutput(before={}, session_id="")


@node(name="wait_for_click", outcomes=("ok",))
def _wait_for_click(payload: _WaitForClickInput) -> _WaitForClickOutput:
    return _WaitForClickOutput(after={})


@node(name="collect_snapshots", outcomes=("ok",))
def _collect_snapshots(payload: _CollectSnapshotsInput) -> _CollectSnapshotsOutput:
    return _CollectSnapshotsOutput(before={}, after={})


def _browser_click_api(
    artifact_store: FileWorkflowArtifactStore,
) -> tuple[WorkflowApi, WfMcpService]:
    mcp_root = artifact_store.root / "browser_mcp" / str(id(artifact_store))
    service = WfMcpService(
        store=FileStore(mcp_root),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(mcp_root),
    )
    service.register_connection(
        ConnectionConfig(
            id="local.browser_click", server="local", account="browser_click"
        )
    )
    service.register_specs(
        "local.browser_click",
        _open_click_page,
        _wait_for_click,
        _collect_snapshots,
    )
    context = context_from_service(service)
    return WorkflowApi(context), service


@pytest.mark.asyncio
async def test_create_draft_from_capability_does_not_bind_optional_inputs(
    tmp_path: Path,
) -> None:
    api, _service = _browser_click_api(
        FileWorkflowArtifactStore(tmp_path / "drafts_required_inputs")
    )

    created = await api.create_draft_workspace_from_capability(
        workspace_id="browser",
        capability_name="local.browser_click.open_click_page",
        name="browser",
    )
    workspace = await api.get_draft_workspace(
        workspace_id="browser",
        include_draft=True,
    )

    assert created["wrapper_hints"]["input_map"] == {}
    assert workspace["draft"]["steps"]["call"]["input"] == []
    assert any("open_browser" in note for note in created["wrapper_hints"]["notes"])


@pytest.mark.asyncio
async def test_add_step_projects_explicit_optional_workflow_inputs(
    tmp_path: Path,
) -> None:
    api, _service = _browser_click_api(
        FileWorkflowArtifactStore(tmp_path / "drafts_explicit_optional_input")
    )

    await api.create_draft_workspace_from_capability(
        workspace_id="browser",
        capability_name="local.browser_click.open_click_page",
        name="browser",
    )

    result = await api.add_step_from_capability(
        workspace_id="browser",
        revision=1,
        step_id="wait",
        capability_name="local.browser_click.wait_for_click",
        route_from_step="call",
        routes={"ok": "__end__"},
        input_map={
            "state.session_id": "session_id",
            "input.simulate": "simulate",
            "input.timeout_seconds": "timeout_seconds",
        },
        bind_outputs={"after": "state.after"},
    )

    assert result["status"] == "valid", result["diagnostics"]
    workspace = await api.get_draft_workspace(
        workspace_id="browser", include_draft=True
    )
    properties = workspace["draft"]["input_schema"]["properties"]
    assert properties["simulate"]["type"] == "object"
    assert properties["timeout_seconds"]["type"] == "integer"


@pytest.mark.asyncio
async def test_add_step_persists_invalid_forward_route(tmp_path: Path) -> None:
    api, _service = _browser_click_api(
        FileWorkflowArtifactStore(tmp_path / "drafts_forward_route")
    )

    await api.create_draft_workspace_from_capability(
        workspace_id="browser",
        capability_name="local.browser_click.open_click_page",
        name="browser",
    )

    # Use only state.session_id — simulate/timeout_seconds are not declared
    # in the workflow input schema from open_click_page.
    result = await api.add_step_from_capability(
        workspace_id="browser",
        revision=1,
        step_id="wait",
        capability_name="local.browser_click.wait_for_click",
        route_from_step="call",
        routes={"ok": "collect"},
        input_map={
            "state.session_id": "session_id",
        },
        bind_outputs={"after": "state.after"},
    )

    assert result["revision"] == 2
    assert result["status"] == "invalid"
    assert any(
        item["code"] == "unknown_edge_destination" for item in result["diagnostics"]
    )

    stored = await api.get_draft_workspace(
        workspace_id="browser",
        include_draft=True,
    )
    assert (
        stored["draft"]["steps"]["wait"]["use"] == "local.browser_click.wait_for_click"
    )
    assert stored["draft"]["routes"]["wait"]["ok"] == "collect"


@pytest.mark.asyncio
async def test_invalid_forward_route_cannot_compile_or_save(tmp_path: Path) -> None:
    api, _service = _browser_click_api(
        FileWorkflowArtifactStore(tmp_path / "drafts_compile_boundary")
    )

    await api.create_draft_workspace_from_capability(
        workspace_id="browser",
        capability_name="local.browser_click.open_click_page",
        name="browser",
    )

    await api.add_step_from_capability(
        workspace_id="browser",
        revision=1,
        step_id="wait",
        capability_name="local.browser_click.wait_for_click",
        route_from_step="call",
        routes={"ok": "collect"},
        input_map={"state.session_id": "session_id"},
        bind_outputs={"after": "state.after"},
    )

    compiled = await api.compile_draft_workspace(workspace_id="browser")

    assert compiled["status"] == "invalid"
    assert any(
        item["code"] == "unknown_edge_destination" for item in compiled["diagnostics"]
    )

    saved = await api.create_artifact_from_workspace(
        workspace_id="browser",
        artifact_id="browser_workflow",
        version=1,
        title="Browser Workflow",
        outcomes=["ok"],
    )

    assert saved["status"] == "invalid"
    assert saved["saved"] is False
    assert any(
        item["code"] == "unknown_edge_destination" for item in saved["diagnostics"]
    )


@pytest.mark.asyncio
async def test_forward_route_becomes_valid_after_target_step_is_added(
    tmp_path: Path,
) -> None:
    api, _service = _browser_click_api(
        FileWorkflowArtifactStore(tmp_path / "drafts_repair_path")
    )

    await api.create_draft_workspace_from_capability(
        workspace_id="browser",
        capability_name="local.browser_click.open_click_page",
        name="browser",
    )

    await api.add_step_from_capability(
        workspace_id="browser",
        revision=1,
        step_id="wait",
        capability_name="local.browser_click.wait_for_click",
        route_from_step="call",
        routes={"ok": "collect"},
        input_map={
            "state.session_id": "session_id",
        },
        bind_outputs={"after": "state.after"},
    )

    add_collect = await api.add_step_from_capability(
        workspace_id="browser",
        revision=2,
        step_id="collect",
        capability_name="local.browser_click.collect_snapshots",
        route_from_step="wait",
        input_map={
            "state.session_id": "session_id",
            "state.before": "before",
            "state.after": "after",
        },
        bind_outputs={"before": "state.final_before", "after": "state.final_after"},
    )

    assert add_collect["revision"] == 3
    validated = await api.validate_draft_workspace(workspace_id="browser")
    assert validated["status"] == "valid"


@pytest.mark.asyncio
async def test_bind_draft_local_output_to_workflow_output_lowers_through_state(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_bind_output_workflow_output"
    )
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="report",
        draft={
            "name": "report",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "render",
            "steps": {
                "render": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [],
                }
            },
            "routes": {"render": {"ok": "__end__"}},
        },
    )

    result = await authoring.bind_draft(
        workspace_id="report",
        revision=1,
        step_id="render",
        source_path="local.echoed",
        target_path="output.echoed",
    )

    assert result["status"] == "valid"
    workspace = await api.get_draft_workspace(workspace_id="report", include_draft=True)
    assert workspace["draft"]["steps"]["render"]["output"] == [
        {"source": "echoed", "target": "state.echoed"}
    ]
    assert workspace["draft"]["output"] == [
        {"path": "state.echoed", "target": "echoed"}
    ]
    assert (
        workspace["draft"]["state_schema"]["properties"]["echoed"]["type"] == "string"
    )
    assert (
        workspace["draft"]["output_schema"]["properties"]["echoed"]["type"] == "string"
    )


@pytest.mark.asyncio
async def test_bind_draft_local_output_to_workflow_output_reuses_compatible_state(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_bind_existing_output_state"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="report",
        draft={
            "name": "report",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {
                "type": "object",
                "properties": {
                    "echoed": {
                        "description": "Echoed text",
                        "title": "Echoed",
                        "type": "string",
                    }
                },
            },
            "output_schema": {"type": "object", "properties": {}},
            "start": "render",
            "steps": {
                "render": {
                    "use": "demo.personal.echo_tool",
                    "input": [],
                    "output": [{"source": "echoed", "target": "state.echoed"}],
                }
            },
            "routes": {"render": {"ok": "__end__"}},
        },
    )

    result = await authoring.bind_draft(
        workspace_id="report",
        revision=1,
        step_id="render",
        source_path="local.echoed",
        target_path="output.echoed",
    )

    assert result["status"] == "valid"
    workspace = await api.get_draft_workspace(workspace_id="report", include_draft=True)
    assert workspace["draft"]["steps"]["render"]["output"] == [
        {"source": "echoed", "target": "state.echoed"}
    ]
    assert workspace["draft"]["output"] == [
        {"path": "state.echoed", "target": "echoed"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_local_output_to_state_reuses_compatible_state(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_existing_state")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["state_schema"] = {
        "type": "object",
        "properties": {
            "echoed": {
                "description": "Echoed text",
                "title": "Echoed",
                "type": "string",
            }
        },
    }
    await api.create_draft_workspace(workspace_id="report", draft=draft)

    result = await authoring.bind_draft(
        workspace_id="report",
        revision=1,
        step_id="echo",
        source_path="local.echoed",
        target_path="state.echoed",
    )

    assert result["status"] == "valid", result["diagnostics"]
    workspace = await api.get_draft_workspace(workspace_id="report", include_draft=True)
    assert workspace["draft"]["steps"]["echo"]["output"] == [
        {"source": "echoed", "target": "state.echoed"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_local_output_to_quoted_workflow_output_field(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_quoted_output")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["state_schema"] = {"type": "object", "properties": {}}
    draft["output_schema"] = {"type": "object", "properties": {}}
    draft["steps"]["echo"]["output"] = []
    await api.create_draft_workspace(workspace_id="quoted", draft=draft)

    result = await authoring.bind_draft(
        workspace_id="quoted",
        revision=1,
        step_id="echo",
        source_path="local.echoed",
        target_path='output."public.echoed"',
    )

    assert result["status"] == "valid"
    workspace = await api.get_draft_workspace(workspace_id="quoted", include_draft=True)
    assert workspace["draft"]["steps"]["echo"]["output"] == [
        {"source": "echoed", "target": 'state."public.echoed"'}
    ]
    assert workspace["draft"]["output"] == [
        {"path": 'state."public.echoed"', "target": '"public.echoed"'}
    ]


@pytest.mark.asyncio
async def test_bind_draft_replaces_previous_public_output_for_local_field(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_rebind_output")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["state_schema"] = {
        "type": "object",
        "properties": {
            "old": {"type": "string"},
        },
    }
    draft["output_schema"] = {
        "type": "object",
        "properties": {
            "old": {"type": "string"},
        },
    }
    draft["steps"]["echo"]["output"] = [{"source": "echoed", "target": "state.old"}]
    draft["output"] = [{"path": "state.old", "target": "old"}]
    await api.create_draft_workspace(workspace_id="report", draft=draft)

    result = await authoring.bind_draft(
        workspace_id="report",
        revision=1,
        step_id="echo",
        source_path="local.echoed",
        target_path="output.echoed",
    )

    assert result["status"] == "valid"
    workspace = await api.get_draft_workspace(workspace_id="report", include_draft=True)
    assert workspace["draft"]["output"] == [
        {"path": "state.echoed", "target": "echoed"}
    ]


@pytest.mark.asyncio
async def test_remove_draft_binding_rejects_non_object_entries(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bad_bindings")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = _echo_draft()
    draft["steps"]["echo"]["input"] = ["not-an-object"]
    await api.create_draft_workspace(workspace_id="bad", draft=draft)

    with pytest.raises(ValueError, match="input binding entries.*objects"):
        await authoring.remove_draft_binding(
            workspace_id="bad",
            revision=1,
            step_id="echo",
            inputs=["text"],
        )


@pytest.mark.asyncio
async def test_validate_draft_workspace_omits_unusable_nested_input_repair_hint(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_nested_input_schema_hint"
    )
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="nested_ws",
        draft={
            "name": "nested",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "call",
            "steps": {
                "call": {
                    "use": "demo.personal.echo_tool",
                    "input": [{"target": "payload.text", "path": "input.undeclared"}],
                    "output": [],
                }
            },
            "routes": {"call": {"ok": "__end__"}},
        },
    )

    payload = await api.validate_draft_workspace(workspace_id="nested_ws")

    diagnostic = next(
        item for item in payload["diagnostics"] if item["code"] == "invalid_source_path"
    )
    assert "repair_hint" not in diagnostic


@pytest.mark.asyncio
async def test_validate_draft_workspace_details_invalid_input_source_path(
    tmp_path: Path,
) -> None:
    """invalid_source_path on a step input must carry step_id, source_path, target_field."""
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_invalid_source_details"
    )
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="wait_ws",
        draft={
            "name": "wait",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "wait",
            "steps": {
                "wait": {
                    "use": "demo.personal.echo_tool",
                    "input": [
                        {
                            "target": "text",
                            "path": "input.undeclared",
                        }
                    ],
                    "output": [],
                }
            },
            "routes": {"wait": {"ok": "__end__"}},
        },
    )

    payload = await api.validate_draft_workspace(workspace_id="wait_ws")

    diagnostic = payload["diagnostics"][0]
    assert diagnostic["code"] == "invalid_source_path"
    assert diagnostic["step_id"] == "wait"
    assert diagnostic["details"]["source_path"] == "input.undeclared"
    assert diagnostic["details"]["target_field"] == "text"


@pytest.mark.asyncio
async def test_validate_draft_workspace_hints_input_schema_projection(
    tmp_path: Path,
) -> None:
    """invalid_source_path with input.* source must produce a repair_hint."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_input_schema_hint")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="wait_ws",
        draft={
            "name": "wait",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "wait",
            "steps": {
                "wait": {
                    "use": "demo.personal.echo_tool",
                    "input": [
                        {
                            "target": "text",
                            "path": "input.undeclared",
                        }
                    ],
                    "output": [],
                }
            },
            "routes": {"wait": {"ok": "__end__"}},
        },
    )

    payload = await api.validate_draft_workspace(workspace_id="wait_ws")

    diagnostic = payload["diagnostics"][0]
    assert diagnostic["code"] == "invalid_source_path"
    assert diagnostic["step_id"] == "wait"
    assert diagnostic["repair_hint"] == (
        "wf draft bind wait_ws --revision 1 "
        "--step wait --from input.undeclared --to local.text"
    )


@pytest.mark.asyncio
async def test_validate_draft_workspace_hints_state_schema_projection(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_state_schema_hint")
    api, _service, _authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="wait_ws",
        draft={
            "name": "wait",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "wait",
            "steps": {
                "wait": {
                    "use": "demo.personal.echo_tool",
                    "input": [{"target": "text", "path": "state.undeclared"}],
                    "output": [],
                }
            },
            "routes": {"wait": {"ok": "__end__"}},
        },
    )

    payload = await api.validate_draft_workspace(workspace_id="wait_ws")

    diagnostic = next(
        item for item in payload["diagnostics"] if item["code"] == "invalid_source_path"
    )
    assert diagnostic["repair_hint"] == (
        "wf draft bind wait_ws --revision 1 "
        "--step wait --from state.undeclared --to local.text"
    )
