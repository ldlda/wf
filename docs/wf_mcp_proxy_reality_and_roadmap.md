# wf_mcp Proxy Reality And Roadmap

This document is the current practical position for `wf-mcp` proxy work after
the first live protocol investigations. It is intentionally more opinionated
than [`mcp_protocol_proxy_inventory.md`](mcp_protocol_proxy_inventory.md),
which remains the fact log.

## Current Position

`wf-mcp` should keep using FastMCP as its proxy foundation.

FastMCP is already giving us substantial value:

- ordinary proxied tools work
- listed resources and resource templates work
- resource reads through namespaced URIs work
- proxy mounting, transforms, and client/server plumbing are real leverage
- selected advanced forwarding paths already exist upstream, including roots,
  sampling, elicitation, logging, and progress

But FastMCP proxying is not currently a fully transparent MCP relay. We should
not block the rest of the product on making it one.

## What Works Today

### Proxy Surface

- normal `tools/list` and `tools/call`
- tool title, description, and JSON-schema metadata
- listed resource and resource-template namespacing
- namespaced resource reads
- current dotted tool names and slash-separated resource URI namespaces

### Local wf-mcp Behavior

- local admin reload emits downstream list-changed notifications for the current
  request session
- internal event projection for local tool/resource/prompt changes exists
- unchanged mounted connections are reused across reload through
  `ProxyMountRegistry`

### Local Workarounds We Intentionally Own

- tool-returned `ResourceLink` URIs are rewritten by
  `wf_mcp.proxy_results`

This workaround is worth owning because it is bounded, local, well-tested, and
deletable if FastMCP gains a general result-transform hook later.

## Confirmed Gaps

### 1. Generic upstream notifications are not relayed downstream

Confirmed on 2026-05-16 with fixture-backed tests and the runnable
`docs/f/` repros.

The upstream-side client sees:

- `notifications/tools/list_changed`
- `notifications/resources/list_changed`
- `notifications/prompts/list_changed`
- `notifications/resources/updated`
- `notifications/message`

The downstream client connected through the proxy sees none of them.

This is currently tracked upstream as:

- `PrefectHQ/fastmcp#4161`

The closest related upstream issue found so far is:

- `PrefectHQ/fastmcp#4124`
  - downstream cancellation is not propagated upstream

Together, these suggest FastMCP's proxy layer forwards selected protocol
features but is not yet a general bidirectional protocol relay.

### 2. Tool-returned ResourceLinks were not rewritten

FastMCP namespaced listed resources correctly, but ordinary `ResourceLink`
content inside proxied tool results kept raw upstream URIs.

This is currently tracked upstream as:

- `PrefectHQ/fastmcp#4154`

We already have the local workaround described above.

### 3. Session resource behavior is still unresolved

The Everything server's session resource returned by
`gzip-file-as-resource` was not readable through the proxy during the live
probe. Direct reading also failed in that Codex session, so this is not yet
classified as a proxy bug.

### 4. Tasks remain unsupported

Task-required tools are discoverable but not usable through our current surface.
This is a real protocol-support gap, not an ordinary tool-call issue.

### 5. LLM harnesses may not adopt dynamic tool changes reliably

`wf-mcp` can expose new tools after reload, but that does not guarantee an agent
harness rebuilds the callable tool schema for the model turn that is already in
flight.

Observed on 2026-05-17 with Codex:

- `playwright.default` was enabled
- `wf.admin.reload_config` remounted it successfully
- `wf.admin.list_proxy_tools` showed the new tools
- after reconnect, the Codex UI showed `playwright.default.browser_navigate`
- the model turn still did not receive a callable binding for that new tool

This is a common Codex / Claude Code / general LLM harness class of problem, not
just a proxy-server problem. The host may refresh `tools/list` for display or
inspection while model invocation still uses a previously materialized tool
schema.

Design consequence: do not make core workflows depend on newly registered MCP
tools becoming callable immediately. Prefer stable control tools plus explicit
inspection/call paths when the client must work reliably across harnesses.

When the exposed tool catalog grows large or changes often, FastMCP's search
transform is a good mitigation: keep a stable pinned control/workflow spine
visible, and use `search_tools` plus its synthetic `call_tool` for the changing
rest of the catalog. Do not confuse that synthetic raw-tool caller with a
future workflow-capability test tool; testing a normalized `NodeSpec` contract
is a separate operation and should also remain pinned once it exists.

## What Is Probably Not Worth Owning Yet

Do **not** rush to implement a custom full protocol relay for:

- generic upstream notification forwarding
- cancellation propagation
- resource subscription ownership
- task execution
- broad replacement of FastMCP proxy internals

Those are cross-cutting lifecycle problems. They touch request identity,
session ownership, namespace projection, reconnect behavior, and possibly
transport-specific semantics. A small local workaround here would likely turn
into a second proxy framework by accident.

## Decision Rule For Local Workarounds

Own a local workaround only when all are true:

1. the gap blocks near-term product work
2. the behavior boundary is narrow and testable
3. the workaround can live in one isolated module family
4. deleting it later will be cheap if upstream support lands

`ResourceLink` rewriting passed that test.

Generic notification relay does not pass it yet.

## Roadmap From Here

### Continue Building Now

These areas do not require a perfect transparent proxy:

1. capability and source inventory surfaced clearly to users and LLM clients
2. admin/control UX over configured sources
3. workflow artifacts, deployments, and dependency validation
4. `wf.std` and `wf.mcp` authoring/runtime affordances
5. LLM-facing workflow construction using existing sources

These keep compounding even if upstream proxy transparency remains imperfect for
a while.

### Keep Investigating Selectively

Continue protocol investigation only where it changes near-term design:

1. which upstream capabilities are safe to expose publicly
2. what per-source capability metadata the admin surface should show
3. whether session resources matter to workflows we actually want soon
4. whether a specific advanced FastMCP forwarding path is needed by a real
   source before we depend on it

### Revisit Later

Come back to deeper proxy work when one of these becomes true:

- FastMCP ships official support we can adopt
- a concrete user-facing workflow needs the missing protocol feature
- the missing feature becomes small enough to isolate cleanly

## Near-Term Recommended Next Work

The best next repo work is **not** another proxy internals expedition.

Recommended order:

1. expose richer source/capability inventory through the public/admin surfaces
2. keep per-source protocol support visible rather than pretending all mounted
   sources are equivalent
3. continue the workflow/platform layer that consumes those sources

That preserves the long-term proxy ambition without letting it dominate the
project before the upstream foundation is ready.
