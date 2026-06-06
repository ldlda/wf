# Auth Diagnostics Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface missing auth references as explicit diagnostics in live source checks and source-registry apply summaries.

**Architecture:** Keep auth diagnostics MCP-provider-specific for now because current source/runtime auth resolution is implemented in `wf_mcp`. Add a small helper in `wf_mcp.auth` that inspects a `ConnectionConfig` and an auth lookup function, then reuse it from `UpstreamTransportService.deployment_diagnostics()` and `SourceRegistryAdminProvider.apply_registry_changes()`. Do not add auth admin CRUD, do not change auth storage, and do not make `wf_api` understand MCP credential payloads.

**Tech Stack:** Python 3.14, dataclasses, pytest, ruff, basedpyright.

---

## Scope

Implement only:

- `auth_not_found` diagnostic helper for connections with string `metadata["auth_ref"]`.
- live source diagnostics before upstream liveness probe.
- source registry apply summary field: `auth_diagnostics`.
- docs status update.

Do not implement:

- auth admin list/save/delete commands
- deployment static validation changes
- OAuth/secret-manager behavior
- source registry mutation rejection on missing auth
- any neutral `wf_api` diagnostic model changes

## Files

- Modify: `src/wf_mcp/auth.py`
  - add `auth_ref_for_connection`
  - add `auth_missing_diagnostic`
  - add `connection_auth_diagnostic`
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
  - use helper in `deployment_diagnostics`
- Modify: `src/wf_mcp/broker/service/source_registry_admin.py`
  - accept optional auth loader
  - return `auth_diagnostics` from `apply_registry_changes`
- Modify: `src/wf_mcp/broker/server.py`
  - wire source-registry admin provider to upstream auth loader if needed
- Test: `tests/wf_mcp/test_auth.py`
  - helper tests
- Test: `tests/wf_mcp/service/test_upstream_transport.py`
  - live diagnostic for missing `auth_ref`
- Test: `tests/wf_mcp/service/test_source_registry_admin.py`
  - apply summary includes auth diagnostics
- Docs: `docs/current_roadmap.md`
- Docs: `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`

## Task 1: MCP auth diagnostic helper

**Files:**
- Modify: `src/wf_mcp/auth.py`
- Modify: `tests/wf_mcp/test_auth.py`

- [ ] **Step 1: Add helper tests**

Append to `tests/wf_mcp/test_auth.py`:

```python
from wf_artifacts import DiagnosticSeverity
from wf_mcp.auth import (
    auth_ref_for_connection,
    connection_auth_diagnostic,
)
from wf_mcp.models import ConnectionConfig


def test_auth_ref_for_connection_returns_string_only() -> None:
    assert (
        auth_ref_for_connection(
            ConnectionConfig(
                id="github.work",
                server="github",
                account="work",
                metadata={"auth_ref": "github.creds"},
            )
        )
        == "github.creds"
    )
    assert (
        auth_ref_for_connection(
            ConnectionConfig(
                id="github.work",
                server="github",
                account="work",
                metadata={"auth_ref": 123},
            )
        )
        is None
    )


def test_connection_auth_diagnostic_reports_missing_auth_ref() -> None:
    connection = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={"auth_ref": "github.creds"},
    )

    diagnostic = connection_auth_diagnostic(
        connection,
        load_auth=lambda auth_ref: None,
        logical_ref="github",
    )

    assert diagnostic is not None
    assert diagnostic.severity == DiagnosticSeverity.ERROR
    assert diagnostic.code == "auth_not_found"
    assert diagnostic.logical_ref == "github"
    assert diagnostic.bound_source == "github.work"
    assert "github.creds" in diagnostic.message
    assert "Add an auth record" in diagnostic.repair_hint


def test_connection_auth_diagnostic_ignores_absent_or_present_auth_ref() -> None:
    no_ref = ConnectionConfig(id="github.work", server="github", account="work")
    with_ref = ConnectionConfig(
        id="github.work",
        server="github",
        account="work",
        metadata={"auth_ref": "github.creds"},
    )
    auth = McpAuthRecord(
        connection_id="github.creds",
        scheme="bearer",
        payload={"token": "secret"},
    )

    assert (
        connection_auth_diagnostic(
            no_ref,
            load_auth=lambda auth_ref: None,
            logical_ref="github",
        )
        is None
    )
    assert (
        connection_auth_diagnostic(
            with_ref,
            load_auth=lambda auth_ref: auth,
            logical_ref="github",
        )
        is None
    )
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/test_auth.py -q
```

Expected: fails because `auth_ref_for_connection` and `connection_auth_diagnostic` do not exist.

- [ ] **Step 3: Implement helper functions**

Modify `src/wf_mcp/auth.py`.

Add imports:

```python
from collections.abc import Callable

from wf_artifacts import DependencyDiagnostic, DiagnosticSeverity

from .models import ConnectionConfig
```

Add functions before `__all__`:

```python
def auth_ref_for_connection(connection: ConnectionConfig) -> str | None:
    """Return the explicit auth ref for one source connection, if present."""

    auth_ref = connection.metadata.get("auth_ref")
    return auth_ref if isinstance(auth_ref, str) else None


def auth_missing_diagnostic(
    *,
    auth_ref: str,
    source_id: str,
    logical_ref: str | None = None,
) -> DependencyDiagnostic:
    """Build a stable diagnostic without including secret payload data."""

    return DependencyDiagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="auth_not_found",
        logical_ref=logical_ref,
        bound_source=source_id,
        message=(
            f"Source {source_id!r} references auth record {auth_ref!r}, "
            "but no auth record was found."
        ),
        repair_hint=(
            "Add an auth record for this auth_ref, update the source auth_ref, "
            "or bind the deployment to a source that does not require it."
        ),
    )


def connection_auth_diagnostic(
    connection: ConnectionConfig,
    *,
    load_auth: Callable[[str], McpAuthRecord | None],
    logical_ref: str | None = None,
) -> DependencyDiagnostic | None:
    """Return an auth diagnostic for explicit auth_ref misses.

    Connections without explicit auth_ref keep legacy no-auth behavior. This
    makes the new auth boundary observable without treating every unauthenticated
    MCP source as an error.
    """

    auth_ref = auth_ref_for_connection(connection)
    if auth_ref is None:
        return None
    if load_auth(auth_ref) is not None:
        return None
    return auth_missing_diagnostic(
        auth_ref=auth_ref,
        source_id=connection.id,
        logical_ref=logical_ref,
    )
```

Add to `__all__`:

```python
"auth_missing_diagnostic",
"auth_ref_for_connection",
"connection_auth_diagnostic",
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/test_auth.py -q
uv run ruff check src/wf_mcp/auth.py tests/wf_mcp/test_auth.py
uv run basedpyright --level error src/wf_mcp/auth.py tests/wf_mcp/test_auth.py
```

Expected: all pass.

## Task 2: Live source auth diagnostics

**Files:**
- Modify: `src/wf_mcp/broker/service/upstream_transport.py`
- Modify: `tests/wf_mcp/service/test_upstream_transport.py`

- [ ] **Step 1: Add live diagnostic test**

Append to `tests/wf_mcp/service/test_upstream_transport.py`:

```python
async def test_upstream_transport_live_diagnostics_report_missing_auth_ref(
    tmp_path: Path,
) -> None:
    events: list[McpEvent] = []
    store = FileStore(tmp_path)
    connections = ConnectionRegistry()
    connection = ConnectionConfig(
        id="github.work",
        server="demo",
        account="work",
        metadata={"auth_ref": "github.creds"},
    )
    connections.register(connection)
    transport = UpstreamTransportService(store=store, event_sink=events.append)
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
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py::test_upstream_transport_live_diagnostics_report_missing_auth_ref -q
```

Expected: fails because live diagnostics currently probe with `auth=None` instead of reporting `auth_not_found`.

- [ ] **Step 3: Add diagnostic before liveness probe**

Modify `src/wf_mcp/broker/service/upstream_transport.py`.

Add import:

```python
from wf_mcp.auth import connection_auth_diagnostic
```

Inside `deployment_diagnostics`, after `connection = source_catalog.connection_lookup(source_id)` succeeds and before `adapter = require_adapter(...)`, add:

```python
                auth_diagnostic = connection_auth_diagnostic(
                    connection,
                    load_auth=self.load_auth,
                    logical_ref=logical_ref,
                )
                if auth_diagnostic is not None:
                    diagnostics.append(auth_diagnostic)
                    continue
```

Use `self.load_auth` here intentionally: it loads by auth ref. Do not use
`load_connection_auth`, because that would convert a missing explicit auth ref
into `None` and lose the diagnostic reason.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_upstream_transport.py -q
uv run ruff check src/wf_mcp/broker/service/upstream_transport.py tests/wf_mcp/service/test_upstream_transport.py
uv run basedpyright --level error src/wf_mcp/broker/service/upstream_transport.py tests/wf_mcp/service/test_upstream_transport.py
```

Expected: all pass.

## Task 3: Source registry apply auth diagnostics

**Files:**
- Modify: `src/wf_mcp/broker/service/source_registry_admin.py`
- Modify: `src/wf_mcp/broker/server.py`
- Modify: `tests/wf_mcp/service/test_source_registry_admin.py`

- [ ] **Step 1: Add apply summary test**

Append to `tests/wf_mcp/service/test_source_registry_admin.py`:

```python
def test_source_registry_apply_reports_missing_auth_ref(tmp_path: Path) -> None:
    entry = McpSourceRegistryEntry(
        id="github.work",
        provider="github",
        account="work",
        auth_ref="github.creds",
        transport=StdioSourceTransport(command="npx"),
    )
    provider, connection_service, _source_catalog = _apply_provider(
        tmp_path,
        registry_sources=[entry],
    )
    provider.load_auth = lambda auth_ref: None

    payload = provider.apply_registry_changes()

    assert payload["applied"] is True
    assert payload["registered"] == ["github.work"]
    assert connection_service.get("github.work").metadata["auth_ref"] == "github.creds"
    assert payload["auth_diagnostics"] == [
        {
            "severity": "error",
            "code": "auth_not_found",
            "logical_ref": None,
            "bound_source": "github.work",
            "message": (
                "Source 'github.work' references auth record 'github.creds', "
                "but no auth record was found."
            ),
            "repair_hint": (
                "Add an auth record for this auth_ref, update the source auth_ref, "
                "or bind the deployment to a source that does not require it."
            ),
        }
    ]
```

If `DependencyDiagnostic.model_dump(mode="json")` uses enum values differently
in this repo, assert individual fields instead:

```python
diagnostic = payload["auth_diagnostics"][0]
assert diagnostic["code"] == "auth_not_found"
assert diagnostic["bound_source"] == "github.work"
assert "github.creds" in diagnostic["message"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_source_registry_admin.py::test_source_registry_apply_reports_missing_auth_ref -q
```

Expected: fails because `SourceRegistryAdminProvider` has no `load_auth` field and apply summary has no `auth_diagnostics`.

- [ ] **Step 3: Add auth loader to provider**

Modify `src/wf_mcp/broker/service/source_registry_admin.py`.

Add imports:

```python
from ...auth import connection_auth_diagnostic
from ...models import AuthRecord
```

Add field to `SourceRegistryAdminProvider`:

```python
    load_auth: Callable[[str], AuthRecord | None] | None = None
```

- [ ] **Step 4: Add diagnostics to apply summary**

In `apply_registry_changes`, after computing `after`, add:

```python
        auth_diagnostics = []
        if self.load_auth is not None:
            for source_id in sorted(after):
                diagnostic = connection_auth_diagnostic(
                    after[source_id],
                    load_auth=self.load_auth,
                )
                if diagnostic is not None:
                    auth_diagnostics.append(diagnostic.model_dump(mode="json"))
```

Then add to the returned dict:

```python
            "auth_diagnostics": auth_diagnostics,
```

Do not reject apply when auth is missing. Apply reconciles desired source state;
auth diagnostics tell the operator why later live calls may fail.

- [ ] **Step 5: Wire runtime provider construction**

Modify `src/wf_mcp/broker/server.py`.

Find where `SourceRegistryAdminProvider(...)` is constructed for MCP-backed
`WorkflowServer`. Add:

```python
load_auth=service.upstream.load_auth,
```

If the file constructs the provider through a helper, pass the loader through
that helper. Do not change local/static server behavior; local/static still has
no source registry admin provider.

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/wf_mcp/service/test_source_registry_admin.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
uv run ruff check src/wf_mcp/broker/service/source_registry_admin.py src/wf_mcp/broker/server.py tests/wf_mcp/service/test_source_registry_admin.py
uv run basedpyright --level error src/wf_mcp/broker/service/source_registry_admin.py src/wf_mcp/broker/server.py tests/wf_mcp/service/test_source_registry_admin.py
```

Expected: all pass.

## Task 4: Docs and verification

**Files:**
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`

- [ ] **Step 1: Update spec status**

In `docs/superpowers/specs/2026-06-06-auth-source-secrets-boundary.md`, update
the `## Status` section to:

```markdown
Slice 1 implements the neutral auth record/store protocol and MCP compatibility
bridge. Slice 2 surfaces missing explicit auth refs through live source
diagnostics and source registry apply summaries. Auth admin surfaces and
provider-specific auth unions are future slices.
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, under the auth/source secrets boundary bullet,
append:

```markdown
    Second implementation slice complete: missing explicit auth refs now surface
    as `auth_not_found` diagnostics in live source checks and source registry
    apply summaries.
```

- [ ] **Step 3: Run final verification**

Run:

```bash
uv run pytest tests/wf_mcp/test_auth.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_source_registry_admin.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q
uv run ruff check src/wf_mcp/auth.py src/wf_mcp/broker/service/upstream_transport.py src/wf_mcp/broker/service/source_registry_admin.py src/wf_mcp/broker/server.py tests/wf_mcp/test_auth.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_source_registry_admin.py
uv run basedpyright --level error src/wf_mcp/auth.py src/wf_mcp/broker/service/upstream_transport.py src/wf_mcp/broker/service/source_registry_admin.py src/wf_mcp/broker/server.py tests/wf_mcp/test_auth.py tests/wf_mcp/service/test_upstream_transport.py tests/wf_mcp/service/test_source_registry_admin.py
```

Expected: all pass.

- [ ] **Step 4: Final report**

Report:

- files changed
- verification output
- final shape of `auth_diagnostics`
- any deviations from the plan

