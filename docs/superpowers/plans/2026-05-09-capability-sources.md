# Capability Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ad hoc broker/proxy/admin/stdlib split with a source registry that can project workflow node specs, MCP tools, prompts, and resources to the right surfaces.

**Architecture:** Add `CapabilitySource` as the source registry model, keep `SpecSource` behavior as a compatibility projection while the rest of the system migrates, then move stdlib and admin capabilities into explicit `wf.std`, `wf.mcp`, and `wf.admin` sources. Broker/proxy servers should project capabilities from sources instead of defining separate duplicate admin tools.

**Tech Stack:** Python 3.14, dataclasses, Pydantic models already used by node specs, FastMCP/MCP server decorators, pytest, ruff, basedpyright.

---

## File Structure

- Create `src/wf_mcp/broker/service/capability_sources.py`: canonical source model, visibility flags, permission flags, capability buckets, projection helpers.
- Modify `src/wf_mcp/broker/service/sources.py`: either delegate to the new model or become a small compatibility import.
- Modify `src/wf_mcp/broker/service/core.py`: store `capability_sources`, derive node-spec resolution from them, keep `spec_sources` and `specs_by_connection` as compatibility views if needed.
- Modify `src/wf_mcp/broker/service/builtins.py`: register `wf.std` stdlib specs and `wf.mcp` runtime specs through capability sources.
- Modify `src/wf_mcp/broker/tools.py`: project broker MCP tools from `wf.admin` source definitions.
- Create `src/wf_mcp/broker/admin_capabilities.py`: one reusable definition of broker/admin tool capabilities.
- Modify `src/wf_mcp/transparent_proxy/admin.py` and `src/wf_mcp/transparent_proxy/runtime.py`: project proxy admin tools from the same `wf.admin` capability definitions when admin MCP exposure is enabled.
- Modify `src/wf_mcp/shared/names.py`: move admin namespace toward `wf.admin` and use `LdaNamespace` where dotted names should be preserved.
- Modify `tests/wf_mcp/test_service.py`, `tests/wf_mcp/test_broker_server.py`, and `tests/wf_mcp/test_transparent_proxy.py`: prove projections and defaults.
- Modify `docs/wf_mcp_capability_sources.md`: update once implementation names are final.

---

### Task 1: Add Canonical Capability Source Model

**Files:**
- Create: `src/wf_mcp/broker/service/capability_sources.py`
- Modify: `src/wf_mcp/broker/service/sources.py`
- Test: `tests/wf_mcp/test_service.py`

- [ ] **Step 1: Write failing tests for source visibility and buckets**

Add tests in `tests/wf_mcp/test_service.py`:

```python
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
    assert std_source.capabilities.tools == {}

    assert mcp_source.id == "wf.mcp"
    assert mcp_source.visibility.planner is True
    assert mcp_source.permissions.calls_upstream is True
    assert "wf.mcp.call_tool" in mcp_source.capabilities.node_specs
```

- [ ] **Step 2: Run the focused failing test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py::test_service_sources_have_visibility_and_capability_buckets -q
```

Expected: fail because `capability_sources` does not exist.

- [ ] **Step 3: Add the source model**

Create `src/wf_mcp/broker/service/capability_sources.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from wf_authoring import NodeSpec

SourceKind = Literal["system", "connection"]


@dataclass(frozen=True, slots=True)
class SourceVisibility:
    planner: bool = False
    mcp_client: bool = False
    admin_dashboard: bool = True


@dataclass(frozen=True, slots=True)
class SourcePermissions:
    safe_for_workflow: bool = False
    calls_upstream: bool = False
    mutates_config: bool = False
    mutates_auth: bool = False


@dataclass(slots=True)
class CapabilityBuckets:
    tools: dict[str, Any] = field(default_factory=dict)
    node_specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
    prompts: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CapabilitySource:
    id: str
    kind: SourceKind
    capabilities: CapabilityBuckets = field(default_factory=CapabilityBuckets)
    enabled: bool = True
    visibility: SourceVisibility = field(default_factory=SourceVisibility)
    permissions: SourcePermissions = field(default_factory=SourcePermissions)
    description: str | None = None

    def as_status(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "enabled": self.enabled,
            "visibility": {
                "planner": self.visibility.planner,
                "mcp_client": self.visibility.mcp_client,
                "admin_dashboard": self.visibility.admin_dashboard,
            },
            "permissions": {
                "safe_for_workflow": self.permissions.safe_for_workflow,
                "calls_upstream": self.permissions.calls_upstream,
                "mutates_config": self.permissions.mutates_config,
                "mutates_auth": self.permissions.mutates_auth,
            },
            "description": self.description,
            "tool_count": len(self.capabilities.tools),
            "node_spec_count": len(self.capabilities.node_specs),
            "prompt_count": len(self.capabilities.prompts),
            "resource_count": len(self.capabilities.resources),
        }
```

- [ ] **Step 4: Keep `SpecSource` as compatibility wrapper**

Modify `src/wf_mcp/broker/service/sources.py` so existing code can still import `SpecSource` while new code can move to `CapabilitySource`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wf_authoring import NodeSpec

from .capability_sources import (
    CapabilityBuckets,
    CapabilitySource,
    SourceKind,
    SourcePermissions,
    SourceVisibility,
)


@dataclass(slots=True)
class SpecSource:
    id: str
    kind: SourceKind
    specs: dict[str, NodeSpec[Any, Any]] = field(default_factory=dict)
    visible: bool = True
    description: str | None = None

    def as_capability_source(self) -> CapabilitySource:
        return CapabilitySource(
            id=self.id,
            kind=self.kind,
            capabilities=CapabilityBuckets(node_specs=self.specs),
            visibility=SourceVisibility(
                planner=self.visible,
                mcp_client=False,
                admin_dashboard=True,
            ),
            permissions=SourcePermissions(safe_for_workflow=self.kind == "system"),
            description=self.description,
        )

    def as_status(self) -> dict[str, Any]:
        return self.as_capability_source().as_status()
```

- [ ] **Step 5: Run focused test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py::test_service_sources_have_visibility_and_capability_buckets -q
```

Expected: fail until service stores `capability_sources`; pass after Task 2.

---

### Task 2: Make `WfMcpService` Store Capability Sources

**Files:**
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: `src/wf_mcp/broker/service/specs.py`
- Test: `tests/wf_mcp/test_service.py`

- [ ] **Step 1: Add failing service projection tests**

Add:

```python
def test_service_spec_views_are_derived_from_capability_sources() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "source_view_store"))

    assert "wf.std" in service.capability_sources
    assert "wf.std" in service.spec_sources
    assert "wf.std" in service.specs_by_connection
    assert (
        service.specs_by_connection["wf.std"]["wf.std.runtime_error"]
        is service.capability_sources["wf.std"].capabilities.node_specs[
            "wf.std.runtime_error"
        ]
    )
```

- [ ] **Step 2: Run focused test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py::test_service_spec_views_are_derived_from_capability_sources -q
```

Expected: fail because compatibility views are not derived from capability sources.

- [ ] **Step 3: Update service fields and registration**

In `src/wf_mcp/broker/service/core.py`, replace the stored `spec_sources` field with canonical capability storage and add derived views:

```python
capability_sources: dict[str, CapabilitySource] = field(default_factory=dict)

@property
def spec_sources(self) -> dict[str, SpecSource]:
    return {
        source.id: SpecSource(
            id=source.id,
            kind=source.kind,
            specs=source.capabilities.node_specs,
            visible=source.enabled and source.visibility.planner,
            description=source.description,
        )
        for source in self.capability_sources.values()
        if source.capabilities.node_specs
    }

@property
def specs_by_connection(self) -> dict[str, dict[str, NodeSpec[Any, Any]]]:
    return {
        source.id: source.capabilities.node_specs
        for source in self.capability_sources.values()
        if source.capabilities.node_specs
    }

def register_capability_source(self, source: CapabilitySource) -> None:
    self.capability_sources[source.id] = source

def register_spec_source(self, source: SpecSource) -> None:
    self.register_capability_source(source.as_capability_source())
```

- [ ] **Step 4: Update spec resolution**

In `src/wf_mcp/broker/service/specs.py`, make `get_qualified_spec` read capability sources:

```python
from collections.abc import Mapping

from .capability_sources import CapabilitySource


def get_qualified_spec(
    sources: Mapping[str, CapabilitySource],
    qualified_name: str,
) -> NodeSpec[Any, Any]:
    source_id, _ = qualified_name.rsplit(".", 1)
    source = sources.get(source_id)
    if (
        source is None
        or not source.enabled
        or qualified_name not in source.capabilities.node_specs
    ):
        raise KeyError(f"unknown qualified node {qualified_name!r}")
    return source.capabilities.node_specs[qualified_name]
```

- [ ] **Step 5: Run focused service tests**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py -q
```

Expected: pass.

---

### Task 3: Move All Authoring Ops Into `wf.std`

**Files:**
- Modify: `src/wf_mcp/broker/service/builtins.py`
- Test: `tests/wf_mcp/test_service.py`

- [ ] **Step 1: Add failing `wf.std` inventory test**

Add:

```python
def test_wf_std_source_contains_authoring_ops() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "stdlib_source_store"))
    specs = service.capability_sources["wf.std"].capabilities.node_specs

    expected = {
        "wf.std.coalesce",
        "wf.std.default_if_none",
        "wf.std.constant",
        "wf.std.pick_key",
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
    assert expected <= set(specs)
```

- [ ] **Step 2: Run focused test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py::test_wf_std_source_contains_authoring_ops -q
```

Expected: fail because only `runtime_error` is currently registered.

- [ ] **Step 3: Register stdlib ops**

In `src/wf_mcp/broker/service/builtins.py`, import `wf_authoring.ops` symbols and qualify each one under `wf.std`:

```python
from wf_authoring import (
    coalesce,
    constant,
    default_if_none,
    first_item,
    first_item_maybe,
    first_item_or_none,
    is_empty,
    last_item,
    last_item_or_none,
    length,
    pick_key,
    runtime_error,
    truthy,
)


def builtin_specs() -> dict[str, NodeSpec[Any, Any]]:
    specs = [
        coalesce,
        default_if_none,
        constant,
        pick_key,
        truthy,
        runtime_error,
        first_item,
        first_item_or_none,
        first_item_maybe,
        last_item,
        last_item_or_none,
        length,
        is_empty,
    ]
    qualified_specs = [
        qualify_spec(BUILTIN_CONNECTION_ID, _strip_authoring_prefix(spec))
        for spec in specs
    ]
    return {spec.name: spec for spec in qualified_specs}


def _strip_authoring_prefix(spec: NodeSpec[Any, Any]) -> NodeSpec[Any, Any]:
    name = spec.name.removeprefix("authoring.")
    return NodeSpec(
        name=name,
        input_model=spec.input_model,
        output_model=spec.output_model,
        outcomes=spec.outcomes,
        fn=spec.fn,
        description=spec.description,
        is_async=spec.is_async,
        accepts_context=spec.accepts_context,
        input_schema_contract=spec.input_schema_contract,
        output_schema_contract=spec.output_schema_contract,
    )
```

- [ ] **Step 4: Run service tests**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py -q
```

Expected: pass.

---

### Task 4: Add `wf.admin` Source Without MCP Exposure

**Files:**
- Create: `src/wf_mcp/broker/admin_capabilities.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/test_service.py`

- [ ] **Step 1: Add failing admin source test**

Add:

```python
def test_wf_admin_source_exists_but_is_not_planner_visible() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "admin_source_store"))
    source = service.capability_sources["wf.admin"]

    assert source.kind == "system"
    assert source.visibility.planner is False
    assert source.visibility.mcp_client is False
    assert source.visibility.admin_dashboard is True
    assert source.permissions.mutates_config is True
    assert "wf.admin.list_sources" in source.capabilities.tools
    assert "wf.admin.disable_source" in source.capabilities.tools
    assert "wf.admin" not in service.get_planner_catalog().snapshots
```

- [ ] **Step 2: Run focused test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py::test_wf_admin_source_exists_but_is_not_planner_visible -q
```

Expected: fail because `wf.admin` does not exist.

- [ ] **Step 3: Define admin capability objects**

Create `src/wf_mcp/broker/admin_capabilities.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .service.capability_sources import (
    CapabilityBuckets,
    CapabilitySource,
    SourcePermissions,
    SourceVisibility,
)

ADMIN_SOURCE_ID = "wf.admin"


@dataclass(frozen=True, slots=True)
class AdminTool:
    name: str
    description: str
    handler_name: str
    mutates_config: bool = False
    mutates_auth: bool = False


def admin_source() -> CapabilitySource:
    tools: dict[str, AdminTool] = {
        "wf.admin.list_sources": AdminTool(
            name="wf.admin.list_sources",
            description="List broker capability sources.",
            handler_name="list_sources",
        ),
        "wf.admin.disable_source": AdminTool(
            name="wf.admin.disable_source",
            description="Disable a capability source.",
            handler_name="disable_source",
            mutates_config=True,
        ),
        "wf.admin.enable_source": AdminTool(
            name="wf.admin.enable_source",
            description="Enable a capability source.",
            handler_name="enable_source",
            mutates_config=True,
        ),
    }
    return CapabilitySource(
        id=ADMIN_SOURCE_ID,
        kind="system",
        capabilities=CapabilityBuckets(tools=tools),
        visibility=SourceVisibility(
            planner=False,
            mcp_client=False,
            admin_dashboard=True,
        ),
        permissions=SourcePermissions(
            safe_for_workflow=False,
            calls_upstream=False,
            mutates_config=True,
            mutates_auth=True,
        ),
        description="Privileged broker administration capabilities.",
    )
```

- [ ] **Step 4: Install admin source**

In `WfMcpService.__post_init__`, register `admin_source()` after builtin sources:

```python
from ..admin_capabilities import admin_source

...

self.register_capability_source(admin_source())
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_service.py -q
```

Expected: pass.

---

### Task 5: Project Broker Admin Tools From `wf.admin`

**Files:**
- Modify: `src/wf_mcp/broker/tools.py`
- Test: `tests/wf_mcp/test_broker_server.py`

- [ ] **Step 1: Add test proving default broker exposes current public tools but has source-backed metadata**

Add to `tests/wf_mcp/test_broker_server.py`:

```python
def test_broker_admin_tools_are_backed_by_wf_admin_source() -> None:
    service = WfMcpService(store=FileStore(local_temp_root() / "broker_admin_source"))
    server = create_broker_server(service)

    tools = asyncio.run(server.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "list_spec_sources" in tool_names
    assert "get_planner_catalog" in tool_names
    assert "wf.admin.list_sources" in service.capability_sources[
        "wf.admin"
    ].capabilities.tools
```

- [ ] **Step 2: Run focused broker test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_broker_server.py::test_broker_admin_tools_are_backed_by_wf_admin_source -q
```

Expected: pass after Task 4; fail before Task 4.

- [ ] **Step 3: Keep current tool names as compatibility exports**

Do not rename public broker MCP tools in this task. Keep:

```text
list_connections
get_connection_statuses
refresh_connection_catalog
get_catalog
get_planner_catalog
list_spec_sources
read_broker_resource
render_broker_prompt
invoke_broker_method
call_broker_tool
get_broker_events
```

Add comments in `src/wf_mcp/broker/tools.py`:

```python
# These MCP tool names are compatibility exports. Their capability metadata
# belongs to the wf.admin source; future admin-enabled servers can project
# dotted wf.admin.* names from that source.
```

- [ ] **Step 4: Run focused broker tests**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_broker_server.py -q
```

Expected: pass.

---

### Task 6: Normalize Transparent Proxy Admin Naming Strategy

**Files:**
- Modify: `src/wf_mcp/shared/names.py`
- Modify: `src/wf_mcp/transparent_proxy/runtime.py`
- Test: `tests/wf_mcp/test_names.py`
- Test: `tests/wf_mcp/test_transparent_proxy.py`

- [ ] **Step 1: Add naming tests for admin namespace**

Add to `tests/wf_mcp/test_names.py`:

```python
def test_admin_namespace_is_distinct_from_wf_mcp_runtime_source() -> None:
    assert ADMIN_NAMESPACE == "wf.admin"
    assert is_admin_tool_name("wf.admin.list_connections") is True
    assert is_admin_tool_name("wf.mcp.call_tool") is False
```

- [ ] **Step 2: Run focused naming test**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_names.py::test_admin_namespace_is_distinct_from_wf_mcp_runtime_source -q
```

Expected: fail because `ADMIN_NAMESPACE` is currently `wf.mcp`.

- [ ] **Step 3: Update namespace constants**

In `src/wf_mcp/shared/names.py`:

```python
ADMIN_NAMESPACE = "wf.admin"


def is_admin_tool_name(proxy_name: str) -> bool:
    return proxy_name.startswith(f"{ADMIN_NAMESPACE}.") or proxy_name.startswith(
        f"{ADMIN_NAMESPACE}_"
    )
```

Use `LdaNamespace(ADMIN_NAMESPACE)` in `src/wf_mcp/transparent_proxy/runtime.py`:

```python
from ..shared.names import ADMIN_NAMESPACE, LdaNamespace

...

admin.add_transform(LdaNamespace(ADMIN_NAMESPACE))
```

- [ ] **Step 4: Update transparent proxy tests**

In `tests/wf_mcp/test_transparent_proxy.py`, update expected admin names from `wf.mcp_*` to dotted `wf.admin.*` if `LdaNamespace` preserves dotted names:

```python
assert "wf.admin.list_connections" in names
assert "wf.admin.get_connection_statuses" in names
assert "wf.admin.list_proxy_tools" in names
assert "wf.admin.get_proxy_tool" in names
```

Call tools by the new names:

```python
connections_result = await client.call_tool("wf.admin.list_connections")
proxy_tools_result = await client.call_tool("wf.admin.list_proxy_tools")
```

- [ ] **Step 5: Run transparent proxy tests**

Run:

```powershell
uv run --with pytest pytest tests\wf_mcp\test_names.py tests\wf_mcp\test_transparent_proxy.py -q
```

Expected: pass if `LdaNamespace` preserves dotted names. If FastMCP still emits underscore names, keep `wf.admin_*` as compatibility and document that dotted projection needs a deeper transform.

---

### Task 7: Update Docs And Full Verification

**Files:**
- Modify: `docs/wf_mcp_capability_sources.md`
- Modify: `docs/wf_mcp_architecture.md`
- Test: full verification commands

- [ ] **Step 1: Update docs with implemented names**

In `docs/wf_mcp_capability_sources.md`, update the migration section to mark implemented pieces:

```markdown
## Implemented Shape

- `CapabilitySource` owns source metadata and capability buckets.
- `wf.std` owns workflow stdlib node specs.
- `wf.mcp` owns workflow MCP runtime node specs.
- `wf.admin` owns privileged admin capability metadata.
- Broker and proxy MCP tool projection remains compatibility-first while the
  admin projection stabilizes.
```

- [ ] **Step 2: Run full pytest**

Run:

```powershell
uv run --with pytest pytest -q
```

Expected: all tests pass, live-only tests may skip when env is absent.

- [ ] **Step 3: Run ruff**

Run:

```powershell
uv run ruff check src tests examples main.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run basedpyright errors**

Run:

```powershell
uv run basedpyright src tests examples main.py --level error
```

Expected: `0 errors`.

---

## Self-Review

Spec coverage:

- Capability source model is covered by Tasks 1 and 2.
- `wf.std` migration is covered by Task 3.
- `wf.admin` privileged source is covered by Task 4.
- Broker projection is covered by Task 5.
- Transparent proxy naming and admin namespace separation is covered by Task 6.
- Documentation and verification are covered by Task 7.

Known deliberate scope limits:

- Task 5 keeps current broker MCP public tool names as compatibility exports.
- Task 6 attempts dotted transparent-proxy admin names via `LdaNamespace`; if FastMCP still forces underscore naming, this plan keeps `wf.admin_*` compatibility and defers deeper transform work.
- Source enable/disable runtime behavior is not implemented in this plan beyond introducing `enabled`; it should be the next plan after the registry shape lands.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified implementation steps remain.
- Each task includes exact paths, test names, commands, and expected outcomes.

Type consistency:

- `CapabilitySource`, `CapabilityBuckets`, `SourceVisibility`, and
  `SourcePermissions` are introduced once and reused consistently.
- Compatibility views are named `spec_sources` and `specs_by_connection`.
