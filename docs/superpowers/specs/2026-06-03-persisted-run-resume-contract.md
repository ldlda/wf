# Persisted Run/Resume Contract

Date: 2026-06-03

Status: contract clarification; current V1 mostly implemented

Related:

- [Durable workflow runs and resume design](./2026-05-26-durable-workflow-runs-and-resume-design.md)
- [Durable run operations](../../durable_run_operations.md)
- [WorkflowOperationContext audit](../research/2026-06-03-workflow-operation-context-audit.md)

## Purpose

This spec sharpens the public and internal contract for persisted deployment
runs. The older durable-run design describes the broad model and implemented V1.
This document defines the invariants that future MCP, CLI, and HTTP frontends
must preserve when starting, inspecting, tracing, and resuming stored runs.

The main rule: persisted resume is a human-in-the-loop interrupt mechanism, not
a generic retry/recovery mechanism for dead external sources.

## Contract Summary

- `run_deployment` creates a durable run only after deployment validation passes.
- Every started run receives a stable `run_id`.
- Stopped runs are persisted when execution returns `completed`, `failed`, or
  `interrupted`.
- `resume_run` only resumes runs whose latest stored status is `interrupted`.
- Resume validates the pinned execution environment before mutating execution
  state.
- If pinned dependency validation fails, resume returns `blocked` readiness and
  does not consume the resume payload or write a new execution checkpoint.
- If a live tool/source fails during execution, the run fails. It is not paused.
- Trace entries are never returned wholesale by default; callers must request a
  bounded range.

## Data Model Contract

### WorkflowRunRecord

`WorkflowRunRecord` is the durable summary for one started execution attempt.

Required invariants:

- `id` is a safe run id matching `RUN_ID_PATTERN`.
- `status` is one of `interrupted`, `completed`, or `failed`.
- `resume_readiness` is:
  - `ready` for interrupted runs that are currently resumable.
  - `blocked` for interrupted runs whose pinned dependency environment is
    currently invalid.
  - `not_applicable` for completed and failed runs.
- `environment` pins the exact deployment, root artifact, and child artifacts
  captured at run start.
- `latest_checkpoint_id` points to the latest stored execution checkpoint.
- `diagnostics` stores control-plane diagnostics, especially blocked-resume
  dependency diagnostics.
- `created_at` is stable for the run id.
- `updated_at` changes when the summary changes.

### RunCheckpoint

`RunCheckpoint` is the stored execution state at a public stopped boundary.

Required invariants:

- `run_id` matches the owning `WorkflowRunRecord.id`.
- `sequence` starts at `1` and increases monotonically per run.
- `reason` matches the stopped runtime status that caused checkpoint creation.
- `state` is a validated `PersistedRunState`, not an untyped dict.
- V1 writes checkpoints only when public run operations return stopped states.

### PinnedRunEnvironment

The pinned environment must be sufficient to resume without re-reading mutable
deployment or artifact definitions:

- `deployment`: exact deployment binding snapshot used at start.
- `root_artifact`: exact root artifact snapshot used at start.
- `child_artifacts`: exact saved child artifact snapshots used at start.

Changing or deleting a deployment after a run starts must not silently redirect
or erase that run's resume environment.

## Operation Contract

### `run_deployment`

Input:

- deployment id
- workflow input
- optional trace range

Behavior:

1. Load deployment and artifact from the configured artifact store.
2. Resolve saved child artifact tree.
3. Validate root and child dependency bindings against current available
   sources.
4. If validation has blocking diagnostics:
   - return `status="unrunnable"`
   - return `run_id=None`
   - do not create a run record
   - do not write a checkpoint
5. If validation passes:
   - create pinned environment
   - execute workflow through `WorkflowRuntimeRunner`
   - persist stopped run and checkpoint
   - return compact run payload

Current implementation:

- `WorkflowRunApi.run_deployment()` follows this contract.
- `persist_stopped_run()` rejects active runtime statuses.

### `inspect_run`

Input:

- run id

Behavior:

1. Load `WorkflowRunRecord`.
2. Load latest checkpoint.
3. Decode checkpoint state into `RunState`.
4. Return compact summary:
   - status
   - run id
   - resume readiness
   - interrupt payload when present
   - outcome/error/output when present
   - diagnostics
   - trace count
5. Do not return trace entries.

Current implementation:

- `WorkflowRunApi.inspect_run()` follows this contract.

### `read_run_trace`

Input:

- run id
- trace range with `start >= 0` and `limit > 0`

Behavior:

1. Validate trace range before store lookup.
2. Load run and latest checkpoint.
3. Return compact run summary plus the bounded trace slice.
4. Return trace metadata:
   - `trace_start`
   - `trace_limit`
   - `trace_truncated`
   - `trace_count`

Current implementation:

- `WorkflowRunApi.read_run_trace()` follows this contract.

### `resume_run`

Input:

- run id
- resume payload
- resume outcome, default `submitted`
- optional trace range

Behavior:

1. Load run and latest checkpoint.
2. Reject if stored run status is not `interrupted`.
3. Decode checkpoint state into `RunState`.
4. Validate pinned environment against current available sources.
5. If validation has blocking diagnostics:
   - keep run status `interrupted`
   - set `resume_readiness="blocked"`
   - save updated run summary diagnostics
   - do not write a new execution checkpoint
   - do not apply resume payload
6. If validation passes:
   - restore saved child artifact tree from pinned environment
   - resume workflow through `WorkflowRuntimeRunner`
   - persist next stopped run/checkpoint with same `run_id`
   - return compact run payload

Current implementation:

- `WorkflowRunApi.resume_run()` follows this contract for stored interrupted
  runs and blocked dependency validation.
- `restore_interrupted_run()` rejects non-interrupted statuses.
- `mark_resume_blocked()` updates run summary without writing a checkpoint.

## Status Semantics

| Condition | Public result |
| --- | --- |
| Deployment dependencies invalid before start | `status="unrunnable"`, no run id |
| Workflow reaches explicit interrupt | `status="interrupted"`, `resume_readiness="ready"` |
| Interrupted run has broken pinned dependency before resume | `status="interrupted"`, `resume_readiness="blocked"` |
| Workflow completes | `status="completed"`, `resume_readiness="not_applicable"` |
| Workflow/runtime/tool fails during execution | `status="failed"`, `resume_readiness="not_applicable"` |

`unrunnable` is not a stored run status. It is a pre-start response.

## External Source Failure Rule

External source failure during execution is not a resumable pause.

Rationale:

- A tool may have performed a side effect before disconnecting or failing to
  return a response.
- Resuming from that point without explicit workflow semantics could duplicate
  external side effects.
- Retry/timeout fields exist in models but are not yet an implemented runtime
  policy.

Future retry support must explicitly define idempotency, unknown-side-effect
behavior, and checkpoint boundaries.

## Store Contract

`RunStore` must provide:

- save/get/list run records
- save/get/list checkpoints
- latest-checkpoint lookup
- safe run id validation

`FileRunStore` currently stores:

```text
<store-root>/runs/<run-id>/run.json
<store-root>/runs/<run-id>/checkpoints/000001.json
<store-root>/runs/<run-id>/checkpoints/000002.json
```

Current limits:

- The file store uses per-process locking only.
- It is appropriate for local/dev/single-process use.
- A long-lived API or multi-worker deployment should use a transactional store
  later.

## Frontend Contract

MCP, CLI, and future HTTP surfaces should preserve the same operation semantics:

- Start: `run_deployment`
- Inspect: `inspect_run`
- Debug trace: `read_run_trace`
- Continue explicit interrupt: `resume_run`

Frontend-specific names may differ, but they must not change:

- status meanings
- trace range requirement
- blocked resume behavior
- run id stability
- pinned environment semantics
- no-implicit-pause rule for dead tools/sources

## Current Gaps / Next Implementation Work

The core V1 behavior exists. Remaining implementation work should focus on
hardening and frontend durability:

1. **Required stores for durable API**
   - Implemented for process-local frontends through
     `wf_api.durable_context.require_workflow_stores()` and
     `wf_api.durable_context.durable_workflow_api()`.
   - `WorkflowOperationContext` still allows optional stores for MCP test and
     compatibility paths.

2. **Run listing and checkpoint listing**
   - `RunStore` can list runs/checkpoints, but the public workflow API does not
     yet expose a mature paged run catalog.
   - Add only after inspect/trace semantics remain compact and stable.

3. **Transactional backend**
   - `FileRunStore` is fine for local process use.
   - Multi-process/cloud use needs SQLite/Postgres or another transactional
     store to avoid lost writes and weak concurrent resume behavior.

4. **Resume concurrency guard**
   - Concurrent `resume_run` calls for the same interrupted run should not both
     advance from the same checkpoint.
   - V1 file store does not provide compare-and-swap semantics.

5. **Protocol-native long-running progress**
   - MCP tasks/progress or an HTTP streaming/event surface should report active
     long-running runs without bloating stopped-run responses.

6. **Retry/timeout policy**
   - Do not activate existing retry/timeout fields casually.
   - Specify idempotency and unknown-side-effect semantics first.

## Implementation Order

Recommended order after this contract:

1. Contract regression tests now cover:
   - non-interrupted `resume_run` rejection
   - deleted deployment does not erase existing run inspection
   - trace range validates before store lookup
   - blocked resume writes no checkpoint (`tests/wf_mcp/test_saved_subgraphs.py`)
2. Add a required-store context/factory for durable API surfaces.
3. Specify and implement a transactional run store backend when a cloud/API
   deployment is real.
4. Add paged run listing/checkpoint listing only after the storage boundary is
   stable.

## Non-Goals

- Do not redesign `RunState`.
- Do not checkpoint every node.
- Do not add automatic retry.
- Do not treat source death as an interrupt.
- Do not require MCP clients to reload dynamic tools to run workflows.
- Do not make HTTP/API design depend on `WfMcpService`.
