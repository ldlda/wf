from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from wf_artifacts import DependencyDiagnostic, DiagnosticSeverity
from wf_sources_mcp.storage import AuthStore, CatalogStore

from ...models import ConnectionConfig

ConnectionLookup = Callable[[str], ConnectionConfig]


def _auth_ref(connection: ConnectionConfig) -> str | None:
    value = connection.metadata.get("auth_ref")
    return value if isinstance(value, str) and value else None


def _transport_kind(connection: ConnectionConfig) -> str | None:
    value = connection.metadata.get("transport")
    return value if isinstance(value, str) and value else None


def _auth_scheme_supported(
    *,
    transport_kind: str | None,
    scheme: str | None,
) -> bool:
    if scheme is None:
        return True
    if transport_kind == "stdio":
        return scheme == "env"
    if transport_kind == "http":
        return scheme in {"bearer", "headers", "oauth_refresh_token"}
    return False


def _unsupported_auth_diagnostic(
    *,
    source_id: str,
    auth_ref: str,
    scheme: str,
    transport_kind: str | None,
) -> dict[str, Any]:
    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="auth_scheme_not_supported",
        logical_ref=auth_ref,
        bound_source=source_id,
        message=(
            f"Source {source_id!r} uses {transport_kind or 'unknown'} transport, "
            f"but auth record {auth_ref!r} has unsupported scheme {scheme!r}."
        ),
        repair_hint=(
            "Use env auth for stdio MCP sources, or bearer/headers/"
            "oauth_refresh_token auth for HTTP MCP sources."
        ),
    ).model_dump(mode="json")


def _missing_auth_diagnostic(
    *,
    source_id: str,
    auth_ref: str,
) -> dict[str, Any]:
    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="auth_not_found",
        logical_ref=auth_ref,
        bound_source=source_id,
        message=(
            f"Source {source_id!r} references auth record {auth_ref!r}, "
            "but no auth record was found."
        ),
        repair_hint=(
            "Add an auth record for this auth_ref, update the source auth_ref, "
            "or bind the deployment to a source that does not require it."
        ),
    ).model_dump(mode="json")


def _missing_transport_diagnostic(*, source_id: str) -> dict[str, Any]:
    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="source_transport_missing",
        logical_ref=source_id,
        bound_source=source_id,
        message=f"Source {source_id!r} has no MCP transport configured.",
        repair_hint=(
            "Configure the source with an MCP transport such as stdio or http, "
            "then apply or restart the server."
        ),
    ).model_dump(mode="json")


@dataclass(slots=True)
class SourceDiagnosticsProvider:
    """MCP broker diagnostics for source auth, transport, and catalog state."""

    connection_lookup: ConnectionLookup
    auth_store: AuthStore
    catalog_store: CatalogStore

    def diagnose_source(self, source_id: str) -> dict[str, Any]:
        connection = self.connection_lookup(source_id)
        auth_ref = _auth_ref(connection)
        auth = self.auth_store.load_auth(auth_ref) if auth_ref else None
        transport_kind = _transport_kind(connection)
        snapshot = self.catalog_store.load_catalog(source_id)
        diagnostics: list[dict[str, Any]] = []

        if transport_kind is None:
            diagnostics.append(_missing_transport_diagnostic(source_id=source_id))
        if auth_ref is not None and auth is None:
            diagnostics.append(
                _missing_auth_diagnostic(source_id=source_id, auth_ref=auth_ref)
            )

        transport_supported = _auth_scheme_supported(
            transport_kind=transport_kind,
            scheme=None if auth is None else auth.scheme,
        )
        if auth_ref and auth is not None and not transport_supported:
            diagnostics.append(
                _unsupported_auth_diagnostic(
                    source_id=source_id,
                    auth_ref=auth_ref,
                    scheme=auth.scheme,
                    transport_kind=transport_kind,
                )
            )

        return {
            "source_id": source_id,
            "status": "error" if diagnostics else "ok",
            "enabled": connection.enabled,
            "transport": {
                "kind": transport_kind,
                "configured": transport_kind is not None,
            },
            "auth": {
                "auth_ref": auth_ref,
                "record_present": auth is not None if auth_ref else None,
                "scheme": None if auth is None else auth.scheme,
                "transport_supported": transport_supported,
            },
            "catalog": {
                "has_snapshot": snapshot is not None,
                "fetched_at_epoch_ms": None
                if snapshot is None
                else snapshot.fetched_at_epoch_ms,
                "max_age_seconds": None if snapshot is None else snapshot.max_age_seconds,
                "node_count": 0 if snapshot is None else len(snapshot.nodes),
                "resource_count": 0 if snapshot is None else len(snapshot.resources),
                "prompt_count": 0 if snapshot is None else len(snapshot.prompts),
            },
            "diagnostics": diagnostics,
        }
