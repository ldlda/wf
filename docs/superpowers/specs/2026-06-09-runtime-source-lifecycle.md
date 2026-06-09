# Runtime Source Lifecycle

Date: 2026-06-09

Status: design direction for next source families

Related:

- [Workflow config targets and sources](./2026-06-03-workflow-config-targets-and-sources.md)
- [Store-backed source registry](./2026-06-03-store-backed-source-registry-design.md)
- [Long-lived workflow API boundary](./2026-06-03-long-lived-workflow-api-boundary.md)
- [Project map](../../project_map.md)

## Purpose

The current mutable source registry and apply/reload path are concrete for MCP
sources. The next source families should not be forced through MCP
`ConnectionConfig` language. This spec defines the generic lifecycle that MCP,
Python, HTTP/OpenAPI, and future source providers should share.

The rule:

> Admin mutation changes desired source state. Apply/reload reconciles desired
> source state into live runtime sources. `wf_api` keeps seeing only
> `CapabilitySource`, `NodeSpec`, resources, prompts, and protocol surfaces.

## Current State

MCP has a working implementation:

```text
source registry desired MCP entries
  -> wf admin registry apply
  -> WfMcpService connections/adapters/catalog
  -> WorkflowApi capability/source surfaces
```

This works, but it is still MCP-shaped internally:

- registry entries are `McpSourceRegistryEntry`
- runtime apply mutates `ConnectionService`
- execution uses `McpRuntimePool`
- compatibility glue still translates through legacy `ConnectionConfig`

That is acceptable for MCP. It should not become the required model for Python
or HTTP sources.

## Desired Generic Lifecycle

All source families should fit this lifecycle:

```text
config seed sources + store-backed desired sources
  -> source provider manager
  -> live source instances
  -> capability inventory and executable NodeSpecs
  -> WorkflowApi and transports
```

Definitions:

- **Source config**: deployment bootstrap in `wf_config`.
- **Source registry**: mutable desired state stored by the server.
- **Source provider**: implementation package for one source family, such as
  `wf_sources_mcp`, `wf_sources_python`, or `wf_sources_openapi`.
- **Live source instance**: in-memory runtime object created from desired state.
- **Apply/reload**: reconciliation from desired state to live source instances.
- **Capability projection**: `CapabilitySource` plus executable `NodeSpec`s,
  resources, prompts, reducers, or workflows exposed to `wf_api`.

## Provider Boundary

A future neutral provider boundary should be closer to this shape than to MCP
connections:

```python
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from wf_authoring import NodeSpec
from wf_platform import CapabilitySource


class SourceEntryLike(Protocol):
    id: str
    kind: str
    enabled: bool


class SourceProvider(Protocol):
    kind: str

    async def apply_sources(
        self,
        *,
        desired: Sequence[SourceEntryLike],
    ) -> dict[str, Any]:
        """Reconcile desired entries into live source instances."""
        ...

    @property
    def capability_sources(self) -> Mapping[str, CapabilitySource]:
        """Return current workflow-visible source inventory."""
        ...

    def get_qualified_spec(self, qualified_name: str) -> NodeSpec[Any, Any]:
        """Return the executable spec for one qualified capability."""
        ...
```

This is not an immediate API contract. It is the direction: the provider owns
source-family semantics, while `wf_api` remains source-family neutral.

## Source Family Expectations

### MCP Sources

MCP sources already have:

- desired registry entries
- config seed/locked ownership
- explicit apply/reload
- persistent runtime sessions through `McpRuntimePool`
- catalog snapshots for tools/resources/prompts

MCP may continue to use `ConnectionConfig` behind its compatibility boundary
until the old `wf_mcp` facade is retired.

### Python Sources

Python sources should be the first non-MCP proof that the architecture is not
MCP-shaped.

Expected config example:

```json
{
  "kind": "python",
  "id": "local.ops",
  "module": "my_project.workflow_ops",
  "registry": "registry"
}
```

Expected behavior:

- load a module/object containing `NodeSpec`s or Python functions convertible to
  `NodeSpec`s
- expose them under the configured source id
- execute in-process without MCP sessions
- support reload by re-importing/re-reading the configured registry

Python source reload should be explicit. Do not silently reload modules on every
capability call.

### HTTP/OpenAPI Sources

HTTP/OpenAPI sources should be a separate source family, not a special MCP
transport.

Expected behavior:

- parse OpenAPI or explicit operation definitions
- expose operations as `NodeSpec`s
- use auth records where appropriate
- define a clear HTTP status/outcome policy before implementation
- keep large response/body handling bounded for CLI and workflow safety

This source family needs more design than Python because error semantics,
timeouts, idempotency, and output normalization are product decisions.

## Config vs Registry

Config and registry should keep their current distinction:

- Config is bootstrap, deployment intent, and portable local setup.
- Registry is mutable server-owned desired state.
- `locked` config entries own their ids and shadow registry entries.
- `seed` config entries initialize missing registry entries, then registry owns
  later admin changes.

For future source families, this ownership model should apply to source ids
independently of MCP provider/account fields.

## Apply Semantics

Apply/reload should:

- validate desired source entries before mutating live state
- add newly desired sources
- update changed source instances
- disable or remove deleted desired sources according to provider policy
- preserve diagnostics for referenced missing/disabled sources
- avoid mutating config files
- emit admin-visible events

Apply/reload should not:

- delete auth records by default
- delete old catalog/cache files by default
- rewrite deployments or artifacts
- turn live source failure into workflow interrupts

## Workflow API Boundary

`wf_api` should not know whether a capability came from MCP, Python, HTTP, or a
future source family. It should depend on:

- `WorkflowSpecProvider`
- `CapabilitySource`
- `NodeSpec`
- store/admin protocols

If a future source needs a family-specific operation, put it behind that
provider package or admin surface. Do not add source-family-specific branches to
workflow run execution.

## First Implementation Direction

Recommended next implementation slice:

1. Add `PythonSourceConfig` to `wf_config` as a tagged `server.sources` entry.
2. Create `wf_sources_python` with a loader for `module:object` registries.
3. Project loaded `NodeSpec`s into `CapabilitySource`.
4. Wire local/static `WorkflowServer` construction to include Python sources.
5. Prove `wf cap list`, `wf cap call`, and deployment `run start` work without
   importing `wf_mcp`.

This slice should not implement source registry mutation for Python yet. Static
config first proves the provider shape. Mutable registry/apply can follow once
the provider interface is real.

## Open Questions

- Should generic source registry entries live in `wf_api`, `wf_server`, or a new
  `wf_sources` package?
- Should provider managers be composed by `wf_server.config` or by a separate
  source runtime package?
- How much hot-reload behavior should Python sources support in development?
- What are the safe defaults for HTTP timeouts, retries, and large response
  handling?
