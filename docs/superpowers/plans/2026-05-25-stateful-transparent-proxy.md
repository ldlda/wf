# Stateful Transparent Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve one upstream MCP session for visible proxy operations made by one connected downstream client, while documenting that generic upstream list/resource notifications are still not relayed.

**Architecture:** The workflow execution pool already owns background/offline sessions. The transparent proxy should use FastMCP's `StatefulProxyClient`, which is designed for Playwright-like upstreams and scopes reuse to one downstream MCP session. This slice does not unify interactive proxy sessions with deployment runtimes and does not implement arbitrary notification rebroadcast.

**Tech Stack:** Python 3.14, FastMCP `StatefulProxyClient` and `FastMCPProxy`, pytest fixture MCP server, ruff, basedpyright.

---

### Task 1: Prove Stateful Proxy Behavior

**Files:**

- Modify: `tests/fixtures/mcp_echo_server.py`
- Modify: `tests/wf_mcp/test_proxy.py`
- Modify: `tests/wf_mcp/test_protocol_relay.py`

- [ ] Add fixture tools that store and read a value in the upstream server process.
- [ ] Add a proxy test that writes the value through one proxied request and reads it through another request in the same downstream client session.
- [ ] Change protocol-relay coverage to assert that `tools/list_changed`, `resources/list_changed`, `prompts/list_changed`, and `resources/updated` are not yet relayed. Keep string-valued logging forwarding as a strict expected-failure tripwire because the installed FastMCP `StatefulProxyClient` handler currently assumes mapping-valued MCP log data.
- [ ] Run the focused tests and confirm they fail before proxy construction changes.

### Task 2: Use FastMCP Stateful Proxy Sessions

**Files:**

- Modify: `src/wf_mcp/proxy/mounts.py`

- [ ] Replace `create_proxy(Client(...))` with `StatefulProxyClient(...)` and `FastMCPProxy(client_factory=client.new_stateful, ...)`.
- [ ] Preserve the existing `ProxyNamespace` and `ResourceLinkNamespace` transforms exactly as mounted-provider output transforms.
- [ ] Add a docstring/comment stating that FastMCP owns the interactive session lifecycle and this is intentionally separate from offline workflow execution sessions.

### Task 3: Verification

**Files:**

- Test: `tests/wf_mcp/test_proxy.py`
- Test: `tests/wf_mcp/test_protocol_relay.py`

- [ ] Run focused proxy/protocol tests.
- [ ] Run `uv run pytest -q`.
- [ ] Run `uvx ruff check`.
- [ ] Run `uv run basedpyright --level error`.

## Scope Boundary

- Interactive visible proxy calls share state within one downstream MCP client session.
- Deployment execution continues to use the owned runtime pool because scheduled/background runs may exist without a downstream client session.
- Generic upstream notification relay remains separate work. FastMCP's stateful path is intended to forward logs/progress/elicitation, but string-valued MCP log data currently exposes an upstream FastMCP handler bug and remains documented with an expected-failure test.
