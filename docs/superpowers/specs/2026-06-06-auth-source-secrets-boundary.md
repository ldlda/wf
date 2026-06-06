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
diagnostics and source registry apply summaries. Auth admin surfaces and
provider-specific auth unions are future slices.

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

The resolved credential record. The neutral API should model the record as:

- `id`: the auth ref
- `kind` or `scheme`: credential interpretation, such as `bearer`, `headers`,
  `env`, or `opaque`
- `payload`: secret-bearing implementation data
- `metadata`: non-secret annotations, optional

The neutral record should be generic enough for multiple source providers:

- upstream MCP over stdio may use `env`
- upstream MCP over HTTP may use `headers` or `bearer`
- plain HTTP/API sources may use their own header/query/body credential adapter
- Python/local sources may ignore auth or resolve it into an injected client

MCP can continue adapting the neutral record to the existing
`wf_mcp.models.AuthRecord` until the old type is retired.

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

## Open Decisions

- Whether auth ids should use the exact source id pattern or a slightly wider
  store id pattern.
- Whether the neutral auth record should be a discriminated union
  (`bearer` / `headers` / `env` / `opaque`) or keep `scheme + payload`.
- Whether local config may include development-only inline auth records. The
  recommended default is no; use a file auth store even for local development so
  the production boundary stays honest.
