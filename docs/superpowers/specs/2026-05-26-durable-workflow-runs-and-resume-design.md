# Durable Workflow Runs and Resume Design

Status: v1 implemented; future protocol-native progress and broader recovery remain

Durable workflow runs turn the current process-local `run_deployment` /
`resume_run` behavior into platform state. The runtime already exposes the
essential execution snapshot as `RunState`; the missing boundary is a durable
run repository and a strict persisted codec for that state.

This design intentionally implements safe stopped-run persistence first. It
does not promise replay of an in-flight external side effect or arbitrary
automatic retries for failed MCP tool calls.

## Goals

- Persist workflow runs that stop as `interrupted`, `completed`, or `failed`.
- Let an explicitly interrupted deployment resume after MCP server restart or
  from another process using a durable `run_id`.
- Pin the artifact, deployment binding environment, and prepared dependency
  environment used by a run when it starts.
- Revalidate pinned dependencies before a persisted interrupted run continues.
- Provide compact run inspection and bounded trace retrieval suitable for MCP
  clients and a future dashboard.
- Keep run persistence outside `wf_core` and separate from auth/catalog storage.
- Leave room for finer-grained checkpoints without requiring them in v1.

## Non-Goals

- Do not pause automatically when an MCP connection or tool call fails.
- Do not implement automatic retry or timeout behavior in this slice.
- Do not checkpoint after every node or scheduler tick in v1.
- Do not add time travel, replay from arbitrary historical state, or state edits.
- Do not add LangGraph-style cross-run memory available to arbitrary nodes.
- Do not move artifact, deployment, auth, or catalog storage into one store.

## Current State

`wf_core.RunState` already owns the data necessary to continue a stopped run:

- workflow input, committed state, terminal outcome, and public output
- trace entries
- frames and ready-frame queue
- runtime scopes and lineage writes
- current execution cursor
- error information
- interrupt request and nested subgraph interrupt route

`wf_mcp.workflow_surface.handlers.ActiveWorkflowRun` currently retains the
remaining platform context only in memory:

- `WorkflowDeployment`
- `WorkflowArtifact`
- `RawWorkflowPlan`
- `RunState`

That class is the temporary seam to replace. It is not evidence that run state
belongs inside MCP: MCP is merely one front door for a workflow platform
concern.

## Relationship to LangGraph Persistence

LangGraph distinguishes execution checkpoints from a general memory store:

- A **checkpointer** stores execution snapshots so interrupted graphs can be
  inspected and resumed.
- A **store** provides arbitrary memory shared across threads/runs.

This design needs the first concept only. A workflow run/checkpoint repository
is appropriate now; cross-run node-accessible memory is separate future work.

## Platform Ownership

The conceptual ownership remains:

```text
wf_core
  workflow execution models and runtime

wf_artifacts
  immutable workflow definitions and deployment contracts

wf_platform (future extraction target)
  runs, checkpoints, schedules, run history, UI/admin policy

wf_mcp
  MCP exposure of platform operations
```

The current package graph already has `wf_artifacts` depending on `wf_platform`
for capability/source refs. Placing typed run records in `wf_platform` while
they snapshot `WorkflowArtifact` and `WorkflowDeployment` would introduce a
cycle or weaken those fields into untyped dictionaries. V1 should therefore
place run models/store code under a focused `wf_artifacts.runs` subpackage.
Names and module boundaries must make later extraction straightforward if the
artifact/platform dependency direction is reorganized. Do not expand
`wf_mcp.storage.Store`, which owns MCP auth/catalog snapshots with a different
lifecycle.

## Domain Model

### Workflow Run

A `WorkflowRun` identifies one execution attempt of one pinned deployment
environment.

Required information:

```text
WorkflowRun
  id: stable run id
  deployment_id
  artifact_id
  artifact_version
  status: interrupted | completed | failed
  resume_readiness: ready | blocked | not_applicable
  created_at
  updated_at
  latest_checkpoint_id
  pinned_environment
  diagnostics
```

`unrunnable` is not a run status. It is a pre-start response when deployment
dependency validation fails before an execution begins.

### Run Checkpoint

A `RunCheckpoint` is a stored stopped-state snapshot of a run.

```text
RunCheckpoint
  id
  run_id
  sequence
  reason: interrupted | completed | failed
  created_at
  persisted_run_state
```

V1 writes a checkpoint only when a public run operation stops:

- `run_deployment` returns an interrupted, completed, or failed execution.
- `resume_run` returns an interrupted, completed, or failed execution.

V1 does not guarantee recovery after a process crash while a node or external
tool call is in progress.

### Pinned Execution Environment

Runs must not reinterpret bindings when resumed. The persisted run pins:

- root artifact snapshot, in addition to its exact id/version
- deployment snapshot, including the binding selection used at start
- resolved saved child artifact snapshots, in addition to exact child versions
- dependency contract information needed to revalidate those bindings

A configuration edit after the run starts does not silently redirect a paused
run from one MCP account/source to another. If a future repair/migration flow
allows rebinding a stopped run, that must be explicit and auditable.

Snapshotting artifact contents is required by the current implementation:
`FileWorkflowArtifactStore` stores versioned paths but does not yet reject an
overwrite of an existing version. A durable run must not depend on a later
filesystem overwrite preserving the graph it originally executed. A future
store that enforces immutable artifact writes may still retain snapshots as an
audit record.

## Persisted Runtime Codec

`RunState.to_dict()` is useful for inspection but is not by itself a durable
storage contract. Nested dataclasses, enums, path types, reducer refs, workflow
refs, scopes, lineages, and interrupt routes must round-trip through a
validated persisted model or codec.

The storage codec must:

- serialize the full stopped `RunState` needed for resume
- restore equivalent enum/path/ref/dataclass values rather than loose dicts
- reject corrupted or unsupported stored state with a clear diagnostic
- be versioned or structured so later checkpoint migrations are possible
- contain JSON-compatible values only at the persistence boundary

Core should own the execution-state codec shape because it understands
`RunState`. The platform store should persist the codec output, not reconstruct
runtime internals itself.

## Lifecycle Semantics

### Start

```text
validate deployment and resolved dependencies
if blocking diagnostics:
  return unrunnable response; do not create a run

pin resolved execution environment
execute workflow
persist WorkflowRun and stopped-state checkpoint
return run summary
```

Completed and failed runs are persisted as well as interrupted runs. This makes
inspection and debugging useful immediately without materially increasing
storage implementation complexity.

### Intentional Pause

Only a declared `InterruptNode` creates a resumable pause.

```text
InterruptNode reached
  -> RunStatus.INTERRUPTED
  -> persist interrupted checkpoint
  -> resume_readiness = ready when pinned dependencies validate
```

Interrupts raised within a native saved child subgraph retain the typed
interrupt route already carried in `RunState`, so durable resume re-enters the
original child scope.

### Resume

```text
load run and latest interrupted checkpoint
verify run is interrupted and resumable
revalidate exact pinned dependency environment
if dependency validation fails:
  keep run status interrupted
  set resume_readiness = blocked
  return dependency diagnostics without mutating execution state
else:
  resume from restored RunState
  persist next stopped-state checkpoint
```

When a missing or disabled pinned dependency returns, a later explicit
`validate_run`, `inspect_run`, or `resume_run` may report it ready again.
There is no background auto-resume.

### Failure

An ordinary runtime exception, MCP transport failure, or tool connection loss
while execution is running fails the run.

This is deliberately distinct from interruption. An external tool may have
completed a side effect before losing its response; automatically presenting
that condition as safely resumable could duplicate effects.

```text
tool/source failure during execution
  -> status = failed
  -> persist failed checkpoint and error details
  -> no automatic resume
```

Recovery from such failures must later be declared in workflow semantics, such
as explicit outcome mapping or a carefully specified retry policy.

## Dependency Validation Semantics

Dependency status has three positions:

| Point | Result |
| --- | --- |
| Before start | `unrunnable`; no execution run is created |
| At a declared interrupt | `interrupted`; persisted and potentially resumable |
| Before resume when pinned dependency is broken | run remains `interrupted`, `resume_readiness = blocked`, diagnostics returned |
| During live execution | `failed`, unless future workflow logic explicitly models recovery |

Dependency diagnostics are platform/control-plane information, not graph
outcomes. They must not be forced through a user's declared `ok` / `error`
workflow outcome routes.

## Public Surface

The stable MCP workflow surface should eventually expose:

```text
wf.workflow.run_deployment
  starts a run; always returns a stable run_id once execution starts

wf.workflow.resume_run
  resumes one durable interrupted run after pinned dependency validation

wf.workflow.inspect_run
  returns compact run status, readiness, terminal output/outcome,
  interrupt summary, diagnostics, and trace_count

wf.workflow.read_run_trace
  returns a bounded trace slice selected by range
```

The response style stays progressive:

- start/resume returns compact stopped-state status
- inspect returns detail needed for decision making
- trace is fetched only in bounded slices

## Store Interface Direction

Use a dedicated protocol rather than expanding MCP auth/catalog persistence:

```text
RunStore
  save_run(run)
  get_run(run_id)
  save_checkpoint(checkpoint)
  get_latest_checkpoint(run_id)
  list_runs(query, cursor, limit)
  read_checkpoints(run_id, cursor, limit)
```

The initial backend may be file-based under the configured application store
root:

```text
.wf_mcp_store/
  auth/
  catalog/
  workflows/
  deployments/
  runs/
    <run_id>/
      run.json
      checkpoints/
        000001.json
        000002.json
```

The protocol must allow later SQLite/Postgres storage without changing the MCP
surface or core runtime model.

## Retry and Timeout Fields

The codebase already carries `retry` and `timeout_seconds` fields in node/draft
models, plus a runtime `retry_count` context field. They are not currently an
implemented runtime policy.

For durable-run v1:

- treat these fields as declared-but-unsupported behavior
- do not interpret failed MCP calls as retryable
- do not add recovery checkpoints around external calls
- document clearly when a future slice implements retry/timeout semantics

A future retry design must distinguish known-not-executed failures from
unknown-side-effect failures, or require idempotency/author-provided policy.

## Testing Strategy

Implementation tests must cover:

- persisted `RunState` round-trip for root interrupts
- persisted `RunState` round-trip for native child-subgraph interrupts
- a completed run saved with output and terminal outcome
- a failed run saved with error details
- server/service recreation followed by successful `resume_run`
- pinned dependency disabled after pause: resume is blocked and state remains
  interrupted and unmodified
- pinned dependency restored: later resume succeeds
- changed live configuration cannot silently redirect pinned source bindings
- transport failure during execution produces failed, not interrupted
- trace retrieval is ranged and reports total trace count

## Future Expansion

Once stopped-run persistence is stable:

1. Add checkpoint writes at explicit scheduler-safe boundaries if crash
   recovery during long execution is needed.
2. Investigate MCP tasks/progress reporting for live long-running operations.
3. Design retry/timeout semantics explicitly rather than activating dormant
   fields casually.
4. Consider replay/time-travel only after external side-effect semantics are
   documented.
5. Add general cross-run memory separately if nodes need it; it is not a
   replacement for checkpoints.

## Implemented V1

Durable stopped-run snapshots now provide:

1. A validated persisted `RunState` codec.
2. `WorkflowRunRecord`, `RunCheckpoint`, and `RunStore`.
3. Checkpoints for interrupted, completed, and failed public executions.
4. Durable resume retrieval instead of process-local `_active_runs`.
5. Compact `inspect_run` and bounded `read_run_trace` tools.
6. Pinned dependency revalidation before interrupted runs resume.

This delivers durable human-in-the-loop execution and run inspection while
preserving the correctness boundary that live external-call failures are not
safe implicit pauses.
