# Workflow Lifecycle Operator Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MCP-facing workflow lifecycle understandable end-to-end for LLM clients and human operators.

**Architecture:** This is a documentation and schema-test pass, not a runtime redesign. The docs should describe the current stable workflow control surface: discover capabilities, create a draft workspace, save an artifact, save/validate/delete a deployment, run, inspect trace slices, and resume interrupted durable runs. Keep examples aligned with the actual MCP tool names and current compact-response philosophy.

**Tech Stack:** Markdown docs, Python tests, FastMCP tool metadata, `uv run pytest`, `uv run ruff`, `uv run basedpyright --level error`.

---

## Scope

Implement documentation for the current workflow lifecycle. Do not add new MCP tools unless a test proves a documented flow cannot be expressed with existing tools.

Current tools to document as primary path:

- `wf.workflow.list_capabilities`
- `wf.workflow.inspect_capability`
- `wf.workflow.create_draft_workspace_from_capability`
- `wf.workflow.patch_draft_workspace`
- `wf.workflow.validate_draft_workspace`
- `wf.workflow.create_artifact_from_workspace`
- `wf.workflow.save_deployment`
- `wf.workflow.validate_deployment`
- `wf.workflow.run_deployment`
- `wf.workflow.inspect_run`
- `wf.workflow.read_run_trace`
- `wf.workflow.resume_run`
- `wf.workflow.delete_deployment`

Important behavior to make explicit:

- `validate_deployment` is stored-catalog validation by default.
- `validate_deployment(live_check=true)` contacts required upstream sources and can spawn stdio/network work.
- `run_deployment` returns compact status and `trace_count`; do not request trace by default.
- `read_run_trace` is the explicit bounded debug path.
- `resume_run` works for durable stopped runs when the run is interrupted and dependencies remain compatible.
- `delete_deployment` removes only mutable deployment bindings. It does not delete immutable workflow artifacts or durable run records.

## Files

- Modify: `docs/wf_mcp_operator_manual.md`
  - Primary mental model and short command flow.
- Modify: `docs/wf_mcp_end_to_end_runbook.md`
  - Full happy path with concrete MCP tool payloads.
- Modify: `docs/wf_mcp_troubleshooting.md`
  - Failure-mode lookup for validation, live checks, run, resume, and cleanup.
- Modify: `docs/durable_run_operations.md`
  - Clarify run/resume/trace lifecycle and relationship to deployment deletion.
- Modify: `docs/README.md`
  - Ensure the docs index points readers to the operator manual/runbook/troubleshooting in the right order.
- Modify: `tests/wf_mcp/server/test_docs.py`
  - Add low-cost assertions that the exported docs resources include the new lifecycle terms.
- Modify only if needed: `src/wf_mcp/documentation.py`
  - Do not add new docs resources unless existing resources do not expose the updated docs.

## Task 1: Update The Operator Manual Primary Path

**Files:**

- Modify: `docs/wf_mcp_operator_manual.md`

- [ ] **Step 1: Find the current workflow tool family section**

Run:

```powershell
rg -n "Workflow Tools|workflow tools|validate_deployment|run_deployment|delete_deployment" docs/wf_mcp_operator_manual.md
```

Expected: existing sections mention workflow discovery, deployment validation, run, and resume.

- [ ] **Step 2: Add a concise primary-path checklist**

Add or update a section named exactly:

```markdown
## Primary Workflow Lifecycle
```

Use this content, adjusting surrounding prose only for fit:

```markdown
## Primary Workflow Lifecycle

Use this path when an LLM client needs to build, test, and run a saved workflow.

1. Discover workflow-ready capabilities with `wf.workflow.list_capabilities`.
2. Inspect the selected capability with `wf.workflow.inspect_capability`.
3. Create a patchable draft with `wf.workflow.create_draft_workspace_from_capability`.
4. Patch the draft with `wf.workflow.patch_draft_workspace`.
5. Validate the draft with `wf.workflow.validate_draft_workspace`.
6. Save an immutable workflow or wrapper artifact with `wf.workflow.create_artifact_from_workspace` or `wf.workflow.create_wrapper_from_workspace`.
7. Save a mutable deployment with `wf.workflow.save_deployment`.
8. Validate the deployment with `wf.workflow.validate_deployment`.
9. Optionally call `wf.workflow.validate_deployment` with `live_check=true` before a real run.
10. Run with `wf.workflow.run_deployment`.
11. If the run returns `interrupted`, resume with `wf.workflow.resume_run`.
12. Inspect stopped runs with `wf.workflow.inspect_run`; read bounded trace slices with `wf.workflow.read_run_trace`.
13. Delete temporary deployments with `wf.workflow.delete_deployment`.

Artifacts are immutable saved definitions. Deployments are mutable environment bindings. Runs are durable stopped execution records. Deleting a deployment does not delete artifacts or existing run records.
```

- [ ] **Step 3: Document `live_check` next to deployment validation**

Find the `validate_deployment` section and add:

```markdown
By default, `validate_deployment` validates against the broker's current source inventory and saved catalog snapshots. This is cheap and side-effect-light.

Pass `live_check=true` only when you explicitly want to contact each required upstream source. A live check may spawn stdio MCP servers or perform network I/O. Live-check failures are returned as `source_unreachable` diagnostics.
```

- [ ] **Step 4: Document `delete_deployment` in the tool table**

Add a table row near deployment tools:

```markdown
| Delete a temporary deployment binding | `wf.workflow.delete_deployment` |
```

Also add:

```markdown
`delete_deployment` removes the saved deployment binding only. It does not delete workflow artifacts, wrapper artifacts, or run checkpoints.
```

- [ ] **Step 5: Run a docs grep sanity check**

Run:

```powershell
rg -n "Primary Workflow Lifecycle|live_check|source_unreachable|delete_deployment" docs/wf_mcp_operator_manual.md
```

Expected: all four terms appear.

## Task 2: Update The End-To-End Runbook With Concrete Payloads

**Files:**

- Modify: `docs/wf_mcp_end_to_end_runbook.md`

- [ ] **Step 1: Locate the happy-path flow**

Run:

```powershell
rg -n "create_draft_workspace_from_capability|save_deployment|validate_deployment|run_deployment|resume_run" docs/wf_mcp_end_to_end_runbook.md
```

Expected: existing examples for draft creation, deployment validation, and run execution.

- [ ] **Step 2: Add a compact lifecycle summary near the top**

Add:

```markdown
## Minimal Lifecycle Summary

The shortest dependable lifecycle is:

```text
list_capabilities
inspect_capability
create_draft_workspace_from_capability
patch_draft_workspace
validate_draft_workspace
create_artifact_from_workspace
save_deployment
validate_deployment
run_deployment
inspect_run or read_run_trace only when needed
resume_run only when status is interrupted
delete_deployment for temporary deployments
```

Do not expect a newly saved workflow to appear as a new MCP tool in an existing client session. Use `run_deployment` and `call_capability` as stable front doors.

```

- [ ] **Step 3: Add an explicit live validation example**

Near the deployment validation example, add:

```markdown
### Optional Live Source Check

Use this before a real run when you need to know whether the bound upstream source can currently answer.

```yaml
tool: wf.workflow.validate_deployment
arguments:
  deployment_id: "example.personal"
  live_check: true
```

Expected successful shape:

```json
{
  "deployment_id": "example.personal",
  "status": "runnable",
  "diagnostics": []
}
```

If a bound upstream source is down, expect `status="unrunnable"` and a diagnostic with `code="source_unreachable"`.

```

- [ ] **Step 4: Add a cleanup example**

Near the end of the runbook, add:

```markdown
### Cleanup Temporary Deployments

Temporary test deployments can be removed without touching immutable artifacts.

```yaml
tool: wf.workflow.delete_deployment
arguments:
  deployment_id: "example.personal"
```

Expected:

```json
{
  "deployment_id": "example.personal",
  "deleted": true
}
```

```

- [ ] **Step 5: Run grep sanity check**

Run:

```powershell
rg -n "Minimal Lifecycle Summary|Optional Live Source Check|delete_deployment|source_unreachable" docs/wf_mcp_end_to_end_runbook.md
```

Expected: all four terms appear.

## Task 3: Update Troubleshooting For Live Checks And Cleanup

**Files:**

- Modify: `docs/wf_mcp_troubleshooting.md`

- [ ] **Step 1: Locate validation diagnostics**

Run:

```powershell
rg -n "binding_missing|source_missing|source_disabled|capability_missing|schema_changed|source_unreachable|delete_deployment" docs/wf_mcp_troubleshooting.md
```

Expected: existing sections for static diagnostics; `source_unreachable` may be missing.

- [ ] **Step 2: Add `source_unreachable` section**

Add this section after `source_disabled` or near other deployment validation diagnostics:

```markdown
## `validate_deployment(live_check=true)` Says `source_unreachable`

Meaning: static deployment validation found a matching saved source/catalog, but the live upstream source could not answer when contacted.

Common causes:

- stdio MCP server command is missing or exits during startup
- network MCP server is offline
- auth/config changed outside the broker
- source process starts too slowly and hits the live-check timeout

What to do:

1. Check the connection with `wf.admin.get_connection_statuses`.
2. Refresh or reload the config if the source was recently enabled.
3. Fix the source command/auth/network outside the workflow artifact.
4. Run `wf.workflow.validate_deployment` again with `live_check=true`.

Do not fix this by editing the workflow artifact unless the source capability itself changed. This is an environment problem, not workflow business logic.
```

- [ ] **Step 3: Add deployment cleanup troubleshooting**

Add:

```markdown
## Test Deployment Clutter

Symptom: `wf.workflow.list_deployments` shows temporary deployments from earlier tests or LLM attempts.

Use:

```yaml
tool: wf.workflow.delete_deployment
arguments:
  deployment_id: "test_alias_check"
```

This deletes only the mutable deployment binding. Saved artifacts and durable run records remain.

```

- [ ] **Step 4: Run grep sanity check**

Run:

```powershell
rg -n "source_unreachable|Test Deployment Clutter|delete_deployment|test_alias_check" docs/wf_mcp_troubleshooting.md
```

Expected: all four terms appear.

## Task 4: Update Durable Run Docs For Deployment Deletion Boundaries

**Files:**

- Modify: `docs/durable_run_operations.md`

- [ ] **Step 1: Locate run/deployment lifecycle text**

Run:

```powershell
rg -n "deployment|run_deployment|resume_run|inspect_run|read_run_trace|delete_deployment" docs/durable_run_operations.md
```

Expected: current run/resume docs; `delete_deployment` may be missing.

- [ ] **Step 2: Add deployment deletion boundary note**

Add under the run lifecycle or deployment section:

```markdown
## Deployment Deletion Boundary

`wf.workflow.delete_deployment` removes the mutable deployment binding. It does not delete:

- immutable workflow artifacts
- wrapper artifacts
- stored run records
- run checkpoints

Existing run records keep the pinned deployment and artifact environment captured at run time. Deleting a deployment prevents future runs through that deployment id, but it does not erase historical stopped-run inspection data.
```

- [ ] **Step 3: Reconfirm trace guidance**

Ensure the doc says:

```markdown
Use `inspect_run` for compact stopped-run summaries. Use `read_run_trace` only when trace entries are needed, and always request a bounded `trace_range`.
```

- [ ] **Step 4: Run grep sanity check**

Run:

```powershell
rg -n "Deployment Deletion Boundary|delete_deployment|read_run_trace|trace_range" docs/durable_run_operations.md
```

Expected: all four terms appear.

## Task 5: Update Docs Index And Exported Docs Tests

**Files:**

- Modify: `docs/README.md`
- Modify: `tests/wf_mcp/server/test_docs.py`

- [ ] **Step 1: Update docs index ordering**

In `docs/README.md`, ensure these entries exist and read clearly:

```markdown
- [`wf_mcp_operator_manual.md`](wf_mcp_operator_manual.md): start here for the MCP-facing workflow lifecycle and tool families.
- [`wf_mcp_end_to_end_runbook.md`](wf_mcp_end_to_end_runbook.md): concrete tool-call runbook from capability discovery through deployment, run, resume, and cleanup.
- [`wf_mcp_troubleshooting.md`](wf_mcp_troubleshooting.md): diagnostics and repair steps for source, deployment, run, and resume failures.
- [`durable_run_operations.md`](durable_run_operations.md): durable run records, compact inspection, bounded traces, and resume semantics.
```

- [ ] **Step 2: Add docs resource assertions**

Open `tests/wf_mcp/server/test_docs.py` and find the test that reads `wf://docs/operator-manual` or docs resources.

Add field-level assertions instead of whole-dict assertions:

```python
assert "Primary Workflow Lifecycle" in manual_text
assert "live_check" in manual_text
assert "delete_deployment" in manual_text
```

If the test currently uses a different variable name than `manual_text`, use the existing variable. Do not assert whole payload dict equality.

- [ ] **Step 3: Run focused docs tests**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_docs.py -q
```

Expected: all tests in that file pass.

## Task 6: Final Verification

**Files:**

- All modified docs and tests.

- [ ] **Step 1: Run docs grep checks**

Run:

```powershell
rg -n "Primary Workflow Lifecycle|live_check|source_unreachable|delete_deployment|Deployment Deletion Boundary" docs
```

Expected: terms appear in the intended docs, not only in historical plans.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_docs.py tests/wf_mcp/server/test_tools.py tests/wf_mcp/workflow_surface/test_deployments.py -q
```

Expected: pass.

- [ ] **Step 3: Run lint/format checks for touched files**

Run:

```powershell
uv run ruff check tests/wf_mcp/server/test_docs.py
uv run ruff format --check tests/wf_mcp/server/test_docs.py
```

Expected: pass.

- [ ] **Step 4: Run type check for touched Python files**

Run:

```powershell
uv run basedpyright --level error tests/wf_mcp/server/test_docs.py
```

Expected: `0 errors`.

- [ ] **Step 5: Optional full test suite**

Run when time allows:

```powershell
uv run pytest -q
```

Expected current baseline: full suite passes with the existing skip/xfail count.

## Notes For Opencode

- Keep this docs-first. Do not add new runtime behavior unless a doc assertion proves the current docs cannot represent the actual tool surface.
- Prefer concise examples over giant JSON payloads.
- Use exact current tool names with the `wf.workflow.*` namespace.
- Do not document raw MCP proxy tools as the workflow authoring path.
- Do not claim `delete_deployment` deletes artifacts or runs.
- Do not tell users to expect saved workflows to appear as new MCP tools in existing client sessions.
