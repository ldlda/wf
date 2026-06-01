# wf_mcp Workflow Surface Test Thinning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce duplicated `wf_mcp.workflow_surface` behavior tests now covered by `wf_api` tests while preserving adapter, schema, live-source, run, wrapper, and end-to-end coverage.

**Architecture:** `wf_api` tests are the canonical behavior tests for application-service logic. `wf_mcp.workflow_surface` tests should prove that `WorkflowSurfaceHandlers` exposes that behavior through the MCP-owned adapter boundary and should keep any test that exercises MCP-specific request models, live checks, service event recording, tool schema, or realistic integration paths.

**Tech Stack:** Python 3.14, pytest, `wf_api`, `wf_mcp.workflow_surface`, `WorkflowSurfaceHandlers`, ruff, basedpyright.

---

## Coverage Policy

Use this rule for every deletion:

```text
Only remove a wf_mcp.workflow_surface test when an equal-or-stronger wf_api test
already covers the behavior and a smaller handler smoke/delegation test still
proves the adapter path.
```

Keep tests that cover:

- MCP request/response Pydantic models such as `TraceRange`, `RunDeploymentResult`, and `CreateMinimalDraftWorkspaceRequest`.
- live source checks through `WfMcpService` adapters.
- service event recording.
- handler-to-service wiring.
- saved wrapper calls with deployment bindings.
- source binding, schema drift, reducer dependency, subgraph, or durable run integration.
- next-action guidance generated through real handler operations.

Thin tests that only repeat:

- list filtering/pagination details already covered by `WorkflowCapabilityApi` or `WorkflowArtifactApi`.
- basic inspect/list payload details already covered by `wf_api` domain tests.
- basic draft workspace CRUD details already covered by `WorkflowDraftApi`.
- basic artifact/deployment CRUD details already covered by `WorkflowArtifactApi` or `WorkflowDeploymentApi`.

## File Map

| File | Planned role |
| --- | --- |
| `tests/wf_mcp/workflow_surface/test_artifacts.py` | Thin to one handler adapter smoke test for compact artifact listing. |
| `tests/wf_mcp/workflow_surface/test_capabilities.py` | Thin list/filter/inspect duplicates; keep wrapper-hints, MCP content-block, direct call error, and saved wrapper coverage if not stronger in `wf_api`. |
| `tests/wf_mcp/workflow_surface/test_deployments.py` | Keep live-check, events, alias/XOR, delete event, and compact-vs-detail tests. Maybe remove only duplicate dependency validation if covered by `wf_api`. |
| `tests/wf_mcp/workflow_surface/test_drafts.py` | Keep most tests; remove only the simplest validate/patch/list CRUD duplicates if `wf_api` has equal coverage. |
| `tests/wf_mcp/workflow_surface/test_runs.py` | Keep run/trace/model tests. Do not thin in first pass except the raw plan model extraction test if duplicated in `tests/wf_api/test_raw_workflow_plan_extraction.py`. |
| `tests/wf_mcp/workflow_surface/test_wrappers.py` | Keep all tests in first pass; these are handler integration paths and direct capability REPL behavior. |
| `tests/wf_api/*` | Do not weaken. Add missing behavior tests here before removing handler duplicates. |

---

## Task 1: Build A Deletion Ledger Before Editing

**Files:**
- Create: `docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning-ledger.md`

- [ ] **Step 1: Create the ledger file**

Create `docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning-ledger.md`:

```markdown
# wf_mcp Workflow Surface Test Thinning Ledger

This ledger records every `wf_mcp.workflow_surface` test removed or kept during
the thinning pass. Do not delete a test unless the `replacement` column points
to equal-or-stronger coverage.

| Test | Decision | Replacement / Reason |
| --- | --- | --- |
```

- [ ] **Step 2: Populate the initial ledger with all workflow-surface tests**

Run:

```bash
rg -n "^def test_" tests/wf_mcp/workflow_surface
```

Append each test name to the ledger with `Decision` set to `unclassified`.

Expected: the ledger contains every test from:

```text
tests/wf_mcp/workflow_surface/test_artifacts.py
tests/wf_mcp/workflow_surface/test_capabilities.py
tests/wf_mcp/workflow_surface/test_deployments.py
tests/wf_mcp/workflow_surface/test_drafts.py
tests/wf_mcp/workflow_surface/test_runs.py
tests/wf_mcp/workflow_surface/test_wrappers.py
tests/wf_mcp/workflow_surface/test_next_actions.py
```

- [ ] **Step 3: Mark protected tests**

Mark these as `keep` unless a later task explicitly adds stronger coverage:

```text
tests/wf_mcp/workflow_surface/test_capabilities.py::test_workflow_surface_call_capability_returns_structured_error
tests/wf_mcp/workflow_surface/test_capabilities.py::test_workflow_surface_inspect_capability_includes_wrapper_hints
tests/wf_mcp/workflow_surface/test_capabilities.py::test_workflow_surface_does_not_auto_map_raw_mcp_content_blocks
tests/wf_mcp/workflow_surface/test_deployments.py::test_workflow_surface_validate_deployment_live_check_is_opt_in
tests/wf_mcp/workflow_surface/test_deployments.py::test_workflow_surface_validate_deployment_live_check_reports_unreachable_source
tests/wf_mcp/workflow_surface/test_deployments.py::test_workflow_surface_validate_deployment_live_check_reports_missing_connection
tests/wf_mcp/workflow_surface/test_deployments.py::test_workflow_surface_records_artifact_and_deployment_save_events
tests/wf_mcp/workflow_surface/test_deployments.py::test_workflow_surface_save_deployment_accepts_deployment_id_alias
tests/wf_mcp/workflow_surface/test_deployments.py::test_workflow_surface_save_deployment_rejects_id_and_deployment_id
tests/wf_mcp/workflow_surface/test_runs.py::test_workflow_surface_run_deployment_can_include_trace_detail
tests/wf_mcp/workflow_surface/test_runs.py::test_workflow_surface_run_deployment_can_read_empty_trace_range
tests/wf_mcp/workflow_surface/test_runs.py::test_workflow_surface_runs_deployment_with_bound_node_spec_dependency
tests/wf_mcp/workflow_surface/test_runs.py::test_workflow_surface_runs_artifact_created_from_concrete_node_ref
tests/wf_mcp/workflow_surface/test_runs.py::test_workflow_surface_detects_drift_from_saved_node_spec_snapshot
tests/wf_mcp/workflow_surface/test_runs.py::test_workflow_surface_runs_deployment_with_bound_reducer_dependency
tests/wf_mcp/workflow_surface/test_wrappers.py
```

Reason: these cover adapter wiring, MCP/service behavior, direct wrapper calls,
trace schema behavior, binding logic, reducer dependencies, or important
integration seams.

---

## Task 2: Thin Artifact Listing Duplicates

**Files:**
- Modify: `tests/wf_mcp/workflow_surface/test_artifacts.py`
- Modify: `docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning-ledger.md`
- Test: `tests/wf_api/test_artifact_api.py`, `tests/wf_mcp/workflow_surface/test_artifacts.py`

- [ ] **Step 1: Confirm wf_api artifact coverage**

Run:

```bash
rg -n "list_artifacts|pagination|kind|query|plan\" not in" tests/wf_api/test_artifact_api.py tests/wf_api/test_listing.py
```

Expected: `wf_api` coverage exists for empty list payload, compact artifact rows,
query/kind behavior, and pagination helper shape. If it does not, add the
missing assertion to `tests/wf_api/test_artifact_api.py` before deleting any
handler test.

- [ ] **Step 2: Keep one handler smoke test**

Keep `test_workflow_surface_lists_artifact_catalog_entries` and reduce it only
if needed to these adapter-boundary assertions:

```python
def test_workflow_surface_lists_artifact_catalog_entries() -> None:
    artifact_store = FileWorkflowArtifactStore(local_temp_root() / "surface_artifacts")
    artifact_store.save_artifact(artifact())
    h = handlers(artifact_store)

    payload = asyncio.run(h.list_artifacts())

    nodes = payload["nodes"]
    assert payload["total"] == 1
    assert payload["next_cursor"] is None
    assert nodes[0]["name"] == "workflow.summarize_docs.v1"
    assert nodes[0]["artifact_id"] == "summarize_docs"
    assert "plan" not in nodes[0]
```

- [ ] **Step 3: Remove duplicate pagination/filter handler test**

Delete:

```text
test_workflow_surface_pages_and_filters_artifact_catalog_entries
```

Mark it in the ledger:

```text
remove | Covered by WorkflowArtifactApi list tests plus wf_api.listing pagination tests; handler keeps one list_artifacts smoke test.
```

- [ ] **Step 4: Run artifact tests**

Run:

```bash
uv run pytest tests/wf_api/test_artifact_api.py tests/wf_api/test_listing.py tests/wf_mcp/workflow_surface/test_artifacts.py -q
```

Expected: pass.

---

## Task 3: Thin Capability List/Inspect Duplicates Conservatively

**Files:**
- Modify: `tests/wf_mcp/workflow_surface/test_capabilities.py`
- Modify: `docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning-ledger.md`
- Test: `tests/wf_api/test_capability_api.py`, `tests/wf_mcp/workflow_surface/test_capabilities.py`

- [ ] **Step 1: Confirm wf_api capability coverage**

Run:

```bash
rg -n "list_capabilities|inspect_capability|saved_wrapper|wrapper_hints|runtime_error|content blocks" tests/wf_api/test_capability_api.py tests/wf_mcp/workflow_surface/test_capabilities.py
```

Expected: `wf_api` covers planner-visible listing, source filtering, unknown
inspect, saved wrapper list/inspect, and direct handler delegation smoke.

- [ ] **Step 2: Keep one handler list smoke test**

Keep `test_workflow_surface_lists_planner_visible_capabilities`, but keep it
compact. It should assert adapter path and summary shape only:

```python
def test_workflow_surface_lists_planner_visible_capabilities() -> None:
    h = handlers(FileWorkflowArtifactStore(local_temp_root() / "surface_caps"))

    payload = asyncio.run(h.list_capabilities(limit=2))
    first = payload["capabilities"][0]

    assert len(payload["capabilities"]) == 2
    assert payload["total"] >= 2
    assert payload["next_cursor"] == "2"
    assert first["kind"] == "node_spec"
    assert "input_schema" not in first
```

- [ ] **Step 3: Remove duplicate source-filter test if wf_api has it**

Delete:

```text
test_workflow_surface_filters_stdlib_capabilities_by_source
```

Only delete it if `tests/wf_api/test_capability_api.py` contains:

```text
test_list_capabilities_filters_by_source
```

Mark the ledger:

```text
remove | Covered by WorkflowCapabilityApi source/query filtering; handler list smoke remains.
```

- [ ] **Step 4: Remove duplicate saved-wrapper list/inspect tests if wf_api has them**

Delete these only if `tests/wf_api/test_capability_api.py` has equivalent saved
wrapper list and inspect tests:

```text
test_workflow_surface_lists_saved_wrapper_capabilities
test_workflow_surface_inspects_saved_wrapper_capability
```

Mark the ledger:

```text
remove | Covered by WorkflowCapabilityApi saved wrapper list/inspect tests.
```

- [ ] **Step 5: Keep MCP-specific and guidance-sensitive capability tests**

Keep these tests unchanged:

```text
test_workflow_surface_call_capability_returns_structured_error
test_workflow_surface_inspect_capability_includes_wrapper_hints
test_workflow_surface_does_not_auto_map_raw_mcp_content_blocks
```

Do not remove `test_workflow_surface_inspects_one_capability` unless there is
still another handler-level inspect smoke test after this task.

- [ ] **Step 6: Run capability tests**

Run:

```bash
uv run pytest tests/wf_api/test_capability_api.py tests/wf_mcp/workflow_surface/test_capabilities.py -q
```

Expected: pass.

---

## Task 4: Thin Deployment Tests Only Where Purely Duplicated

**Files:**
- Modify: `tests/wf_mcp/workflow_surface/test_deployments.py`
- Modify: `docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning-ledger.md`
- Test: `tests/wf_api/test_deployment_api.py`, `tests/wf_mcp/workflow_surface/test_deployments.py`

- [ ] **Step 1: Keep MCP live-check and event tests**

Do not delete:

```text
test_workflow_surface_validate_deployment_live_check_is_opt_in
test_workflow_surface_validate_deployment_live_check_reports_unreachable_source
test_workflow_surface_validate_deployment_live_check_reports_missing_connection
test_workflow_surface_records_artifact_and_deployment_save_events
test_workflow_surface_save_deployment_accepts_deployment_id_alias
test_workflow_surface_deletes_deployment
test_workflow_surface_save_deployment_rejects_id_and_deployment_id
test_workflow_surface_lists_compact_deployment_summaries_and_inspects_detail
```

Reason: these exercise MCP service adapters, event recording, request alias
normalization, and compact-vs-detail response shape.

- [ ] **Step 2: Evaluate basic dependency validation duplicate**

Check whether `tests/wf_api/test_deployment_api.py` covers dependency validation
next-actions for an unrunnable deployment:

```bash
rg -n "source_missing|binding_missing|next_actions|unrunnable" tests/wf_api/test_deployment_api.py
```

If the `wf_api` test has equal next-action assertions, delete:

```text
test_workflow_surface_validates_deployment_dependencies
```

If it does not, keep the handler test and mark it:

```text
keep | Handler-level dependency validation still has stronger next-action assertions than wf_api.
```

- [ ] **Step 3: Run deployment tests**

Run:

```bash
uv run pytest tests/wf_api/test_deployment_api.py tests/wf_mcp/workflow_surface/test_deployments.py -q
```

Expected: pass.

---

## Task 5: Thin Draft Tests With High Caution

**Files:**
- Modify: `tests/wf_mcp/workflow_surface/test_drafts.py`
- Modify: `docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning-ledger.md`
- Test: `tests/wf_api/test_drafts_service.py`, `tests/wf_mcp/workflow_surface/test_drafts.py`

- [ ] **Step 1: Identify pure draft API duplicates**

Run:

```bash
rg -n "validate_draft|patch_draft|list_draft_workspaces|delete_draft_workspace|create_minimal_draft_workspace|create_draft_workspace_from_capability|create_artifact_from_workspace|create_wrapper_from_workspace" tests/wf_api/test_drafts_service.py tests/wf_api/test_artifact_api.py tests/wf_api/test_capability_api.py tests/wf_mcp/workflow_surface/test_drafts.py
```

Expected: most simple draft workspace CRUD and patch helper behavior exists in
`tests/wf_api/test_drafts_service.py`.

- [ ] **Step 2: Remove only pure CRUD duplicates**

Candidates for removal if `wf_api` tests cover equal behavior:

```text
test_workflow_surface_validates_draft_without_saving
test_workflow_surface_patches_draft_without_saving
test_workflow_surface_creates_and_gets_draft_workspace
test_workflow_surface_lists_draft_workspaces
test_workflow_surface_deletes_draft_workspace
test_workflow_surface_patch_helpers_update_draft_workspace
test_workflow_surface_patches_draft_workspace_by_revision
```

For each removed test, add a ledger row with the exact `wf_api` replacement test.

- [ ] **Step 3: Keep guidance, model, and artifact integration tests**

Do not delete these in this pass:

```text
test_workflow_surface_rejects_unknown_draft_route_outcome_when_spec_is_known
test_workflow_surface_creates_artifact_from_draft_with_binding_suggestions
test_workflow_surface_draft_artifact_requires_std_self_binding
test_workflow_surface_validates_draft_workspace_with_live_outcomes
test_workflow_surface_creates_minimal_draft_workspace_with_error_route
test_workflow_surface_minimal_draft_honors_explicit_error_message_source
test_minimal_draft_request_accepts_structural_error_message_source
test_workflow_surface_accepts_canonical_bindings_for_minimal_workspace
test_workflow_surface_creates_draft_workspace_from_capability_hints
test_workflow_surface_creates_artifact_from_workspace
test_workflow_surface_workspace_artifact_infers_raw_concrete_dependency
test_workflow_surface_creates_wrapper_from_workspace
test_workflow_surface_low_confidence_draft_returns_patch_guidance
```

Reason: these cover live outcome lookup, request model parsing, wrapper hints,
next actions, artifact persistence, and source dependency inference.

- [ ] **Step 4: Run draft tests**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_api/test_artifact_api.py tests/wf_api/test_capability_api.py tests/wf_mcp/workflow_surface/test_drafts.py -q
```

Expected: pass.

---

## Task 6: Keep Run And Wrapper Tests Mostly Intact

**Files:**
- Modify: `tests/wf_mcp/workflow_surface/test_runs.py`
- Modify: `docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning-ledger.md`
- Test: `tests/wf_api/test_run_api.py`, `tests/wf_mcp/workflow_surface/test_runs.py`, `tests/wf_mcp/workflow_surface/test_wrappers.py`

- [ ] **Step 1: Remove raw plan model duplicate only**

If `tests/wf_api/test_raw_workflow_plan_extraction.py` covers core step and edge
model parsing, delete:

```text
tests/wf_mcp/workflow_surface/test_runs.py::test_raw_workflow_plan_uses_core_step_and_edge_models
```

Mark the ledger:

```text
remove | RawWorkflowPlan extraction is canonical in wf_api model tests.
```

- [ ] **Step 2: Keep run deployment behavior tests**

Keep all remaining tests in `tests/wf_mcp/workflow_surface/test_runs.py`.

Reason: they cover persisted run records, trace slicing with MCP `TraceRange`,
response Pydantic model validation, logical source binding, schema drift, and
reducer dependency integration through the handler/service stack.

- [ ] **Step 3: Keep wrapper tests**

Do not delete tests in `tests/wf_mcp/workflow_surface/test_wrappers.py` in this
pass.

Reason: wrapper direct calls and deployment-bound wrapper calls are meaningful
handler integration tests even if `WorkflowCapabilityApi` also has lower-level
coverage.

- [ ] **Step 4: Run run/wrapper tests**

Run:

```bash
uv run pytest tests/wf_api/test_run_api.py tests/wf_api/test_raw_workflow_plan_extraction.py tests/wf_mcp/workflow_surface/test_runs.py tests/wf_mcp/workflow_surface/test_wrappers.py -q
```

Expected: pass.

---

## Task 7: Final Review And Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning-ledger.md`
- Test: all workflow-surface and wf_api tests

- [ ] **Step 1: Ensure ledger has no unclassified rows**

Run:

```bash
rg -n "unclassified" docs/superpowers/plans/2026-06-02-wf-mcp-workflow-surface-test-thinning-ledger.md
```

Expected: no matches.

- [ ] **Step 2: Run full focused API and adapter tests**

Run:

```bash
uv run pytest tests/wf_api tests/wf_mcp/workflow_surface tests/wf_mcp/server/test_tools.py tests/wf_mcp/server/test_config.py -q
```

Expected: pass.

- [ ] **Step 3: Run lint and type checks**

Run:

```bash
uv run ruff check tests/wf_api tests/wf_mcp/workflow_surface
uv run ruff format --check tests/wf_api tests/wf_mcp/workflow_surface
uv run basedpyright --level error
```

Expected:

- Ruff commands pass.
- Basedpyright reports `0 errors`; if it exits nonzero only because workspace
  enumeration exceeds 10 seconds, report that exact output as an environment
  issue rather than a type failure.

- [ ] **Step 4: Optional full suite**

Run:

```bash
uv run pytest -q
```

Expected: existing suite status remains at least as good as before this pass.

---

## Handoff Report Requirements

When done, report:

- Tests removed, grouped by file.
- Tests kept intentionally, with reasons for any controversial keeps.
- Any new or strengthened `wf_api` tests.
- Ledger path.
- Verification commands and exact outputs.
- Deviations from the plan.

## Self-Review

- Spec coverage: the plan preserves “good tests” by requiring a ledger and exact replacement coverage before any deletion.
- Placeholder scan: no deferred implementation slots; each deletion candidate has a guard and replacement rule.
- Type consistency: all referenced test paths and test names were taken from the current tree inspection.
