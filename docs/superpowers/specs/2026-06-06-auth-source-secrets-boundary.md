# Auth / Source Secrets Boundary

## Purpose

The durable server path now has neutral workflow, source-admin, admin, source
registry, and JSON-RPC surfaces. Source definitions can be configured or stored,
but upstream credentials still live in the old MCP broker shape:
`AuthRecord(connection_id, scheme, payload)`.

This spec defines the next boundary before expanding auth behavior. The
important choice is interface first: file-backed auth is one implementation, not
the architecture.

## Status

Slice 1 implements the neutral auth record/store protocol and MCP compatibility
bridge. Slice 2 surfaces missing explicit auth refs through live source
diagnostics and source registry apply summaries. Slice 3 exposes read-only auth
admin summaries without secret payload values. Slice 4 adds local/dev file-backed
auth save/delete through neutral admin, JSON-RPC, and CLI. Responses still
expose only ids, schemes, metadata, and payload keys; secret payload values
remain write-only. Slice 5 introduces typed stored auth records and MCP auth
binding while preserving old `scheme + payload` compatibility input.

Next auth work should replace the stringly `scheme + payload` record with typed
auth variants and source-owned auth binders. Google Drive's remote HTTP MCP
server is the motivating proof: it is an OAuth-backed MCP source at
`https://drivemcp.googleapis.com/mcp/v1`, but the platform should model this as
generic refresh-token auth applied as HTTP bearer headers, not as a Drive-specific
transport or FastMCP-specific object.

This is not a complete auth product yet. The implemented runtime path only wires
existing MCP-compatible auth records into source calls, diagnostics, and
read-only admin summaries. There is still no user-facing auth creation/mutation
surface, OAuth flow, production secret manager, provider-specific display model,
or full retirement of the legacy `wf_mcp.models.AuthRecord` compatibility type.

## Current State

Existing MCP runtime auth is connection-id keyed:

- `wf_mcp.models.AuthRecord` has `connection_id`, `scheme`, and opaque
  `payload`.
- `wf_mcp.storage.FileStore` persists auth at
  `<store_root>/auth/<connection_id>.json`.
- `UpstreamTransportService` resolves auth with
  `load_auth(connection.id)` before upstream MCP operations.
- Runtime adapters interpret payload keys such as `headers`, `token`, and `env`.

Newer source models already carry references:

- `wf_config.McpSourceConfig.auth_ref`
- `wf_mcp.source_registry.McpSourceRegistryEntry.auth_ref`
- conversion helpers copy `auth_ref` into `ConnectionConfig.metadata`

The mismatch is that source definitions can point at `auth_ref`, but runtime
still effectively assumes `source_id == auth_id`.

## Goals

- Decouple source identity from credential identity.
- Keep secrets out of normal source registry and workflow config documents.
- Make missing or invalid auth visible as diagnostics before upstream calls when
  possible.
- Preserve current MCP runtime behavior while adding a neutral interface that
  future stores, cloud secret managers, and UI/admin surfaces can implement.
- Keep the first implementation small: no OAuth flow, browser login, encryption
  scheme, or production secret backend is required for v1.

## Non-Goals

- No OAuth/OIDC authorization-code flow in this slice.
- No cloud secret manager integration in this slice.
- No encrypted-at-rest file format decision in this slice.
- No automatic credential discovery from environment variables.
- No change to workflow artifacts or deployment binding semantics.

## Concepts

### Source Id

The workflow-facing concrete source id, such as `github.work` or
`everything.default`. It identifies a capability source and is used in
deployment bindings.

### Auth Ref

The credential reference stored on a source definition. Examples:

- `github.work`
- `github.personal`
- `github.shared-ci`

`auth_ref` is not a secret. It is a stable lookup key into an auth store. It may
match a source id for simple cases, but code must not rely on that.

`auth_ref` deliberately carries no provider semantics. It does not say "MCP",
"HTTP bearer token", "Python callback", or "OAuth account". It only names a
credential record. The source provider decides how to interpret the resolved
record.

### Auth Record

The resolved credential record. The current implementation uses `id`,
`scheme`, `payload`, and `metadata`, where `payload` is stringly and
provider-specific. That shape was useful as a bridge, but the next model should
be a discriminated union inside a stored record wrapper:

```python
StoredAuthRecord(
    id="google.drive.personal",
    auth=OAuthRefreshTokenAuth(
        kind="oauth_refresh_token",
        client_id="...",
        client_secret=SecretStr("..."),
        refresh_token=SecretStr("..."),
        token_url="https://oauth2.googleapis.com/token",
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.file",
        ],
    ),
    metadata={},
)
```

Initial variants should stay small and verifiable:

- `bearer`: one access token, materialized as `Authorization: Bearer ...` by
  HTTP-capable source providers.
- `headers`: explicit secret HTTP headers.
- `env`: explicit secret environment variables for stdio-style providers.
- `oauth_refresh_token`: refresh-token credential that can mint access tokens
  and materialize as bearer headers.
- `opaque`: compatibility escape hatch for records that only a specific source
  provider understands.

`oauth_refresh_token` is provider-neutral. Provider-specific behavior belongs in
metadata, token-refresher configuration, or the source-owned binder; do not name
the auth kind `google_oauth` just because Google Drive MCP is the first proof.

Typed auth records should still be generic enough for multiple source providers:

- upstream MCP over stdio may use `env`
- upstream MCP over HTTP may use `headers`, `bearer`, or `oauth_refresh_token`
- Google Drive MCP is an HTTP MCP source that should consume OAuth-derived
  bearer headers
- plain HTTP/API sources may use their own header/query/body credential adapter
- Python/local sources may ignore auth or resolve it into an injected client

MCP can continue reading compatibility `scheme + payload` records until the old
type is retired, but new saves should prefer typed auth variants.

Auth records must not own source-specific behavior. Source providers choose
which auth variants they support and how to materialize them.

### Auth Binding

Auth binding converts a stored auth record into runtime credentials for a
specific source provider and transport. Auth records are generic and durable;
binding is source-owned.

```python
@dataclass(frozen=True)
class BoundMcpHttpAuth:
    headers: Mapping[str, str] = field(default_factory=dict)
    auth: httpx.Auth | None = None

@dataclass(frozen=True)
class BoundMcpStdioAuth:
    env: Mapping[str, str] = field(default_factory=dict)

class McpAuthBinder(Protocol):
    async def bind_http_auth(
        self,
        auth: StoredAuthRecord | None,
    ) -> BoundMcpHttpAuth: ...

    async def bind_stdio_auth(
        self,
        auth: StoredAuthRecord | None,
    ) -> BoundMcpStdioAuth: ...
```

Provider ownership:

- `wf_sources_mcp` implements `McpAuthBinder`.
- Future `wf_sources_openapi` implements its own binder shape.
- `wf_sources_python` should ignore or reject auth until it has a real injection
  model.

The MCP binder may return `headers` or `httpx.Auth` for HTTP MCP because that is
what the MCP HTTP client glue needs. This is intentionally MCP-specific and not
reused as a universal platform DTO. Storage should not persist runtime objects
such as `httpx.Auth` or FastMCP OAuth helpers.

The concrete client glue remains small and local to `open_mcp_session`:

```python
bound = await binder.bind_http_auth(auth)
http_client = httpx.AsyncClient(headers=bound.headers or None, auth=bound.auth)

bound = await binder.bind_stdio_auth(auth)
env = {**transport.env, **bound.env}
```

For Google Drive MCP, `oauth_refresh_token` should be handled by an MCP
auth binder:

```text
refresh token -> access token -> Authorization: Bearer ... -> HTTP MCP session
```

The token refresher should be injected behind a small protocol so unit tests can
verify behavior without Google network or browser login.

First implementation policy: refresh on MCP session open. Do not refresh per
request in the first slice, and do not add token caches or locks until a real
long-lived-session expiry case proves they are needed. If a stateful MCP session
outlives the access token and the server validates each later operation, add a
refresh-aware HTTP auth implementation as a follow-up.

### Auth Store

The interface that resolves references:

```python
class AuthStore(Protocol):
    def load_auth(self, auth_ref: str) -> AuthRecord | None: ...
```

Future admin and UI work can extend this with list/save/delete, but the runtime
dependency should start as read-only. That keeps workflow execution independent
from credential mutation policy.

## Resolution Rules

For every upstream source:

1. Read `auth_ref` from the source definition.
2. If `auth_ref` is absent, pass no auth to the upstream adapter.
3. If `auth_ref` is present, resolve it through `AuthStore.load_auth(auth_ref)`.
4. If the record is missing and the source operation requires auth, return a
   diagnostic before invoking upstream I/O.
5. If the record is present, pass it to the source provider's auth adapter.
   Provider-specific code adapts the record to runtime shape.

MCP compatibility adapter:

- If a connection has `metadata["auth_ref"]`, load that auth ref.
- Otherwise load by `connection.id` to preserve existing behavior.
- Convert the neutral record into `wf_mcp.models.AuthRecord` for current MCP
  adapters.

This fallback is temporary compatibility. New code should carry and resolve
`auth_ref` explicitly.

Provider boundaries:

- `wf_sources_mcp` / current `wf_mcp` code owns MCP auth adaptation.
- Future HTTP/API source packages own HTTP/API auth adaptation.
- Future Python source packages own Python/client injection rules.
- `wf_api` and `wf_config` should not learn each provider's credential payload
  semantics beyond carrying ids, records, and diagnostics.

## Diagnostics

Use stable diagnostic codes so CLI, MCP, and future UI clients can explain the
problem without parsing messages:

- `auth_missing`: the source requires auth but has no `auth_ref`.
- `auth_not_found`: the source has `auth_ref`, but the auth store has no record.
- `auth_invalid`: a record exists but cannot be adapted or validated.

Suggested repair hints:

- Add an auth record for the referenced id.
- Update the source registry/config `auth_ref`.
- Bind the deployment to another source.

Live source checks and source registry apply should prefer diagnostics over late
adapter failures. Runtime invocation can still fail if the upstream server
requires auth but does not declare that requirement.

## Read-Only Display

Read-only admin surfaces may show that an auth record exists, but they must not
promise provider-specific display until auth records are concrete variants.

For the current `scheme + payload` bridge, safe display should stay intentionally
minimal:

- `id`
- `scheme`
- `metadata`
- `payload_keys`

Do not expose payload values. Do not promise token hints, OAuth subjects,
expiry, scopes, header names, or environment-variable names as the stable
neutral contract yet. Once auth records become a discriminated union, each
variant can own a richer safe display method:

- bearer auth can show token presence or a redacted hint
- headers auth can show safe header names
- env auth can show safe environment variable names
- OAuth auth can show subject, expiry, scopes, and refreshability
- opaque auth can stay limited to scheme and payload keys

## Store Shape

The current filesystem store can remain:

```text
<store_root>/
  auth/
    <auth_ref>.json
```

This is a dev/local adapter, not the contract. A SQL store or secret manager can
implement the same `AuthStore` interface later.

File-backed records should keep using the existing path-safety validation rules.
Do not inline secret payloads into:

- `wf_config` source entries
- `source_registry.json`
- workflow artifacts
- deployment records

## Implementation Slices

1. **Neutral auth model and store protocol**
   - Add protocol-neutral auth record/store types under `wf_api` or a focused
     neutral package.
   - Add tests proving `wf_api` imports no `wf_mcp`.
   - Keep current runtime behavior unchanged.

2. **MCP compatibility adapter**
   - Make MCP auth loading prefer `ConnectionConfig.metadata["auth_ref"]`.
   - Fall back to `connection.id` for legacy records.
   - Keep `wf_mcp.models.AuthRecord` as the adapter output until MCP internals
     are split further.

3. **Diagnostics**
   - Surface missing/invalid auth through source apply and live deployment
     checks.
   - Add source ids and auth refs to diagnostic payloads, but never include
     secret payload data.

4. **Auth admin surface**
   - Add read-only auth status first: ids, schemes/kinds, and metadata only.
   - Add mutation only after deciding local-dev file behavior versus production
     secret-manager behavior.

5. **Typed auth records**
   - Introduce a stored auth record wrapper with a discriminated `auth.kind`.
   - Keep a compatibility parser for old `scheme + payload` records.
   - Prefer writing the new shape for new local/dev saves.
   - Keep payload values write-only in admin and CLI responses.

6. **Source-owned auth binder**
   - Add `BoundMcpHttpAuth`, `BoundMcpStdioAuth`, and `McpAuthBinder`.
   - Move MCP header/env interpretation behind `McpAuthBinder`.
   - Keep source providers responsible for declaring supported auth variants.

7. **OAuth refresh-token support**
   - Add `oauth_refresh_token` variant and injected token refresher protocol.
   - Apply OAuth records as bearer headers for HTTP-capable MCP sources.
   - Unit-test with a fake refresher; do not require Google or browser login.

8. **Google Drive MCP smoke**
   - Configure a normal HTTP MCP source:
     `https://drivemcp.googleapis.com/mcp/v1`.
   - Bind it to an OAuth refresh-token auth record.
   - Verify `list_tools` or a harmless read-only tool through the durable server
     path when local credentials are available.

## Open Decisions

- Whether auth ids should use the exact source id pattern or a slightly wider
  store id pattern.
- Resolved direction: move the neutral auth record to a discriminated union
  (`bearer` / `headers` / `env` / `oauth_refresh_token` / `opaque`) inside a
  stored record wrapper. Keep `scheme + payload` only as compatibility input
  until existing local files are migrated or retired.
- Whether local config may include development-only inline auth records. The
  recommended default is no; use a file auth store even for local development so
  the production boundary stays honest.
