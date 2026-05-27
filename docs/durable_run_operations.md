# Durable Run Operations

This document describes the current operational contract for saved workflow
runs exposed through `wf.workflow.*`. It is intentionally about the platform
surface, not the lower-level scheduler internals.

## Mental Model

A deployment run is a stored execution attempt for one saved deployment.
`run_deployment` starts the attempt and returns when the workflow either:

- completes
- fails
- pauses at an interrupt
- is blocked before resume because a pinned dependency is unavailable

Every started deployment receives a stable `run_id`. That id is the handle for
inspection, bounded trace reads, and interrupt resume.

Durability is checkpointed at public stopped boundaries only. V1 does not
checkpoint after every node, during an in-flight tool call, or in the middle of
one scheduler tick.

## Primary Tool Flow

Use this flow for normal clients:

```text
wf.workflow.run_deployment
  -> wf.workflow.inspect_run
  -> wf.workflow.read_run_trace, only if debugging
  -> wf.workflow.resume_run, only if interrupted
```

`run_deployment` is the stable front door. Do not rely on saved workflows being
projected as newly-created MCP tools in the current session; many clients do
not rebuild callable schemas after `tools/list` changes.

These run tools are MCP control tools, not graph-usable workflow capabilities.
They are discovered through MCP `tools/list` or harness search-tools, not through
`wf.workflow.list_capabilities`.

## `run_deployment`

Starts one deployment execution:

```json
{
  "deployment_id": "echo.personal",
  "workflow_input": {"text": "hello"}
}
```

The compact response includes:

- `run_id`: durable handle for this execution attempt
- `status`: runtime status such as `completed`, `failed`, or `interrupted`
- `outcome`: terminal workflow outcome when available
- `error`: failed-run error text when execution failed before a terminal outcome
- `output`: projected workflow output when available
- `diagnostics`: dependency/runtime diagnostics
- `trace_count`: total trace entry count
- `latest_checkpoint_id`: latest stopped-state checkpoint when persisted

Omit `trace_range` for normal calls. Trace entries can include resolved node
inputs, outputs, and state changes, so they are debug payloads rather than
summary data.

## `inspect_run`

Reads one stopped run by `run_id` without returning trace entries:

```json
{"run_id": "run_abc123"}
```

Use this when a client already has a `run_id` and needs the current durable
summary: status, outcome/output if available, failed-run error text,
diagnostics, and checkpoint metadata.

## `read_run_trace`

Reads a bounded trace slice:

```json
{
  "run_id": "run_abc123",
  "trace_range": {"start": 0, "limit": 10}
}
```

Keep ranges small. This is the intended path for debugging failed or surprising
runs without bloating every run response.

## `resume_run`

Resumes an interrupted run:

```json
{
  "run_id": "run_abc123",
  "resume_payload": {"approved": true},
  "resume_outcome": "submitted"
}
```

Before applying the resume payload, the platform revalidates the pinned
dependency environment captured for the run. If a required source or saved child
artifact is missing, disabled, or incompatible, resume returns blocked readiness
diagnostics and does not consume the payload or append a new execution
checkpoint.

Ordinary live execution failures are not pauses. If an upstream tool disconnects
or raises during normal execution, the run fails and should be inspected/debugged
like any other failed run.

## Checkpoint Boundaries

Current stopped checkpoints are written when public run operations return:

- `run_deployment` returns completed, failed, or interrupted
- `resume_run` returns completed, failed, or interrupted

Blocked resume readiness is different: the execution state did not advance, so
the previous checkpoint remains the latest execution checkpoint.

This keeps the initial durable model simple and safe. Future protocol-native
long-running work may add task/progress integration, but it should not change
the core rule that external callers resume by `run_id`.

## Debugging Rules For LLM Clients

- Always capture `run_id` from `run_deployment`.
- Prefer `inspect_run` before reading trace detail.
- Use `read_run_trace` with explicit small ranges.
- Treat `trace_count` as metadata, not an instruction to fetch the entire trace.
- If a run failed with `trace_count: 0`, read the top-level `error` first; the
  failure may have happened before any trace entry could be emitted.
- If `resume_run` is blocked, repair the reported dependency issue and retry
  with the same `run_id`.
- If the run failed because a live source errored during execution, do not retry
  through `resume_run`; start a new run after repairing the source/problem.

## Current Limits

- No mid-call crash recovery.
- No per-node checkpoint stream.
- No protocol-native MCP Tasks integration yet.
- No dynamic saved-workflow-as-tool projection requirement.
- No automatic pause on disconnected sources; source failures are failed runs.
