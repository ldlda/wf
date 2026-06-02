# WorkflowOperationContext Shape Audit

Date: 2026-06-03

## Summary

`WorkflowOperationContext` is the right seam for protocol-neutral workflow APIs.
After the recent cleanup it no longer depends on MCP transport classes or the old
artifact-cataloger hop. The remaining shape is usable, but it still mixes three
different concepts:

- persistence stores (`artifact_store`, `draft_workspace_store`, `run_store`)
- capability/source lookup (`capability_sources`, `specs`)
- operational side effects (`events`, `runtime`, `live_sources`)

This is acceptable for the current MCP/CLI path. Before building a durable HTTP
API or persisted resume workflow, the context should become a little more explicit
so future frontends do not inherit accidental MCP-era seams.

## Current Shape

```python
@dataclass(frozen=True, slots=True)
class WorkflowOperationContext:
    artifact_store: WorkflowArtifactStore | None
    draft_workspace_store: DraftWorkspaceStore | None
    run_store: RunStore | None
    capability_sources: Mapping[str, CapabilitySource]
    events: WorkflowEventRecorder
    specs: WorkflowSpecProvider
    runtime: WorkflowRuntimeRunner
    live_sources: WorkflowLiveSourceChecker | None = None
```

## Field Audit

| Field | Used by | Classification | Recommendation |
| --- | --- | --- | --- |
| `artifact_store` | artifacts, deployments, capabilities, runs | Real dependency | Keep, but consider grouping all stores under a `WorkflowStores` field so store availability is one explicit concern. |
| `draft_workspace_store` | drafts, artifacts | Real dependency | Keep short-term; same grouping recommendation as `artifact_store`. |
| `run_store` | runs | Real dependency | Keep; persisted resume will need this and probably stronger checkpoint APIs. |
| `capability_sources` | capabilities, deployments, runs, capability requirements | Duplicated dependency | Prefer moving reads through `specs.capability_sources`; keeping both gives two paths to the same source map. |
| `events` | artifacts, deployments, operation-context tests | Real dependency | Keep; it is protocol-neutral enough because workflow APIs call `record_workflow_event()`. |
| `specs` | drafts, capabilities | Real dependency | Keep; rename to `capabilities` or `source_index` later if it grows beyond spec lookup. |
| `runtime` | capabilities, runs | Real dependency | Keep; this is the important seam for durable runtime backends. |
| `live_sources` | deployments | Optional adapter hook | Keep optional; only live validation should touch external sources. |

## Main Issue

`capability_sources` and `specs.capability_sources` are the same concept exposed
twice. Today this is harmless because `context_from_service()` passes:

```python
specs = WfMcpWorkflowSpecProvider(service)
capability_sources=specs.capability_sources
specs=specs
```

But it creates a future maintenance trap: one API may iterate
`context.capability_sources` while another iterates
`context.specs.capability_sources`. A future backend could accidentally make those
two source maps disagree. `context.specs.get_qualified_spec()` is a related lookup
operation, but it is not the duplicate inventory path.

Recommendation: remove the top-level `capability_sources` field in a small future
slice and update consumers to use `context.specs.capability_sources`.

## Store Shape Issue

The context currently stores three optional stores directly. Each domain API has
to repeat availability checks:

- `WorkflowArtifactApi._artifact_store()`
- `WorkflowDeploymentApi._artifact_store()`
- `WorkflowDraftApi._draft_store()`
- `WorkflowRunApi._run_store()`

This is fine for MCP where stores may be disabled in test/config paths. For a
durable API, store availability is not optional: no run store means no persisted
resume.

Recommendation:

- Keep optional stores for current MCP compatibility.
- For durable API work, introduce a required `WorkflowStores` bundle at the API
  construction boundary, or a `require_stores()` helper that produces a stricter
  context for durable surfaces.

## Runtime Shape

`WorkflowRuntimeRunner` is a good seam:

- `run_workflow_from_plan()` already receives deployment, artifact, and saved
  subgraph tree.
- `resume_workflow_from_plan()` already receives pinned artifact/deployment context.

For persisted resume, this seam should stay. The durable run design should focus
on:

- how `RunStore` checkpoints are loaded
- how pinned deployment/artifact/source diagnostics are validated
- how interrupted runs are resumed across process restarts

It should not reintroduce direct MCP service access.

## Completed Context Simplification

Completed before the persisted-run spec:

1. Removed top-level `WorkflowOperationContext.capability_sources`.
2. Updated `wf_api` consumers to use `context.specs.capability_sources`.
3. Updated tests that asserted `context.capability_sources`.
4. Kept `WorkflowSpecProvider.capability_sources` as the single source inventory
   path.

Why this was first:

- It is low-risk and mechanical.
- It removes duplicate source inventory paths before durable resume depends on
  source diagnostics.
- It clarifies that source/capability lookup is a single domain dependency.

### Inline Cleanup Result

This cleanup was small enough to do inline without a separate agent plan.

1. Updated `src/wf_api/operation_context.py`.
   - Removed `capability_sources: Mapping[str, CapabilitySource]` from
     `WorkflowOperationContext`.
   - Kept `WorkflowSpecProvider.capability_sources`.

2. Updated `src/wf_mcp/broker/service/workflow_operation_context.py`.
   - Stopped passing `capability_sources=specs.capability_sources` to
     `WorkflowOperationContext`.

3. Updated `wf_api` consumers.
   - In `capabilities.py`, replaced `self.context.capability_sources` with
     `self.context.specs.capability_sources`.
   - In `deployments.py`, replaced `self.context.capability_sources` with
     `self.context.specs.capability_sources`.
   - In `runs.py`, replaced `self.context.capability_sources` with
     `self.context.specs.capability_sources`.
   - In `capability_requirements.py`, replaced `context.capability_sources` with
     `context.specs.capability_sources`.

4. Updated tests.
   - In `tests/wf_api/test_operation_context.py`, replaced assertions on
     `context.capability_sources` with assertions on
     `context.specs.capability_sources`.

5. Verification target.
   - `uv run pytest tests/wf_api -q`
   - `uv run pytest tests/wf_mcp/service/test_workflow_runtime.py tests/wf_mcp/workflow_surface -q`
   - `uv run ruff check src/wf_api src/wf_mcp/broker/service/workflow_operation_context.py tests/wf_api`
   - `uv run ruff format --check src/wf_api src/wf_mcp/broker/service/workflow_operation_context.py tests/wf_api`
   - `uv run basedpyright --level error`

## Follow-Up For Persisted Runs

After the context simplification, write the persisted run/resume spec around these
requirements:

- Run records must store enough pinned environment data to resume after process
  restart.
- Resume must validate run status/readiness before executing.
- Resume must validate pinned deployment/artifacts/source capabilities before
  executing.
- Dead external sources should not pause runs; they should produce diagnostics or
  runtime failure. Only workflow interrupts pause/resume.
- Trace output should stay paged/ranged; full trace remains opt-in.

## Non-Goals

- Do not move stores out of `wf_artifacts` in this pass.
- Do not make `live_sources` required; live checks are optional and expensive.
- Do not make `WorkflowOperationContext` depend on `wf_mcp`.
- Do not redesign `WorkflowRuntimeRunner` until the persisted-run spec needs a
  concrete change.
