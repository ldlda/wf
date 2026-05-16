# Retire Legacy MCP Modes Plan

> **Status:** current execution plan for the next cleanup pass.

## Goal

Make **unified mode** the only public MCP server mode exposed by `wf-mcp`.

`broker` mode and `proxy` mode were useful while the unified surface was being
built, but keeping all three as public launch modes now creates the wrong mental
model:

- broker mode suggests local workflow/admin tools are a separate product surface
- proxy mode suggests upstream projection is a separate product surface
- unified mode is already the real target: one server that exposes local
  capabilities and proxied upstream capabilities together

The public product should have one server mode. The implementation may still
have multiple internal concern packages.

## Existing Documentation

This replaces the migration stance in
[`2026-05-12-unified-mcp-surface.md`](2026-05-12-unified-mcp-surface.md),
which said to keep broker/proxy as compatibility modes until coverage existed.
That compatibility period is now considered complete enough to end.

Related documents already cover adjacent plans:

- [`../../wf_mcp_architecture.md`](../../wf_mcp_architecture.md)
  - concern boundaries and proxy mount lifecycle
- [`../../wf_mcp_capability_sources.md`](../../wf_mcp_capability_sources.md)
  - source model, admin/workflow exposure, source inventory
- [`../../workflow_artifacts.md`](../../workflow_artifacts.md)
  - artifacts, deployments, stable workflow control surface
- [`../../wf_mcp_proxy_reality_and_roadmap.md`](../../wf_mcp_proxy_reality_and_roadmap.md)
  - what the proxy does well today and what should remain upstream-dependent
- [`../../mcp_protocol_proxy_inventory.md`](../../mcp_protocol_proxy_inventory.md)
  - observed protocol behavior and relay gaps

No other major active plan was found to be undocumented while preparing this
pass.

## What Gets Retired

### Public CLI modes

Remove the public `serve --mode broker` and `serve --mode proxy` choices.

After this pass:

- `wf-mcp serve` runs the server surface
- users no longer choose among three product modes
- docs should describe one server behavior, not a mode matrix

### Public framing

Stop presenting broker/proxy as user-facing alternatives in docs and help text.
Where historical explanation is useful, call them legacy migration surfaces.

### Compatibility-only tests and docs

Delete or rewrite tests whose only purpose is to prove the old public mode split.
Keep behavior tests for the underlying capabilities when those behaviors still
exist through unified mode.

## What Stays

### Internal concern packages

Do **not** flatten the codebase just because the public mode split disappears.
These packages still represent useful implementation boundaries:

- `wf_mcp.broker`
- `wf_mcp.transparent_proxy`
- `wf_mcp.server`

`transparent_proxy` is already partly a legacy package name, but the code inside
it still owns real proxy-mounting mechanics used by the server. Rename or
re-home that code only as a later cleanup if the package name becomes a real
source of confusion.

### Shared services

Keep the service/config/store/runtime objects that unified mode already uses.
This pass is about removing duplicate **entrypoints**, not rewriting the
underlying architecture.

### Stable local capability names

Keep the source model and namespaces:

- `wf.workflow.*`
- `wf.admin.*`
- `wf.std.*`
- `wf.mcp.*`
- `<connection_id>.*`

The cleanup should reduce surfaces, not churn the capability vocabulary.

## Expected Code Changes

1. Simplify CLI mode selection so `serve` has one public behavior.
2. Remove or privatize old broker/proxy server launch functions that only exist
   for the retired public modes.
3. Collapse docs/help text that still describe three user-facing modes.
4. Keep implementation reuse through the existing unified server path.
5. Update tests so they assert unified behavior directly instead of branching on
   legacy mode names.

## Non-Goals For This Pass

- No full rewrite of the proxy subsystem.
- No attempt to solve generic upstream notification relay.
- No safe unmount implementation for retired FastMCP providers.
- No renaming of every legacy internal package just to match the new public
  shape.
- No workflow artifact redesign.

Those topics already have separate docs and should stay separate.

## Success Criteria

- `wf-mcp serve` has one public MCP server behavior.
- No public docs imply that broker/proxy are still supported product modes.
- Unified mode continues to expose:
  - proxied upstream capabilities
  - stable local workflow tools
  - optional admin tools
- The test suite passes with the old public mode split removed.
- Remaining roadmap docs still point to the real unresolved work instead of
  making the reader rediscover why unified mode exists.

## Follow-On Work After This Pass

Once the public surface is singular, the next useful cleanup is not more mode
work. It is easier-to-explain capability projection:

1. keep improving source inventory and admin visibility
2. continue documenting proxy relay limitations explicitly
3. build workflow-facing wrapper artifacts on top of stable sources

That keeps the system moving toward a clean platform without pretending the
proxy layer is already a perfect MCP relay.
