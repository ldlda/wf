# Store-Backed Source Registry Design

Related:

- [Runtime source lifecycle](./2026-06-09-runtime-source-lifecycle.md)

## Purpose

The workflow server now has neutral read-only workflow, source-admin, and
admin/config surfaces. The next platform step is safe mutation: adding,
updating, disabling, and removing server-owned sources/connections without
editing config files by hand.

This spec defines the persistence and merge rules before mutation commands are
implemented.

## Current State

`wf_mcp.storage.FileStore` persists:

- auth records under `auth/<connection_id>.json`
- catalog snapshots under `catalog/<connection_id>.json`

It does not persist the connection/source registry itself. Current connection
definitions come from config and live in memory through `ConnectionService`.

Neutral workflow config currently has:

- `client.target`: local or JSON-RPC HTTP target
- `server.store`: filesystem store root
- `server.transports`: server-hosted transports
- `server.sources`: static built-in sources such as `wf.std` / `wf.recipes`

Legacy MCP config still has `connections`.

## Goals

- Persist server-owned dynamic source/connection changes across process restarts.
- Keep config useful as bootstrap and deployment-time infrastructure.
- Preserve structural source identity. Source ids are explicit ids, not parsed
  from dotted display names.
- Make mutation validation explicit and fail-fast.
- Keep disabled/missing sources visible as diagnostics, not silent deletion from
  deployments or runs.
- Avoid turning catalog snapshots into source definitions. Catalogs are observed
  capability state; registry entries are desired configuration state.

## Non-Goals

- No UI design.
- No auth-secret format redesign beyond referencing existing auth records.
- No SQL store in the first implementation.
- No automatic source id inference from provider/account strings.
- No workflow lifecycle changes.

## Registry Model

The persisted registry stores desired source/connection definitions:

```json
{
  "version": 1,
  "sources": [
    {
      "id": "github.work",
      "kind": "mcp",
      "enabled": true,
      "provider": "github",
      "account": "work",
      "profile": null,
      "transport": {
        "kind": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {}
      },
      "auth_ref": "github.work",
      "metadata": {}
    }
  ]
}
```

### Source Identity

`id` is the stable workflow-facing concrete source id. Examples:

- `github.work`
- `github.personal`
- `everything.default`
- `wf.std`

The id is not decomposed for meaning. The structured fields carry meaning:

- `provider`: logical provider/server family, such as `github`
- `account`: account/workspace name, such as `work`
- `profile`: optional variant under one provider/account
- `transport`: concrete connectivity details

Transport belongs to the concrete source entry, not only to the provider. The
same provider/account may need different connection transports in different
server deployments, and one source id must carry the exact runtime transport the
server should use.

### Source Kinds

Initial persisted kind:

- `mcp`: upstream MCP source

Bootstrap-only / built-in kinds can remain config/code-owned for now:

- `stdlib`
- `docs`
- `admin`

Do not persist built-in `wf.std`, `wf.recipes`, or `wf.admin` in the dynamic
registry unless/until there is a real need.

## Store Shape

Add a registry store beside existing auth/catalog files:

```text
<store_root>/
  auth/
  catalog/
  source_registry.json
```

Why one file first:

- The registry is small.
- Writes can be atomic by writing a temp file then replacing it.
- Whole-file validation is simple.
- It matches config-like semantics.

Future stores can expose the same interface over SQL or another durable backend.

## Merge Rules

On server startup:

1. Load built-in sources from code/config.
2. Load config-defined connections/sources.
3. Load `source_registry.json`.
4. Merge into one desired source map.
5. Hydrate runtime `ConnectionService` / `SourceCatalogService` from that map.

Current v1 precedence:

1. Built-in reserved ids always win for reserved ids.
2. Config-defined entries win over dynamic registry entries with the same id.
3. Dynamic registry entries fill in ids not present in config.

Rationale: this first pass is conservative. Config is deployment bootstrap and
operator-controlled, so dynamic store state should not secretly override source
definitions checked into deployment config before source ownership policy exists.

Long-term ownership policy:

- Config remains valid for bootstrap, dev/test portability, disaster recovery,
  and operator-managed static sources.
- Store-backed registry is the normal mutable desired-state authority for
  server-owned dynamic sources.
- Config should not win forever by default. Future source definitions should
  distinguish at least two config ownership modes:
  - `locked`: config owns the id. Registry add/update for that id is rejected
    or remains explicitly shadowed.
  - `seed`: config creates or hydrates the initial store entry when missing,
    then the store owns later admin changes.

Until that policy exists in models and startup merge, same-id config entries
continue to shadow store entries for safety.

Duplicate behavior:

- Duplicate ids inside one config or one registry file are validation errors.
- A registry entry with the same id as config is allowed but ignored with a
  diagnostic/event in v1. Future `seed` config entries should instead allow the
  store entry to become authoritative after seeding.
- A registry entry using a reserved id is invalid.

## Mutation Rules

Initial mutation commands should target the registry only, not config:

- add source
- update source
- enable/disable source
- remove source

Rules:

- Mutations validate the full registry before saving.
- Mutations write one atomic registry replacement.
- Enabling a source requires validation of source shape and transport config.
- Optional live validation can be requested, but ordinary connection failure
  should not corrupt registry state.
- Removing a source deletes desired registry state only. It does not delete old
  catalog/auth files in the first pass.
- Disable is preferred over remove when deployments may still reference the
  source.

## Runtime Semantics

If a deployment references a missing/disabled/unreachable source:

- validation reports diagnostics (`source_missing`, `source_disabled`,
  `source_unreachable`)
- run start fails or is blocked by validation
- existing deployments are not rewritten
- ordinary dead tools/sources do not become interrupts or pauses

## Events

Registry mutations should emit broker/server events:

- `source_registered`
- `source_updated`
- `source_enabled`
- `source_disabled`
- `source_removed`
- `source_registry_ignored_config_shadow`

Events are read-only through the existing `WorkflowAdminApi`.

## API Surfaces

Do not add mutation to `WorkflowApiSurface`.

Likely surfaces:

- `WorkflowSourceAdminSurface`: read-only source list/inspect already exists
- future `WorkflowSourceRegistrySurface`: mutating registry operations
- `WorkflowAdminSurface`: read-only connections/status/events already exists

The mutation surface may live in `wf_api` if it remains protocol-neutral. If it
becomes transport/provider-heavy, split it into a platform admin package instead
of bloating workflow lifecycle APIs.

## First Implementation Slices

### Slice 1: Registry Models and File Store

- Add Pydantic registry models.
- Add `SourceRegistryStore` protocol.
- Add `FileSourceRegistryStore`.
- Validate duplicate ids and reserved ids.
- Atomic write for filesystem store.
- No runtime wiring yet.

Status: complete. The first implementation lives in `wf_mcp.source_registry`
because the entry shape is MCP-specific: connection-id validation, reserved
source ids, and concrete MCP transports all come from the MCP broker layer.

### Slice 2A: Generic Registry Mechanics

Status: complete. Generic registry mechanics live in `wf_api.source_registry`;
MCP source entries and transports remain in `wf_mcp.source_registry`.

- Move protocol-neutral registry mechanics to `wf_api.source_registry`.
- Keep MCP source entries, MCP transports, connection-id parsing, and reserved
  id rules in `wf_mcp.source_registry`.
- Generic mechanics include safe registry-id validation, duplicate-id checking,
  a registry-store protocol, and a small atomic JSON model store.
- Do not wire registry state into startup yet.

This resolves the current location tension without pretending an MCP source
entry is a generic workflow source. Future non-MCP source families should reuse
the generic mechanics and define their own entry models.

### Slice 2B: MCP Entry Conversion

Status: complete. `registry_entry_to_connection_config()` converts MCP registry
entries to broker `ConnectionConfig` values while preserving metadata, `auth_ref`,
profile, transport details, enabled state, and source-registry origin.

- Add explicit conversion from `McpSourceRegistryEntry` to `ConnectionConfig`.
- Preserve structural fields such as provider, account, profile, transport,
  enabled state, auth reference, and metadata.
- Do not merge config and registry yet.

### Slice 3: Startup Merge

Status: complete. Broker/service construction now loads `source_registry.json`,
merges config-defined connections with dynamic registry entries, preserves config
precedence, and emits `source_registry_ignored_config_shadow` for shadowed
registry entries.

### Slice 4: Read Registry Through Admin

Status: complete for API/transport/CLI plumbing. `WorkflowSourceRegistryApi`
provides neutral read-only access to desired registry entries. JSON-RPC methods
`workflow.admin.source_registry.list` and `.inspect` are registered. CLI commands
`wf admin registry list` and `wf admin registry inspect` are available for
targets that expose the surface. Local/static servers report
`source_registry_unavailable` instead of pretending to have an empty registry.
No mutations added. `wf source list` behavior remains unchanged. Concrete
MCP-backed `WorkflowServer` construction remains future work.

### Slice 5: Mutating RPC/CLI

Status: complete. Add/update/enable/disable/remove operations are available
through `WorkflowSourceRegistryApi`, JSON-RPC methods, and CLI commands.
Mutations target persisted desired registry state only; config files, auth
records, and catalog snapshots are not mutated. Config-shadowed add is rejected
in v1. Remove requires `--confirm` in CLI. Local/static servers report
unavailable for mutation commands. Concrete MCP-backed `WorkflowServer`
construction remains future work.

### Slice 6: Config Ownership Policy

Status: complete. MCP broker config connections now support
`source_config_ownership="locked" | "seed"`. `locked` preserves v1 shadowing.
`seed` materializes missing store entries and lets existing registry entries
own future runtime state.

### Apply Semantics

Registry mutation commands write desired persisted state. They do not implicitly
change the running server. `apply_registry_changes` is the explicit boundary
that reconciles desired registry state with the current runtime source graph.

The apply operation mirrors config reload reconciliation by calling the same
connection/source merge logic. It preserves `locked` config shadowing and `seed`
config handoff rules. It does not mutate config files, remount public MCP proxy
providers, or handle upstream credential prompts.

## Open Questions

- Should dynamic registry entries support non-MCP transports in v1, or only MCP
  stdio/HTTP?
- Should auth references be required for sources that need auth, or optional
  until live validation?
- Should strict mode fail on `locked` config/store conflicts, or keep them as
  explicit shadow diagnostics?
- Should disabled registry entries still hydrate as disabled sources so inspect
  can explain them, or stay only in registry/admin output?

## Recommendation

Implement Slice 2A next. Keep it independent from runtime startup so the
generic/MCP split becomes solid before it affects source hydration.

Catalog/auth remain observed/secret state; the new registry is desired source
configuration state. Generic registry mechanics can live in `wf_api`, but
provider-specific entries and conversion into broker runtime connections stay
with the package that owns that provider.
