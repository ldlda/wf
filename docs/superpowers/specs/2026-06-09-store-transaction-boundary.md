# Store Transaction And Locking Boundary

Date: 2026-06-09

Status: current contract clarification

Related:

- [Persisted run/resume contract](./2026-06-03-persisted-run-resume-contract.md)
- [Workflow config targets and sources](./2026-06-03-workflow-config-targets-and-sources.md)
- [Store-backed source registry](./2026-06-03-store-backed-source-registry-design.md)

## Purpose

This spec defines what the current file-backed stores guarantee and what they
intentionally do not guarantee. The product path is now a long-lived
`wf-rpc-server`, so future agents must not assume that JSON files plus
process-local locks provide cloud-grade transaction semantics.

The short rule:

> File stores are local/dev/single-process stores. Multi-process or cloud use
> needs a transactional backend before claiming strong concurrent mutation
> safety.

## Current Store Classes

| Store | Current role | Current concurrency guarantee |
| --- | --- | --- |
| `FileWorkflowArtifactStore` | Immutable artifact versions and mutable deployments | Path validation only; simple JSON writes/deletes; no multi-operation transaction |
| `FileDraftWorkspaceStore` | Mutable draft workspaces | Per-process `RLock`; optimistic revision checks are safe inside one process only |
| `FileRunStore` | Durable stopped-run summaries and checkpoints | Per-process `RLock` around individual writes; `WorkflowRunApi.resume_run()` adds a per-run async critical section in one API process |
| `AtomicJsonRegistryStore` / `FileSourceRegistryStore` | Desired source registry document | Whole-file temp-write + replace; no compare-and-swap revision; concurrent writers are last-writer-wins |
| `FileAuthStore` | Local/dev MCP auth JSON records | Simple JSON writes/deletes; payload values are write-only through admin surfaces, but storage is plaintext local JSON |
| `FileCatalogStore` | MCP catalog snapshots | Simple JSON writes; snapshot cache, not an authoritative source of truth |
| `FileStore` | Compatibility wrapper for MCP auth + catalog stores | Delegates to `FileAuthStore` and `FileCatalogStore`; no extra locking |

## Guarantees Today

### Path Safety

All durable file stores validate ids before constructing filesystem paths. A
rejected id must not escape the configured store root.

### Single-Process Mutation Safety

Some stores protect multi-step operations inside one process:

- `FileDraftWorkspaceStore.create_workspace()` and `.replace_workspace()` keep
  duplicate/revision checks and writes under one process-local lock.
- `WorkflowRunApi.resume_run()` serializes the restore, pinned dependency
  validation, runtime resume, and checkpoint write sequence per `run_id` in one
  API/server process.

These are process-local guards. They do not coordinate with another Python
process that points at the same root.

### Atomic Single-File Replacement

Some writes use temp files followed by `Path.replace()`:

- draft workspace writes
- run checkpoint/run summary writes
- source registry whole-file writes

This reduces partially-written file risk for one file. It does not make a
multi-file operation transactional.

## Non-Guarantees Today

Current file stores do not guarantee:

- Cross-process locks.
- Compare-and-swap updates.
- Serializable transactions.
- Crash recovery across a multi-file mutation.
- Rollback when one file write succeeds and a later related write fails.
- Secret encryption at rest.
- Multi-writer safety for registry/auth/admin mutation endpoints.

## API-Layer Policies

Some correctness rules intentionally live above stores:

- `WorkflowArtifactApi.delete_artifact()` checks referencing deployments before
  deleting an artifact version. `FileWorkflowArtifactStore.delete_artifact()`
  only removes the file.
- `WorkflowRunApi.resume_run()` owns same-process resume serialization.
  `FileRunStore` only saves and loads run records/checkpoints.
- Source registry config ownership rules are enforced by the registry admin and
  connection services. `FileSourceRegistryStore` only loads/saves the desired
  registry document.

This is acceptable for current local/dev use, but a transactional backend should
move the relevant compare-and-swap guarantees into the store layer.

## Future Transactional Store Requirements

A SQL or equivalent transactional backend should provide:

- Atomic artifact/deployment mutation policies where needed.
- Draft workspace compare-and-swap by revision.
- Per-run transaction or lock for resume state transitions.
- Monotonic checkpoint sequence allocation per run.
- Source registry revision or compare-and-swap writes.
- Auth record storage suitable for the deployment environment, preferably via a
  secret manager or encrypted-at-rest store.
- Clear behavior for multiple API workers.

## Implementation Guidance

- Do not add ad hoc filesystem lock files unless a real cross-process locking
  design is specified and tested on Windows.
- Do not claim a file-backed deployment is cloud-safe just because focused tests
  pass.
- Prefer keeping local file stores simple and adding a dedicated transactional
  store implementation when the product needs multi-worker durability.
- Keep error messages explicit when an operation is blocked by policy rather
  than by missing files.
