# Workflow Config Targets and Sources

Date: 2026-06-03

Status: design note

Related:

- [Long-lived workflow API boundary](./2026-06-03-long-lived-workflow-api-boundary.md)
- [Persisted run/resume contract](./2026-06-03-persisted-run-resume-contract.md)
- [Current roadmap](../../current_roadmap.md)

## Purpose

Define the next workflow config shape before remote CLI targeting and source
provider config expand. The key distinctions are:

- `client.target` chooses where a client sends workflow operations by default.
- `server` declares what a long-lived process can host.
- `server.sources` declare capability providers available to that server.

These must not be collapsed into one concept.

## Client Target

`client.target.kind` answers: where should this client send workflow
operations by default?

It is a control-plane setting for clients such as `wf`. It should be
overridable by CLI flags, for example:

```bash
wf --config wf.json --url http://127.0.0.1:8765/rpc run start demo.default
wf --config wf.json --local run start demo.default
```

CLI overrides should affect only the current invocation. They should not mutate
the config file unless a dedicated config-write command is used.

Example local target:

```json
{
  "client": {
    "target": {
      "kind": "local"
    }
  }
}
```

This means the CLI builds an in-process `WorkflowApi` from local stores and
local source providers.

Example remote target:

```json
{
  "client": {
    "target": {
      "kind": "rpc_http",
      "url": "http://127.0.0.1:8765/rpc",
      "timeout_seconds": 30
    }
  }
}
```

This means the CLI should call the long-lived JSON-RPC server. It should not
construct local runtime services for execution unless `--local` or an equivalent
override is supplied.

Recommended Pydantic shape:

```python
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class LocalTargetConfig(BaseModel):
    kind: Literal["local"] = "local"


class RpcHttpTargetConfig(BaseModel):
    kind: Literal["rpc_http"]
    url: str
    timeout_seconds: float = 30.0


TargetConfig = Annotated[
    LocalTargetConfig | RpcHttpTargetConfig,
    Field(discriminator="kind"),
]
```

Do not add `client.target.kind = "mcp"` for the workflow CLI path. MCP can be
hosted by the server as one transport, but `wf` should use JSON-RPC for
first-class workflow operations.

## Server Hosting

`server` answers: what can this process host if started as a long-lived
workflow server?

A server can host multiple transports at the same time. This is required so a
user can point `wf` at JSON-RPC while another client points MCP at the same
server process.

Recommended shape:

```json
{
  "server": {
    "store": {
      "kind": "filesystem",
      "root": ".wf_store"
    },
    "transports": [
      {
        "kind": "rpc_http",
        "host": "127.0.0.1",
        "port": 8765,
        "path": "/rpc"
      },
      {
        "kind": "mcp_http",
        "host": "127.0.0.1",
        "port": 8765,
        "path": "/mcp"
      }
    ],
    "sources": [
      {"kind": "stdlib", "id": "wf.std"}
    ]
  }
}
```

Recommended Pydantic shape:

```python
class RpcHttpTransportConfig(BaseModel):
    kind: Literal["rpc_http"]
    host: str = "127.0.0.1"
    port: int = 8765
    path: str = "/rpc"


class McpHttpTransportConfig(BaseModel):
    kind: Literal["mcp_http"]
    host: str = "127.0.0.1"
    port: int = 8765
    path: str = "/mcp"


ServerTransportConfig = Annotated[
    RpcHttpTransportConfig | McpHttpTransportConfig,
    Field(discriminator="kind"),
]


class ServerConfig(BaseModel):
    store: StoreConfig = StoreConfig(kind="filesystem", root=Path(".wf_store"))
    transports: list[ServerTransportConfig] = []
    sources: list[SourceConfig] = []
```

Transport configs describe what the server hosts. They are not workflow
sources.

## Store

`server.store` answers: where does the server persist workflow platform state?

The current implementation uses one default filesystem store root:

```json
{
  "server": {
    "store": {
      "kind": "filesystem",
      "root": ".wf_store"
    }
  }
}
```

That single root fans out internally into role-specific files/directories:

- workflow records: artifacts, deployments, draft workspaces, runs, and traces
- source registry desired state
- source catalog/cache snapshots
- auth records for local/dev MCP-compatible credentials

Recommended Pydantic shape for the first slice:

```python
class FilesystemStoreConfig(BaseModel):
    kind: Literal["filesystem"]
    root: Path = Path(".wf_store")


class SqliteStoreConfig(BaseModel):
    kind: Literal["sqlite"]
    url: str


StoreConfig = Annotated[
    FilesystemStoreConfig | SqliteStoreConfig,
    Field(discriminator="kind"),
]
```

Only `filesystem` needs implementation immediately. The tagged union exists so
the config does not bake the store concept into a single `store_root` field.

Relative filesystem paths should resolve relative to the config file directory.
SQL-backed stores are future work.

### Store Roles

`server.store` is the default store for every role. Future configs should allow
optional role-specific overrides without breaking existing files:

```json
{
  "server": {
    "store": {
      "kind": "filesystem",
      "root": ".wf_store"
    },
    "stores": {
      "workflow": {
        "kind": "filesystem",
        "root": ".wf_store"
      },
      "auth": {
        "kind": "filesystem",
        "root": ".wf_auth"
      },
      "source_registry": {
        "kind": "filesystem",
        "root": ".wf_sources"
      },
      "catalog_cache": {
        "kind": "filesystem",
        "root": ".wf_catalog"
      }
    }
  }
}
```

Implementation status: first filesystem-only slice implemented. Role overrides
are optional and fall back to `server.store`. MCP auth and catalog/cache
storage now have separate file-store adapters; `server.store` still remains
the fallback for missing roles.

Resolution rule:

```text
effective_store(role) = server.stores[role] if present else server.store
```

The first implementation should keep all role overrides optional and filesystem
only. This preserves the current single-root config while making the boundary
ready for secret-manager auth stores, database-backed workflow records, and
separate catalog/cache storage.

The store layer should own mutable workflow platform registries:

- artifact records
- deployment records
- draft workspaces
- run/checkpoint records
- source registry entries
- source catalog snapshots
- source liveness/status metadata
- auth records or auth references

This matters for daemon/server mode. A source added dynamically through an admin
tool or UI should survive process restart because it was written to the store,
not only held in process memory.

## Sources

`sources[].kind` answers: what type of capability provider is this?

Sources are execution/catalog configuration owned by the server runtime. They
are not client target configuration and not transport configuration.

`server.sources` are bootstrap source declarations. They are loaded at server
startup and should be treated as desired startup state, not the only possible
source registry.

Long-term mutable sources should live in a store-backed source registry. The
effective source catalog is:

```text
effective sources = config bootstrap sources + stored source registry entries
```

Conflict rules must be explicit:

- duplicate source ids between config and store should fail fast in the first
  implementation
- config bootstrap sources can be treated as immutable unless copied into the
  store by an explicit admin action
- store-backed sources can be added, disabled, refreshed, or deleted by future
  admin/UI flows
- server startup validates the effective source set before accepting workflow
  runs

Recommended shape:

```json
{
  "server": {
    "sources": [
      {
        "kind": "stdlib",
        "id": "wf.std"
      },
      {
        "kind": "mcp",
        "id": "github.work",
        "server": "mcp-github",
        "account": "work",
        "transport": {
          "kind": "stdio",
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-github"]
        },
        "auth": {
          "kind": "env",
          "name": "GITHUB_WORK_TOKEN"
        }
      },
      {
        "kind": "mcp",
        "id": "github.personal",
        "server": "github-2",
        "account": "personal",
        "transport": {
          "kind": "stdio",
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-github"]
        },
        "auth": {
          "kind": "env",
          "name": "GITHUB_PERSONAL_TOKEN"
        }
      }
    ]
  }
}
```

Recommended Pydantic shape:

```python
class StdlibSourceConfig(BaseModel):
    kind: Literal["stdlib"]
    id: Literal["wf.std", "wf.recipes"]


class McpStdioTransportConfig(BaseModel):
    kind: Literal["stdio"]
    command: str
    args: list[str] = []
    cwd: str | None = None
    env: dict[str, str] = {}


class AuthEnvRef(BaseModel):
    kind: Literal["env"]
    name: str


class McpSourceConfig(BaseModel):
    kind: Literal["mcp"]
    id: str
    server: str
    account: str | None = None
    transport: McpStdioTransportConfig
    auth: AuthEnvRef | None = None


class OpenApiSourceConfig(BaseModel):
    kind: Literal["openapi"]
    id: str
    spec_url: str | None = None
    spec_path: str | None = None
    auth: AuthEnvRef | None = None


SourceConfig = Annotated[
    StdlibSourceConfig | McpSourceConfig | OpenApiSourceConfig,
    Field(discriminator="kind"),
]
```

Exact transport/auth subtypes can expand later. The important decision is that
the top-level source union is discriminated by `kind`.

## Identity Rules

`id` is the primary source identity.

Rules:

- `sources[].id` must be unique across the config.
- Artifact and deployment bindings refer to source ids, not `server` or
  `account`.
- `server` and `account` are provider-specific metadata/config, not identity.
- Same `server` with different `account` is allowed.
- Same `server` and same `account` with different `id` is allowed only when
  the implementation can prove or report why the entries differ.
- No code should split a source id to infer `server`, `account`, provider, or
  version.
- Dotted ids are display-friendly names, not parseable structure.

This matters for cases like:

```text
github.work      -> MCP source using server "mcp-github", account "work"
github.personal  -> MCP source using server "github-2", account "personal"
```

Both are valid even though their display ids share a prefix. Runtime validation
must use the explicit struct fields.

## Deployment Binding Relationship

Artifacts describe required logical sources. Deployments bind those logical
sources to concrete source ids available on the execution target.

Example:

```json
{
  "required_sources": ["github.work"],
  "deployment": {
    "bindings": [
      {
        "logical_source": "github.work",
        "concrete_source": "github.personal"
      }
    ]
  }
}
```

Before run, validation should check:

- the concrete source id exists on the selected execution target
- the concrete source exposes the required capability keys
- the pinned artifact/deployment dependencies are still runnable

If `client.target.kind = "rpc_http"`, the remote server is the source of truth
for execution-time source availability. The local CLI config should not pretend
its local `server.sources` prove remote runnability unless the same process is
also serving that target.

## Config File Direction

The current `wf_mcp.config.json` shape is MCP-specific:

```json
{
  "store_root": ".wf_mcp_store",
  "connections": []
}
```

The workflow platform needs a neutral config shape:

```json
{
  "version": 1,
  "client": {
    "target": {
      "kind": "local"
    }
  },
  "server": {
    "store": {
      "kind": "filesystem",
      "root": ".wf_store"
    },
    "transports": [],
    "sources": []
  }
}
```

Compatibility can keep loading old MCP configs for MCP commands, but new
workflow CLI/server config should move toward the neutral shape.

Relative paths should resolve relative to the config file directory.

## Non-Goals

- Do not redesign artifact/deployment binding models in this note.
- Do not implement source provider lifecycle here.
- Do not store production secrets directly in JSON config.
- Do not make `client.target.kind` influence workflow source identity.
- Do not derive identity by splitting dotted source ids.
- Do not use MCP as the first-class `wf` CLI target.

## Implementation Status

First slice implemented:

- neutral `wf_config` models and loader
- filesystem server store config
- stdlib source bootstrap config is parsed and fail-fast limited to currently
  wired source ids (`wf.std`, `wf.recipes`)
- local and JSON-RPC client targets
- `wf` root overrides for `--local`, `--url`, and `--timeout`
- remote JSON-RPC client support now covers capability, draft workspace,
  artifact, deployment, and run CLI commands
- draft/artifact/deploy commands no longer fail fast for `rpc_http` targets
- `wf-rpc-server --config` support for server store and RPC HTTP transport,
  including configured RPC path

Still future:

- store-backed mutable source registry
- MCP/OpenAPI source config
- arbitrary stdlib source aliases
- `/mcp` hosting from neutral server config
- auth and SQL stores

## Next Implementation Slice

First config implementation should be small:

1. Add neutral config models for `version`, `client.target`, and `server`.
2. Support `client.target.kind = "local"` and
   `client.target.kind = "rpc_http"`.
3. Support CLI overrides for `--local` and `--url` without mutating config.
4. Support `server.transports.kind = "rpc_http"` for `wf-rpc-server`.
5. Support `server.store.kind = "filesystem"` and map it to existing file
   stores.
6. Support `server.sources.kind = "stdlib"` only, plus a compatibility bridge
   for the existing MCP config where needed.
7. Update `wf_cli.context` so local/remote target selection is explicit.
8. Keep store-backed source registry, full MCP source config migration, SQL
   stores, and `/mcp` hosting for later slices.
