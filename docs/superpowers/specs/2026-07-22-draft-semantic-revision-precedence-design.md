# Draft Semantic Revision Precedence Design

## Goal

Make optimistic-lock behavior predictable across every content-aware draft
authoring helper. Once a request envelope is valid, a stale caller must receive
`revision_conflict` before the API inspects draft steps, routes, bindings,
schemas, or capability metadata.

## Problem

`WorkflowDraftAuthoringApi.add_step` and the focused lifecycle operations check
the expected revision before semantic preflight. Several older composed helpers
do not. They load current workspace content first, and some also query the
capability catalog, before delegating mutation to the revision-checked patch
path.

For a stale request, this can expose an error from content the caller did not
author. For example, a stale bind request can report that a step is missing or
does not use a capability instead of reporting that the workspace has advanced.
The mutation remains protected, but the public error precedence is inconsistent
and makes agent repair less reliable.

## Terms

- **Envelope validation** checks facts intrinsic to the request, without reading
  workspace content or external catalogs. An example is requiring at least one
  input or output name for `remove_draft_binding`.
- **Revision preflight** loads the current workspace and compares its revision
  with the caller's expected revision.
- **Semantic validation** reads draft content or capability metadata to decide
  whether an edit is meaningful and valid.
- **Mutation guard** is the existing revision check performed by
  `patch_draft_workspace` immediately before persistence.

## Scope

Normalize revision precedence in these `WorkflowDraftAuthoringApi` methods:

- `bind_draft`;
- `add_step_from_capability`;
- `branch_draft`;
- `handle_draft`;
- `remove_draft_route`;
- `remove_draft_step`;
- `remove_draft_binding`.

`add_step` already follows the intended order and remains the reference
behavior. Transport-facing API, JSON-RPC, remote client, and CLI signatures do
not change; they inherit the corrected behavior through existing delegation.

## Out Of Scope

This slice does not:

- add new authoring commands or request fields;
- alter JSON Patch semantics;
- change workspace storage or locking;
- combine several edits into a transaction;
- fix data-shaping, nested projection, fan-out, literal binding, or step
  metadata gaps;
- expand TypeScript JSON-RPC coverage;
- change validation precedence for malformed request envelopes.

## Canonical Precedence

Every affected operation follows this order:

1. Validate request-envelope facts that require no workspace or catalog read.
2. Load the workspace and compare the expected revision.
3. Return the canonical `revision_conflict` result immediately when stale.
4. Inspect current steps, routes, bindings, schemas, and capability metadata.
5. Build the semantic patch or determine that the edit is a no-op.
6. For a no-op, return the current workspace summary.
7. For a mutation, call `patch_draft_workspace`, which checks the revision again
   immediately before persistence.

The two revision checks are intentional. The early check establishes public
error precedence. The existing mutation-time check protects against a race in
which another writer advances the workspace after semantic preflight.

Missing workspaces keep the existing store/API behavior. Invalid request
envelopes may still fail before workspace lookup. After envelope validation,
`revision_conflict` wins over all errors derived from workspace content or the
capability catalog.

## Implementation Shape

Generalize `_workspace_if_revision_matches` from a no-op-specific helper into
the semantic-edit preflight. It continues returning either:

- the current `WorkflowDraftWorkspace`; or
- the existing conflict result produced from `summarize_draft_workspace` with
  `status: "conflict"` and a `revision_conflict` diagnostic.

Each affected method calls the helper once near its entry, returns immediately
on conflict, and uses the returned workspace for all subsequent semantic work.
This removes direct preflight calls to `_draft_store().get_workspace` and
removes repeated late checks from no-op branches. It does not introduce a
decorator, exception translation layer, or revision-aware storage API.

## Behavioral Contract

For a current revision:

- existing semantic errors remain unchanged;
- valid edits produce one new revision;
- valid no-ops remain no-ops and do not increment the revision;
- capability lookups and schema projection behave as before.

For a stale revision:

- every affected method returns `status: "conflict"`;
- the first diagnostic code is `revision_conflict`;
- no capability lookup or draft semantic validation determines the response;
- the workspace document and revision remain unchanged.

For a request that becomes stale between preflight and persistence, the
mutation-time guard returns the same canonical conflict result and does not
apply the patch.

## Testing

Add focused API tests that pair a stale revision with a competing semantic
condition for every affected method. Conditions should include, where
applicable:

- missing or non-capability steps;
- unknown capabilities;
- missing routes or route maps with invalid current shape;
- missing steps or malformed current binding lists;
- edits that would otherwise be no-ops.

Each stale case asserts the canonical conflict payload and compares the stored
workspace before and after the call to prove no mutation. Existing tests continue
to pin current-revision semantic errors, successful edits, and no-op behavior.

Add one race-oriented regression at the semantic/patch seam only if the current
suite does not already prove that `patch_draft_workspace` rejects a revision
advanced after preflight. Do not add timing-dependent concurrency tests when a
deterministic store mutation or stub can exercise the same guard.

No new RPC or CLI tests are required unless review finds a transport that
rewrites the returned conflict envelope instead of delegating it unchanged.

## Documentation And Issue State

After verification:

- check only the `Draft revision semantics` item in `ISSUES.md`;
- add a completed roadmap entry linking to the archived implementation plan;
- archive the implementation plan under `docs/historical/superpowers/plans/`.

The remaining data-shaping, step-metadata, and TypeScript parity issues stay
open.

## Success Criteria

- All seven affected semantic helpers gate workspace-derived work on revision.
- Stale revisions consistently beat competing draft-content and capability
  errors after request-envelope validation.
- Current-revision behavior and response shapes remain compatible.
- No-op edits remain revision-checked without creating a new revision.
- Mutation-time revision checking remains in place as the race-safe final guard.
- Focused tests, Ruff, formatting, basedpyright, and the relevant API/RPC/CLI
  regression suites pass.
