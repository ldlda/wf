# Project Overview

`lda-workflow-as-struct` is a Python 3.14 prototype for `lda.chat`: an AI-assisted workflow system where an LLM plans structured workflows and a deterministic executor validates/runs them.

Main packages live under `src/`:

- `wf_core`: workflow model, validation, runtime semantics, frames, trace, interrupts, foreach, async execution.
- `wf_authoring`: ergonomic authoring layer including `@node`, `NodeSpec`, `WorkflowBuilder`, conditions, paths, and subgraph wrapping.
- `wf_mcp`: MCP broker/proxy layer for managing multiple backend MCP connections, transparent FastMCP proxying, live config/admin tools, hot reload, tool introspection, discovery/catalog snapshots, and eventual workflow build/run integration.

Important docs:

- `readme.md`: running design notes and architecture.
- `authoring_sketch.md`: authoring API direction.
- `wf_mcp_plan.md`: MCP proxy/broker/workflow integration plan.
- `scratchpad.md`: rough design history.

Current MCP direction:

- Transparent proxy mode is the main product path.
- Old broker mode remains useful for debugging/admin/catalog operations.
- Protocol-native FastMCP proxying exposes upstream tools/resources/prompts as first-class MCP capabilities.
- Current configured live connections have included `context7.default`, `serena.default`, and `everything.default`; treat `wf_mcp.config.json` as user-owned live state.
- Direct Serena is configured outside `wf_mcp` and should be preferred for code navigation/editing because it does not reset when `wf-mcp` hot-reloads.

Recent `wf_mcp` capabilities:

- Pydantic config boundary in `config_models.py`.
- Config mutation boundary in `config_manager.py`.
- Proxy validation in `proxy_validation.py`.
- Transparent proxy runtime and manual hot reload in `transparent_proxy.py`.
- Explicit name mapping in `names.py`.
- Opaque cursor pagination helpers in `pagination.py`.
- Admin tools under `wf.mcp_*`: list/get config, add/update/enable/disable/remove connection, reload config, list/get proxy tools.
- `wf.mcp_list_proxy_tools` supports `connection_id`, `query`, `limit`, and `cursor`; returns `{tools, nextCursor, total}`.
- `wf.mcp_get_proxy_tool` returns one detailed proxied tool row with schema where available.
