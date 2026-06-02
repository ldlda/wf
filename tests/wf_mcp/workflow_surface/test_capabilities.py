from __future__ import annotations

import asyncio

from wf_artifacts import FileWorkflowArtifactStore, FileDraftWorkspaceStore
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_mcp.workflow_surface import WorkflowSurfaceHandlers

from ..test_support import echo_tool, local_temp_root
from .conftest import (
    ContentOnlyOutputAdapter,
    failing_tool,
    handlers,
)


def test_workflow_surface_lists_planner_visible_capabilities() -> None:
    h = handlers(FileWorkflowArtifactStore(local_temp_root() / "surface_caps"))

    payload = asyncio.run(h.list_capabilities(limit=2))
    first = payload["capabilities"][0]

    assert len(payload["capabilities"]) == 2
    assert payload["total"] >= 2
    assert payload["next_cursor"] == "2"
    assert first["kind"] == "node_spec"
    assert "input_schema" not in first


def test_workflow_surface_call_capability_returns_structured_error() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_call_capability_error_mcp"),
        artifact_store=FileWorkflowArtifactStore(
            local_temp_root() / "surface_call_capability_error"
        ),
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", failing_tool)
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.call_capability(
            qualified_name="demo.personal.failing_tool",
            payload={"message": "hello"},
        )
    )

    assert payload["qualified_name"] == "demo.personal.failing_tool"
    assert payload["source_id"] == "demo.personal"
    assert payload["kind"] == "node_spec"
    assert payload["outcome"] == "runtime_error"
    assert payload["output"] is None
    assert payload["diagnostics"][0]["code"] == "capability_call_failed"
    assert payload["diagnostics"][0]["severity"] == "error"
    assert "demo.personal.failing_tool" in payload["diagnostics"][0]["message"]
    assert "upstream exploded" in payload["diagnostics"][0]["message"]


def test_workflow_surface_inspects_one_capability() -> None:
    h = handlers(FileWorkflowArtifactStore(local_temp_root() / "surface_inspect_cap"))

    payload = asyncio.run(h.inspect_capability(qualified_name="wf.std.runtime_error"))

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
    h = WorkflowSurfaceHandlers(service)

    payload = asyncio.run(
        h.inspect_capability(qualified_name="demo.personal.echo_tool")
    )

    hints = payload["wrapper_hints"]
    assert hints["capability_name"] == "demo.personal.echo_tool"
    assert hints["declared_outcomes"] == ["ok"]
    assert hints["input_map"] == {"input.text": "text"}
    assert hints["output_map"] == {"echoed": "state.echoed"}
    assert hints["outcome_policy"] == "preserve_declared"


def test_workflow_surface_does_not_auto_map_raw_mcp_content_blocks() -> None:
    artifact_store = FileWorkflowArtifactStore(
        local_temp_root() / "surface_content_only_content_hint"
    )
    service = WfMcpService(
        store=FileStore(local_temp_root() / "surface_content_only_content_hint_mcp"),
        artifact_store=artifact_store,
        draft_workspace_store=FileDraftWorkspaceStore(
            local_temp_root() / "surface_content_only_content_hint_mcp"
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

    inspected = asyncio.run(
        h.inspect_capability(qualified_name="everything.default.echo")
    )
    created = asyncio.run(
        h.create_draft_workspace_from_capability(
            workspace_id="content_blocks",
            capability_name="everything.default.echo",
            name="content_blocks",
        )
    )

    assert inspected["wrapper_hints"]["output_map"] == {}
    assert created["wrapper_hints"]["output_map"] == {}
    assert inspected["wrapper_hints"]["missing_decisions"][0]["kind"] == (
        "review_nested_output"
    )
    assert "Raw MCP content blocks" in inspected["wrapper_hints"]["notes"][2]
