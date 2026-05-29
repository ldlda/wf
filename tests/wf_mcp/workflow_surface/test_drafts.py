from __future__ import annotations

import asyncio

from wf_artifacts import FileWorkflowArtifactStore, WorkflowDeployment
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers
from wf_mcp.workflow_surface.models import CreateMinimalDraftWorkspaceRequest
from wf_core.models.steps import InputPathBinding, OutputBinding
from wf_core.paths import GraphSourcePath, LocalPath, StatePath

from ..test_support import echo_tool, local_temp_root
from .conftest import (
    echo_draft,
    handlers,
    mcp_echo_tool,
)


def test_workflow_surface_validates_draft_without_saving() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_draft_validate"
    )
    h = handlers(artifact_store)

    payload = asyncio.run(h.validate_draft(draft=echo_draft()))

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
    h = WorkflowSurfaceHandlers(service)
    draft = echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}

    payload = asyncio.run(h.validate_draft(draft=draft))

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
    h = WorkflowSurfaceHandlers(service)
    draft = echo_draft()
    draft["steps"]["echo"]["use"] = "demo.personal.echo_tool"

    payload = asyncio.run(
        h.create_artifact_from_draft(
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
    h = handlers(artifact_store)

    asyncio.run(
        h.create_artifact_from_draft(
            artifact_id="draft_echo_missing_std",
            version=1,
            title="Draft Echo Missing Std",
            draft=echo_draft(),
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
        h.validate_deployment(deployment_id="draft_echo_missing_std.personal")
    )

    assert payload["status"] == "unrunnable"
    assert payload["diagnostics"][0]["code"] == "binding_missing"
    assert payload["diagnostics"][0]["logical_ref"] == "wf.std.replace"


def test_workflow_surface_patches_draft_without_saving() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_draft_patch"
    )
    h = handlers(artifact_store)

    payload = asyncio.run(
        h.patch_draft(
            draft=echo_draft(),
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
    h = handlers(artifact_store)

    created = asyncio.run(
        h.create_draft_workspace(
            workspace_id="echo_draft",
            title="Echo Draft",
            draft=echo_draft(),
        )
    )
    fetched = asyncio.run(
        h.get_draft_workspace(
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
    h = handlers(artifact_store)
    asyncio.run(
        h.create_draft_workspace(
            workspace_id="b_draft",
            draft=echo_draft(),
            title="B Draft",
        )
    )
    asyncio.run(
        h.create_draft_workspace(
            workspace_id="a_draft",
            draft=echo_draft(),
            title="A Draft",
        )
    )

    payload = asyncio.run(h.list_draft_workspaces())

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
    h = handlers(artifact_store)
    asyncio.run(
        h.create_draft_workspace(
            workspace_id="echo_draft",
            draft=echo_draft(),
        )
    )

    deleted = asyncio.run(h.delete_draft_workspace(workspace_id="echo_draft"))
    deleted_again = asyncio.run(h.delete_draft_workspace(workspace_id="echo_draft"))
    listed = asyncio.run(h.list_draft_workspaces())

    assert deleted["deleted"] is True
    assert deleted["status"] == "deleted"
    assert deleted_again["deleted"] is False
    assert deleted_again["status"] == "not_found"
    assert listed["workspaces"] == []


def test_workflow_surface_patch_helpers_update_draft_workspace() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_patch_helpers"
    )
    h = handlers(artifact_store)
    asyncio.run(
        h.create_draft_workspace(
            workspace_id="echo_draft",
            draft=echo_draft(),
        )
    )

    named = asyncio.run(
        h.set_draft_name(
            workspace_id="echo_draft",
            revision=1,
            name="echo_v2",
        )
    )
    routed = asyncio.run(
        h.set_draft_route(
            workspace_id="echo_draft",
            revision=2,
            step_id="echo",
            outcome="error",
            target="__end__",
        )
    )
    input_mapped = asyncio.run(
        h.set_step_input_map(
            workspace_id="echo_draft",
            revision=3,
            step_id="echo",
            input_map={"input.text": "message"},
        )
    )
    output_mapped = asyncio.run(
        h.set_step_output_map(
            workspace_id="echo_draft",
            revision=4,
            step_id="echo",
            output_map={"echoed": "state.echoed"},
        )
    )
    fetched = asyncio.run(
        h.get_draft_workspace(workspace_id="echo_draft", include_draft=True)
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
    h = WorkflowSurfaceHandlers(service)
    draft = echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}
    asyncio.run(
        h.create_draft_workspace(
            workspace_id="echo_draft",
            draft=draft,
        )
    )

    payload = asyncio.run(h.validate_draft_workspace(workspace_id="echo_draft"))
    fetched = asyncio.run(h.get_draft_workspace(workspace_id="echo_draft"))

    assert payload["revision"] == 1
    assert payload["status"] == "invalid"
    assert payload["diagnostics"][0]["code"] == "unknown_outcome"
    assert fetched["status"] == "invalid"


def test_workflow_surface_patches_draft_workspace_by_revision() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_patch"
    )
    h = handlers(artifact_store)
    asyncio.run(
        h.create_draft_workspace(
            workspace_id="echo_draft",
            draft=echo_draft(),
        )
    )

    patched = asyncio.run(
        h.patch_draft_workspace(
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
    h = WorkflowSurfaceHandlers(service)

    result = asyncio.run(
        h.create_minimal_draft_workspace(
            workspace_id="echo_draft_static_error",
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
    workspace = service.draft_workspace_store.get_workspace("echo_draft_static_error")

    assert result["workspace_id"] == "echo_draft_static_error"
    assert workspace.draft["routes"]["call"]["ok"] == "__end__"
    assert workspace.draft["routes"]["call"]["error"] == "tool_error"
    assert workspace.draft["steps"]["tool_error"]["use"] == "wf.std.runtime_error"
    assert workspace.draft["steps"]["tool_error"]["input"] == [
        {
            "target": {"root": "local", "parts": ["message"]},
            "value": "Capability call failed",
        }
    ]


def test_workflow_surface_minimal_draft_honors_explicit_error_message_source() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_minimal_explicit_error_mcp"),
        artifact_store=FileWorkflowArtifactStore(
            local_temp_root() / "surface_minimal_explicit_error"
        ),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", mcp_echo_tool)
    h = WorkflowSurfaceHandlers(service)

    asyncio.run(
        h.create_minimal_draft_workspace(
            workspace_id="echo_draft_explicit_error",
            name="echo",
            capability_name="demo.personal.mcp_echo_tool",
            input_schema={"type": "object"},
            state_schema={"fields": {"error_message": {"type": "string"}}},
            output_schema={"type": "object"},
            input_map={"input.text": "text"},
            output_map={"echoed": "state.echoed"},
            error_message_source=GraphSourcePath.state("error_message"),
        )
    )
    assert service.draft_workspace_store is not None
    workspace = service.draft_workspace_store.get_workspace("echo_draft_explicit_error")

    assert workspace.draft["steps"]["tool_error"]["input"] == [
        {
            "target": {"root": "local", "parts": ["message"]},
            "path": {"root": "state", "parts": ["error_message"]},
        }
    ]


def test_minimal_draft_request_accepts_structural_error_message_source() -> None:
    request = CreateMinimalDraftWorkspaceRequest.model_validate(
        {
            "workspace_id": "echo_draft_structural_error",
            "name": "echo",
            "capability_name": "demo.personal.mcp_echo_tool",
            "input_schema": {"type": "object"},
            "state_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "error_message_source": {
                "root": "state",
                "parts": ["error_message"],
            },
        }
    )

    assert isinstance(request.error_message_source, GraphSourcePath)
    assert request.error_message_source.root == "state"
    assert request.error_message_source.parts == ("error_message",)


def test_workflow_surface_accepts_canonical_bindings_for_minimal_workspace() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_minimal_canonical_mcp"),
        artifact_store=FileWorkflowArtifactStore(
            local_temp_root() / "surface_minimal_canonical"
        ),
    )
    h = WorkflowSurfaceHandlers(service)

    result = asyncio.run(
        h.create_minimal_draft_workspace(
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
    h = WorkflowSurfaceHandlers(service)

    result = asyncio.run(
        h.create_draft_workspace_from_capability(
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
    h = WorkflowSurfaceHandlers(service)
    asyncio.run(
        h.create_draft_workspace(
            workspace_id="echo_draft",
            draft=echo_draft(),
        )
    )

    result = asyncio.run(
        h.create_artifact_from_workspace(
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
    assert artifact.plan["nodes"][0]["node"] == "demo.echo_tool"
    required = artifact.required_capability_map()["demo.echo_tool"]
    assert required.kind == "node_spec"
    assert str(required.observed_concrete_source) == "demo.personal"
    assert required.input_schema_snapshot is not None
    assert required.output_schema_snapshot is not None


def test_workflow_surface_workspace_artifact_infers_raw_concrete_dependency() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_workspace_artifact_raw_dependency"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_workspace_artifact_raw_mcp"),
        artifact_store=artifact_store,
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    h = WorkflowSurfaceHandlers(service)
    asyncio.run(
        h.create_draft_workspace(
            workspace_id="echo_draft",
            draft=echo_draft(),
        )
    )

    asyncio.run(
        h.create_artifact_from_workspace(
            workspace_id="echo_draft",
            artifact_id="workspace_echo_raw_dependency",
            version=1,
            title="Workspace Echo Raw Dependency",
            outcomes=("completed",),
        )
    )

    artifact = artifact_store.get_artifact("workspace_echo_raw_dependency", 1)
    required = artifact.required_capability_map()["demo.personal.echo_tool"]
    assert required.kind == "node_spec"
    assert required.input_schema_snapshot is not None
    assert required.output_schema_snapshot is not None


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
    h = WorkflowSurfaceHandlers(service)
    asyncio.run(
        h.create_draft_workspace(
            workspace_id="echo_draft",
            draft=echo_draft(),
        )
    )

    result = asyncio.run(
        h.create_wrapper_from_workspace(
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
