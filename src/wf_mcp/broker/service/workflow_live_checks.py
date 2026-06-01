"""MCP-adapter-owned live source diagnostics for deployment validation.

Static deployment validation only checks the last known source catalog.
This probe intentionally performs live upstream I/O, so MCP tools keep it
disabled by default and only run it when the caller asks for liveness.

This module owns the MCP-only imports to avoid a circular import:
handlers.py -> workflow_operation_context.py -> handlers.py
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import anyio
import httpx
from mcp.client.streamable_http import StreamableHTTPError
from mcp.shared.exceptions import McpError

from wf_artifacts import (
    DependencyDiagnostic,
    DiagnosticSeverity,
    WorkflowArtifact,
    WorkflowDeployment,
)

from .adapters import require_adapter
from .core import WfMcpService

LIVE_SOURCE_CHECK_TIMEOUT_SECONDS = 8.0
_LIVE_SOURCE_CHECK_FAILURES = (
    KeyError,
    TimeoutError,
    OSError,
    anyio.ClosedResourceError,
    anyio.EndOfStream,
    anyio.BrokenResourceError,
    httpx.HTTPError,
    McpError,
    StreamableHTTPError,
)


def _required_live_sources(
    deployment: WorkflowDeployment,
    artifacts: Sequence[WorkflowArtifact],
) -> dict[str, str]:
    """Return concrete upstream source ids to live-check, with one logical ref."""
    bindings = deployment.binding_map()
    required: dict[str, str] = {}
    for artifact in artifacts:
        for logical_ref, capability in artifact.required_capability_map().items():
            source_id = bindings.get(capability.logical_source)
            if source_id is not None:
                required.setdefault(source_id, logical_ref)
    return required


async def live_source_diagnostics(
    service: WfMcpService,
    *,
    deployment: WorkflowDeployment,
    artifacts: Sequence[WorkflowArtifact],
) -> list[DependencyDiagnostic]:
    """Return opt-in diagnostics for bound upstream sources that cannot answer.

    Static deployment validation only checks the last known source catalog.
    This probe intentionally performs live upstream I/O, so MCP tools keep it
    disabled by default and only run it when the caller asks for liveness.
    """
    diagnostics: list[DependencyDiagnostic] = []
    for source_id, logical_ref in _required_live_sources(deployment, artifacts).items():
        source = service.capability_sources.get(source_id)
        if (
            source is None
            or not source.enabled
            or not source.permissions.calls_upstream
        ):
            continue
        try:
            connection = service.connections.get(source_id)
            adapter = require_adapter(connection, service.adapters)
            auth = service.load_auth(source_id)
            await asyncio.wait_for(
                adapter.list_tools(connection, auth),
                timeout=LIVE_SOURCE_CHECK_TIMEOUT_SECONDS,
            )
        except _LIVE_SOURCE_CHECK_FAILURES as exc:
            diagnostics.append(
                DependencyDiagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    code="source_unreachable",
                    logical_ref=logical_ref,
                    bound_source=source_id,
                    message=(
                        f"Live check for upstream source {source_id!r} failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    repair_hint=(
                        "Start or reconnect the source, fix its transport/auth "
                        "configuration, or bind this deployment to another source."
                    ),
                )
            )
    return diagnostics


__all__ = [
    "LIVE_SOURCE_CHECK_TIMEOUT_SECONDS",
    "live_source_diagnostics",
]
