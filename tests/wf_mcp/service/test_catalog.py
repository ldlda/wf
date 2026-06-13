from __future__ import annotations

import shutil
from pathlib import Path

from wf_authoring import NodeSpec
from wf_core import RunStatus
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.source_catalog import SourceCatalogService
from wf_mcp.models import CatalogSnapshot, ConnectionConfig
from wf_mcp.storage import FileCatalogStore, FileStore
from wf_platform import (
    CapabilityBuckets,
    CapabilitySource,
    DocumentationResource,
    SourceVisibility,
)

from ..test_support import (
    FakeAdapter,
    echo_tool,
    finalize_tool,
)
from .conftest import single_echo_plan


def test_service_builds_namespaced_catalog(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "catalog_store"))
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


def test_service_rejects_reserved_connection_ids(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "reserved_ids_store"))

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


def test_service_installs_builtin_stdlib_specs_by_default(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "builtin_store"))

    assert (
        "wf.std.runtime_error"
        in service.capability_sources["wf.std"].capabilities.node_specs
    )
    assert "wf.mcp" not in service.capability_sources


def test_service_does_not_install_workflow_stores_implicitly(tmp_path: Path) -> None:
    root = tmp_path / "service_no_implicit_workflow_stores"
    service = WfMcpService(store=FileStore(root))

    assert service.artifact_store is None
    assert service.draft_workspace_store is None
    assert service.run_store is None


def test_service_registers_empty_source_for_connection_without_catalog(
    tmp_path: Path,
) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "empty_source"))

    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    source = service.capability_sources["demo.personal"]
    assert source.enabled is True
    assert source.capabilities.node_specs == {}
    assert source.description == "No catalog loaded for demo.personal."


def test_service_lists_all_capability_sources_with_owned_capability_names(
    tmp_path: Path,
) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "source_inventory"))

    sources = service.list_sources()
    sources_by_id = {source["id"]: source for source in sources}

    std_source = sources_by_id["wf.std"]
    assert "wf.std.runtime_error" in std_source["capabilities"]["node_specs"]
    assert set(std_source["capabilities"]["reducers"]) == {
        "wf.std.append",
        "wf.std.max",
        "wf.std.merge_object",
        "wf.std.replace",
        "wf.std.set_union",
        "wf.std.add",
    }
    assert std_source["capabilities"]["tools"] == []
    assert std_source["reducer_count"] == 6

    admin_source = sources_by_id["wf.admin"]
    assert admin_source["visibility"]["planner"] is False
    assert "wf.admin.list_sources" in admin_source["capabilities"]["tools"]


def test_service_lists_compact_source_summaries(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "source_summaries"))

    payload = service.list_source_summaries(limit=1)

    assert len(payload["sources"]) == 1
    assert payload["total"] >= 2
    assert payload["next_cursor"] == "1"
    assert "capabilities" not in payload["sources"][0]

    full_page = service.list_source_summaries(limit=100)
    sources_by_id = {source["id"]: source for source in full_page["sources"]}
    std_source = sources_by_id["wf.std"]
    assert "wf.std.coalesce" in std_source["preview"]["node_specs"]
    assert std_source["has_more"]["node_specs"] is True


def test_wf_std_source_contains_authoring_ops(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "stdlib_source_store"))
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
        "wf.std.filter_items",
        "wf.std.filter_items_present",
        "wf.std.extract_field",
        "wf.std.concat",
    }
    assert set(specs) == expected


def test_wf_std_source_contains_builtin_reducers(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "stdlib_reducer_store"))
    reducers = service.capability_sources["wf.std"].capabilities.reducers

    assert set(reducers) == {
        "wf.std.replace",
        "wf.std.append",
        "wf.std.max",
        "wf.std.merge_object",
        "wf.std.set_union",
        "wf.std.add",
    }


def test_service_sources_have_visibility_and_capability_buckets(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "source_shape_store"))

    std_source = service.capability_sources["wf.std"]

    assert std_source.id == "wf.std"
    assert std_source.kind == "system"
    assert std_source.visibility.planner is True
    assert std_source.visibility.client is True
    assert std_source.visibility.admin_dashboard is True
    assert "wf.std.runtime_error" in std_source.capabilities.node_specs
    assert not std_source.capabilities.tools


def test_wf_recipes_source_contains_composed_capabilities(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "recipes_source_store"))
    specs = service.capability_sources["wf.recipes"].capabilities.node_specs

    assert set(specs) == {"wf.recipes.extract_text_content"}
    assert (
        service.capability_sources["wf.recipes"].permissions.safe_for_workflow is True
    )


def test_wf_admin_source_exists_but_is_not_planner_visible(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "admin_source_store"))
    source = service.capability_sources["wf.admin"]

    assert source.kind == "system"
    assert source.visibility.planner is False
    assert source.visibility.client is False
    assert source.visibility.admin_dashboard is True
    assert source.permissions.safe_for_workflow is False
    assert source.permissions.calls_upstream is False
    assert source.permissions.mutates_config is True
    assert source.permissions.mutates_auth is True
    assert "wf.admin.list_sources" in source.capabilities.tools
    assert "wf.admin.disable_source" in source.capabilities.tools
    assert "wf.admin.enable_source" in source.capabilities.tools
    assert "wf.admin" not in service.get_planner_catalog().snapshots


def test_service_can_disable_builtin_stdlib_specs(tmp_path: Path) -> None:
    service = WfMcpService(
        store=FileStore(tmp_path / "no_builtin_store"),
        include_builtin_specs=False,
    )

    assert "wf.std" not in service.capability_sources
    assert "wf.recipes" not in service.capability_sources


def test_service_planner_catalog_excludes_hidden_sources(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "hidden_list_store"))
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


def test_service_catalog_split_keeps_system_specs_out_of_backend_catalog(
    tmp_path: Path,
) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "planner_store"))

    backend_payload = service.get_catalog().as_payload()
    planner_payload = service.get_planner_catalog().as_payload()

    assert backend_payload["nodes"] == []
    planner_node_names = {node["qualified_name"] for node in planner_payload["nodes"]}
    assert "wf.std.runtime_error" in planner_node_names
    available_names = {entry.qualified_name for entry in service.list_available_specs()}
    assert "wf.std.runtime_error" in available_names


async def test_service_hydrates_planner_specs_from_stored_catalog(
    tmp_path: Path,
) -> None:
    store = tmp_path / "restart_planner_store"
    shutil.rmtree(store, ignore_errors=True)
    first_service = WfMcpService(store=FileStore(store))
    first_service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    first_service.register_adapter("demo", FakeAdapter())
    await first_service.refresh_connection_catalog("demo.personal")

    second_service = WfMcpService(store=FileStore(store))
    second_service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    second_service.register_adapter("demo", FakeAdapter())

    planner_names = {
        node["qualified_name"]
        for node in second_service.get_planner_catalog().as_payload()["nodes"]
    }
    run = await second_service.run_workflow_from_plan(
        single_echo_plan("hydrated_plan", "demo.personal.echo_tool"),
        {"text": "hello"},
    )

    assert "demo.personal.echo_tool" in planner_names
    assert run.status == RunStatus.COMPLETED
    assert run.output["echoed"] == "hello"


def test_source_catalog_service_registers_and_lists_sources_directly(
    tmp_path: Path,
) -> None:
    store = FileStore(tmp_path / "source_catalog_direct")

    def unused_tool_executor(connection: ConnectionConfig):
        raise AssertionError("tool executor should not be used by source listing")

    catalog = SourceCatalogService(
        store=store,
        connection_lookup=lambda connection_id: ConnectionConfig(
            id=connection_id,
            server="demo",
            account="personal",
        ),
        connection_list_enabled=lambda: [],
        connection_list_all=lambda: [],
        tool_executor_for=unused_tool_executor,
        load_auth=lambda connection_id: None,
        emit_event=lambda event: None,
    )

    catalog.register_capability_source(
        CapabilitySource(
            id="demo.personal",
            kind="connection",
            capabilities=CapabilityBuckets(),
            visibility=SourceVisibility(planner=True),
        )
    )

    payload = catalog.list_source_summaries(limit=10)

    assert payload["total"] == 1
    assert payload["sources"][0]["id"] == "demo.personal"


def test_wfmcpservice_capability_sources_proxy_source_catalog(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "source_catalog_proxy"))

    assert service.capability_sources is service.source_catalog.capability_sources
    assert "wf.std" in service.source_catalog.capability_sources


def test_source_catalog_service_excludes_hidden_sources_from_planner_catalog(
    tmp_path: Path,
) -> None:
    def unused_tool_executor(connection: ConnectionConfig):
        raise AssertionError("tool executor should not be used by planner listing")

    catalog = SourceCatalogService(
        store=FileStore(tmp_path / "source_catalog_hidden"),
        connection_lookup=lambda connection_id: ConnectionConfig(
            id=connection_id,
            server="demo",
            account="personal",
        ),
        connection_list_enabled=lambda: [],
        connection_list_all=lambda: [],
        tool_executor_for=unused_tool_executor,
        load_auth=lambda connection_id: None,
        emit_event=lambda event: None,
    )
    visible_tool = NodeSpec(
        name="visible.source.echo_tool",
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
    hidden_tool = NodeSpec(
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
    catalog.register_capability_source(
        CapabilitySource(
            id="visible.source",
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs={"visible.source.echo_tool": visible_tool}
            ),
            visibility=SourceVisibility(planner=True),
        )
    )
    catalog.register_capability_source(
        CapabilitySource(
            id="hidden.source",
            kind="system",
            capabilities=CapabilityBuckets(
                node_specs={"hidden.source.echo_tool": hidden_tool}
            ),
            visibility=SourceVisibility(planner=False, admin_dashboard=False),
        )
    )

    planner_names = {
        entry.qualified_name for entry in catalog.get_planner_catalog().entries()
    }

    assert "visible.source.echo_tool" in planner_names
    assert "hidden.source.echo_tool" not in planner_names


async def test_source_catalog_hydrates_connection_source_from_snapshot_directly(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source_catalog_hydrate_direct"
    shutil.rmtree(root, ignore_errors=True)
    first_service = WfMcpService(store=FileStore(root))
    first_service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    first_service.register_adapter("demo", FakeAdapter())
    await first_service.refresh_connection_catalog("demo.personal")

    second_service = WfMcpService(store=FileStore(root))
    second_service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )

    specs = second_service.source_catalog.capability_sources[
        "demo.personal"
    ].capabilities.node_specs

    assert "demo.personal.echo_tool" in specs


def test_source_catalog_register_specs_replaces_discovered_specs_directly(
    tmp_path: Path,
) -> None:
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
    )

    def unused_tool_executor(connection: ConnectionConfig):
        raise AssertionError("tool executor should not be used by spec registration")

    catalog = SourceCatalogService(
        store=FileStore(tmp_path / "source_catalog_register_specs"),
        connection_lookup=lambda connection_id: connection,
        connection_list_enabled=lambda: [connection],
        connection_list_all=lambda: [connection],
        tool_executor_for=unused_tool_executor,
        load_auth=lambda connection_id: None,
        emit_event=lambda event: None,
    )

    catalog.register_capability_source(
        CapabilitySource(
            id="demo.personal",
            kind="connection",
            capabilities=CapabilityBuckets(
                node_specs={"demo.personal.finalize_tool": finalize_tool}
            ),
            visibility=SourceVisibility(planner=True),
        )
    )
    assert "demo.personal.finalize_tool" in (
        catalog.capability_sources["demo.personal"].capabilities.node_specs
    )

    catalog.register_specs("demo.personal", echo_tool)

    specs = catalog.capability_sources["demo.personal"].capabilities.node_specs

    assert set(specs) == {"demo.personal.echo_tool"}
    assert catalog.store.load_catalog("demo.personal") is not None


def test_source_catalog_finds_local_documentation_resource_directly(
    tmp_path: Path,
) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "source_local_docs"))
    test_resource = DocumentationResource(
        name="test.docs.example",
        uri="wf://docs/example",
        title="Example Doc",
        description="Test documentation resource.",
        mime_type="text/markdown",
        text="# Example",
    )
    service.register_capability_source(
        CapabilitySource(
            id="test.docs",
            kind="system",
            capabilities=CapabilityBuckets(
                resources={"test.docs.example": test_resource}
            ),
            visibility=SourceVisibility(planner=True),
        )
    )

    result = service.source_catalog.local_documentation_resource("test.docs.example")

    assert result is not None
    assert result.uri == test_resource.uri


def test_broker_local_sources_are_platform_sources(tmp_path: Path) -> None:
    service = WfMcpService(store=FileStore(tmp_path / "platform_sources"))

    wf_recipes = service.capability_sources["wf.recipes"]

    assert wf_recipes.policy.platform is True
    assert wf_recipes.policy.binding_required is False


def test_source_catalog_uses_catalog_store_only(tmp_path: Path) -> None:
    catalog_store = FileCatalogStore(tmp_path / "catalog")
    service = SourceCatalogService(
        store=catalog_store,
        connection_lookup=lambda connection_id: ConnectionConfig(
            id=connection_id,
            server="demo",
            account="personal",
        ),
        connection_list_enabled=lambda: [],
        connection_list_all=lambda: [],
        tool_executor_for=lambda connection: (_ for _ in ()).throw(
            AssertionError("unexpected executor")
        ),
        load_auth=lambda connection: None,
        emit_event=lambda event: None,
    )
    snapshot = CatalogSnapshot(
        connection_id="demo.personal",
        fetched_at_epoch_ms=1,
        max_age_seconds=300,
        nodes=[],
        resources=[],
        prompts=[],
        metadata={},
    )
    service.store.save_catalog(snapshot)

    assert service.store.load_catalog("demo.personal") == snapshot
    assert (tmp_path / "catalog" / "catalog" / "demo.personal.json").exists()
