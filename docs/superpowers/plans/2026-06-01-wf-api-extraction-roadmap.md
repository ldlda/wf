# wf_api Extraction Roadmap

> **For agentic workers:** This is an architecture roadmap, not a deterministic implementation checklist. Use it to choose and scope future focused implementation plans. Do not execute multiple slices at once.

**Goal:** Extract a protocol-neutral workflow application API from `wf_mcp` while preserving current process-local behavior and avoiding a large semantic rewrite.

**Architecture:** `wf_api` becomes the long-lived in-process application service layer. `wf_mcp`, `wf_cli`, and future HTTP/UI adapters call `wf_api`; `wf_api` must not import `wf_mcp`.

**Current State:** Slice 1 introduced `wf_api.WorkflowApi`,
`wf_api.WorkflowApiBackend`, and `wf_mcp.broker.service.WfMcpWorkflowApiBackend`.
Both CLI and MCP workflow tools now call `WorkflowApi`; `wf_api` imports no
`wf_mcp` modules. `WorkflowSurfaceHandlers` still contains the existing
operation implementation and still depends on `WfMcpService`, but it is now
MCP-owned backend plumbing rather than the public application API.

Slice 3 moved the protocol-neutral workflow helpers into `wf_api`: constants,
capability refs, wrapper hints, next actions, raw workflow plan model, runtime
dependency resolution, saved subgraph preparation, and durable run lifecycle
helpers. The old `wf_mcp.workflow_surface.*` module paths remain compatibility
shims for those helpers.

**Current Constraint:** `WorkflowSurfaceHandlers` is large and still carries
most workflow-surface logic. Slice 1 fixed dependency direction only; later
slices can split and rename once the boundary is correct.

---

## Target Shape

```text
wf_core       = workflow execution kernel
wf_authoring = Python authoring sugar and NodeSpec construction
wf_artifacts = saved workflow/deployment/run models and stores
wf_platform  = source/capability/event platform primitives
wf_api       = process-local workflow application service/use cases
wf_mcp       = MCP adapter and MCP runtime/proxy/admin surface
wf_cli       = CLI adapter
```

Desired dependency direction:

```text
wf_cli ─┐
        ├──> wf_api ───> wf_artifacts / wf_platform / wf_core / wf_authoring
wf_mcp ─┘
```

Forbidden dependency direction:

```text
wf_api -> wf_mcp
```

Process-local behavior remains the default:

```python
config = load_broker_config(path)
service = build_service_from_config(config)
api = WorkflowApi(WfMcpWorkflowApiBackend(service))
```

No FastAPI, daemon, socket, auth redesign, or network boundary is required for this extraction.

## Slice 1: Dependency Direction Cleanup

### Goal

Make both CLI and MCP call a protocol-neutral `WorkflowApi`, while `WorkflowApi`
does not import `wf_mcp`.

### Allowed

- Create `src/wf_api/`.
- Add `WorkflowApiBackend` protocol.
- Add `WorkflowApi`.
- Add `WfMcpWorkflowApiBackend` adapter around `WfMcpService`.
- Update `wf_cli.context` to construct `WorkflowApi`.
- Update MCP workflow tool registration to use `WorkflowApi`.
- Keep compatibility aliases if existing imports need a transition.
- Keep payloads and behavior unchanged.

### Not Allowed

- Do not split `WorkflowApi` by domain yet.
- Do not move every helper module yet.
- Do not rename events yet.
- Do not redesign stores.
- Do not add FastAPI.
- Do not change response payloads.
- Do not change command/tool names.

### Implemented Shape

```text
src/wf_api/
  __init__.py
  backend.py       # WorkflowApiBackend high-level operation protocol
  service.py       # WorkflowApi thin delegating facade

src/wf_mcp/workflow_surface/
  handlers.py      # existing implementation; now backend plumbing
  tools.py         # MCP adapter; calls WorkflowApi

src/wf_mcp/broker/service/
  workflow_api_backend.py  # WfMcpWorkflowApiBackend
```

`WorkflowApiBackend` currently exposes high-level workflow operations that mirror
the old workflow surface (`list_capabilities`, `create_draft_workspace`, `run_deployment`,
and so on). That is intentionally not the final clean domain API. It keeps
behavior and payloads stable while introducing the dependency seam. Later slices
can replace selected `dict[str, Any]` method boundaries with stronger domain
models after callers are routed through `WorkflowApi`.

Live source validation remains behind the MCP backend adapter because it touches
MCP connections, adapters, and auth. `wf_api` owns the operation name, but the
current backend owns the live-check implementation.

### Success Criteria

- `wf_api` imports no `wf_mcp` modules. **Done.**
- `wf_cli` uses `WorkflowApi`. **Done.**
- `wf_mcp.workflow_surface.tools` uses `WorkflowApi`. **Done.**
- Existing MCP workflow-surface tests pass. **Done at implementation time.**
- Existing CLI tests pass. **Done at implementation time.**
- Behavior and payloads are unchanged. **Intended and guarded by tests.**

## Slice 2: Stabilize API Names And Compatibility Shims

### Goal

Make naming honest without breaking callers.

### Docs-First Current Slice

Before renames, document the new ownership:

- `wf_api.WorkflowApi` is the application-facing process-local API.
- `wf_api.WorkflowApiBackend` is the high-level backend protocol.
- `wf_mcp.broker.service.WfMcpWorkflowApiBackend` adapts the current MCP service
  stack into the backend protocol.
- `wf_mcp.workflow_surface.WorkflowSurfaceHandlers` is legacy/internal
  implementation plumbing. New adapter code should not treat it as the canonical
  API.

### Later Likely Work

- Rename `WorkflowSurfaceHandlers` usage to `WorkflowApi` in tests and CLI code.
- If a class rename is chosen, keep a temporary import shim:

```python
from wf_api import WorkflowApi as WorkflowSurfaceHandlers
```

- Update docs to say:

```text
MCP tools and CLI commands are adapters over wf_api.
```

- Rename test fixture helpers from `handlers(...)` to `api(...)` if useful.

### If/Then

- If shims create confusion, remove them quickly after imports are migrated.
- If too many downstream imports still expect `WorkflowSurfaceHandlers`, keep the shim for one release/work session and document it as deprecated.

### Success Criteria

- New code imports `WorkflowApi`.
- Old name remains only in compatibility modules or is gone.
- Docs describe `wf_api` as the application service layer.

## Slice 3: Move Protocol-Neutral Workflow Surface Modules

### Goal

Move helper modules that are not MCP-specific out of `wf_mcp.workflow_surface`.

### Completed Moves

```text
wf_mcp.workflow_surface.constants             -> wf_api.constants
wf_mcp.workflow_surface.refs                  -> wf_api.refs
wf_mcp.workflow_surface.wrapper_hints         -> wf_api.wrapper_hints
wf_mcp.workflow_surface.next_actions          -> wf_api.next_actions
wf_mcp.models.RawWorkflowPlan                 -> wf_api.models.RawWorkflowPlan
wf_mcp.workflow_surface.runtime_dependencies  -> wf_api.runtime_dependencies
wf_mcp.workflow_surface.saved_subgraphs       -> wf_api.saved_subgraphs
wf_mcp.workflow_surface.run_lifecycle         -> wf_api.run_lifecycle
```

The full `wf_mcp.workflow_surface.models` module did not move. It still holds
MCP tool request/response schemas such as `TraceRange` and workflow tool result
models. Move or split those only when the MCP schema boundary is clearer.

### If/Then

- If a module imports MCP connection/adapters/auth, do not move it in this slice.
- If imports become circular, leave a shim in the old location and move one module at a time.
- If a helper is really platform vocabulary, consider `wf_platform` instead of `wf_api`.

### Success Criteria

- `wf_api` owns protocol-neutral workflow API helpers. **Done.**
- `wf_mcp.workflow_surface` keeps MCP adapter/schema code plus compatibility
  shims. **Mostly done.**
- Tests still pass with import-only or near-import-only changes. **Done at
  implementation time.**

## Slice 4: Split The Big API By Domain

### Goal

Reduce the large `WorkflowApi` class after the package boundary is correct.

### Slice 4A: Operation Context Scaffolding

Do not move handler methods first. `WorkflowSurfaceHandlers` methods currently
reach through `self.service` for stores, capability sources, events, live source
calls, adapter lookup, and catalog helpers. Moving method bodies before defining
that dependency surface would either make `wf_api` import `wf_mcp` or produce a
fake split where every domain service still depends on the whole MCP service.

First introduce a small protocol-neutral operation context in `wf_api`:

```text
src/wf_api/
  operation_context.py  # protocols/dataclass for stores, sources, events, live calls
```

The exact names may change, but the context should answer these questions:

- How does workflow API code access artifact, draft workspace, deployment, and run stores?
- How does it read planner-visible `CapabilitySource` objects?
- How does it record artifact/deployment/run lifecycle events without importing MCP event types?
- How does it perform live source validation or live capability calls without importing MCP adapters/auth?
- Which existing `WfMcpService` helpers are still required by moved domain methods?

`WfMcpWorkflowApiBackend` or another MCP-owned adapter can build this context
from `WfMcpService`. The context is scaffolding only: Slice 4A should not move
capability/draft/artifact/deployment/run method bodies yet and should not change
public payloads.

### Candidate Shape

```text
src/wf_api/
  service.py        # facade that composes domain services
  operation_context.py
  capabilities.py
  drafts.py
  artifacts.py
  deployments.py
  runs.py
```

Possible facade:

```python
class WorkflowApi:
    capabilities: CapabilityApi
    drafts: DraftApi
    artifacts: ArtifactApi
    deployments: DeploymentApi
    runs: RunApi
```

Compatibility can keep flat methods:

```python
async def list_capabilities(...):
    return await self.capabilities.list_capabilities(...)
```

### Planned Domain Split Order

After Slice 4A proves the operation-context seam, split method groups in small
behavior-preserving slices:

#### Slice 4B: Drafts First

Move stateless draft and draft workspace operations first:

```text
validate_draft
compile_draft
patch_draft
list_draft_workspaces
create_draft_workspace
get_draft_workspace
delete_draft_workspace
validate_draft_workspace
patch_draft_workspace
set_draft_name
set_draft_route
set_step_input_map
set_step_output_map
create_minimal_draft_workspace
```

Reason: drafts mostly use the draft workspace store, workflow draft compiler,
wrapper hints, and deterministic patch helpers. They have the lowest live-source
and durable-runtime coupling.

Leave `create_draft_workspace_from_capability` in the MCP-backed handler during
4B. It depends on `inspect_capability`, wrapper hints, and capability source
inspection, so it should move with either a small follow-up capability bootstrap
slice or Slice 4E.

#### Slice 4C: Artifacts And Deployments

Move saved artifact and deployment operations next:

```text
list_artifacts
save_artifact
create_artifact_from_plan
create_artifact_from_draft
create_artifact_from_workspace
create_wrapper_from_workspace
inspect_artifact
list_deployments
inspect_deployment
save_deployment
delete_deployment
validate_deployment
```

Reason: this group is store-heavy and introduces dependency validation, saved
subgraph tree resolution, and event recording. It should move only after drafts
prove the context seam.

#### Slice 4D: Runs

Move run lifecycle operations after artifacts/deployments:

```text
run_deployment
resume_run
inspect_run
read_run_trace
```

Reason: runs are runtime-sensitive. They touch durable checkpoints, pinned
dependency environments, resume readiness, prepared saved subgraphs, trace
slicing, and compact next-action guidance. This should not be the first method
move.

#### Slice 4E: Capabilities Last

Move workflow capability operations last:

```text
list_capabilities
inspect_capability
call_capability
create_draft_workspace_from_capability
```

Reason: capabilities look simple but are the messiest boundary. They combine
planner-visible source inventory, wrapper artifacts, direct wrapper calls,
external live source calls, source visibility, and schema/wrapper hints.
`create_draft_workspace_from_capability` also belongs here because it is driven
by `inspect_capability` wrapper hints. Keep them in the MCP-backed
implementation until the other domain services are stable.

#### After Slice 4E: Helper Promotion Cleanup

Once the handler is mostly a compatibility adapter, promote duplicated helper
symbols into stable homes instead of leaving long-term cross-domain private
imports:

```text
raw_plan_from_artifact                 -> wf_api.artifact_plans or wf_artifacts
artifact_capability_id                 -> wf_api artifact/capability refs helper
available_sources_from_capability_sources -> wf_api source snapshot helper
```

This should be a cleanup slice, not part of 4E unless required to avoid circular
imports or behavior drift.

### If/Then

- If the context starts mirroring all of `WfMcpService`, stop and split it into
  smaller protocols rather than creating a new god object.
- If callers benefit from flat methods, keep the facade flat and split internals only.
- If domain APIs are clean enough, expose nested services later.
- If a method spans domains, keep it in the facade until a better boundary appears.
- If live source calls cannot be abstracted cleanly yet, leave capability
  calling in the MCP backend and move drafts/artifacts first.

### Success Criteria

- `wf_api` has an explicit operation context/protocol seam that imports no
  `wf_mcp` modules.
- `WfMcpWorkflowApiBackend` can adapt `WfMcpService` into that seam.
- No workflow method behavior changes in Slice 4A.
- Each domain file is readable on its own.
- Public payloads remain unchanged.
- `wf_cli` and `wf_mcp` do not care about the internal split.

## Slice 5: Move Listing/Event Primitives To Better Homes

### Goal

Remove remaining protocol-neutral utilities from MCP-named packages.

### Current Recommendation

Split this into two different concerns. Listing/helper consolidation is
behavior-preserving cleanup and should happen first. Event migration changes
domain vocabulary and should remain separate until lifecycle event semantics are
clearer.

### Slice 5A/5B: Listing And Workflow Helper Consolidation

Concrete plan:

```text
docs/superpowers/plans/2026-06-02-wf-api-slice-5a-5b-helper-consolidation.md
```

Planned moves:

```text
wf_api.capabilities._matches_query          -> wf_api.listing.matches_query
wf_api.artifacts._matches_query             -> wf_api.listing.matches_query
wf_api.capabilities._paged_list_payload     -> wf_api.listing.paged_list_payload
wf_api.artifacts._paged_list_payload        -> wf_api.listing.paged_list_payload
wf_mcp.workflow_surface.handlers fallback   -> wf_api.listing.paged_list_payload

wf_api.runs._raw_plan_from_artifact         -> wf_api.artifact_plans.raw_plan_from_artifact
wf_api.capabilities._raw_plan_from_artifact -> wf_api.artifact_plans.raw_plan_from_artifact
wf_api.capabilities._artifact_capability_id -> wf_api.artifact_refs.artifact_capability_id
wf_api.artifacts._artifact_capability_id    -> wf_api.artifact_refs.artifact_capability_id
wf_api.{drafts,artifacts,capabilities} requirement helpers
                                             -> wf_api.capability_requirements
```

Do not move `wf_mcp.shared.pagination` in this slice. It is still used by proxy
tool search/listing code, so treating it as dead workflow-surface debt would be
incorrect.

### Post-5 Helper Cleanup: Workflow Surface Test Thinning

Concrete plan:

```text
docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning.md
```

Intent:

```text
wf_api tests                 = canonical application behavior tests
wf_mcp.workflow_surface tests = adapter/schema/live-source/integration smoke tests
```

Do not replace stronger workflow-surface integration tests with weaker unit
tests. Only remove a handler test when an equal-or-stronger `wf_api` test exists
and at least one handler-level smoke/delegation test still protects the adapter
path.

### Candidate Moves

```text
wf_mcp.shared.listing.matches_query       -> wf_platform.listing or wf_api.listing
wf_mcp.shared.listing.paged_list_payload  -> wf_platform.listing or wf_api.listing
wf_mcp.events.McpEvent                    -> wf_platform.events.DomainEvent
wf_mcp.events.EventBus                    -> wf_platform.events.EventBus
```

### If/Then

- If events are only used by MCP admin/proxy code, leave them in `wf_mcp`.
- If events describe artifact/deployment/run lifecycle, move or fork them into `wf_platform`.
- If renaming `McpEvent` causes churn, introduce `DomainEvent` first and keep `McpEvent` as an alias temporarily.

### Success Criteria

- Workflow API lifecycle events no longer require MCP naming.
- Listing helpers used by CLI/API are not imported from `wf_mcp`.

## Slice 6: Store Construction And Config Boundary

### Goal

Make store/runtime construction less MCP-owned.

### Current Problem

`build_service_from_config` and `WfMcpService.__post_init__` currently build or own protocol-neutral stores. CLI uses this path because it is pragmatic, but long term config/store construction should be reusable without MCP server assumptions.

### Candidate Work

- Extract config-to-store construction into a neutral builder.
- Keep MCP connection config in `wf_mcp`.
- Let `wf_cli` and future API/server adapters reuse the neutral store builder.

### If/Then

- If extraction creates too many config model moves, defer it.
- If CLI needs only current config behavior, keep using `wf_mcp` builder until FastAPI/UI pressure appears.

### Success Criteria

- Artifact/draft/run stores can be constructed without starting MCP concepts.
- Current `wf_mcp.config.json` remains supported.

## Slice 7: Future HTTP/FastAPI Adapter

### Goal

Expose `WorkflowApi` over HTTP only after the in-process API is stable.

### Not Yet

Do not start this until:

- `wf_api` exists.
- CLI and MCP both call `wf_api`.
- Run/draft/deployment payloads are stable enough.
- Auth and multi-client lifecycle questions are explicit.

### Future Shape

```text
wf_http or wf_server
  routes/
    capabilities.py
    drafts.py
    artifacts.py
    deployments.py
    runs.py
```

Routes should be thin:

```python
@router.post("/runs")
async def start_run(...):
    return await api.run_deployment(...)
```

### Success Criteria

- HTTP is an adapter, not a new source of workflow logic.
- Process-local API remains usable without HTTP.

## Open Questions

1. Should `WorkflowApiBackend` be one protocol or several domain protocols?
   - Recommendation for Slice 1: one protocol. Split later only if it hurts.

2. Should live source validation live in `wf_api`?
   - Recommendation: `wf_api` owns the operation, backend owns the live-check implementation.

3. Should `wf_api` expose flat methods or nested services?
   - Recommendation for Slice 1: flat methods for compatibility. Consider nested internals later.

4. Should `WorkflowSurfaceHandlers` disappear immediately?
   - Recommendation: no. Keep a short-lived shim if it reduces churn.

5. Should `wf_cli` stop importing `wf_mcp` after Slice 1?
   - Not fully. It may still use `wf_mcp` config/service construction until store/config extraction happens.

## Immediate Next Plan Status

Slice 1 implementation plan exists and was executed:

```text
docs/superpowers/plans/2026-06-01-wf-api-slice-1-dependency-direction.md
```

The next implementation plan should cover Slice 2 only. Prefer docs and
compatibility naming first; do not move helper modules until Slice 3.
