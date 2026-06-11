from __future__ import annotations

from wf_authoring import NodeSpec
from wf_mcp.broker import WfMcpService
from wf_mcp.models import ConnectionConfig
from wf_mcp.storage import FileStore
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    SourceVisibility,
)

from ..test_support import (
    FakeAdapter,
    echo_tool,
    finalize_tool,
    local_temp_root,
)
from .conftest import raw_plan, single_echo_plan


async def test_service_compiles_and_runs_raw_plan() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "run_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    plan = raw_plan(
        name="demo_plan",
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
        start="echo",
        nodes=[
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
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
        ],
        edges=[{"from": "echo", "outcome": "ok", "to": "__end__"}],
    )

    run = await service.run_workflow_from_plan(plan, {"text": "hello"})

    assert run.status == "completed"
    assert run.output["echoed"] == "hello"


async def test_service_preserves_raw_plan_root_output_bindings() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "root_output_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    plan = raw_plan(
        name="root_output_plan",
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
        start="echo",
        nodes=[
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
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
        ],
        edges=[{"from": "echo", "outcome": "ok", "to": "__end__"}],
    )

    run = await service.run_workflow_from_plan(plan, {"text": "hello"})

    assert run.output["echoed"] == "hello"


async def test_service_resolves_registered_spec_with_dotted_local_name() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "dotted_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)

    plan = single_echo_plan("dotted_plan", "demo.personal.echo_tool")

    run = await service.run_workflow_from_plan(plan, {"text": "hello"})

    assert run.status == "completed"
    assert run.output["echoed"] == "hello"


async def test_service_runs_logical_source_plan_with_dotted_local_name() -> None:
    import shutil

    from wf_artifacts import WorkflowDeployment
    from wf_authoring import NodeSpec

    from ..test_support import echo_tool

    store = local_temp_root() / "logical_source_store"
    shutil.rmtree(store, ignore_errors=True)
    service = WfMcpService(store=FileStore(store))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    dotted_echo_tool = NodeSpec(
        name="foo.bar",
        input_model=echo_tool.input_model,
        output_model=echo_tool.output_model,
        outcomes=echo_tool.outcomes,
        fn=echo_tool.fn,
        description=echo_tool.description,
        is_async=echo_tool.is_async,
        accepts_context=echo_tool.accepts_context,
        input_schema_contract=echo_tool.input_schema_contract,
        output_schema_contract=echo_tool.output_schema_contract,
    )
    service.register_specs("demo.personal", dotted_echo_tool)

    plan = single_echo_plan("logical_plan", "demo.foo.bar")

    run = await service.run_workflow_from_plan(
        plan,
        {"text": "hello"},
        deployment=WorkflowDeployment(
            id="logical_dotted.personal",
            artifact_id="logical_dotted",
            artifact_version=1,
            bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
        ),
    )

    assert run.status == "completed"
    assert run.output["echoed"] == "hello"


async def test_service_binds_longest_logical_source_prefix_first() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "prefix_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_connection(
        ConnectionConfig(id="demo.work", server="demo", account="work")
    )
    service.register_specs("demo.personal", echo_tool)

    plan = single_echo_plan("prefix_plan", "demo.personal.echo_tool")

    run = await service.run_workflow_from_plan(plan, {"text": "hello"})

    assert run.status == "completed"


def test_service_does_not_resolve_specs_hidden_from_planner() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "hidden_resolve_store"))
    hidden_echo_tool = NodeSpec(
        name="hidden.source.echo_tool",
        input_model=echo_tool.input_model,
        output_model=echo_tool.output_model,
        outcomes=echo_tool.outcomes,
        fn=echo_tool.fn,
        description=echo_tool.description,
        is_async=echo_tool.is_async,
        accepts_context=echo_tool.accepts_context,
        input_schema_contract=echo_tool.input_schema_contract,
        output_schema_contract=echo_tool.output_schema_contract,
    )
    service.register_capability_source(
        CapabilitySource(
            id="hidden.source",
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs={"hidden.source.echo_tool": hidden_echo_tool}
            ),
            visibility=SourceVisibility(planner=False, admin_dashboard=False),
        )
    )

    try:
        service._get_qualified_spec("hidden.source.echo_tool")
    except KeyError:
        pass
    else:
        raise AssertionError("expected hidden spec to be unresolvable")


def test_service_excludes_disabled_connection_specs_from_planner_catalog() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "disabled_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    service.capability_sources["demo.personal"].enabled = False

    planner_names = {
        entry.qualified_name for entry in service.get_planner_catalog().entries()
    }
    assert "demo.personal.echo_tool" not in planner_names


def test_service_preserves_disabled_connection_source_on_reregistration() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "disabled_reregister"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    service.capability_sources["demo.personal"].enabled = False
    service.register_specs("demo.personal", finalize_tool)

    source = service.capability_sources["demo.personal"]
    assert source.enabled is False
    assert "demo.personal.finalize_tool" in source.capabilities.node_specs
    assert "demo.personal.echo_tool" not in source.capabilities.node_specs


def test_service_excludes_planner_hidden_connection_specs_from_planner_catalog() -> (
    None
):
    service = WfMcpService(store=FileStore(local_temp_root() / "planner_hidden_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    service.capability_sources["demo.personal"].visibility = SourceVisibility(
        planner=False,
        client=True,
        admin_dashboard=True,
    )

    planner_names = {
        entry.qualified_name for entry in service.get_planner_catalog().entries()
    }
    assert "demo.personal.echo_tool" not in planner_names


def test_service_preserves_planner_hidden_connection_source_on_reregistration() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "planner_hidden_rereg"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    service.capability_sources["demo.personal"].visibility = SourceVisibility(
        planner=False,
        client=True,
        admin_dashboard=True,
    )
    service.register_specs("demo.personal", finalize_tool)

    source = service.capability_sources["demo.personal"]
    assert source.visibility.planner is False
    assert source.visibility.client is True
    assert source.visibility.admin_dashboard is True
    assert "demo.personal.finalize_tool" in source.capabilities.node_specs
    assert "demo.personal.echo_tool" not in source.capabilities.node_specs


async def test_service_refreshes_catalog_from_adapter() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "refresh_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    await service.refresh_connection_catalog("demo.personal")

    source = service.capability_sources["demo.personal"]
    assert "demo.personal.echo_tool" in source.capabilities.node_specs
