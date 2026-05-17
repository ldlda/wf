from __future__ import annotations

import asyncio
import shutil

from wf_authoring import NodeSpec
from wf_core import END, NodeUse, RunStatus
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.capability_sources import (
    CapabilityBuckets,
    CapabilitySource,
    SourceVisibility,
)
from wf_mcp.models import AuthRecord, ConnectionConfig, RawWorkflowPlan
from wf_mcp.shared.errors import error_payload
from wf_mcp.storage import FileStore

from .test_support import (
    FailingDiscoveryAdapter,
    FakeAdapter,
    echo_tool,
    finalize_tool,
    local_temp_root,
)


def _single_echo_plan(plan_name: str, node_name: str) -> RawWorkflowPlan:
    return _raw_plan(
        name=plan_name,
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
                "node": node_name,
                "in_map": {"input.text": "text"},
                "out_map": {"echoed": "state.echoed"},
            }
        ],
        edges=[
            {"from": "echo", "outcome": "ok", "to": END},
        ],
    )


def _raw_plan(**payload: object) -> RawWorkflowPlan:
    """Parse JSON-shaped workflow input through the public typed boundary."""
    return RawWorkflowPlan.model_validate(payload)


def test_service_builds_namespaced_catalog() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "catalog_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool, finalize_tool)

    payload = service.get_catalog().as_payload()
    names = [node["qualified_name"] for node in payload["nodes"]]

    assert names == [
        "demo.personal.echo_tool",
        "demo.personal.finalize_tool",
    ]


def test_service_rejects_reserved_connection_ids() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "reserved_ids_store"))

    for connection_id in ("wf.admin", "wf.mcp"):
        try:
            service.register_connection(
                ConnectionConfig(id=connection_id, server="wf", account="reserved")
            )
        except ValueError as exc:
            assert connection_id in str(exc)
            assert "reserved by wf-mcp" in str(exc)
        else:
            raise AssertionError(f"expected {connection_id!r} to be rejected")


def test_service_installs_builtin_stdlib_specs_by_default() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "builtin_store"))

    assert (
        "wf.std.runtime_error"
        in service.capability_sources["wf.std"].capabilities.node_specs
    )
    assert (
        "wf.mcp.call_tool"
        in service.capability_sources["wf.mcp"].capabilities.node_specs
    )


def test_service_lists_all_capability_sources_with_owned_capability_names() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "source_inventory"))

    sources = service.list_sources()
    sources_by_id = {source["id"]: source for source in sources}

    std_source = sources_by_id["wf.std"]
    assert "wf.std.runtime_error" in std_source["capabilities"]["node_specs"]
    assert std_source["capabilities"]["reducers"] == [
        "wf.std.append",
        "wf.std.max",
        "wf.std.merge_object",
        "wf.std.replace",
        "wf.std.set_union",
    ]
    assert std_source["capabilities"]["tools"] == []
    assert std_source["reducer_count"] == 5

    mcp_source = sources_by_id["wf.mcp"]
    assert mcp_source["capabilities"]["node_specs"] == ["wf.mcp.call_tool"]

    admin_source = sources_by_id["wf.admin"]
    assert admin_source["visibility"]["planner"] is False
    assert "wf.admin.list_sources" in admin_source["capabilities"]["tools"]


def test_wf_std_source_contains_authoring_ops() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "stdlib_source_store"))
    specs = service.capability_sources["wf.std"].capabilities.node_specs

    expected = {
        "wf.std.coalesce",
        "wf.std.default_if_none",
        "wf.std.constant",
        "wf.std.pick_key",
        "wf.std.pick_path",
        "wf.std.project_fields",
        "wf.std.rename_fields",
        "wf.std.truthy",
        "wf.std.runtime_error",
        "wf.std.first_item",
        "wf.std.first_item_or_none",
        "wf.std.first_item_maybe",
        "wf.std.last_item",
        "wf.std.last_item_or_none",
        "wf.std.length",
        "wf.std.is_empty",
    }
    assert set(specs) == expected


def test_wf_std_source_contains_builtin_reducers() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "stdlib_reducer_store"))
    reducers = service.capability_sources["wf.std"].capabilities.reducers

    assert set(reducers) == {
        "wf.std.replace",
        "wf.std.append",
        "wf.std.max",
        "wf.std.merge_object",
        "wf.std.set_union",
    }


def test_service_sources_have_visibility_and_capability_buckets() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "source_shape_store"))

    std_source = service.capability_sources["wf.std"]
    mcp_source = service.capability_sources["wf.mcp"]

    assert std_source.id == "wf.std"
    assert std_source.kind == "system"
    assert std_source.visibility.planner is True
    assert std_source.visibility.mcp_client is True
    assert std_source.visibility.admin_dashboard is True
    assert "wf.std.runtime_error" in std_source.capabilities.node_specs
    assert not std_source.capabilities.tools

    assert mcp_source.id == "wf.mcp"
    assert mcp_source.visibility.planner is True
    assert mcp_source.permissions.calls_upstream is True
    assert "wf.mcp.call_tool" in mcp_source.capabilities.node_specs


def test_wf_admin_source_exists_but_is_not_planner_visible() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "admin_source_store"))
    source = service.capability_sources["wf.admin"]

    assert source.kind == "system"
    assert source.visibility.planner is False
    assert source.visibility.mcp_client is False
    assert source.visibility.admin_dashboard is True
    assert source.permissions.safe_for_workflow is False
    assert source.permissions.calls_upstream is False
    assert source.permissions.mutates_config is True
    assert source.permissions.mutates_auth is True
    assert "wf.admin.list_sources" in source.capabilities.tools
    assert "wf.admin.disable_source" in source.capabilities.tools
    assert "wf.admin.enable_source" in source.capabilities.tools
    assert "wf.admin" not in service.get_planner_catalog().snapshots


def test_service_can_disable_builtin_stdlib_specs() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "no_builtin_store"),
        include_builtin_specs=False,
    )

    assert "wf.std" not in service.capability_sources
    assert "wf.mcp" not in service.capability_sources


def test_service_planner_catalog_excludes_hidden_sources() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "hidden_list_store"))
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

    planner_names = {
        entry.qualified_name for entry in service.get_planner_catalog().entries()
    }
    assert "hidden.source.echo_tool" not in planner_names


def test_service_catalog_split_keeps_system_specs_out_of_backend_catalog() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "planner_store"))

    backend_payload = service.get_catalog().as_payload()
    planner_payload = service.get_planner_catalog().as_payload()

    assert backend_payload["nodes"] == []
    planner_node_names = {node["qualified_name"] for node in planner_payload["nodes"]}
    assert "wf.mcp.call_tool" in planner_node_names
    assert "wf.std.runtime_error" in planner_node_names
    available_names = {entry.qualified_name for entry in service.list_available_specs()}
    assert "wf.mcp.call_tool" in available_names
    assert "wf.std.runtime_error" in available_names


def test_service_hydrates_planner_specs_from_stored_catalog() -> None:
    store = local_temp_root() / "restart_planner_store"
    shutil.rmtree(store, ignore_errors=True)
    first_service = WfMcpService(store=FileStore(store))
    first_service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    first_service.register_adapter("demo", FakeAdapter())
    asyncio.run(first_service.refresh_connection_catalog("demo.personal"))

    second_service = WfMcpService(store=FileStore(store))
    second_service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    second_service.register_adapter("demo", FakeAdapter())

    planner_names = {
        node["qualified_name"]
        for node in second_service.get_planner_catalog().as_payload()["nodes"]
    }
    run = asyncio.run(
        second_service.run_workflow_from_plan(
            _single_echo_plan("hydrated_plan", "demo.personal.echo_tool"),
            {"text": "hello"},
        )
    )

    assert "demo.personal.echo_tool" in planner_names
    assert run.status == RunStatus.COMPLETED
    assert run.output["echoed"] == "hello"


def test_service_compiles_and_runs_raw_plan() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "run_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool, finalize_tool)

    plan = _raw_plan(
        name="demo_plan",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        state_schema={
            "fields": {
                "echoed": {"type": "string"},
                "result": {"type": "string"},
            }
        },
        output_schema={
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        },
        start="echo",
        nodes=[
            {
                "id": "echo",
                "type": "node",
                "node": "demo.personal.echo_tool",
                "in_map": {"input.text": "text"},
                "out_map": {"echoed": "state.echoed"},
            },
            {
                "id": "finalize",
                "type": "node",
                "node": "demo.personal.finalize_tool",
                "in_map": {"state.echoed": "echoed"},
                "out_map": {"result": "state.result"},
            },
        ],
        edges=[
            {"from": "echo", "outcome": "ok", "to": "finalize"},
            {"from": "finalize", "outcome": "done", "to": END},
        ],
    )

    run = asyncio.run(service.run_workflow_from_plan(plan, {"text": "hello"}))

    assert run.status == RunStatus.COMPLETED
    assert run.output == {"result": "final:hello"}
    event_kinds = [event.kind for event in service.list_events()]
    assert "workflow_run_started" in event_kinds
    assert "workflow_run_completed" in event_kinds


def test_service_resolves_registered_spec_with_dotted_local_name() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "dotted_spec_store"))
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

    plan = _raw_plan(
        name="dotted_local_name_plan",
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
                "node": "demo.personal.foo.bar",
                "in_map": {"input.text": "text"},
                "out_map": {"echoed": "state.echoed"},
            }
        ],
        edges=[
            {"from": "echo", "outcome": "ok", "to": END},
        ],
    )

    workflow = service.compile_plan(plan)
    run = asyncio.run(service.run_workflow_from_plan(plan, {"text": "hello"}))

    assert workflow.name == "dotted_local_name_plan"
    first_node = workflow.nodes[0]
    assert isinstance(first_node, NodeUse)
    assert first_node.node == "demo.personal.foo.bar"
    assert run.status == RunStatus.COMPLETED
    assert run.output["echoed"] == "hello"


def test_service_does_not_resolve_specs_hidden_from_planner() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "hidden_spec_store"))
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
            visibility=SourceVisibility(planner=False),
        )
    )

    plan = _raw_plan(
        name="hidden_source_plan",
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
                "node": "hidden.source.echo_tool",
                "in_map": {"input.text": "text"},
                "out_map": {"echoed": "state.echoed"},
            }
        ],
        edges=[
            {"from": "echo", "outcome": "ok", "to": END},
        ],
    )

    try:
        service.compile_plan(plan)
    except KeyError as exc:
        assert "hidden.source.echo_tool" in str(exc)
    else:
        raise AssertionError("expected planner-hidden spec resolution to fail")


def test_service_excludes_disabled_connection_specs_from_planner_catalog() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "disabled_connection_spec_store")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    service.capability_sources["demo.personal"].enabled = False

    planner_payload = service.get_planner_catalog().as_payload()
    planner_names = [node["qualified_name"] for node in planner_payload["nodes"]]
    available_names = [entry.qualified_name for entry in service.list_available_specs()]

    assert "demo.personal.echo_tool" not in planner_names
    assert "demo.personal.echo_tool" not in available_names
    assert "demo.personal" not in service.get_planner_catalog().snapshots

    try:
        service.compile_plan(
            _single_echo_plan("disabled_connection_plan", "demo.personal.echo_tool")
        )
    except KeyError as exc:
        assert "demo.personal.echo_tool" in str(exc)
    else:
        raise AssertionError("expected disabled connection spec resolution to fail")


def test_service_preserves_disabled_connection_source_on_reregistration() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "disabled_reregister_spec_store")
    )
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
    service = WfMcpService(
        store=FileStore(local_temp_root() / "hidden_connection_spec_store")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    service.capability_sources["demo.personal"].visibility = SourceVisibility(
        planner=False,
        mcp_client=True,
        admin_dashboard=True,
    )

    planner_payload = service.get_planner_catalog().as_payload()
    planner_names = [node["qualified_name"] for node in planner_payload["nodes"]]
    available_names = [entry.qualified_name for entry in service.list_available_specs()]

    assert "demo.personal.echo_tool" not in planner_names
    assert "demo.personal.echo_tool" not in available_names
    assert "demo.personal" not in service.get_planner_catalog().snapshots

    try:
        service.compile_plan(
            _single_echo_plan("hidden_connection_plan", "demo.personal.echo_tool")
        )
    except KeyError as exc:
        assert "demo.personal.echo_tool" in str(exc)
    else:
        raise AssertionError(
            "expected planner-hidden connection spec resolution to fail"
        )


def test_service_preserves_planner_hidden_connection_source_on_reregistration() -> None:
    service = WfMcpService(
        store=FileStore(local_temp_root() / "hidden_reregister_spec_store")
    )
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", echo_tool)
    service.capability_sources["demo.personal"].visibility = SourceVisibility(
        planner=False,
        mcp_client=True,
        admin_dashboard=True,
    )

    service.register_specs("demo.personal", finalize_tool)

    source = service.capability_sources["demo.personal"]
    assert source.visibility.planner is False
    assert source.visibility.mcp_client is True
    assert source.visibility.admin_dashboard is True
    assert "demo.personal.finalize_tool" in source.capabilities.node_specs
    assert "demo.personal.echo_tool" not in source.capabilities.node_specs


def test_service_refreshes_catalog_from_adapter() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "adapter_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.save_auth(
        AuthRecord(
            connection_id="demo.personal",
            scheme="token",
            payload={"token": "abc"},
        )
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    payload = service.get_catalog().as_payload()
    assert payload["nodes"] == [
        {
            "qualified_name": "demo.personal.echo_tool",
            "connection_id": "demo.personal",
            "local_name": "echo_tool",
            "title": "Echo Tool",
            "description": "Echo text back",
            "outcomes": ["ok"],
            "input_schema": {
                "properties": {
                    "text": {
                        "description": "Text to echo",
                        "type": "string",
                    }
                },
                "required": ["text"],
                "type": "object",
            },
            "output_schema": {
                "properties": {
                    "echoed": {
                        "description": "Echoed text",
                        "type": "string",
                    }
                },
                "required": ["echoed"],
                "type": "object",
            },
        }
    ]
    assert payload["resources"] == [
        {
            "qualified_name": "demo.personal.resource.welcome",
            "connection_id": "demo.personal",
            "local_name": "resource.welcome",
            "title": "Welcome Resource",
            "uri": "demo://docs/welcome",
            "description": "Welcome resource",
            "mime_type": "text/plain",
            "metadata": {"kind": "static"},
        }
    ]
    assert payload["prompts"] == [
        {
            "qualified_name": "demo.personal.prompt.summarize",
            "connection_id": "demo.personal",
            "local_name": "prompt.summarize",
            "title": "Summarize Prompt",
            "description": "Summarize text",
            "arguments": [
                {
                    "name": "text",
                    "required": True,
                    "description": "Text to summarize",
                }
            ],
            "metadata": {"kind": "template"},
        }
    ]
    assert payload["connections"] == [
        {
            "connection_id": "demo.personal",
            "fetched_at_epoch_ms": payload["connections"][0]["fetched_at_epoch_ms"],
            "max_age_seconds": 300,
            "metadata": {
                "server": "demo",
                "account": "personal",
                "auth_scheme": "token",
            },
        }
    ]
    event_kinds = [event.kind for event in service.list_events()]
    assert "catalog_refresh_started" in event_kinds
    assert "catalog_refresh_completed" in event_kinds


def test_service_catalog_preserves_json_schema_description_metadata() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "schema_doc_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    node = service.get_catalog().as_payload()["nodes"][0]
    assert node["input_schema"]["type"] == "object"
    assert isinstance(node["input_schema"]["properties"], dict)
    assert node["input_schema"]["properties"]["text"]["description"] == "Text to echo"
    assert node["output_schema"]["type"] == "object"
    assert isinstance(node["output_schema"]["properties"], dict)


def test_service_wrapped_tool_adapter_model_validates_simple_schema_types() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "schema_model_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))
    spec = service.capability_sources["demo.personal"].capabilities.node_specs[
        "demo.personal.echo_tool"
    ]

    parsed = spec.input_model.model_validate({"text": "hello"})
    assert parsed.model_dump() == {"text": "hello"}
    assert (
        spec.input_model.model_json_schema()["properties"]["text"]["description"]
        == "Text to echo"
    )

    try:
        spec.input_model.model_validate({"text": 123})
    except ValueError as exc:
        assert "text" in str(exc)
    else:
        raise AssertionError(
            "expected generated adapter model to reject non-string text"
        )


def test_service_records_tool_call_events() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "event_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    plan = _raw_plan(
        name="tool_only_plan",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        state_schema={
            "fields": {
                "echoed": {"type": "string"},
            }
        },
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
                "in_map": {"input.text": "text"},
                "out_map": {"echoed": "state.echoed"},
            }
        ],
        edges=[
            {"from": "echo", "outcome": "ok", "to": END},
        ],
    )

    run = asyncio.run(service.run_workflow_from_plan(plan, {"text": "hello"}))

    assert run.status == RunStatus.COMPLETED
    tool_events = [
        event for event in service.list_events() if "tool_call" in event.kind
    ]
    assert [event.kind for event in tool_events] == [
        "tool_call_started",
        "tool_call_completed",
    ]
    assert tool_events[0].capability_id == "demo.personal.echo_tool"
    assert tool_events[1].payload["outcome"] == "ok"


def test_service_can_call_upstream_tool_through_wf_mcp_system_node() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "system_tool_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    plan = _raw_plan(
        name="system_tool_plan",
        input_schema={
            "type": "object",
            "properties": {
                "connection_id": {"type": "string"},
                "tool_name": {"type": "string"},
                "arguments": {"type": "object"},
            },
            "required": ["connection_id", "tool_name", "arguments"],
        },
        state_schema={
            "fields": {
                "tool_result": {"type": "object"},
            }
        },
        output_schema={
            "type": "object",
            "properties": {"tool_result": {"type": "object"}},
            "required": ["tool_result"],
        },
        start="call_tool",
        nodes=[
            {
                "id": "call_tool",
                "type": "node",
                "node": "wf.mcp.call_tool",
                "in_map": {
                    "input.connection_id": "connection_id",
                    "input.tool_name": "tool_name",
                    "input.arguments": "arguments",
                },
                "out_map": {"output": "state.tool_result"},
            }
        ],
        edges=[
            {"from": "call_tool", "outcome": "ok", "to": END},
            {"from": "call_tool", "outcome": "error", "to": END},
        ],
    )

    run = asyncio.run(
        service.run_workflow_from_plan(
            plan,
            {
                "connection_id": "demo.personal",
                "tool_name": "echo_tool",
                "arguments": {"text": "hello"},
            },
        )
    )

    assert run.status == RunStatus.COMPLETED
    assert run.output["tool_result"]["echoed"] == "hello"


def test_service_can_inspect_resources_and_prompts() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "inspect_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    resources = service.list_resources(connection_id="demo.personal")
    prompts = service.list_prompts(connection_id="demo.personal")

    assert [resource.qualified_name for resource in resources] == [
        "demo.personal.resource.welcome"
    ]
    assert [prompt.qualified_name for prompt in prompts] == [
        "demo.personal.prompt.summarize"
    ]

    resource = service.get_resource("demo.personal.resource.welcome")
    prompt = service.get_prompt("demo.personal.prompt.summarize")

    assert resource.uri == "demo://docs/welcome"
    assert prompt.arguments[0]["name"] == "text"


def test_service_reports_connection_statuses() -> None:
    store = local_temp_root() / "status_store"
    # clear store before test
    shutil.rmtree(store)
    service = WfMcpService(store=FileStore(store))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    before = service.connection_statuses()
    assert before == [
        {
            "connection_id": "demo.personal",
            "server": "demo",
            "account": "personal",
            "enabled": True,
            "has_snapshot": False,
            "fetched_at_epoch_ms": None,
            "max_age_seconds": None,
            "node_count": 0,
            "resource_count": 0,
            "prompt_count": 0,
        }
    ]

    asyncio.run(service.refresh_connection_catalog("demo.personal"))
    after = service.connection_statuses()
    assert after[0]["has_snapshot"] is True
    assert after[0]["node_count"] == 1
    assert after[0]["resource_count"] == 1
    assert after[0]["prompt_count"] == 1


def test_service_can_proxy_resource_reads_and_prompt_gets() -> None:
    store = local_temp_root() / "proxy_store"
    # new store
    shutil.rmtree(store)
    service = WfMcpService(store=FileStore(store))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    asyncio.run(service.refresh_connection_catalog("demo.personal"))

    resource_result = asyncio.run(
        service.read_resource("demo.personal.resource.welcome")
    )
    prompt_result = asyncio.run(
        service.render_prompt(
            "demo.personal.prompt.summarize",
            arguments={"text": "hello world"},
        )
    )

    assert (
        resource_result["contents"][0]["text"]
        == "Welcome from the fake adapter resource."
    )
    assert (
        prompt_result["messages"][0]["content"]["text"]
        == "Summarize this text:\n\nhello world"
    )

    event_kinds = [event.kind for event in service.list_events()]
    assert "resource_read_started" in event_kinds
    assert "resource_read_completed" in event_kinds
    assert "prompt_get_started" in event_kinds
    assert "prompt_get_completed" in event_kinds


def test_service_can_invoke_raw_method_and_notification() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "raw_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    result = asyncio.run(
        service.invoke_method("demo.personal", "demo.echo", params={"text": "hello"})
    )
    asyncio.run(
        service.send_notification(
            "demo.personal",
            "notifications/progress",
            params={"progress": 1},
        )
    )

    assert result == {"echoed": "hello"}
    event_kinds = [event.kind for event in service.list_events()]
    assert "raw_method_started" in event_kinds
    assert "raw_method_completed" in event_kinds
    assert "raw_notification_started" in event_kinds
    assert "raw_notification_completed" in event_kinds


def test_service_can_call_upstream_tool_directly() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "direct_tool_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FakeAdapter())

    result = asyncio.run(
        service.call_tool(
            "demo.personal",
            "echo_tool",
            arguments={"text": "hello"},
        )
    )

    assert result == {
        "outcome": "ok",
        "output": {"echoed": "hello"},
        "meta": {},
    }
    event_kinds = [event.kind for event in service.list_events()]
    assert "tool_call_started" in event_kinds
    assert "tool_call_completed" in event_kinds


def test_service_records_catalog_refresh_failures() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "refresh_fail_store"))
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_adapter("demo", FailingDiscoveryAdapter())

    try:
        asyncio.run(service.refresh_connection_catalog("demo.personal"))
    except PermissionError as exc:
        assert str(exc) == "Access is denied"
    else:
        raise AssertionError("expected refresh to fail")

    failure_events = [
        event
        for event in service.list_events()
        if event.kind == "catalog_refresh_failed"
    ]
    assert len(failure_events) == 1
    assert failure_events[0].payload == {
        "error_type": "PermissionError",
        "error": "Access is denied",
    }


def test_error_payload_unwraps_exception_group() -> None:
    exc = ExceptionGroup("outer", [PermissionError("Access is denied")])
    assert error_payload(exc) == {
        "error_type": "PermissionError",
        "error": "Access is denied",
    }
