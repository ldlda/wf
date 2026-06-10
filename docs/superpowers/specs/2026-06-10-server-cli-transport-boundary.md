# Server CLI And Transport Boundary

Date: 2026-06-10

Status: first move slice implemented

Related:

- [Long-lived workflow API boundary](./2026-06-03-long-lived-workflow-api-boundary.md)
- [Runtime source lifecycle](./2026-06-09-runtime-source-lifecycle.md)
- [Workflow config targets and sources](./2026-06-03-workflow-config-targets-and-sources.md)
- [Project map](../../project_map.md)

## Purpose

`wf-rpc-server` currently lives in `wf_transport_rpc_http.cli`, but the module
does more than transport work. It parses server startup config, selects local
static vs MCP-backed composition, handles legacy `--mcp-config`, and starts the
JSON-RPC HTTP transport.

That made sense while JSON-RPC was the only long-lived server path. It is now
the wrong long-term ownership. Server composition belongs in `wf_server`; HTTP
JSON-RPC should stay a transport adapter around an already-built
`WorkflowServer`.

## Ownership Rule

```text
wf_server
  owns process startup policy
  owns WorkflowServer composition from wf_config / legacy inputs
  decides which transports to host

wf_transport_rpc_http
  owns JSON-RPC HTTP app/client/envelope code
  owns create_rpc_app(server)
  may provide a small serve helper for an already-built WorkflowServer
```

The script name can remain `wf-rpc-server` for compatibility, but its entrypoint
should eventually point at `wf_server.cli:main`.

## Current Shape

Current script registration:

```toml
wf-rpc-server = "wf_transport_rpc_http.cli:main"
```

Current responsibilities inside `wf_transport_rpc_http.cli`:

- parse `--config`
- parse `--store-root`
- parse legacy `--mcp-config`
- load neutral `wf_config`
- detect MCP sources
- select local/static or MCP-backed `WorkflowServer`
- select RPC bind host/port/path
- call `create_rpc_app(server)`
- call `uvicorn.run(...)`

Only the last two bullets are transport-specific.

## Desired Shape

Recommended first refactor:

```text
src/wf_server/cli.py
  Typer app for durable server startup
  parses config and startup overrides
  builds WorkflowServer through wf_server.config
  starts configured transports

src/wf_transport_rpc_http/cli.py
  compatibility shim:
    from wf_server.cli import app, main

src/wf_transport_rpc_http/app.py
  unchanged create_rpc_app(server, rpc_path="/rpc")
```

Updated script registration:

```toml
wf-rpc-server = "wf_server.cli:main"
```

Keep `wf_transport_rpc_http.cli` temporarily so tests and imports do not break
immediately.

## Implementation Status

First move slice complete:

- `wf-rpc-server` script entrypoint points at `wf_server.cli:main`.
- `wf_server.cli` owns startup config parsing and server composition.
- `wf_transport_rpc_http.cli` remains as a compatibility shim.
- `wf_transport_rpc_http.create_rpc_app(server)` remains the JSON-RPC HTTP
  transport adapter.

## Why Not Move `create_rpc_app`

`create_rpc_app(server)` is transport code:

- JSON-RPC route and method registration
- JSON-RPC error mapping
- HTTP health endpoint
- FastAPI/fastapi-jsonrpc object construction

It should stay in `wf_transport_rpc_http`. Future transports should have their
own equivalent adapter over `WorkflowServer`.

## Why Move The Typer Entrypoint

The Typer entrypoint answers process-level questions:

- Which config file is used?
- Is this local/static or MCP-backed?
- Are source providers loaded from neutral config?
- Is legacy config accepted?
- Which transports are hosted?
- Which store roles are used?

Those questions are server composition policy. They should not live in an HTTP
transport package because the same process may later host JSON-RPC HTTP, MCP
HTTP, WebSocket, or other transports together.

## Compatibility Policy

- Keep the command name `wf-rpc-server` during the move.
- Keep `wf_transport_rpc_http.cli.app` and `.main` as re-export shims for one
  compatibility window.
- Update tests to target `wf_server.cli` for behavior.
- Keep one compatibility test proving the old import path is identity-equal.
- Do not change runtime behavior in the move slice.

## First Implementation Slice

The first slice should be a pure move/refactor:

1. Create `src/wf_server/cli.py` by moving the current implementation from
   `src/wf_transport_rpc_http/cli.py`.
2. Replace `src/wf_transport_rpc_http/cli.py` with:

   ```python
   from wf_server.cli import app, main

   __all__ = ["app", "main"]
   ```

3. Update `pyproject.toml`:

   ```toml
   wf-rpc-server = "wf_server.cli:main"
   ```

4. Move CLI behavior tests from `tests/wf_transport_rpc_http/test_cli.py` to a
   server-focused test module, for example `tests/wf_server/test_cli.py`.
5. Update monkeypatch targets from `wf_transport_rpc_http.cli...` to
   `wf_server.cli...`.
6. Add a compatibility import test for `wf_transport_rpc_http.cli`.
7. Update docs and project map.

## Non-Goals

- Do not add WebSocket, MCP HTTP, or multi-transport hosting in the move slice.
- Do not change `create_rpc_app`.
- Do not remove the `wf_transport_rpc_http.cli` shim immediately.
- Do not redesign `wf_config`.
- Do not change `wf` client targeting behavior.

## Future Follow-Up

After the move, `wf_server.cli` can grow toward multi-transport hosting:

```text
wf-server --config wf.config.json
  hosts server.transports[] from config
```

`wf-rpc-server` can remain as an alias or convenience command for the RPC-only
case. The important boundary is that server startup composes transports; a
transport package does not compose the server.
