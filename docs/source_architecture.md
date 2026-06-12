# Source Architecture

This map explains how workflow capability sources fit together. Use it when
deciding where to add a new source family or when untangling `wf_sources_mcp`
from the older `wf_mcp` compatibility package.

## Short Version

```text
wf_authoring
  creates NodeSpec, reducers, and authored workflows

wf_platform
  defines neutral source DTOs:
    CapabilitySource
    CapabilityBuckets
    SourceVisibility
    SourcePermissions

wf_api
  consumes source DTOs through WorkflowSpecProvider
  owns built-in local sources:
    wf.std
    wf.recipes

wf_sources_mcp
  implements MCP as an upstream source provider

wf_sources_python
  implements trusted in-process Python source loading

wf_server
  composes configured providers into WorkflowServer

wf_transport_*
  exposes WorkflowServer over protocols
```

The workflow API should not care whether a capability came from MCP, Python,
OpenAPI, or a built-in source. It should see `CapabilitySource` and executable
`NodeSpec` objects.

## Package Responsibilities

| Package | Owns | Does not own |
| --- | --- | --- |
| `wf_authoring` | `@node`, `NodeSpec`, builder DSL, reducers, reusable authored ops. | Server config, source loading, MCP sessions. |
| `wf_platform` | Neutral source DTOs and source visibility/permission metadata. | Provider-specific loading or execution. |
| `wf_api` | Application operations over capabilities, drafts, artifacts, deployments, and runs. Built-in `wf.std` / `wf.recipes` sources. | MCP/Python/OpenAPI source-specific behavior. |
| `wf_sources_mcp` | MCP source ids, connection models, auth/catalog stores, discovery, SDK facade, persistent runtime pool, converters, wrappers. | MCP frontend/proxy compatibility, durable server composition. |
| `wf_sources_python` | Trusted Python module registry loading and projection to `CapabilitySource`. | Authoring primitives, registry mutation/apply, sandboxing. |
| `wf_server` | `WorkflowServer` composition from config/store/source providers. | JSON-RPC method definitions, MCP protocol frontend. |
| `wf_transport_rpc_http` | JSON-RPC HTTP app/client around an existing `WorkflowServer`. | Server startup policy, source-provider composition. |
| `wf_mcp` | Legacy/special-purpose MCP frontend, broker glue, proxy, compatibility shims. | New durable product behavior unless explicitly retiring old callers. |

## Data Flow

```text
wf_config.server.sources[]
  -> wf_server.config selects source providers
  -> provider loads live source inventory
  -> CapabilitySource map
  -> WorkflowSpecProvider
  -> WorkflowApi / WorkflowServer
  -> transport or CLI
```

The first shared provider seam is intentionally static:

```python
class WorkflowSourceProvider(Protocol):
    def load_sources(self) -> Mapping[str, CapabilitySource]: ...
```

This covers source families that can project configured inventory into
workflow-facing `CapabilitySource` objects. Provider-specific runtime pools,
admin/apply hooks, auth, catalog caches, and live health checks stay outside
this narrow seam until a source family needs them.

For MCP, the provider also owns stateful upstream sessions:

```text
McpSourceConnection
  -> McpRuntimePool
  -> McpSourceClient
  -> MCP ClientSession
```

For Python, the provider is simpler:

```text
PythonSourceConfig(path, module, registry)
  -> PythonSourceProvider
  -> import module
  -> load NodeSpec registry
  -> qualify specs under source id
  -> CapabilitySource(kind="python")
```

For a concrete operator flow, see the
[`Python source runbook`](runbooks/python-source.md). It covers writing `ops.py`,
configuring `path`/`module`/`registry`, validating the config, calling a
capability, and running a saved workflow deployment.

## Built-Ins Versus Configured Sources

`wf.std` and `wf.recipes` are built-in local sources owned by `wf_api.local_sources`.
They are always platform-versioned content.

Configured sources are explicit server/operator choices:

- `kind: "mcp"`: upstream MCP server capabilities.
- `kind: "python"`: trusted in-process project capabilities.
- future `kind: "openapi"`: HTTP/OpenAPI operations.

Do not move `wf.std` or `wf.recipes` into `wf_sources_python`. They are not
operator-configured project sources.

Generated draft workflows may still require built-in helper sources such as
`wf.std`; deployment examples should bind both the configured source and any
built-in requirements reported by validation.

## `wf_sources_mcp` Internal Layers

`wf_sources_mcp` is clearer if read from bottom to top:

```text
ids / transports / connections
  source identity and MCP connection description

auth / storage
  source auth records and catalog cache files

client
  one live MCP ClientSession facade

runtime
  persistent session pool for stateful upstream operations

sdk
  one-shot adapter, operation protocols, and MCP-to-workflow converters

catalog / discovery / tool_wrappers
  turn MCP tools/resources/prompts into workflow-facing source inventories
```

`wf_mcp` may still re-export or adapt some of this while old callers exist. New
durable server/source work should prefer `wf_sources_mcp` directly.

## Adding A New Source Family

Start with a provider package:

```text
src/wf_sources_<kind>/
  __init__.py
  loader.py or provider.py
  tests/
```

Then add:

1. A `wf_config` discriminated-union source model.
2. A provider loader that returns `CapabilitySource`.
3. `wf_server.config` composition for that source kind.
4. Tests proving `cap list`, `cap call`, and one workflow run path.
5. Docs stating which parts are static, mutable, reloadable, or deferred.

Do not add source-family branches inside `wf_api` run execution. Source-specific
logic belongs in the provider package or server composition layer.
