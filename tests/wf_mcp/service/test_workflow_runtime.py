from __future__ import annotations

from wf_artifacts import WorkflowDeployment
from wf_core import END, NodeUse, RunStatus
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.source_catalog import SourceCatalogService
from wf_mcp.broker.service.specs import qualify_spec
from wf_mcp.broker.service.workflow_runtime import WorkflowRuntimeService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_platform import CapabilityBuckets, CapabilitySource, SourceVisibility

from ..test_support import FakeAdapter, echo_tool, local_temp_root, output_binding
from .conftest import raw_plan, single_echo_plan


def _unused_tool_executor(connection: ConnectionConfig):
    raise AssertionError("tool executor should not be used by direct compile tests")


def _source_catalog() -> SourceCatalogService:
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
    )
    catalog = SourceCatalogService(
        store=FileStore(local_temp_root() / "runtime_source_catalog"),
        connection_lookup=lambda connection_id: connection,
        connection_list_enabled=lambda: [connection],
        connection_list_all=lambda: [connection],
        tool_executor_for=_unused_tool_executor,
        load_auth=lambda connection_id: None,
        emit_event=lambda event: None,
    )
    qualified_echo = qualify_spec("demo.personal", echo_tool)
    catalog.register_capability_source(
        CapabilitySource(
            id="demo.personal",
            kind="connection",
            capabilities=CapabilityBuckets(
                node_specs={"demo.personal.echo_tool": qualified_echo}
            ),
            visibility=SourceVisibility(planner=True),
        )
    )
    return catalog


def test_workflow_runtime_service_compiles_plan_directly() -> None:
    runtime = WorkflowRuntimeService(
        source_catalog=_source_catalog(),
        artifact_store=None,
        emit_event=lambda event: None,
    )

    workflow = runtime.compile_plan(
        single_echo_plan("runtime_compile", "demo.echo_tool"),
        {"demo.echo_tool": "demo.personal.echo_tool"},
    )

    node = workflow.nodes[0]
    assert isinstance(node, NodeUse)
    assert node.node == "demo.personal.echo_tool"
    node_def_names = [nd.name for nd in workflow.node_defs]
    assert "demo.personal.echo_tool" in node_def_names


def test_wfmcpservice_constructs_workflow_runtime_with_source_catalog() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "runtime_delegate"))

    assert service.workflow_runtime.source_catalog is service.source_catalog
    assert service.workflow_runtime.artifact_store is service.artifact_store
    assert service.workflow_runtime.read_resource_handler is not None


def test_wfmcpservice_compile_plan_delegates_to_workflow_runtime() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "runtime_compile_delegate")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    workflow = service.compile_plan(
        single_echo_plan("runtime_delegate_compile", "demo.echo_tool"),
        {"demo.echo_tool": "demo.personal.echo_tool"},
    )

    assert "demo.personal.echo_tool" in [
        n.node for n in workflow.nodes if isinstance(n, NodeUse)
    ]


def test_workflow_runtime_service_prepares_node_registry_and_reducers() -> None:
    runtime = WorkflowRuntimeService(
        source_catalog=_source_catalog(),
        artifact_store=None,
        emit_event=lambda event: None,
    )

    workflow, registry, reducers, prepared_subgraphs, platform_context = (
        runtime.prepare_workflow_runtime(
            single_echo_plan("runtime_prepare", "demo.personal.echo_tool"),
            deployment=None,
            artifact=None,
        )
    )

    assert "demo.personal.echo_tool" in [nd.name for nd in workflow.node_defs]
    assert "demo.personal.echo_tool" in registry
    assert isinstance(reducers, dict)
    assert prepared_subgraphs == {}
    assert platform_context.source_bindings == {}
    assert isinstance(platform_context.platform_sources, set)
    assert platform_context.read_resource_handler is None


def test_wfmcpservice_prepares_platform_context_with_resource_handler() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "runtime_platform_context")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    *_runtime, platform_context = service.workflow_runtime.prepare_workflow_runtime(
        single_echo_plan("runtime_platform_context", "demo.personal.echo_tool"),
        deployment=None,
        artifact=None,
    )

    assert platform_context.read_resource_handler is not None


async def test_workflow_runtime_service_runs_plan_and_emits_events() -> None:
    events = []
    runtime = WorkflowRuntimeService(
        source_catalog=_source_catalog(),
        artifact_store=None,
        emit_event=events.append,
    )

    run = await runtime.run_workflow_from_plan(
        single_echo_plan("runtime_run", "demo.personal.echo_tool"),
        {"text": "hello"},
    )

    assert run.output["echoed"] == "hello"
    assert [event.kind for event in events] == [
        "workflow_run_started",
        "workflow_run_completed",
    ]
    assert events[1].payload["status"] == "completed"


async def test_wf_source_read_resource_runs_through_platform_context() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "runtime_source_resource")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())
    await service.refresh_connection_catalog("demo.personal")

    run = await service.workflow_runtime.run_workflow_from_plan(
        raw_plan(
            name="runtime_source_resource",
            input_schema={"type": "object", "properties": {}},
            state_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
            start="read",
            nodes=[
                {
                    "id": "read",
                    "type": "node",
                    "node": "wf.source.read_resource",
                    "input": [
                        {
                            "value": {
                                "kind": "source_resource_ref",
                                "logical_source": "drive",
                                "uri": "demo://docs/welcome",
                            },
                            "target": {"root": "local", "parts": ["ref"]},
                        },
                        {
                            "value": 7,
                            "target": {"root": "local", "parts": ["max_chars"]},
                        },
                    ],
                    "output": [output_binding("text", "state.text")],
                }
            ],
            edges=[{"from": "read", "outcome": "ok", "to": END}],
            output=[
                {
                    "path": {"root": "state", "parts": ["text"]},
                    "target": {"root": "local", "parts": ["text"]},
                }
            ],
        ),
        {},
        deployment=WorkflowDeployment(
            id="runtime_source_resource.default",
            artifact_id="runtime_source_resource",
            artifact_version=1,
            bindings={"drive": "demo.personal"},
        ),
    )

    assert run.status == RunStatus.COMPLETED
    assert run.output == {"text": "Welcome"}


async def test_workflow_runtime_service_emits_failed_event_for_failed_run() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "runtime_failed_event"))

    run = await service.workflow_runtime.run_workflow_from_plan(
        raw_plan(
            name="runtime_failed_event",
            input_schema={"type": "object", "properties": {}},
            state_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            start="fail",
            nodes=[
                {
                    "id": "fail",
                    "type": "node",
                    "node": "wf.std.runtime_error",
                    "input": [
                        {
                            "value": "boom",
                            "target": {
                                "root": "local",
                                "parts": ["message"],
                            },
                        }
                    ],
                }
            ],
            edges=[{"from": "fail", "outcome": "ok", "to": END}],
        ),
        {},
    )

    assert run.status == RunStatus.FAILED
    assert [event.kind for event in service.list_events()][-2:] == [
        "workflow_run_started",
        "workflow_run_failed",
    ]
    assert service.list_events()[-1].payload["status"] == "failed"
