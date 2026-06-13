# lda.chat workflow platform

This repository is building a workflow runtime for AI-assisted digital work.
Agents discover capabilities, author typed workflows, validate them, deploy
them, and run them through a deterministic executor. The LLM plans; the runtime
executes.

## Quick Start

```powershell
uv run wf --help
uv run wf --local cap list --format ids
uv run wf --local cap inspect wf.std.constant
uv run wf --local cap call wf.std.constant --input '{"value":"hello"}'
uv run pytest -q
```

Run the durable JSON-RPC server:

```powershell
uv run wf-rpc-server --config wf.config.json --host 127.0.0.1 --port 8765
uv run wf --url http://127.0.0.1:8765/rpc cap list --format ids
```

## Current Shape

```text
wf_cli
  -> wf_transport_rpc_http or local target
  -> wf_server
  -> wf_api
  -> wf_core / wf_artifacts / wf_sources_*
```

- `wf_core`: deterministic graph/runtime kernel.
- `wf_authoring`: Python authoring helpers and `NodeSpec` creation.
- `wf_api`: workflow application surface shared by local and remote frontends.
- `wf_server`: durable server composition boundary.
- `wf_transport_rpc_http`: JSON-RPC-over-HTTP client/server transport.
- `wf_sources_mcp`: upstream MCP source implementation and persistent runtime.
- `wf_mcp`: MCP frontend, legacy entrypoints, proxy/admin glue, and compatibility
  shims during extraction.
- `wf_cli`: command-line frontend over local or remote workflow APIs.

## Start Reading

- [docs/README.md](docs/README.md): documentation index.
- [docs/wf_cli.md](docs/wf_cli.md): CLI lifecycle, remote targets, and common
  diagnostics.
- [docs/runbooks/python-source.md](docs/runbooks/python-source.md): trusted
  project-local Python source setup and workflow-run flow.
- [docs/source_architecture.md](docs/source_architecture.md): source package
  boundaries and terms such as source, tool, workflow capability, resource, and
  prompt.
- [docs/wf_api_architecture.md](docs/wf_api_architecture.md): current API,
  server, transport, and source package boundaries.
- [docs/project_map.md](docs/project_map.md): package map, entrypoints, examples,
  and verification commands.
- [docs/current_roadmap.md](docs/current_roadmap.md): active next work.

Historical design notes and completed implementation plans live under
[docs/historical/](docs/historical/). The previous long top-level running-design
note is intentionally no longer the project front door; current model details
are split across the docs index above.
