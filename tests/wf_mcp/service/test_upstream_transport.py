from __future__ import annotations

from pathlib import Path

from wf_artifacts import WorkflowDeployment
from wf_mcp.broker import WfMcpService
from wf_mcp.broker.service.source_catalog import SourceCatalogService
from wf_mcp.broker.service.upstream_transport import UpstreamTransportService
from wf_mcp.connections import ConnectionRegistry
from wf_mcp.events import McpEvent
from wf_mcp.models import AuthRecord, CatalogSnapshot, ConnectionConfig
from wf_mcp.storage import FileAuthStore, FileCatalogStore, FileStore
from wf_platform import CapabilityBuckets, CapabilitySource, SourcePermissions

from ..test_support import FakeAdapter, local_temp_root
from ..workflow_surface.conftest import echo_artifact


def _fake_transport_metadata() -> dict[str, object]:
    return {"transport": "stdio", "command": "fake-mcp-server"}


def _transport(root: Path) -> UpstreamTransportService:
    events: list[McpEvent] = []
    return UpstreamTransportService(
        auth_store=FileStore(root),
        catalog_store=FileStore(root),
        event_sink=events.append,
    )


def test_upstream_transport_registers_adapter() -> None:
    events: list[McpEvent] = []
    transport = UpstreamTransportService(
        auth_store=FileStore(local_temp_root() / "upstream_adapter"),
        catalog_store=FileStore(local_temp_root() / "upstream_adapter"),
        event_sink=events.append,
    )
    adapter = FakeAdapter()

    transport.register_adapter("demo", adapter)

    assert transport.adapters["demo"] is adapter


def test_upstream_transport_saves_and_loads_auth_with_event() -> None:
    events: list[McpEvent] = []
    transport = UpstreamTransportService(
        auth_store=FileStore(local_temp_root() / "upstream_auth"),
        catalog_store=FileStore(local_temp_root() / "upstream_auth"),
        event_sink=events.append,
    )
    record = AuthRecord(connection_id="demo.personal", scheme="bearer")

    transport.save_auth(record)
    loaded = transport.load_auth("demo.personal")

    assert loaded is not None
    assert loaded.connection_id == "demo.personal"
    assert events[-1].kind == "auth_saved"
    assert events[-1].connection_id == "demo.personal"


def test_wfmcpservice_uses_upstream_transport_for_adapters_and_auth() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "service_upstream"))
    adapter = FakeAdapter()

    service.register_adapter("demo", adapter)
    service.save_auth(AuthRecord(connection_id="demo.personal", scheme="bearer"))

    assert service.upstream.adapters["demo"] is adapter
    assert service.adapters is service.upstream.adapters
    assert service.load_auth("demo.personal") is not None
    assert service.list_events()[-1].kind == "auth_saved"


async def test_upstream_transport_invokes_raw_method_and_records_events() -> None:
    events: list[McpEvent] = []
    connections = ConnectionRegistry()
    connections.register(
        ConnectionConfig(
            id="demo.personal",
            server="demo",
            account="personal",
            metadata=_fake_transport_metadata(),
        )
    )
    transport = UpstreamTransportService(
        auth_store=FileStore(local_temp_root() / "upstream_raw_method"),
        catalog_store=FileStore(local_temp_root() / "upstream_raw_method"),
        event_sink=events.append,
    )
    transport.register_adapter("demo", FakeAdapter())

    result = await transport.invoke_method(
        connections.get("demo.personal"),
        "demo.echo",
        params={"text": "hello"},
    )

    assert result["echoed"] == "hello"
    assert [event.kind for event in events] == [
        "raw_method_started",
        "raw_method_completed",
    ]


async def test_upstream_transport_refreshes_catalog_directly() -> None:
    events: list[McpEvent] = []
    store = FileStore(local_temp_root() / "upstream_refresh")
    connections = ConnectionRegistry()
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        metadata=_fake_transport_metadata(),
    )
    connections.register(connection)
    transport = UpstreamTransportService(
        auth_store=store,
        catalog_store=store,
        event_sink=events.append,
    )
    transport.register_adapter("demo", FakeAdapter())
    source_catalog = SourceCatalogService(
        store=store,
        connection_lookup=connections.get,
        connection_list_enabled=connections.list_enabled,
        connection_list_all=connections.list_all,
        tool_executor_for=transport.tool_executor_for,
        load_auth=transport.load_connection_auth,
        emit_event=events.append,
    )
    source_catalog.hydrate_connection_source_from_snapshot(connection)

    await transport.refresh_connection_catalog(
        connection,
        source_catalog=source_catalog,
        record_catalog_change_events=lambda source_id, snapshot, reason: None,
    )

    snapshot = store.load_catalog("demo.personal")
    assert snapshot is not None
    assert len(snapshot.nodes) >= 1
    assert "catalog_refresh_started" in [event.kind for event in events]
    assert "catalog_refresh_completed" in [event.kind for event in events]


async def test_upstream_transport_live_diagnostics_report_missing_connection() -> None:
    transport = UpstreamTransportService(
        auth_store=FileStore(local_temp_root() / "upstream_live_missing"),
        catalog_store=FileStore(local_temp_root() / "upstream_live_missing"),
        event_sink=lambda event: None,
    )

    def _raise_missing_connection(connection_id: str) -> ConnectionConfig:
        raise KeyError(connection_id)

    source_catalog = SourceCatalogService(
        store=transport.catalog_store,
        connection_lookup=_raise_missing_connection,
        connection_list_enabled=lambda: [],
        connection_list_all=lambda: [],
        tool_executor_for=transport.tool_executor_for,
        load_auth=transport.load_connection_auth,
        emit_event=lambda event: None,
    )
    source_catalog.register_capability_source(
        CapabilitySource(
            id="demo.personal",
            kind="connection",
            permissions=SourcePermissions(calls_upstream=True),
            capabilities=CapabilityBuckets(),
        )
    )
    artifact = echo_artifact()
    deployment = WorkflowDeployment(
        id="echo.personal",
        artifact_id="echo",
        artifact_version=1,
        bindings=[{"logical_source": "demo", "concrete_source": "demo.personal"}],
    )

    diagnostics = await transport.deployment_diagnostics(
        deployment=deployment,
        artifacts=[artifact],
        source_catalog=source_catalog,
    )

    assert diagnostics[0].code == "source_unreachable"
    assert diagnostics[0].bound_source == "demo.personal"


def test_upstream_load_connection_auth_prefers_auth_ref(tmp_path: Path) -> None:
    service = _transport(tmp_path)
    service.save_auth(
        AuthRecord(
            connection_id="github.creds",
            scheme="bearer",
            payload={"token": "secret"},
        )
    )
    service.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "wrong"},
        )
    )
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={**_fake_transport_metadata(), "auth_ref": "github.creds"},
    )

    assert service.load_connection_auth(connection) == AuthRecord(
        connection_id="github.creds",
        scheme="bearer",
        payload={"token": "secret"},
    )


def test_upstream_load_connection_auth_falls_back_to_connection_id(
    tmp_path: Path,
) -> None:
    service = _transport(tmp_path)
    service.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "legacy"},
        )
    )
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
    )

    assert service.load_connection_auth(connection) == AuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={"token": "legacy"},
    )


def test_upstream_load_connection_auth_ignores_non_string_auth_ref(
    tmp_path: Path,
) -> None:
    service = _transport(tmp_path)
    service.save_auth(
        AuthRecord(
            connection_id="github.work",
            scheme="bearer",
            payload={"token": "legacy"},
        )
    )
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={"auth_ref": 123},
    )

    assert service.load_connection_auth(connection) == AuthRecord(
        connection_id="github.work",
        scheme="bearer",
        payload={"token": "legacy"},
    )


async def test_upstream_transport_live_diagnostics_report_missing_auth_ref(
    tmp_path: Path,
) -> None:
    events: list[McpEvent] = []
    store = FileStore(tmp_path)
    connections = ConnectionRegistry()
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={**_fake_transport_metadata(), "auth_ref": "github.creds"},
    )
    connections.register(connection)
    transport = UpstreamTransportService(
        auth_store=store,
        catalog_store=store,
        event_sink=events.append,
    )
    transport.register_adapter("demo", FakeAdapter())
    source_catalog = SourceCatalogService(
        store=store,
        connection_lookup=connections.get,
        connection_list_enabled=connections.list_enabled,
        connection_list_all=connections.list_all,
        tool_executor_for=transport.tool_executor_for,
        load_auth=transport.load_connection_auth,
        emit_event=events.append,
    )
    source_catalog.register_capability_source(
        CapabilitySource(
            id="github.work",
            kind="connection",
            permissions=SourcePermissions(calls_upstream=True),
            capabilities=CapabilityBuckets(),
        )
    )
    artifact = echo_artifact()
    deployment = WorkflowDeployment(
        id="echo.personal",
        artifact_id="echo",
        artifact_version=1,
        bindings=[{"logical_source": "demo", "concrete_source": "github.work"}],
    )

    diagnostics = await transport.deployment_diagnostics(
        deployment=deployment,
        artifacts=[artifact],
        source_catalog=source_catalog,
    )

    assert diagnostics[0].code == "auth_not_found"
    assert diagnostics[0].bound_source == "github.work"
    assert "github.creds" in diagnostics[0].message


def test_upstream_transport_uses_separate_auth_and_catalog_stores(
    tmp_path: Path,
) -> None:
    auth_store = FileAuthStore(tmp_path / "auth")
    catalog_store = FileCatalogStore(tmp_path / "catalog")
    events = []
    transport = UpstreamTransportService(
        auth_store=auth_store,
        catalog_store=catalog_store,
        event_sink=events.append,
    )
    record = AuthRecord(connection_id="demo.personal", scheme="bearer")
    transport.save_auth(record)
    snapshot = CatalogSnapshot(
        connection_id="demo.personal",
        fetched_at_epoch_ms=1,
        max_age_seconds=300,
        nodes=[],
        resources=[],
        prompts=[],
        metadata={},
    )
    transport.catalog_store.save_catalog(snapshot)

    assert (tmp_path / "auth" / "auth" / "demo.personal.json").exists()
    assert (tmp_path / "catalog" / "catalog" / "demo.personal.json").exists()


class _StatefulRuntime:
    def __init__(self) -> None:
        self.resources: list[tuple[str, str]] = []
        self.prompts: list[tuple[str, str, dict[str, str] | None]] = []

    async def call_tool(self, connection, auth, tool_name, payload):
        raise AssertionError("not used by these tests")

    async def read_resource(self, connection, auth, uri: str):
        self.resources.append((connection.id, uri))
        return {"contents": [{"uri": uri, "text": "stateful resource"}]}

    async def get_prompt(
        self,
        connection,
        auth,
        prompt_name: str,
        arguments: dict[str, str] | None = None,
    ):
        self.prompts.append((connection.id, prompt_name, arguments))
        return {
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": "stateful prompt"},
                }
            ]
        }


class _ExplodingContentAdapter(FakeAdapter):
    async def read_resource(self, connection, auth, uri):
        raise AssertionError("adapter read_resource should not be used")

    async def get_prompt(self, connection, auth, prompt_name, arguments=None):
        raise AssertionError("adapter get_prompt should not be used")


async def test_upstream_transport_prefers_stateful_runtime_for_resource_reads(
    tmp_path: Path,
) -> None:
    events: list[McpEvent] = []
    runtime = _StatefulRuntime()
    transport = UpstreamTransportService(
        auth_store=FileStore(tmp_path),
        catalog_store=FileStore(tmp_path),
        event_sink=events.append,
        stateful_runtime=runtime,
    )
    transport.register_adapter("demo", _ExplodingContentAdapter())
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        metadata=_fake_transport_metadata(),
    )

    result = await transport.read_resource(
        connection,
        "demo.personal.resource.welcome",
        "fixture://docs/welcome",
    )

    assert result["contents"][0]["text"] == "stateful resource"
    assert runtime.resources == [("demo.personal", "fixture://docs/welcome")]
    assert [event.kind for event in events] == [
        "resource_read_started",
        "resource_read_completed",
    ]


async def test_upstream_transport_prefers_stateful_runtime_for_prompts(
    tmp_path: Path,
) -> None:
    events: list[McpEvent] = []
    runtime = _StatefulRuntime()
    transport = UpstreamTransportService(
        auth_store=FileStore(tmp_path),
        catalog_store=FileStore(tmp_path),
        event_sink=events.append,
        stateful_runtime=runtime,
    )
    transport.register_adapter("demo", _ExplodingContentAdapter())
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        metadata=_fake_transport_metadata(),
    )

    result = await transport.render_prompt(
        connection,
        "demo.personal.prompt.summarize",
        "prompt.summarize",
        {"text": "hello"},
    )

    assert result["messages"][0]["content"]["text"] == "stateful prompt"
    assert runtime.prompts == [
        ("demo.personal", "prompt.summarize", {"text": "hello"})
    ]
    assert [event.kind for event in events] == [
        "prompt_get_started",
        "prompt_get_completed",
    ]
