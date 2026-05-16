# MCP Protocol Relay Design

## Goal

Make `wf-mcp` a truthful high-quality MCP proxy, not merely a tool forwarder.

The next phase is about understanding and then projecting advanced MCP protocol
behavior correctly:

- upstream notifications
- server capability advertisement
- downstream client capability relay
- later request forwarding for client-side features such as elicitation, roots,
  sampling, and task-augmented requests

The immediate next work is still **investigation first**, because advertising a
capability before we can bridge it end to end would make `wf-mcp` lie to clients.

## Current State

`wf-mcp` already has:

- a unified MCP surface
- proxy mounting with stable public names
- local list-changed notifications after reload
- ordinary tool/resource/prompt proxying
- resource-link URI rewriting for ordinary tool-returned `ResourceLink`s

Known remaining uncertainty:

- which upstream notifications FastMCP proxying already forwards
- which advanced MCP requests FastMCP can already bridge
- how initialization capabilities should be projected through a broker with
  multiple enabled upstream connections

## Core Distinction

MCP has two different capability directions.

### Server capabilities

These are advertised by `wf-mcp` to its downstream client:

- `tools`
- `resources`
- `prompts`
- `logging`
- `completions`
- `tasks`

`wf-mcp` may advertise a server capability only when the unified server can
actually serve it. The correct eventual shape is a **selected union**:

- local capabilities implemented by `wf-mcp`
- plus enabled upstream server capabilities that `wf-mcp` can proxy safely

### Client capabilities

These are advertised by the downstream client to `wf-mcp`:

- `roots`
- `sampling`
- `elicitation`
- client-side `tasks`

`wf-mcp` must not advertise these as its own server capabilities. Instead, when
an upstream server needs one of them, `wf-mcp` may relay the downstream client's
real capabilities upstream only if the corresponding request path can also be
forwarded correctly.

Examples:

- If the downstream client supports elicitation and `wf-mcp` can relay
  `elicitation/create`, an upstream server may use elicitation through the
  proxy.
- If the downstream client supports roots and `wf-mcp` can relay `roots/list`,
  an upstream server may request roots through the proxy.

## Design Principles

1. **Truthful advertisement**
   Never advertise a capability solely because some upstream declares it.

2. **Direction-aware relay**
   Keep server-side projection and client-side relay as separate concepts.

3. **Selected union, not blind union**
   Disabled upstreams and unsupported bridge paths must not inflate the public
   capability set.

4. **Protocol first, workflow later**
   This phase improves MCP proxy behavior. Workflow artifacts and planner-facing
   source models should not absorb this complexity.

5. **Use official MCP boundary types**
   Model protocol behavior with `mcp.types` capability and notification models
   where possible. Do not create parallel ad hoc protocol dicts.

6. **Consent at source connection time**
   A connected proxy source should normally be able to use the capabilities it
   declares, but powerful client-side relays should be visible to the user when
   the source is connected, similar to an app-permissions screen. Later admin UI
   may disable individual relays such as sampling, roots, or elicitation for a
   source without changing the base protocol model.

## Phase 1: Upstream Notification Inventory

### Questions

1. Does FastMCP already forward upstream:
   - `notifications/tools/list_changed`
   - `notifications/resources/list_changed`
   - `notifications/prompts/list_changed`
   - `notifications/resources/updated`
   - `notifications/message`
   - `notifications/progress`
   - `notifications/tasks/status`
2. If some notifications are forwarded, are payloads transformed correctly?
3. For resource updates, are resource URIs projected into downstream namespace
   form or leaked as raw upstream URIs?
4. Do local client surfaces we can inspect, such as Inspector or Codex, visibly
   react to the forwarded notifications?

### Method

1. Extend the fixture server only where needed to emit deterministic events.
2. Probe direct upstream behavior first.
3. Probe the same behavior through `wf-mcp`.
4. Record observed behavior in `docs/mcp_protocol_proxy_inventory.md`.
5. Do not implement forwarding until the behavior gap is proven.

### Expected Outputs

- a table of each notification kind:
  - direct upstream behavior
  - through-proxy behavior
  - payload correctness
  - whether action is needed
- regression tests for any behavior we decide to rely on

## Phase 2: Capability Negotiation Inventory

### Questions

1. What server capabilities does the current unified `wf-mcp` server advertise?
2. What server capabilities do configured upstreams advertise?
3. What downstream client capabilities are visible to `wf-mcp` during
   initialization?
4. Which advanced features can FastMCP already bridge today?
5. Which advertised upstream capabilities would be false for `wf-mcp` to expose
   until request forwarding is added?

### Expected Outputs

- a server-capability projection matrix
- a client-capability relay matrix
- a concrete list of:
  - already safe to advertise
  - bridgeable with small glue
  - unsupported until a larger forwarding subsystem exists

## Intended Architecture

Likely later modules:

```text
wf_mcp.protocol_relay/
  server_capabilities.py
  client_capabilities.py
  notifications.py
```

Conceptually:

```text
enabled upstream capabilities
        +
local wf-mcp capabilities
        |
        v
ServerCapabilityProjection
        |
        v
downstream initialize result

downstream client capabilities
        |
        v
ClientCapabilityRelay
        |
        v
selected upstream initialize requests
```

The exact module names may change after the inventory. The separation should
not:

- projecting what `wf-mcp` offers as a server
- relaying what the downstream client offers to upstream servers

Mixed upstream support should not be hidden. MCP's top-level capability object is
coarse, so `wf-mcp` should eventually expose per-source and, where useful,
per-capability detail through its admin inventory tools even when the public
server capability advertisement is a selected union.

## Feature Notes

### Elicitation

Elicitation is a client capability, not a server capability. Supporting it
through `wf-mcp` means forwarding upstream elicitation requests to the
downstream client and returning the response.

### Roots

Roots are also a client capability. They represent client-exposed filesystem or
workspace roots that a server may query. Supporting roots through `wf-mcp` means
relaying `roots/list`, not pretending `wf-mcp` itself owns roots.

### Sampling

Sampling is another client capability. It lets a server ask the client-side LLM
to generate content. This is powerful and should remain explicit because it can
cross trust boundaries.

### Tasks

Tasks exist in both directions:

- server tasks: downstream client task-augments calls into `wf-mcp`
- client tasks: upstream servers task-augment requests they send toward the
  downstream client

Treat these as separate negotiated capabilities. Do not assume “tasks supported”
is one global boolean.

### MCP Apps And `_meta.ui`

`_meta.ui` belongs to the MCP Apps extension layer, not the base server/client
capability split above. `wf-mcp` should still preserve and proxy it faithfully.

Expected proxy behavior:

- preserve upstream `_meta.ui` values
- rewrite referenced UI resource URIs when they cross a namespace boundary, the
  same way ordinary proxied resource URIs are projected
- do not rely on `_meta.ui` for core protocol correctness, because clients may
  ignore extension metadata they do not understand

Possible later use:

- `wf-mcp` may expose its own source-consent, login/logout, catalog, and toggle
  surfaces as MCP Apps UI resources/tools
- that is a UI delivery choice, not a reason to mix UI metadata into the core
  capability negotiation model

## Non-Goals For The Next Pass

- Do not blindly union all upstream capability dicts.
- Do not build a custom protocol stack around FastMCP before measuring what it
  already forwards.
- Do not solve workflow-artifact dependency validation here.
- Do not build UI controls here.
- Do not claim support for elicitation, roots, sampling, or tasks until an
  end-to-end relay path is demonstrated.

## Success Criteria

The next pass is successful when we can answer, with evidence:

1. Which upstream notifications already survive the proxy?
2. Which server capabilities may `wf-mcp` advertise truthfully today?
3. Which downstream client capabilities can safely be relayed upstream today?
4. What exact small implementation should happen next, instead of guessing?
