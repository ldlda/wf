# Unified MCP Surface And Protocol Proxy Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge broker mode and transparent proxy mode into one MCP server surface that supports direct upstream capability projection, stable workflow/admin tools, protocol-level proxying, and local broker notifications.

**Architecture:** Use one service/config/store layer and explicit projection layers. The unified server should expose upstream tools/resources/prompts directly when enabled, expose stable local workflow/admin tools, and route bidirectional MCP protocol features through well-named proxy components rather than ad hoc tool wrappers.

**Tech Stack:** FastMCP 3.x, MCP Python SDK, existing `WfMcpService`, transparent proxy runtime, capability source registry, pytest, basedpyright.

---

## Why This Plan Exists

The current project has two partial MCP surfaces:

- Broker mode exposes stable control/workflow tools such as
  `create_workflow_artifact_from_plan`, `validate_workflow_deployment`, and
  `run_workflow_deployment`.
- Transparent proxy mode exposes upstream capabilities directly through MCP
  `tools/list` and `tools/call`.

That split is not enough. A real MCP proxy has more than tools:

- resources
- prompts
- tool calls
- notifications
- progress
- logging
- resource subscriptions
- elicitation
- sampling
- tasks
- capability/list-changed events

The unified server must not be a "tools-only proxy." It needs a protocol plan
that decides what is pass-through, what is projected, what is local, what is
unsupported, and what needs explicit client/server capability negotiation.

## Definitions

### Upstream Server

An MCP server configured as a connection, such as `everything.default`,
`context7.default`, or `serena.default`.

### Downstream Client

The MCP client connected to our server, such as Codex or MCP Inspector.

### Local Capability

A capability implemented by this project, such as `wf.workflow.run_deployment`
or `wf.admin.list_connections`.

### Proxy Capability

A capability discovered from an upstream server and projected through our
server, such as `everything.default_echo`.

### Protocol Proxy

Bidirectional routing for MCP protocol messages that are not ordinary
tools/resources/prompts list/read/get calls. Examples: sampling requests,
elicitation requests, progress notifications, task status notifications, and
resource update notifications.

## Target Surface

One MCP server instance should expose both proxy capabilities and local
capabilities.

```text
upstream tools:
  everything.default_echo
  context7.default_query-docs

upstream resources:
  everything.default.instructions.md

upstream prompts:
  everything.default.simple-prompt

stable workflow tools:
  wf.workflow.list_artifacts
  wf.workflow.create_artifact_from_plan
  wf.workflow.save_deployment
  wf.workflow.validate_deployment
  wf.workflow.run_deployment

admin tools, only when explicitly enabled:
  wf.admin.list_connections
  wf.admin.refresh_connection_catalog
  wf.admin.list_proxy_tools
  wf.admin.reload_config
```

Compatibility broker tool names such as `get_planner_catalog` can remain during
migration, but namespaced tools should become the recommended interface.

## Protocol Coverage Matrix

| MCP Feature | Near-Term Behavior | Long-Term Behavior | Notes |
| --- | --- | --- | --- |
| `tools/list` | Project upstream tools plus local workflow/admin tools | Same, with pagination/search | Already partially supported in transparent proxy and broker separately. |
| `tools/call` | Forward upstream tool calls and execute local tools | Same, with tasks/progress support | Local tools should share handlers across modes. |
| `resources/list` | Project upstream resources | Same, plus local docs/resources | Resources-as-tools remains optional compatibility. |
| `resources/read` | Forward upstream reads | Same, with subscriptions | Needs namespacing and URI/local-name mapping. |
| `prompts/list` | Project upstream prompts | Same, plus local authoring manuals | Prompts-as-tools remains optional compatibility. |
| `prompts/get` | Forward upstream prompt rendering | Same | Must preserve arguments and metadata. |
| `notifications/progress` | Forward where the SDK/server surface supports it | First-class run/proxy progress bus | Local workflow runs should emit progress later. |
| `notifications/resources/updated` | Not reliable yet | Proxy subscriptions with lifecycle tracking | Requires subscription ownership and reload behavior. |
| `notifications/resources/list_changed` | Emit local changed events after refresh/reload if supported | Also forward upstream changes | Needed when tools/resources/prompts change. |
| `notifications/tools/list_changed` | Emit after config reload/catalog refresh if supported | Same | Important for clients that refresh tools. |
| `notifications/prompts/list_changed` | Emit after prompt catalog changes if supported | Same | Same shape as tool/resource changed. |
| `notifications/message` / logging | Proxy upstream logging where supported | Add local broker logging notifications | Everything server has logging examples. |
| Elicitation | Do not fake it as a tool | Route upstream elicitation to downstream client | Requires bidirectional request routing and capability checks. |
| Sampling | Do not fake it as a tool | Route upstream sampling to downstream client | Requires downstream client sampling support. |
| Tasks | Do not invent custom primary API | Use MCP Tasks for long-running runs where supported | Custom `start_run` only as compatibility fallback. |
| Ping | Support local ping and keep upstream health separately | Same | Upstream ping should be a health/admin operation, not necessarily forwarded blindly. |

## Current Risks

- FastMCP mount/unmount lifecycle is not complete enough for safe dynamic
  unmount of all proxied capabilities.
- Transparent reload is currently best-effort.
- Bidirectional upstream requests such as elicitation/sampling require access to
  the downstream client session, not just an upstream SDK client.
- Notifications must be scoped: a resource update from `everything.default`
  should not look like a local broker config update.
- Clients vary. Codex may not immediately refresh tool lists. Inspector may show
  more protocol features. The proxy must be robust even when clients ignore
  optional notifications.

## Required Boundaries

### Shared Service Layer

`WfMcpService` or a sibling service owns:

- configured connections
- adapters
- auth/catalog stores
- capability sources
- workflow artifact store
- events

It should not own FastMCP decorators directly.

### Projection Layer

Projection modules register MCP-visible capabilities:

- upstream tools/resources/prompts
- local workflow tools
- local admin tools
- local docs/prompts/resources

Projection modules call shared handlers. They should not contain business logic.

### Protocol Routing Layer

Protocol routing handles bidirectional features:

- upstream-to-downstream elicitation
- upstream-to-downstream sampling
- upstream/local notifications
- tasks/progress
- subscriptions

This layer should be explicit. Do not bury protocol routing inside a generic
`call_tool` helper.

### Event/Notification Bus

Local events should be emitted once and then projected to:

- stored broker events
- MCP notifications where the client supports them
- future UI/dashboard streams

Examples:

```text
connection_registered
catalog_refresh_started
catalog_refresh_completed
tool_call_started
tool_call_completed
workflow_artifact_saved
workflow_deployment_saved
workflow_run_started
workflow_run_progress
workflow_run_completed
source_enabled
source_disabled
config_reloaded
```

## Prerequisites

- Complete `2026-05-12-workflow-artifact-hardening.md`.
- Keep artifact operations in shared callable functions, not duplicated
  FastMCP decorators.
- Keep config mutation/admin operations behind explicit admin exposure.
- Document client capability assumptions for elicitation, sampling, tasks, and
  notifications.
- Add tests against the fixture MCP server and the everything server where
  practical.

## Phase 1: Inventory And Adapter Reality Check

**Files:**
- Create: `docs/mcp_protocol_proxy_inventory.md`
- Inspect: `src/wf_mcp/sdk/adapter.py`
- Inspect: `src/wf_mcp/transparent_proxy/runtime.py`
- Inspect: `src/wf_mcp/broker/artifact_tools.py`
- Test: no new tests required in this phase

- [ ] List which MCP SDK APIs are currently wrapped by `BackendAdapter`.
- [ ] List which FastMCP server APIs we currently use.
- [ ] List which features everything-server exposes that we can test:
  - progress
  - logging
  - resource updates
  - elicitation
  - sampling
  - tasks
- [ ] Identify SDK gaps before implementation. If an MCP feature is not
  accessible through FastMCP/MCP SDK at our current version, document it instead
  of inventing a fake abstraction.

## Phase 2: Extract Shared Workflow/Admin Handlers

**Files:**
- Create: `src/wf_mcp/workflow_surface/handlers.py`
- Create: `src/wf_mcp/admin_surface/handlers.py`
- Modify: `src/wf_mcp/broker/artifact_tools.py`
- Modify: `src/wf_mcp/broker/tools.py`
- Modify: `src/wf_mcp/transparent_proxy/admin.py`
- Test: `tests/wf_mcp/test_broker_server.py`
- Test: `tests/wf_mcp/test_transparent_proxy.py`

- [ ] Move workflow artifact list/save/inspect/validate/run logic into shared
  handler functions/classes.
- [ ] Move admin list/refresh/config/reload logic into shared handler
  functions/classes.
- [ ] Keep broker compatibility tool names working.
- [ ] Keep transparent proxy admin tool names working.
- [ ] Do not change behavior in this phase; only remove duplicated logic and
  create a single implementation path.

## Phase 3: Unified Server Factory

**Files:**
- Create: `src/wf_mcp/server/unified.py`
- Modify: `src/wf_mcp/cli.py`
- Modify: `src/wf_mcp/broker/server.py`
- Test: `tests/wf_mcp/test_unified_server.py`

- [ ] Build one FastMCP server from `BrokerConfig`.
- [ ] Register local workflow tools with namespaced names:
  - `wf.workflow.list_artifacts`
  - `wf.workflow.create_artifact_from_plan`
  - `wf.workflow.save_artifact`
  - `wf.workflow.list_deployments`
  - `wf.workflow.save_deployment`
  - `wf.workflow.validate_deployment`
  - `wf.workflow.run_deployment`
- [ ] Register admin tools only when admin exposure is enabled.
- [ ] Project upstream tools using the transparent proxy path.
- [ ] Keep existing `broker` and `proxy` CLI modes during migration.
- [ ] Add `unified` CLI mode.
- [ ] Do not make unified default until manual Inspector/Codex tests pass.

## Phase 4: Namespacing And Collision Policy

**Files:**
- Modify: `src/wf_mcp/shared/names.py`
- Test: `tests/wf_mcp/test_names.py`
- Test: `tests/wf_mcp/test_unified_server.py`

- [ ] Use `wf.workflow.*` for stable workflow tools.
- [ ] Use `wf.admin.*` for privileged admin/control tools.
- [ ] Keep `wf.mcp.*` for workflow runtime helpers, not admin.
- [ ] Keep upstream proxy names collision-safe.
- [ ] Reject configured connection ids that collide with reserved local
  namespaces.
- [ ] Decide whether compatibility broker names remain visible by default in
  unified mode. Recommended: yes during migration, no after migration.

## Phase 5: Tool/Resource/Prompt Projection Parity

**Files:**
- Modify: `src/wf_mcp/transparent_proxy/runtime.py`
- Modify: unified server files from Phase 3.
- Test: `tests/wf_mcp/test_unified_server.py`

- [ ] Ensure upstream tools and stable workflow/admin tools both appear in
  `tools/list`.
- [ ] Ensure upstream resources appear in `resources/list` and can be read.
- [ ] Ensure upstream prompts appear in `prompts/list` and can be rendered.
- [ ] Ensure resources-as-tools and prompts-as-tools remain optional projection
  modes, not the only way to access resources/prompts.
- [ ] Ensure search/pagination includes stable local tools and upstream tools.

## Phase 6: Local Notification Bus

**Files:**
- Create: `src/wf_mcp/events/bus.py`
- Modify: `src/wf_mcp/broker/events.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Modify: unified server files from Phase 3.
- Test: `tests/wf_mcp/test_events.py`

- [x] Introduce an in-process event bus abstraction.
- [x] Keep the existing stored `McpEvent` list as one subscriber/sink.
- [ ] Add event kinds for workflow artifacts and deployments:
  - [x] `workflow_artifact_saved`
  - [x] `workflow_deployment_saved`
  - [x] `workflow_run_started`
  - [x] `workflow_run_completed`
  - `workflow_run_failed`
- [ ] Add event kinds for capability changes:
  - `source_enabled`
  - `source_disabled`
  - `catalog_changed`
  - `tools_changed`
  - `resources_changed`
  - `prompts_changed`
- [ ] Do not emit MCP notifications yet unless the server/session API is
  clearly available. This phase creates the source of truth.

## Phase 7: MCP Notifications

**Files:**
- Modify: unified server files from Phase 3.
- Modify: `src/wf_mcp/events/bus.py`
- Test: `tests/wf_mcp/test_unified_server.py`

- [ ] Emit MCP list-changed notifications when local or upstream catalogs
  change, if supported:
  - `notifications/tools/list_changed`
  - `notifications/resources/list_changed`
  - `notifications/prompts/list_changed`
- [ ] Emit local workflow progress notifications where supported.
- [ ] Proxy upstream logging notifications where supported.
- [ ] Ensure clients that ignore notifications can still poll/list manually.
- [ ] Add tests that assert notifications are requested/emitted through whatever
  FastMCP/MCP SDK surface is available. If no testable surface exists, document
  the limitation in `docs/mcp_protocol_proxy_inventory.md`.

## Phase 8: Elicitation And Sampling Routing

**Files:**
- Create: `src/wf_mcp/protocol/elicitation.py`
- Create: `src/wf_mcp/protocol/sampling.py`
- Modify: SDK adapter/session layer if supported.
- Test: `tests/wf_mcp/test_protocol_proxy.py`

- [ ] Determine how upstream MCP SDK exposes server-to-client elicitation
  requests.
- [ ] Determine how FastMCP exposes downstream client elicitation responses.
- [ ] Route upstream elicitation requests to the downstream client only when the
  downstream client advertised support.
- [ ] Route upstream sampling requests to the downstream client only when the
  downstream client advertised support.
- [ ] Preserve request ids/correlation ids so responses return to the correct
  upstream session.
- [ ] Return structured unsupported diagnostics when routing is impossible.
- [ ] Do not convert elicitation/sampling into normal tools as the primary
  behavior.

## Phase 9: Tasks And Long-Running Workflow Runs

**Files:**
- Create: `src/wf_mcp/workflow_surface/runs.py`
- Modify: unified server files from Phase 3.
- Test: `tests/wf_mcp/test_workflow_tasks.py`

- [ ] Prefer MCP Tasks for long-running `wf.workflow.run_deployment` when the
  client/server support task execution.
- [ ] Keep synchronous run behavior for short/manual local tests.
- [ ] Add a compatibility run store only if MCP Tasks are unavailable or
  insufficient for Codex/Inspector.
- [ ] Map workflow interrupts to task status such as `input_required` only after
  the runtime supports the needed resume model.
- [ ] Do not implement durable scheduling/cron here.

## Phase 10: Mode Migration

**Files:**
- Modify: `docs/wf_mcp_architecture.md`
- Modify: `docs/wf_mcp_capability_sources.md`
- Modify: `src/wf_mcp/cli.py`
- Test: `tests/wf_mcp/test_cli.py`

- [ ] Document unified mode as the recommended local mode once it passes manual
  Codex and Inspector checks.
- [ ] Keep broker/proxy modes as compatibility modes.
- [ ] Mark compatibility broker tool names as legacy once namespaced local tools
  work in unified mode.
- [ ] Do not delete compatibility modes until tests cover every important
  surface.

## Manual Verification Checklist

- [ ] Codex can list upstream tools.
- [ ] Codex can call `everything.default_echo` or equivalent upstream tool.
- [ ] Codex can call `wf.workflow.list_artifacts`.
- [ ] Codex can create an artifact from a plan.
- [ ] Codex can save a deployment.
- [ ] Codex can validate and run a deployment.
- [ ] Inspector shows upstream resources and prompts.
- [ ] Inspector shows local workflow tools with useful names/descriptions.
- [ ] If everything-server elicitation is triggered, the proxy either routes it
  correctly or returns a clear unsupported diagnostic.
- [ ] If everything-server progress/logging is triggered, the proxy either
  forwards it correctly or documents why not.

## Non-Goals

- No native `wf_core` subgraph implementation.
- No UI/dashboard implementation.
- No cron/scheduler implementation.
- No hidden conversion of every protocol feature into a tool.
- No pretending unsupported protocol features are proxied.

## Success Criteria

The project can run one local MCP server that gives an LLM client both:

- direct access to upstream MCP capabilities
- stable workflow/admin capabilities implemented by this project

The implementation must be explicit about unsupported protocol features and must
have a path to proxy elicitation, sampling, notifications, and tasks without
duplicating mode-specific logic.
