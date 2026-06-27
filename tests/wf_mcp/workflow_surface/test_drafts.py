from __future__ import annotations

import asyncio
from pathlib import Path

from wf_artifacts import (
    FileDraftWorkspaceStore,
    FileWorkflowArtifactStore,
    WorkflowDeployment,
)
from wf_core.models.steps import InputPathBinding, OutputBinding
from wf_core.paths import GraphSourcePath, LocalPath, StatePath
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers
from wf_mcp.workflow_surface.models import CreateMinimalDraftWorkspaceRequest

from ..test_support import echo_tool
from .conftest import (
    ContentOnlyOutputAdapter,
    echo_draft,
    handlers,
    mcp_echo_tool,
)


def test_workflow_surface_rejects_unknown_draft_route_outcome_when_spec_is_known(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "surface_draft_bad_outcome")
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_draft_bad_outcome_mcp"),
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
    assert payload["diagnostics"][0]["path"] == "edges[0].outcome"


def test_workflow_surface_creates_artifact_from_draft_with_binding_suggestions(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "surface_draft_create")
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_draft_create_mcp"),
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
    assert payload["required_logical_sources"] == ["demo"]
    assert payload["suggested_bindings"] == {}
    assert artifact.plan["nodes"][0]["node"] == "demo.echo_tool"
    assert artifact.required_capability_map()["demo.echo_tool"].logical_source == "demo"


def test_workflow_surface_draft_artifact_with_platform_source_succeeds(
    tmp_path: Path,
) -> None:
    """Platform sources like wf.std don't require explicit bindings."""
    artifact_store = FileWorkflowArtifactStore(tmp_path / "surface_draft_platform")
    h = handlers(artifact_store)

    asyncio.run(
        h.create_artifact_from_draft(
            artifact_id="draft_echo_platform",
            version=1,
            title="Draft Echo Platform",
            draft=echo_draft(),
            outcomes=("completed",),
            source_bindings={"demo": "demo.personal"},
        )
    )
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="draft_echo_platform.personal",
            artifact_id="draft_echo_platform",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        )
    )

    payload = asyncio.run(
        h.validate_deployment(deployment_id="draft_echo_platform.personal")
    )

    # wf.std is a platform source, so no binding_missing diagnostic for it
    # The only diagnostic should be source_missing for demo.personal (not registered)
    assert payload["status"] == "unrunnable"
    assert len(payload["diagnostics"]) == 1
    assert payload["diagnostics"][0]["code"] == "source_missing"
    assert payload["diagnostics"][0]["logical_ref"] == "demo.echo_tool"


def test_workflow_surface_validates_draft_workspace_with_live_outcomes(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "surface_workspace_validate")
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_workspace_validate_mcp"),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "surface_workspace_validate_mcp"
        ),
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
    assert payload["diagnostics"][0]["code"] == "undeclared_edge_outcome"
    assert fetched["status"] == "invalid"


def test_workflow_surface_creates_minimal_draft_workspace_with_error_route(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "surface_minimal_workspace")
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_minimal_workspace_mcp"),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "surface_minimal_workspace_mcp"
        ),
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
            "target": "message",
            "value": "Capability call failed",
        }
    ]


def test_workflow_surface_minimal_draft_honors_explicit_error_message_source(
    tmp_path: Path,
) -> None:
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_minimal_explicit_error_mcp"),
        artifact_store=FileWorkflowArtifactStore(
            tmp_path / "surface_minimal_explicit_error"
        ),
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "surface_minimal_explicit_error_mcp"
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
            "target": "message",
            "path": "state.error_message",
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


def test_workflow_surface_accepts_canonical_bindings_for_minimal_workspace(
    tmp_path: Path,
) -> None:
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_minimal_canonical_mcp"),
        artifact_store=FileWorkflowArtifactStore(
            tmp_path / "surface_minimal_canonical"
        ),
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "surface_minimal_canonical_mcp"
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
            "target": "text",
            "path": "input.text",
        }
    ]
    assert workspace.draft["steps"]["call"]["output"] == [
        {
            "source": "echoed",
            "target": "state.echoed",
        }
    ]


def test_workflow_surface_creates_draft_workspace_from_capability_hints(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "surface_workspace_from_capability"
    )
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_workspace_from_capability_mcp"),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "surface_workspace_from_capability_mcp"
        ),
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
    next_actions = result["next_actions"]
    assert next_actions["can_continue"] is True
    assert next_actions["can_save_now"] is True
    assert (
        next_actions["recommended_next_tool"] == "wf.workflow.validate_draft_workspace"
    )
    assert "high confidence" in next_actions["reason"]
    assert next_actions["patch_examples"] == []
    assert next_actions["warnings"] == []
    assert workspace.draft["steps"]["call"]["use"] == "demo.personal.echo_tool"
    assert workspace.draft["steps"]["call"]["input"] == [
        {
            "target": "text",
            "path": "input.text",
        }
    ]
    assert workspace.draft["steps"]["call"]["output"] == [
        {
            "source": "echoed",
            "target": "state.echoed",
        }
    ]


def test_workflow_surface_creates_artifact_from_workspace(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "surface_workspace_artifact")
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_workspace_artifact_mcp"),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "surface_workspace_artifact_mcp"
        ),
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


def test_workflow_surface_workspace_artifact_infers_raw_concrete_dependency(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "surface_workspace_artifact_raw_dependency"
    )
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_workspace_artifact_raw_mcp"),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "surface_workspace_artifact_raw_mcp"
        ),
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


def test_workflow_surface_creates_wrapper_from_workspace(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "surface_workspace_wrapper")
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_workspace_wrapper_mcp"),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "surface_workspace_wrapper_mcp"
        ),
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


def test_workflow_surface_low_confidence_draft_returns_patch_guidance(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "surface_workspace_low_confidence"
    )
    service = WfMcpService(
        store=FileStore(tmp_path / "surface_workspace_low_confidence_mcp"),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(
            tmp_path / "surface_workspace_low_confidence_mcp"
        ),
    )
    service.register_connection(
        ConnectionConfig(
            id="everything.default", server="everything", account="default"
        )
    )
    service.register_adapter("everything", ContentOnlyOutputAdapter())
    asyncio.run(service.refresh_connection_catalog("everything.default"))
    h = WorkflowSurfaceHandlers(service)

    result = asyncio.run(
        h.create_draft_workspace_from_capability(
            workspace_id="content_wrapper",
            capability_name="everything.default.echo",
            name="content_wrapper",
        )
    )

    next_actions = result["next_actions"]
    assert next_actions["can_continue"] is True
    assert next_actions["can_save_now"] is False
    assert next_actions["recommended_next_tool"] == "wf.workflow.patch_draft_workspace"
    assert "missing wrapper decisions" in next_actions["reason"]
    assert (
        next_actions["patch_examples"][0]["tool"] == "wf.workflow.patch_draft_workspace"
    )
    assert (
        next_actions["patch_examples"][0]["request"]["workspace_id"]
        == "content_wrapper"
    )
    assert (
        next_actions["patch_examples"][0]["request"]["revision"] == result["revision"]
    )
    assert next_actions["warnings"]
