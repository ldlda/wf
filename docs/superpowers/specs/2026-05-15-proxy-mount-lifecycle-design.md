# Proxy Mount Lifecycle Design

## Goal

Reduce avoidable proxy churn during `ProxyRuntime.reload()` without pretending
that FastMCP's missing unmount lifecycle is solved.

The next step is not "fully correct hot reload." The next step is to introduce a
small mount registry that can reuse unchanged enabled upstream proxy mounts
across reloads, while keeping the current best-effort remount behavior for
changed or removed connections.

## Current State

`ProxyRuntime.reload()` currently:

1. reloads config
2. resets the server provider list to `local_provider`
3. recreates the admin mount
4. recreates a `Client`, `FastMCPProxy`, and `Namespace(connection.id)` mount for
   every enabled connection

This is simple and currently works, but it churns every upstream proxy mount on
every reload even when a connection is unchanged.

FastMCP does not currently expose a complete official mount/unmount lifecycle
that we can rely on for safe per-connection teardown. The codebase should keep
treating reload as best-effort until that exists.

## Non-Goals

- Do not implement a custom general-purpose unmount system.
- Do not claim long-lived subscriptions survive reload.
- Do not wire proxy-result `ResourceLink` rewriting into runtime as part of this
  work.
- Do not replace FastMCP's own proxy/provider internals.
- Do not change public MCP naming or config formats.

## Recommended Design

Add a dedicated module:

```text
src/wf_mcp/transparent_proxy/mounts.py
```

with two internal models:

```python
ProxyMount
ProxyMountRegistry
```

### `ProxyMount`

Owns the mount objects created for one enabled connection:

- `connection_id`
- a stable config fingerprint
- the FastMCP proxy object returned by `create_proxy(...)`
- any future lifecycle metadata we need

It should not initially promise ownership of client shutdown. FastMCP owns too
much of that behavior today through its proxy/client factory internals.

### `ProxyMountRegistry`

Owns reusable mounts keyed by `connection_id`.

Minimal responsibilities:

- return an existing mount when the enabled connection fingerprint is unchanged
- create a new mount when the connection is new or materially changed
- report which cached mounts are no longer active after a reload
- keep the stale/retired concept explicit so later cleanup can be added in one
  place when FastMCP exposes a safe lifecycle API

Initial API shape:

```python
class ProxyMountRegistry:
    def get_or_create(self, connection: ConnectionConfig, *, store_root: Path) -> ProxyMount:
        ...

    def active_mounts_for(self, config: BrokerConfig) -> list[ProxyMount]:
        ...

    def retired_connection_ids(self, active_connection_ids: set[str]) -> set[str]:
        ...
```

The exact API can shrink during implementation; the boundary is more important
than these method names.

## Reload Flow

Target flow:

```text
reload config
validate config
reset mounted providers to local_provider
mount admin surface
ask ProxyMountRegistry for active enabled mounts
mount each active proxy
publish reload events
return ProxyReloadResult
```

For an unchanged enabled connection, the same proxy mount object should be
reused across reloads.

For a changed connection, create a new mount using the new config fingerprint.

For a disabled or removed connection, stop mounting it and mark its cached mount
retired. Do not invent unsafe teardown yet.

## Fingerprint

Reuse should be based on the connection fields that affect upstream transport or
identity:

- `id`
- `server`
- `account`
- `enabled`
- `metadata`

The fingerprint must be deterministic and easy to test. It does not need to be a
cryptographic API contract; it is an internal reuse key.

## Why Not Just A Dict In `reload()`

A raw dictionary inside `ProxyRuntime.reload()` would work for the first happy
path, but it would bury lifecycle decisions in the loop:

- when a cached proxy is still valid
- when changed config invalidates it
- what "retired" means
- where future close/unmount logic belongs

That is exactly the logic likely to grow once FastMCP exposes a real lifecycle
API. A small registry keeps the future deletion/replacement localized.

## Relationship To FastMCP

FastMCP already gives us:

- `create_proxy(...)`
- `ProxyProvider`
- component-list caching
- forwarded advanced protocol behavior

We should keep using those pieces. This work should not subclass or monkeypatch
FastMCP.

If FastMCP later ships official dynamic provider unmount or proxy lifecycle
support, the registry should become thinner or disappear.

## Testing

Add focused tests before implementation:

1. unchanged enabled connection reuses the same proxy mount across reloads
2. changed connection metadata produces a new mount
3. disabled or removed connection is not remounted
4. reload public payload remains unchanged
5. existing list-changed event/notification behavior remains unchanged

Do not write tests that imply retired mounts are safely closed until that is
actually implemented.

## Deferred Work

- safe close/unmount of retired mounts
- preserving long-lived subscriptions across reload
- forwarding upstream notifications through mount lifecycle changes
- wiring `wf_mcp.proxy_results` helpers into real tool-result handling
- replacing FastMCP behavior that should be fixed upstream instead

## Investigation Result

FastMCP 3.3.0 makes unchanged-mount reuse reasonable, with caveats:

- `create_proxy_mount()` passes a disconnected `Client` into `create_proxy(...)`.
  FastMCP turns that into `client.new()` per request, so reusing a
  `FastMCPProxy` does **not** keep one permanently connected upstream session
  alive.
- `ProxyProvider` intentionally caches tools, resources, templates, and prompts
  for lookup efficiency. The default TTL is 300 seconds.
- Every explicit `list_*` call refreshes the corresponding proxy cache. Direct
  lookup paths may use a still-fresh cached list until TTL expiry.
- `FastMCP.mount()` returns no provider handle, and no public general-purpose
  unmount API was found. Parent-side provider-list rebuild is still the only
  safe visible-surface removal we currently own.

Therefore the current registry behavior is acceptable:

- reuse unchanged enabled mounts
- rebuild changed mounts
- stop remounting disabled or removed mounts
- do not claim safe close/unmount of retired mounts yet

If dynamic upstream catalogs become a practical problem, prefer a documented
refresh/invalidation policy over throwing away unchanged mounts on every reload.
