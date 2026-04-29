# Project Overview

`lda-workflow-as-struct` is a Python 3.14 prototype for `lda.chat`: an AI-assisted workflow system where an LLM plans structured workflows and a deterministic executor validates/runs them.

Main packages live under `src/`:
- `wf_core`: workflow model, validation, runtime semantics, frames, trace, interrupts, foreach, async execution.
- `wf_authoring`: ergonomic authoring layer including `@node`, `NodeSpec`, `WorkflowBuilder`, conditions, paths, and subgraph wrapping.
- `wf_mcp`: MCP broker/proxy layer for managing multiple backend MCP connections, discovery/catalog snapshots, transparent FastMCP proxying, config/admin tools, and eventual workflow build/run integration.

Important docs:
- `readme.md`: running design notes and architecture.
- `authoring_sketch.md`: authoring API direction.
- `wf_mcp_plan.md`: MCP proxy/broker/workflow integration plan.
- `scratchpad.md`: rough design history.

Current MCP direction: transparent proxy mode is the main product path. Old broker tools remain useful for debugging/admin/catalog operations, but protocol-native FastMCP proxying exposes upstream tools/resources/prompts as first-class MCP capabilities.