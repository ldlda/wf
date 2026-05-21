from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from wf_artifacts import (
    FileWorkflowArtifactStore,
    RequiredCapability,
    WorkflowArtifact,
    WorkflowDeployment,
)
from wf_authoring import node, reducer
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig, RawWorkflowPlan
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import TraceRange, WorkflowSurfaceHandlers
from wf_core.models.steps import InputPathBinding, OutputBinding
from wf_core.paths import GraphSourcePath, LocalPath, StatePath
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)

from .test_support import echo_tool, input_binding, local_temp_root, output_binding


class AmountInput(BaseModel):
    amount: int


class AmountOutput(BaseModel):
    amount: int


class ChangedEchoInput(BaseModel):
    message: str


class ChangedEchoOutput(BaseModel):
    echoed: str


@node()
async def amount_tool(payload: AmountInput) -> AmountOutput:
    return AmountOutput(amount=payload.amount)


@node(name="echo_tool")
def changed_echo_tool(payload: ChangedEchoInput) -> ChangedEchoOutput:
    return ChangedEchoOutput(echoed=payload.message)


@node(name="mcp_echo_tool", outcomes=("ok", "error"))
def mcp_echo_tool(payload: ChangedEchoInput) -> ChangedEchoOutput:
    """Test fixture that mirrors naive MCP wrappers with ok/error outcomes."""
    return ChangedEchoOutput(echoed=payload.message)


@reducer(name="custom.default.multiply")
def multiply(current: int | None, incoming: int) -> int:
    return (current or 1) * incoming


def test_workflow_surface_lists_artifact_catalog_entries() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_artifacts")
    artifact_store.save_artifact(_artifact())
    handlers = _handlers(artifact_store)

    payload = asyncio.run(handlers.list_artifacts())

    nodes = payload["nodes"]
    assert len(nodes) == 1
    assert nodes[0]["name"] == "workflow.summarize_docs.v1"
    assert nodes[0]["artifact_id"] == "summarize_docs"
    assert nodes[0]["version"] == 1
    assert nodes[0]["kind"] == "workflow"
    assert nodes[0]["required_sources"] == ["context7"]
    assert "plan" not in nodes[0]


def test_workflow_surface_lists_planner_visible_capabilities() -> None:
    handlers = _handlers(FileWorkflowArtifactStore(local_temp_root() / "surface_caps"))

    payload = asyncio.run(handlers.list_capabilities(limit=2))
    names = [capability["name"] for capability in payload["capabilities"]]
    first = payload["capabilities"][0]

    assert len(names) == 2
    assert payload["total"] >= 2
    assert payload["next_cursor"] == "2"
    assert "description" in first
    assert "source_id" in first
    assert first["kind"] == "node_spec"
    assert "input_fields" in first
    assert "output_fields" in first
    assert "input_schema" not in first
    assert "wf.admin.list_sources" not in names


def test_workflow_surface_filters_stdlib_capabilities_by_source() -> None:
    handlers = _handlers(
        FileWorkflowArtifactStore(local_temp_root() / "surface_filtered_caps")
    )

    payload = asyncio.run(
        handlers.list_capabilities(source_id="wf.std", query="truthy")
    )

    assert [capability["name"] for capability in payload["capabilities"]] == [
        "wf.std.truthy"
    ]
    assert payload["capabilities"][0]["source_id"] == "wf.std"


def test_workflow_surface_lists_saved_wrapper_capabilities() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_wrapper_caps"
    )
    artifact_store.save_artifact(
        _echo_artifact().model_copy(
            update={
                "id": "echo_wrapper",
                "kind": "wrapper",
                "description": "Reusable echo wrapper.",
            }
        )
    )
    artifact_store.save_artifact(_echo_artifact())
    handlers = _handlers(artifact_store)

    payload = asyncio.run(
        handlers.list_capabilities(source_id="workflow", query="echo")
    )

    names = [capability["name"] for capability in payload["capabilities"]]
    assert names == ["workflow.echo_wrapper.v1"]
    assert payload["capabilities"][0]["source_id"] == "workflow"
    assert payload["capabilities"][0]["kind"] == "wrapper_artifact"
    assert payload["capabilities"][0]["artifact_id"] == "echo_wrapper"
    assert payload["capabilities"][0]["version"] == 1
    assert payload["capabilities"][0]["title"] == "Echo"
    assert payload["capabilities"][0]["outcomes"] == ["completed"]
    assert payload["capabilities"][0]["input_fields"] == ["text"]
    assert payload["capabilities"][0]["output_fields"] == ["echoed"]


def test_workflow_surface_inspects_one_capability() -> None:
    handlers = _handlers(
        FileWorkflowArtifactStore(local_temp_root() / "surface_inspect_cap")
    )

    payload = asyncio.run(
        handlers.inspect_capability(qualified_name="wf.std.runtime_error")
    )

    assert payload["name"] == "wf.std.runtime_error"
    assert payload["outcomes"] == ["ok"]
    assert "input_schema" in payload


def test_workflow_surface_inspect_capability_includes_wrapper_hints() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_wrapper_hints_mcp"),
        artifact_store=FileWorkflowArtifactStore(
            local_temp_root() / "surface_wrapper_hints_artifacts"
        ),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.inspect_capability(qualified_name="demo.personal.echo_tool")
    )

    hints = payload["wrapper_hints"]
    assert hints["capability_name"] == "demo.personal.echo_tool"
    assert hints["declared_outcomes"] == ["ok"]
    assert hints["input_map"] == {"input.text": "text"}
    assert hints["output_map"] == {"echoed": "state.echoed"}
    assert hints["outcome_policy"] == "preserve_declared"


def test_workflow_surface_inspects_saved_wrapper_capability() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_inspect_wrapper_cap"
    )
    artifact_store.save_artifact(
        _echo_artifact().model_copy(update={"id": "echo_wrapper", "kind": "wrapper"})
    )
    handlers = _handlers(artifact_store)

    payload = asyncio.run(
        handlers.inspect_capability(qualified_name="workflow.echo_wrapper.v1")
    )

    assert payload["name"] == "workflow.echo_wrapper.v1"
    assert payload["source_id"] == "workflow"
    assert payload["kind"] == "wrapper_artifact"
    assert payload["artifact_id"] == "echo_wrapper"
    assert payload["outcomes"] == ["completed"]
    assert "input_schema" in payload
    hints = payload["wrapper_hints"]
    assert hints["capability_name"] == "workflow.echo_wrapper.v1"
    assert hints["declared_outcomes"] == ["completed"]
    assert hints["suggested_wrapper_outcomes"] == ["completed"]
    assert hints["input_map"] == {"input.text": "text"}
    assert hints["output_map"] == {"echoed": "state.echoed"}


def test_workflow_surface_validates_deployment_dependencies() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_validate")
    artifact_store.save_artifact(_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
            bindings=[
                {"logical_source": "context7", "concrete_source": "context7.personal"}
            ],
        )
    )
    handlers = _handlers(artifact_store)

    payload = asyncio.run(
        handlers.validate_deployment(deployment_id="summarize_docs.personal")
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "source_missing"


def test_workflow_surface_records_artifact_and_deployment_save_events() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_events")
    handlers = _handlers(artifact_store)

    artifact_payload = asyncio.run(
        handlers.save_artifact(_echo_artifact().model_dump(mode="json"))
    )
    deployment_payload = asyncio.run(
        handlers.save_deployment(
            WorkflowDeployment(
                id="echo.personal",
                artifact_id="echo",
                artifact_version=1,
                bindings=[
                    {"logical_source": "demo", "concrete_source": "demo.personal"}
                ],
            ).model_dump(mode="json")
        )
    )

    events = handlers.service.list_events()
    assert artifact_payload["saved"] is True
    assert deployment_payload["saved"] is True
    assert [event.kind for event in events] == [
        "workflow_artifact_saved",
        "workflow_deployment_saved",
    ]
    assert events[0].capability_id == "workflow.echo.v1"
    assert events[1].capability_id == "deployment.echo.personal"


def test_workflow_surface_lists_compact_deployment_summaries_and_inspects_detail() -> (
    None
):
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_deployment_list"
    )
    handlers = _handlers(artifact_store)
    deployment = WorkflowDeployment(
        id="echo.personal",
        artifact_id="echo",
        artifact_version=1,
        bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
    )
    artifact_store.save_deployment(deployment)

    listed = asyncio.run(handlers.list_deployments())
    inspected = asyncio.run(
        handlers.inspect_deployment(deployment_id="echo.personal")
    )

    assert listed["deployments"][0]["id"] == "echo.personal"
    assert listed["deployments"][0]["binding_count"] == 1
    assert "bindings" not in listed["deployments"][0]
    assert inspected["bindings"][0]["logical_source"] == "demo"
    assert inspected["bindings"][0]["concrete_source"] == "demo.personal"


def test_workflow_surface_creates_wrapper_artifact_from_plan() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_wrapper_plan"
    )
    handlers = _handlers(artifact_store)

    payload = asyncio.run(
        handlers.create_artifact_from_plan(
            artifact_id="echo_wrapper",
            version=1,
            title="Echo Wrapper",
            kind="wrapper",
            plan=_echo_artifact().plan,
            outcomes=("completed",),
        )
    )
    artifact = artifact_store.get_artifact("echo_wrapper", 1)

    assert payload["saved"] is True
    assert artifact.kind == "wrapper"


def test_workflow_surface_creates_artifact_with_logical_node_refs() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_logical_refs"
    )
    handlers = _handlers(artifact_store)
    plan = _echo_artifact().plan
    plan["nodes"][0]["node"] = "demo.personal.echo_tool"

    asyncio.run(
        handlers.create_artifact_from_plan(
            artifact_id="echo_logical",
            version=1,
            title="Echo Logical",
            plan=plan,
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact = artifact_store.get_artifact("echo_logical", 1)

    assert artifact.plan["nodes"][0]["node"] == "demo.echo_tool"
    assert artifact.required_capability_map()["demo.echo_tool"].logical_source == "demo"


def test_workflow_surface_validates_draft_without_saving() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_draft_validate"
    )
    handlers = _handlers(artifact_store)

    payload = asyncio.run(handlers.validate_draft(draft=_echo_draft()))

    assert payload["status"] == "valid"
    assert payload["diagnostics"] == []
    assert payload["compiled_plan"]["nodes"][0]["type"] == "node"
    assert not artifact_store.list_artifacts()


def test_workflow_surface_rejects_unknown_draft_route_outcome_when_spec_is_known() -> (
    None
):
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_draft_bad_outcome"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_draft_bad_outcome_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)
    draft = _echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}

    payload = asyncio.run(handlers.validate_draft(draft=draft))

    assert payload["status"] == "invalid"
    assert payload["diagnostics"][0]["path"] == "routes.echo.typo"


def test_workflow_surface_creates_artifact_from_draft_with_binding_suggestions() -> (
    None
):
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_draft_create"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_draft_create_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)
    draft = _echo_draft()
    draft["steps"]["echo"]["use"] = "demo.personal.echo_tool"

    payload = asyncio.run(
        handlers.create_artifact_from_draft(
            artifact_id="draft_echo",
            version=1,
            title="Draft Echo",
            draft=draft,
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact = artifact_store.get_artifact("draft_echo", 1)

    assert payload["saved"] is True
    assert payload["required_logical_sources"] == ["demo", "wf.std"]
    assert payload["suggested_bindings"]["wf.std"] == "wf.std"
    assert artifact.plan["nodes"][0]["node"] == "demo.echo_tool"
    assert artifact.required_capability_map()["demo.echo_tool"].logical_source == "demo"


def test_workflow_surface_draft_artifact_requires_std_self_binding() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_draft_missing_std"
    )
    handlers = _handlers(artifact_store)

    asyncio.run(
        handlers.create_artifact_from_draft(
            artifact_id="draft_echo_missing_std",
            version=1,
            title="Draft Echo Missing Std",
            draft=_echo_draft(),
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="draft_echo_missing_std.personal",
            artifact_id="draft_echo_missing_std",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )

    payload = asyncio.run(
        handlers.validate_deployment(deployment_id="draft_echo_missing_std.personal")
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "binding_missing"
    assert payload["diagnostics"][0]["logical_ref"] == "wf.std.replace"


def test_workflow_surface_patches_draft_without_saving() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_draft_patch"
    )
    handlers = _handlers(artifact_store)

    payload = asyncio.run(
        handlers.patch_draft(
            draft=_echo_draft(),
            patch=[
                {
                    "op": "replace",
                    "path": "/steps/echo/input/0/target/parts/0",
                    "value": "message",
                }
            ],
        )
    )

    assert payload["status"] == "valid"
    assert payload["draft"]["steps"]["echo"]["input"][0]["target"] == {
        "root": "local",
        "parts": ["message"],
    }
    assert not artifact_store.list_artifacts()


def test_workflow_surface_creates_and_gets_draft_workspace() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_workspace")
    handlers = _handlers(artifact_store)

    created = asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            title="Echo Draft",
            draft=_echo_draft(),
        )
    )
    fetched = asyncio.run(
        handlers.get_draft_workspace(
            workspace_id="echo_draft",
            include_draft=True,
        )
    )

    assert created["workspace_id"] == "echo_draft"
    assert created["revision"] == 1
    assert fetched["draft"]["steps"]["echo"]["use"] == "demo.personal.echo_tool"


def test_workflow_surface_lists_draft_workspaces() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_list"
    )
    handlers = _handlers(artifact_store)
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="b_draft",
            draft=_echo_draft(),
            title="B Draft",
        )
    )
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="a_draft",
            draft=_echo_draft(),
            title="A Draft",
        )
    )

    payload = asyncio.run(handlers.list_draft_workspaces())

    assert [workspace["workspace_id"] for workspace in payload["workspaces"]] == [
        "a_draft",
        "b_draft",
    ]
    assert payload["workspaces"][0]["title"] == "A Draft"
    assert "draft" not in payload["workspaces"][0]


def test_workflow_surface_deletes_draft_workspace() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_delete"
    )
    handlers = _handlers(artifact_store)
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            draft=_echo_draft(),
        )
    )

    deleted = asyncio.run(handlers.delete_draft_workspace(workspace_id="echo_draft"))
    deleted_again = asyncio.run(
        handlers.delete_draft_workspace(workspace_id="echo_draft")
    )
    listed = asyncio.run(handlers.list_draft_workspaces())

    assert deleted["deleted"] is True
    assert deleted["status"] == "deleted"
    assert deleted_again["deleted"] is False
    assert deleted_again["status"] == "not_found"
    assert listed["workspaces"] == []


def test_workflow_surface_patch_helpers_update_draft_workspace() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_patch_helpers"
    )
    handlers = _handlers(artifact_store)
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            draft=_echo_draft(),
        )
    )

    named = asyncio.run(
        handlers.set_draft_name(
            workspace_id="echo_draft",
            revision=1,
            name="echo_v2",
        )
    )
    routed = asyncio.run(
        handlers.set_draft_route(
            workspace_id="echo_draft",
            revision=2,
            step_id="echo",
            outcome="error",
            target="__end__",
        )
    )
    input_mapped = asyncio.run(
        handlers.set_step_input_map(
            workspace_id="echo_draft",
            revision=3,
            step_id="echo",
            input_map={"input.text": "message"},
        )
    )
    output_mapped = asyncio.run(
        handlers.set_step_output_map(
            workspace_id="echo_draft",
            revision=4,
            step_id="echo",
            output_map={"echoed": "state.echoed"},
        )
    )
    fetched = asyncio.run(
        handlers.get_draft_workspace(workspace_id="echo_draft", include_draft=True)
    )

    assert named["revision"] == 2
    assert routed["revision"] == 3
    assert input_mapped["revision"] == 4
    assert output_mapped["revision"] == 5
    assert fetched["draft"]["name"] == "echo_v2"
    assert fetched["draft"]["routes"]["echo"]["error"] == "__end__"
    assert fetched["draft"]["steps"]["echo"]["input"] == [
        {
            "target": {"root": "local", "parts": ["message"]},
            "path": {"root": "input", "parts": ["text"]},
        }
    ]
    assert fetched["draft"]["steps"]["echo"]["output"] == [
        {
            "source": {"root": "local", "parts": ["echoed"]},
            "target": {"root": "state", "parts": ["echoed"]},
        }
    ]


def test_workflow_surface_validates_draft_workspace_with_live_outcomes() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_validate"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_workspace_validate_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)
    draft = _echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            draft=draft,
        )
    )

    payload = asyncio.run(handlers.validate_draft_workspace(workspace_id="echo_draft"))
    fetched = asyncio.run(handlers.get_draft_workspace(workspace_id="echo_draft"))

    assert payload["revision"] == 1
    assert payload["status"] == "invalid"
    assert payload["diagnostics"][0]["code"] == "unknown_outcome"
    assert fetched["status"] == "invalid"


def test_workflow_surface_patches_draft_workspace_by_revision() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_patch"
    )
    handlers = _handlers(artifact_store)
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            draft=_echo_draft(),
        )
    )

    patched = asyncio.run(
        handlers.patch_draft_workspace(
            workspace_id="echo_draft",
            revision=1,
            patch=[{"op": "replace", "path": "/name", "value": "echo_v2"}],
        )
    )

    assert patched["revision"] == 2
    assert patched["status"] == "valid"


def test_workflow_surface_creates_minimal_draft_workspace_with_error_route() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_minimal_workspace"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_minimal_workspace_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", mcp_echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    result = asyncio.run(
        handlers.create_minimal_draft_workspace(
            workspace_id="echo_draft_canonical_error",
            name="echo",
            capability_name="demo.personal.mcp_echo_tool",
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
    )
    assert service.draft_workspace_store is not None
    workspace = service.draft_workspace_store.get_workspace(
        "echo_draft_canonical_error"
    )

    assert result["workspace_id"] == "echo_draft_canonical_error"
    assert workspace.draft["routes"]["call"]["ok"] == "__end__"
    assert workspace.draft["routes"]["call"]["error"] == "tool_error"
    assert workspace.draft["steps"]["tool_error"]["use"] == "wf.std.runtime_error"
    assert workspace.draft["steps"]["tool_error"]["input"] == [
        {
            "target": {"root": "local", "parts": ["message"]},
            "path": {"root": "state", "parts": ["echoed"]},
        }
    ]


def test_workflow_surface_accepts_canonical_bindings_for_minimal_workspace() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_minimal_canonical_mcp"),
        artifact_store=FileWorkflowArtifactStore(
            local_temp_root() / "surface_minimal_canonical"
        ),
    )
    handlers = WorkflowSurfaceHandlers(service)

    result = asyncio.run(
        handlers.create_minimal_draft_workspace(
            workspace_id="echo_draft_canonical",
            name="echo",
            capability_name="demo.personal.echo_tool",
            input_schema={"type": "object"},
            state_schema={"fields": {"echoed": {"type": "string"}}},
            output_schema={"type": "object"},
            input=[
                InputPathBinding(
                    target=LocalPath(("text",)),
                    path=GraphSourcePath("input", ("text",)),
                )
            ],
            output=[
                OutputBinding(
                    source=LocalPath(("echoed",)),
                    target=StatePath(("echoed",)),
                )
            ],
        )
    )
    assert service.draft_workspace_store is not None
    workspace = service.draft_workspace_store.get_workspace("echo_draft_canonical")

    assert result["workspace_id"] == "echo_draft_canonical"
    assert workspace.draft["steps"]["call"]["input"] == [
        {
            "target": {"root": "local", "parts": ["text"]},
            "path": {"root": "input", "parts": ["text"]},
        }
    ]
    assert workspace.draft["steps"]["call"]["output"] == [
        {
            "source": {"root": "local", "parts": ["echoed"]},
            "target": {"root": "state", "parts": ["echoed"]},
        }
    ]


def test_workflow_surface_creates_draft_workspace_from_capability_hints() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_from_capability"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_workspace_from_capability_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    result = asyncio.run(
        handlers.create_draft_workspace_from_capability(
            workspace_id="echo_from_capability_canonical",
            capability_name="demo.personal.echo_tool",
            name="echo_from_capability",
        )
    )
    assert service.draft_workspace_store is not None
    workspace = service.draft_workspace_store.get_workspace(
        "echo_from_capability_canonical"
    )

    assert result["workspace_id"] == "echo_from_capability_canonical"
    assert result["wrapper_hints"]["input_map"] == {"input.text": "text"}
    assert result["wrapper_hints"]["output_map"] == {"echoed": "state.echoed"}
    assert workspace.draft["steps"]["call"]["use"] == "demo.personal.echo_tool"
    assert workspace.draft["steps"]["call"]["input"] == [
        {
            "target": {"root": "local", "parts": ["text"]},
            "path": {"root": "input", "parts": ["text"]},
        }
    ]
    assert workspace.draft["steps"]["call"]["output"] == [
        {
            "source": {"root": "local", "parts": ["echoed"]},
            "target": {"root": "state", "parts": ["echoed"]},
        }
    ]


def test_workflow_surface_creates_artifact_from_workspace() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_artifact"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_workspace_artifact_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            draft=_echo_draft(),
        )
    )

    result = asyncio.run(
        handlers.create_artifact_from_workspace(
            workspace_id="echo_draft",
            artifact_id="workspace_echo",
            version=1,
            title="Workspace Echo",
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )

    artifact = artifact_store.get_artifact("workspace_echo", 1)
    assert result["saved"] is True
    assert artifact.id == "workspace_echo"


def test_workflow_surface_creates_wrapper_from_workspace() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_wrapper"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_workspace_wrapper_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)
    asyncio.run(
        handlers.create_draft_workspace(
            workspace_id="echo_draft",
            draft=_echo_draft(),
        )
    )

    result = asyncio.run(
        handlers.create_wrapper_from_workspace(
            workspace_id="echo_draft",
            artifact_id="workspace_echo_wrapper",
            version=1,
            title="Workspace Echo Wrapper",
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact = artifact_store.get_artifact("workspace_echo_wrapper", 1)

    assert result["saved"] is True
    assert artifact.kind == "wrapper"
    assert artifact.plan["nodes"][0]["node"] == "demo.echo_tool"


def test_raw_workflow_plan_uses_core_step_and_edge_models() -> None:
    plan = RawWorkflowPlan.model_validate(_echo_artifact().plan)

    assert plan.nodes[0].type == "node"
    assert plan.edges[0].outcome == "ok"


def test_workflow_surface_runs_non_interrupting_deployment() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_run")
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_run_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )

    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert payload["diagnostics"] == []
    assert payload["trace_count"] == 1
    assert "trace" not in payload


def test_workflow_surface_run_deployment_can_include_trace_detail() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_run_trace_detail"
    )
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_run_trace_detail_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
            trace_range=TraceRange(start=0, limit=10),
        )
    )

    assert payload["status"] == "completed"
    assert payload["trace_count"] == 1
    assert payload["trace_start"] == 0
    assert payload["trace_limit"] == 10
    assert payload["trace_truncated"] is False
    assert len(payload["trace"]) == 1
    assert payload["trace"][0]["node_id"] == "echo"
    assert payload["trace"][0]["outcome"] == "ok"


def test_workflow_surface_run_deployment_can_read_empty_trace_range() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_run_trace_empty_range"
    )
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_run_trace_empty_range_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
            trace_range=TraceRange(start=5, limit=10),
        )
    )

    assert payload["trace_count"] == 1
    assert payload["trace_start"] == 5
    assert payload["trace_limit"] == 10
    assert payload["trace"] == []
    assert payload["trace_truncated"] is False


def test_workflow_surface_runs_deployment_with_bound_node_spec_dependency() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_bound_node")
    artifact_store.save_artifact(_logical_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.personal",
            artifact_id="logical_echo",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_bound_node_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="echo.personal",
            workflow_input={"text": "hello"},
        )
    )

    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert payload["diagnostics"] == []


def test_workflow_surface_runs_artifact_created_from_concrete_node_ref() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_created_bound_node"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_created_bound_node_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    asyncio.run(
        handlers.create_artifact_from_plan(
            artifact_id="created_echo",
            version=1,
            title="Created Echo",
            plan=_echo_artifact().plan,
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="created_echo.personal",
            artifact_id="created_echo",
            artifact_version=1,
            bindings={
                "demo": "demo.personal",
                "wf.std": "wf.std",
            },
        )
    )

    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="created_echo.personal",
            workflow_input={"text": "hello"},
        )
    )
    artifact = artifact_store.get_artifact("created_echo", 1)

    assert artifact.plan["nodes"][0]["node"] == "demo.echo_tool"
    assert artifact.required_capability_map()["demo.echo_tool"].logical_source == "demo"
    assert payload["status"] == "completed"
    assert payload["output"]["echoed"] == "hello"
    assert payload["diagnostics"] == []


def test_workflow_surface_detects_drift_from_saved_node_spec_snapshot() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_created_drift"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_created_drift_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    asyncio.run(
        handlers.create_artifact_from_plan(
            artifact_id="created_echo_drift",
            version=1,
            title="Created Echo Drift",
            plan=_echo_artifact().plan,
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="created_echo_drift.personal",
            artifact_id="created_echo_drift",
            artifact_version=1,
            bindings={
                "demo": "demo.personal",
                "wf.std": "wf.std",
            },
        )
    )

    required = artifact_store.get_artifact(
        "created_echo_drift",
        1,
    ).required_capability_map()["demo.echo_tool"]
    assert required.input_schema_hash is not None

    service.register_connection(
        ConnectionConfig(id="demo.work", server="demo", account="work")
    )
    service.register_specs("demo.work", changed_echo_tool)
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="created_echo_drift.work",
            artifact_id="created_echo_drift",
            artifact_version=1,
            bindings={
                "demo": "demo.work",
                "wf.std": "wf.std",
            },
        )
    )

    payload = asyncio.run(
        handlers.validate_deployment(deployment_id="created_echo_drift.work")
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "schema_changed"


def test_workflow_surface_runs_deployment_with_bound_reducer_dependency() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_reducer")
    artifact_store.save_artifact(_custom_reducer_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="multiply.personal",
            artifact_id="multiply",
            artifact_version=1,
            bindings={
                "demo": "demo.personal",
                "custom": "custom.default",
            },
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_reducer_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", amount_tool)
    service.register_capability_source(
        CapabilitySource(
            id="custom.default",
            kind="system",
            capabilities=CapabilityBuckets(
                reducers={multiply.definition.spec.name: multiply.definition.spec},
                reducer_definitions={
                    multiply.definition.spec.name: multiply.definition,
                },
            ),
            visibility=SourceVisibility(planner=True),
            permissions=SourcePermissions(safe_for_workflow=True),
        )
    )
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.run_deployment(
            deployment_id="multiply.personal",
            workflow_input={"total": 2, "amount": 3},
        )
    )

    assert payload["status"] == "completed"
    assert payload["output"]["total"] == 6
    assert payload["diagnostics"] == []


def test_workflow_surface_calls_saved_wrapper_artifact() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_wrapper_call"
    )
    wrapper = _echo_artifact().model_copy(
        update={"id": "echo_wrapper", "kind": "wrapper"}
    )
    artifact_store.save_artifact(wrapper)
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_wrapper_call_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.call_capability(
            qualified_name="workflow.echo_wrapper.v1",
            payload={"text": "hello"},
        )
    )

    assert payload["qualified_name"] == "workflow.echo_wrapper.v1"
    assert payload["source_id"] == "workflow"
    assert payload["kind"] == "wrapper_artifact"
    assert payload["diagnostics"] == []
    assert payload["outcome"] == "completed"
    assert payload["output"]["echoed"] == "hello"


def test_workflow_surface_calls_live_node_spec_with_self_describing_response() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_live_capability_call"),
        artifact_store=FileWorkflowArtifactStore(
            local_temp_root() / "surface_live_capability_call_artifacts"
        ),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.call_capability(
            qualified_name="demo.personal.echo_tool",
            payload={"text": "hello"},
        )
    )

    assert payload["qualified_name"] == "demo.personal.echo_tool"
    assert payload["source_id"] == "demo.personal"
    assert payload["kind"] == "node_spec"
    assert payload["diagnostics"] == []
    assert payload["outcome"] == "ok"
    assert payload["output"]["echoed"] == "hello"


def test_workflow_surface_calls_saved_wrapper_artifact_with_deployment_bindings() -> (
    None
):
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_wrapper_bound_call"
    )
    wrapper = _logical_echo_artifact().model_copy(
        update={"id": "logical_echo_wrapper", "kind": "wrapper"}
    )
    artifact_store.save_artifact(wrapper)
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="logical_echo_wrapper.personal",
            artifact_id="logical_echo_wrapper",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_wrapper_bound_call_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    handlers = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        handlers.call_capability(
            qualified_name="workflow.logical_echo_wrapper.v1",
            payload={"text": "hello"},
            deployment_id="logical_echo_wrapper.personal",
        )
    )

    assert payload["qualified_name"] == "workflow.logical_echo_wrapper.v1"
    assert payload["source_id"] == "workflow"
    assert payload["kind"] == "wrapper_artifact"
    assert payload["deployment_id"] == "logical_echo_wrapper.personal"
    assert payload["diagnostics"] == []
    assert payload["outcome"] == "completed"
    assert payload["output"]["echoed"] == "hello"


def _handlers(artifact_store: FileWorkflowArtifactStore) -> WorkflowSurfaceHandlers:
    service = WfMcpService(
        store=FileStore(artifact_store.root / "surface_mcp" / str(id(artifact_store))),
        artifact_store=artifact_store,
    )
    return WorkflowSurfaceHandlers(service)


def _artifact() -> WorkflowArtifact:
    return WorkflowArtifact(
        id="summarize_docs",
        version=1,
        title="Summarize Docs",
        description="Summarize retrieved documentation.",
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=("done",),
        plan={"name": "summarize_docs", "nodes": [], "edges": []},
        required_capabilities={
            "context7.query-docs": RequiredCapability(
                ref="context7.query-docs",
                kind="tool",
                input_schema_hash="sha256:input",
                output_schema_hash="sha256:output",
            )
        },
    )


def _echo_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
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
        "nodes": [
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
                "input": [input_binding("input.text", "text")],
                "output": [output_binding("echoed", "state.echoed")],
            }
        ],
        "edges": [{"from": "echo", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="echo",
        version=1,
        title="Echo",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities={
            "demo.echo_tool": RequiredCapability(
                ref="demo.echo_tool",
                kind="node_spec",
            )
        },
    )


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


def _logical_echo_artifact() -> WorkflowArtifact:
    artifact = _echo_artifact()
    plan = dict(artifact.plan)
    nodes = [dict(node) for node in plan["nodes"]]
    nodes[0]["node"] = "demo.echo_tool"
    plan["nodes"] = nodes
    return artifact.model_copy(
        update={
            "id": "logical_echo",
            "plan": plan,
        }
    )


def _custom_reducer_artifact() -> WorkflowArtifact:
    plan: dict[str, Any] = {
        "name": "multiply",
        "input_schema": {
            "type": "object",
            "properties": {
                "total": {"type": "integer"},
                "amount": {"type": "integer"},
            },
            "required": ["total", "amount"],
        },
        "state_schema": {
            "type": "object",
            "properties": {
                "total": {
                    "type": "integer",
                    "reducer": "custom.multiply",
                }
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {"total": {"type": "integer"}},
            "required": ["total"],
        },
        "start": "amount",
        "nodes": [
            {
                "id": "amount",
                "type": "node",
                "node": "demo.personal.amount_tool",
                "input": [input_binding("input.amount", "amount")],
                "output": [output_binding("amount", "state.total")],
            }
        ],
        "edges": [{"from": "amount", "outcome": "ok", "to": "__end__"}],
    }
    return WorkflowArtifact(
        id="multiply",
        version=1,
        title="Multiply",
        input_schema=plan["input_schema"],
        output_schema=plan["output_schema"],
        outcomes=("completed",),
        plan=plan,
        required_capabilities={
            "demo.amount_tool": RequiredCapability(
                ref="demo.amount_tool",
                kind="node_spec",
            ),
            "custom.multiply": RequiredCapability(
                ref="custom.multiply",
                kind="reducer",
            ),
        },
    )
