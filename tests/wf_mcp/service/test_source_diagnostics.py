from __future__ import annotations

from wf_mcp.broker.service.source_diagnostics import SourceDiagnosticsProvider
from wf_mcp.connections import ConnectionRegistry
from wf_mcp.models import ConnectionConfig
from wf_sources_mcp.auth import AuthRecord
from wf_sources_mcp.catalog import CatalogSnapshot
from wf_sources_mcp.storage import FileAuthStore, FileCatalogStore


def _connection(**metadata: object) -> ConnectionConfig:
    return ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        enabled=True,
        metadata={"transport": "http", "url": "https://example.test/mcp", **metadata},
    )


def _provider(tmp_path, connection: ConnectionConfig) -> SourceDiagnosticsProvider:
    registry = ConnectionRegistry()
    registry.register(connection)
    return SourceDiagnosticsProvider(
        connection_lookup=registry.get,
        auth_store=FileAuthStore(tmp_path / "auth"),
        catalog_store=FileCatalogStore(tmp_path / "catalog"),
    )


def test_source_diagnostics_reports_present_auth(tmp_path) -> None:
    connection = _connection(auth_ref="demo.creds")
    provider = _provider(tmp_path, connection)
    provider.auth_store.save_auth(
        AuthRecord(
            connection_id="demo.creds",
            scheme="oauth_refresh_token",
            payload={
                "client_id": "client",
                "client_secret": "secret",
                "refresh_token": "refresh",
                "token_url": "https://oauth2.example.test/token",
            },
        )
    )

    payload = provider.diagnose_source("demo.personal")

    assert payload["source_id"] == "demo.personal"
    assert payload["status"] == "ok"
    assert payload["auth"]["auth_ref"] == "demo.creds"
    assert payload["auth"]["record_present"] is True
    assert payload["auth"]["scheme"] == "oauth_refresh_token"
    assert payload["auth"]["transport_supported"] is True
    assert payload["diagnostics"] == []


def test_source_diagnostics_reports_missing_auth(tmp_path) -> None:
    payload = _provider(
        tmp_path,
        _connection(auth_ref="missing.creds"),
    ).diagnose_source("demo.personal")

    assert payload["status"] == "error"
    assert payload["auth"]["record_present"] is False
    assert payload["diagnostics"][0]["code"] == "auth_not_found"


def test_source_diagnostics_reports_missing_transport(tmp_path) -> None:
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        metadata={},
    )

    payload = _provider(tmp_path, connection).diagnose_source("demo.personal")

    assert payload["status"] == "error"
    assert payload["transport"]["configured"] is False
    assert payload["diagnostics"][0]["code"] == "source_transport_missing"


def test_source_diagnostics_reports_unsupported_transport_auth(tmp_path) -> None:
    connection = ConnectionConfig(
        id="demo.personal",
        server="demo",
        account="personal",
        metadata={"transport": "stdio", "command": "demo", "auth_ref": "demo.creds"},
    )
    provider = _provider(tmp_path, connection)
    provider.auth_store.save_auth(
        AuthRecord(
            connection_id="demo.creds",
            scheme="oauth_refresh_token",
            payload={
                "client_id": "client",
                "client_secret": "secret",
                "refresh_token": "refresh",
                "token_url": "https://oauth2.example.test/token",
            },
        )
    )

    payload = provider.diagnose_source("demo.personal")

    assert payload["status"] == "error"
    assert payload["auth"]["transport_supported"] is False
    assert payload["diagnostics"][0]["code"] == "auth_scheme_not_supported"


def test_source_diagnostics_reports_catalog_snapshot(tmp_path) -> None:
    provider = _provider(tmp_path, _connection())
    provider.catalog_store.save_catalog(
        CatalogSnapshot(
            connection_id="demo.personal",
            fetched_at_epoch_ms=123,
            max_age_seconds=60,
        )
    )

    payload = provider.diagnose_source("demo.personal")

    assert payload["catalog"] == {
        "has_snapshot": True,
        "fetched_at_epoch_ms": 123,
        "max_age_seconds": 60,
        "node_count": 0,
        "resource_count": 0,
        "prompt_count": 0,
    }
