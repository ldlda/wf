# `wf_mcp` Plan

This document describes the intended direction of `wf_mcp`.

The important change in scope is this:

- `wf_mcp` is not just a tool wrapper layer
- `wf_mcp` is a namespaced MCP capability broker plus workflow build/run layer

That means it should be able to face:

- human users
- client LLMs
- workflow execution services

without forcing every MCP capability to immediately become a workflow node.

## Goals

`wf_mcp` should:

- manage multiple named MCP backend connections
- persist auth/session state
- discover and cache MCP capabilities per connection
- expose namespaced catalogs to humans and LLMs
- wrap callable tool capabilities into workflow-executable `NodeSpec`s
- compile and run workflows against those capabilities
- preserve traceability between client actions, MCP backend calls, and workflow runs

## Non-goals for the first phase

- full persistence of workflow runs/jobs
- parallel workflow execution semantics beyond what `wf_core` already supports
- turning every MCP capability type into a workflow node immediately
- hiding protocol complexity by inventing vague magic abstractions

## Layering

### `wf_core`

Owns:

- workflow model
- validation
- runtime semantics
- frames
- trace
- interrupts
- foreach

Does not own:

- MCP connections
- auth/session persistence
- discovery caching
- capability brokerage

### `wf_authoring`

Owns:

- `@node`
- `NodeSpec`
- `WorkflowBuilder`
- condition DSL
- subgraph wrapping

Does not own:

- MCP transport/client logic

### `wf_mcp`

Owns:

- connection registry
- auth store
- capability discovery/cache
- namespaced capability catalog
- MCP backend adapter layer
- tool-to-`NodeSpec` wrapping
- raw plan compilation and workflow execution entrypoints
- future user-facing service/API surface

## Mental model

Think of `wf_mcp` as having two planes.

### 1. Capability proxy plane

This plane exposes what a backend MCP connection offers.

Capabilities include:

- tools
- resources
- prompts
- notifications/events
- auth metadata
- tasks
- elicitations
- app/server metadata

This plane is about discovery, namespacing, caching, and proxying.

### 2. Workflow execution plane

This plane decides which capabilities can be used inside workflows and how.

In the first phase:

- tools become executable workflow nodes
- resources and prompts are exposed in catalog/proxy APIs first
- tasks, notifications, and elicitations are modeled and surfaced first, then integrated into workflows later

## Connection identity

Connections must be first-class and stable.

Expected shape:

- `<server>.<account>`

Examples:

- `google.personal`
- `google.work`
- `github.main`
- `everything.default`

The same backend/server type may have multiple configured connections with different auth, tool availability, or environment.

## Namespacing

All exposed capabilities should be explicitly namespaced.

Examples:

- `google.personal.tool.list_files`
- `google.personal.prompt.summarize_folder`
- `google.personal.resource.drive://folder/abc`
- `everything.default.tool.echo_tool`

The exact string shape can evolve, but these properties should hold:

- globally unique
- reversible back to connection id + local capability id
- understandable by both humans and LLMs

## Current implemented slice

Already present:

- connection config and registry
- pluggable file-backed auth/catalog store
- tool catalog snapshots
- raw workflow plan compilation
- workflow execution via async runtime
- lightweight adapter protocol
- fake adapter tests
- real MCP SDK adapter for `stdio` and `streamable_http`

This is a good first vertical slice for tool execution.

## What "good proxy" means

For `wf_mcp`, "proxy" should not only mean "call tools on behalf of a client."

It should mean:

- discover backend MCP capabilities and expose them with stable namespacing
- preserve enough metadata that a client can understand what exists and how to use it
- forward or mirror backend-facing events and responses in a traceable way
- keep auth/session boundaries explicit per connection
- separate "what the backend offers" from "what becomes a workflow node"

So the proxy layer should eventually broker:

- tools
- resources
- prompts
- notifications/events
- auth-related state markers
- tasks / long-running operations
- elicitations / human-input capabilities
- app/server metadata

Not all of these need workflow semantics immediately, but they should still have a place in the package model.

## Next capability expansion

The next architectural move should be broadening the capability model beyond tools.

### Add models for

- `DiscoveredResource`
- `DiscoveredPrompt`
- `DiscoveredNotification`
- `DiscoveredTaskCapability`
- `DiscoveredElicitationCapability`
- maybe `DiscoveredAppMetadata`

These do not all need execution semantics immediately.

They do need:

- namespacing
- storage/caching
- catalog exposure

## Catalog direction

We should move from a tool-only catalog to a unified capability catalog.

The catalog should be able to expose, per connection:

- tools
- resources
- prompts
- capability metadata
- auth requirements or state markers
- freshness metadata

The client-facing catalog payload should be usable by:

- a human inspector UI
- an LLM that builds workflows
- internal service code

## Near-term implementation order

This is the intended order of work from here.

### Milestone 1: Broaden discovery models

Add normalized discovery models for:

- resources
- prompts
- notifications
- tasks
- elicitations
- app/server metadata

Outcome:

- `wf_mcp` can describe more of an MCP backend than just tools
- namespacing rules apply uniformly across capability types

### Milestone 2: Unified capability snapshots

Move from tool-only snapshots to connection-scoped capability snapshots that can store:

- tools
- resources
- prompts
- capability metadata
- freshness timestamps
- auth-state hints

Outcome:

- the catalog becomes useful to a real client or inspector
- capability caching is no longer tool-specific

### Milestone 3: Service APIs for non-tool capabilities

Expose service methods that let a client:

- inspect resources
- inspect prompts
- read capability metadata
- refresh one connection or all connections

Outcome:

- `wf_mcp` becomes a usable broker, not only a workflow launcher

### Milestone 4: Trace/event correlation

Add a light event model that can connect:

- client action
- backend MCP request/response
- workflow run/step trace

Outcome:

- better observability
- cleaner debugging
- future notification/task support has a home

### Milestone 5: Selective workflow mapping

Only after the above is stable:

- keep tools as workflow nodes
- evaluate whether prompts/resources should become helper nodes or stay catalog-only
- map elicitation to workflow interrupts carefully

Outcome:

- workflow integration grows from understood protocol behavior, not guesses

## Workflow integration policy

Not every capability becomes a workflow node right away.

### Immediate workflow nodes

- tools

### Catalog/proxy first, workflow later

- resources
- prompts
- notifications
- tasks
- elicitations

Why:

- tools already match the node call model well
- the others need more careful semantic mapping

## Elicitations and interrupts

Elicitations are especially interesting because they align with the workflow interrupt model.

Planned stance:

- expose MCP elicitation capability in catalogs first
- understand the backend semantics first
- later map appropriate elicitation flows into workflow `InterruptNode` behavior

This should be done deliberately, because workflow interrupt semantics are stronger and more structured than generic protocol-level elicitation.

## Tasks and long-running work

Tasks likely align with future run/job persistence, but they should not force that design immediately.

Near-term stance:

- surface task capability in capability catalogs
- understand the task API shape
- leave run persistence mostly out of scope for now

Future direction:

- scheduled jobs
- persisted runs
- polling or event-driven task monitoring

## Notifications and traceability

Traceability is a major requirement.

We should eventually distinguish:

- workflow execution trace
- backend MCP call trace
- client-facing event stream

The important design rule is that these should be related, but not collapsed into one giant anonymous log.

## Concrete next files

If we follow the plan above, the next likely modules are:

- `wf_mcp/discovery.py`
  - orchestrate refresh and cache policy for all capability types
- `wf_mcp/capabilities.py`
  - broader normalized capability models if `models.py` starts getting crowded
- `wf_mcp/events.py`
  - event / trace correlation shapes
- `wf_mcp/resources.py`
  - resource-facing service helpers
- `wf_mcp/prompts.py`
  - prompt-facing service helpers

Whether these stay as separate files or fold back into `models.py` / `service.py` should be driven by clarity, not purity.

## Auth and storage

Auth should remain behind a pluggable store interface.

First implementation:

- file-backed store

Expected future replacements:

- database-backed store
- encrypted local store
- secret-manager-backed store

The store should persist:

- auth records
- cached capability snapshots

It may later persist:

- saved plans/workflows
- job specs
- run metadata

## Execution model

Near-term execution stance:

- async-first at the MCP layer
- use existing async workflow runtime
- keep workflow runs mostly in memory
- leave room for future scheduled/offline execution

The important offline use case is:

- build workflow once
- execute it later without the LLM in the loop

This is closer to scheduled automation than to interactive planning.

## Public API direction

`wf_mcp` should expose two explicit entrypoints.

### 1. Convenient/build-style API

For human or higher-level service use.

Examples:

- build workflow from selected catalog items
- helper methods around namespaced tools/resources/prompts

### 2. Raw plan API

For client LLM use.

This should accept plans that:

- reference namespaced capabilities directly
- avoid raw `NodeDef` authoring
- still compile down to `wf_core.Workflow`

## Test organization direction

The current test suite is still small enough to live in two top-level files, but it will get noisy if `wf_mcp` grows beyond tools.

Recommended direction once the next capability work starts:

- `tests/wf_core/`
- `tests/wf_authoring/`
- `tests/wf_mcp/`
- `tests/fixtures/`

For `wf_mcp`, likely split by concern:

- `tests/wf_mcp/test_store.py`
- `tests/wf_mcp/test_catalog.py`
- `tests/wf_mcp/test_service.py`
- `tests/wf_mcp/test_adapters.py`
- `tests/wf_mcp/test_sdk_adapter.py`

This does not need to happen immediately, but it should happen before one `test_wf_mcp.py` turns into a junk drawer.

## Working rule for the next phase

Before making a new MCP capability executable inside workflows, first answer:

- is this primarily catalog/proxy surface, or workflow surface?
- what is the stable namespaced identifier?
- what is the trace/event story?
- does it need auth/session context?
- does it map cleanly to `wf_core`, or does it stay above it?

That rule should keep us from forcing everything through the node model too early.
