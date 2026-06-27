# Draft Invalid Intermediate Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let draft workspaces persist patchable invalid intermediate graph states, especially forward routes to steps that will be added later, while keeping save/compile strict.

**Architecture:** Treat malformed JSON Patch as non-mutating, but treat valid draft edits that produce validation diagnostics as persisted revisions with `status: "invalid"`. Audit semantic helpers that currently raise before storage, then adjust only the forward-route path needed for iterative authoring. Final artifact save and compile continue to require valid drafts.

**Tech Stack:** Python 3.14, workflow draft workspace API, Typer CLI, pytest, Ruff, basedpyright.

---

## File Structure

- Modify `src/wf_api/draft_authoring.py`: allow forward-route semantic helper edits to reach draft workspace persistence instead of aborting.
- Inspect `src/wf_artifacts/drafts/api.py`: confirm whether `patch_workflow_draft`
  returns the patched draft when validation status is invalid; change it only
  if the failing test proves the draft is lost.
- Inspect `src/wf_artifacts/draft_workspaces/api.py`: confirm whether
  `patch_draft_workspace` stores invalid validation results with an incremented
  revision; change it only if the failing test proves the workspace is not
  persisted.
- Modify `tests/wf_api/test_drafts_service.py`: focused API behavior.
- Modify `tests/wf_cli/test_remote_target.py`: CLI/RPC behavior for forward route.
- Modify `docs/wf_cli.md`, `skills/wf-cli/SKILL.md`, and `skills/wf-workflow/references/draft-workspaces.md`: explain invalid intermediate drafts.
- Modify `docs/current_roadmap.md`: mark completion when done.

### Task 1: Capture The Current Forward-Route Failure

**Files:**
- Modify: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Write the failing API test**

Add a test that creates a draft from a simple capability, adds `wait` with a
route to missing `collect`, and asserts the edit persists as invalid:

```python
async def test_add_step_persists_invalid_forward_route(api_with_browser_specs) -> None:
    await api_with_browser_specs.create_draft_workspace_from_capability(
        workspace_id="browser",
        capability_name="local.browser_click.open_click_page",
        name="browser",
    )

    result = await api_with_browser_specs.add_step_from_capability(
        workspace_id="browser",
        revision=1,
        step_id="wait",
        capability_name="local.browser_click.wait_for_click",
        route_from_step="call",
        routes={"ok": "collect"},
        input_map={
            "state.session_id": "session_id",
            "input.simulate": "simulate",
            "input.timeout_seconds": "timeout_seconds",
        },
        bind_outputs={"after": "state.after"},
    )

    assert result["revision"] == 2
    assert result["status"] == "invalid"
    assert any(
        item["code"] == "unknown_edge_destination"
        for item in result["diagnostics"]
    )

    stored = await api_with_browser_specs.get_draft_workspace(
        workspace_id="browser",
        include_draft=True,
    )
    assert stored["draft"]["steps"]["wait"]["use"] == "local.browser_click.wait_for_click"
    assert stored["draft"]["routes"]["wait"]["ok"] == "collect"
```

Use the existing draft authoring API fixture/helper in
`tests/wf_api/test_drafts_service.py`. If the file does not already provide
browser-click specs, add a local helper that registers these three `NodeSpec`
objects with the same names and outcomes used by the example source:

```python
local.browser_click.open_click_page -> outcome ok
local.browser_click.wait_for_click -> outcome ok
local.browser_click.collect_snapshots -> outcome ok
```

The helper should define only the schemas needed by this test:

```python
open_click_page.output_schema.properties.before
open_click_page.output_schema.properties.session_id
wait_for_click.input_schema.properties.session_id
wait_for_click.input_schema.properties.simulate
wait_for_click.input_schema.properties.timeout_seconds
wait_for_click.output_schema.properties.after
collect_snapshots.input_schema.properties.session_id
collect_snapshots.input_schema.properties.before
collect_snapshots.input_schema.properties.after
collect_snapshots.output_schema.properties.before
collect_snapshots.output_schema.properties.after
```

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_add_step_persists_invalid_forward_route -q
```

Expected: failure showing the edit does not persist or the helper raises.

- [ ] **Step 3: Record exact failure mode in a code comment**

If the failure is caused by a pre-persistence `ValueError` or `KeyError`, add
one short comment in the implementation seam in the next task explaining why
draft helpers must allow invalid persisted revisions.

### Task 2: Persist Valid Edits With Invalid Validation Status

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Inspect/modify: `src/wf_artifacts/drafts/api.py`
- Inspect/modify: `src/wf_artifacts/draft_workspaces/api.py`

- [ ] **Step 1: Identify where the edit is lost**

Run the failing test with verbose output:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_add_step_persists_invalid_forward_route -q -vv
```

Expected: one concrete failure mode:

- helper raises before `patch_draft_workspace`, or
- `patch_workflow_draft` returns no `draft`, or
- workspace replacement rejects the invalid state.

- [ ] **Step 2: Fix only the observed loss point**

If `draft_authoring.py` raises before patching because a route target does not
exist, remove that preflight for target existence and let validation report the
diagnostic after the patch.

If `patch_workflow_draft` loses the patched draft on `KeyError`, change it so a
valid patched `dict` is returned alongside validation diagnostics:

```python
result = validate_workflow_draft(patched, node_defs=effective_node_defs)
if result["status"] == "valid":
    patched = WorkflowDraft.model_validate(patched).model_dump(mode="json")
return {"draft": patched, **result}
```

Do not change the existing malformed JSON Patch branch:

```python
if "draft" not in patched:
    # malformed JSON Patch remains non-mutating
```

- [ ] **Step 3: Run the focused API test**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_add_step_persists_invalid_forward_route -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add src/wf_api/draft_authoring.py src/wf_artifacts/drafts/api.py src/wf_artifacts/draft_workspaces/api.py tests/wf_api/test_drafts_service.py
git commit -m "fix: persist invalid draft forward routes"
```

### Task 3: Prove Invalid Drafts Stay Strict At Boundaries

**Files:**
- Modify: `tests/wf_api/test_drafts_service.py`
- Modify: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add API boundary assertions**

Extend the API test or add a second test:

```python
async def test_invalid_forward_route_cannot_compile_or_save(api_with_browser_specs) -> None:
    await api_with_browser_specs.create_draft_workspace_from_capability(
        workspace_id="browser",
        capability_name="local.browser_click.open_click_page",
        name="browser",
    )
    await api_with_browser_specs.add_step_from_capability(
        workspace_id="browser",
        revision=1,
        step_id="wait",
        capability_name="local.browser_click.wait_for_click",
        route_from_step="call",
        routes={"ok": "collect"},
        input_map={"state.session_id": "session_id"},
        bind_outputs={"after": "state.after"},
    )

    compiled = await api_with_browser_specs.compile_draft_workspace(
        workspace_id="browser"
    )

    assert compiled["status"] == "invalid"
    assert any(
        item["code"] == "unknown_edge_destination"
        for item in compiled["diagnostics"]
    )
```

If the API exposes `save_draft_workspace`, assert it returns invalid diagnostics
instead of saving an artifact. Follow existing tests for the exact method name
and assertion shape.

- [ ] **Step 2: Add CLI/RPC smoke coverage**

In `tests/wf_cli/test_remote_target.py`, add a command route test that invokes:

```python
[
    "--url",
    rpc_url,
    "draft",
    "add-step",
    "browser",
    "--revision",
    "1",
    "--step",
    "wait",
    "--capability",
    "local.browser_click.wait_for_click",
    "--from-step",
    "call",
    "--route",
    "ok=collect",
    "--input",
    "state.session_id=session_id",
    "--bind-output",
    "after=state.after",
]
```

Assert:

```python
assert result.exit_code == 0
payload = json.loads(result.output)
assert payload["status"] == "invalid"
assert payload["revision"] == 2
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py -q
```

Expected: PASS, except unrelated pre-existing failures must be documented in
the implementation report if they occur.

- [ ] **Step 4: Commit**

```powershell
git add tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
git commit -m "test: cover invalid intermediate draft routes"
```

### Task 4: Prove The Follow-Up Repair Path

**Files:**
- Modify: `tests/wf_api/test_drafts_service.py`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`

- [ ] **Step 1: Add a repair-path test**

Add a test that:

1. persists `wait -> collect` while `collect` is missing,
2. adds `collect` in the next revision, and
3. validates the workspace as valid.

Use the exact current API helpers:

```python
await api.add_step_from_capability(...)
await api.add_step_from_capability(
    workspace_id="browser",
    revision=2,
    step_id="collect",
    capability_name="local.browser_click.collect_snapshots",
    route_from_step="wait",
    input_map={
        "state.session_id": "session_id",
        "state.before": "before",
        "state.after": "after",
    },
    bind_outputs={"before": "state.final_before", "after": "state.final_after"},
)
validated = await api.validate_draft_workspace(workspace_id="browser")
assert validated["status"] == "valid"
```

Use the same fixture/helper from Task 1. Do not read example solution files or
copy plan JSON from `examples/browser_click_workflow`; this test is about the
draft authoring API contract.

- [ ] **Step 2: Run and verify PASS**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_forward_route_becomes_valid_after_target_step_is_added -q
```

Expected: PASS.

- [ ] **Step 3: Document the sequence**

In `skills/wf-workflow/references/draft-workspaces.md`, add:

```markdown
Forward routes in drafts are allowed as invalid intermediate state. If
`wf draft add-step --route ok=collect` returns `status: invalid`, add the
missing `collect` step next, then run `wf draft validate`. Do not save or
compile until validation is valid.
```

- [ ] **Step 4: Commit**

```powershell
git add tests/wf_api/test_drafts_service.py skills/wf-workflow/references/draft-workspaces.md
git commit -m "docs: explain invalid intermediate draft routes"
```

### Task 5: Final Docs And Verification

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-06-28-draft-invalid-intermediate-authoring.md`

- [ ] **Step 1: Update docs**

In `docs/wf_cli.md`, under draft workspace commands, add:

```markdown
Draft commands may return `status: invalid` after persisting an edit. That is
normal for intermediate authoring. Repair diagnostics, run `wf draft validate`,
then save/compile only after the workspace is valid.
```

In `skills/wf-cli/SKILL.md`, add:

```markdown
`status: invalid` from a draft edit is not always a command failure. Inspect
diagnostics and continue repairing the same workspace unless the command
reports a conflict or malformed patch.
```

- [ ] **Step 2: Update roadmap**

Add a completed bullet under Priority 1:

```markdown
- Completed: draft workspaces can persist invalid intermediate route states,
  allowing agents to add missing target steps before final validation/save.
```

- [ ] **Step 3: Archive this plan**

Move this file to:

```text
docs/historical/superpowers/plans/2026-06-28-draft-invalid-intermediate-authoring.md
```

- [ ] **Step 4: Run final verification**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py tests/docs -q
uv run ruff check src/wf_api/draft_authoring.py src/wf_artifacts/drafts/api.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
uv run ruff format --check src/wf_api/draft_authoring.py src/wf_artifacts/drafts/api.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
uv run basedpyright --level error src/wf_api/draft_authoring.py src/wf_artifacts/drafts/api.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
```

Expected: all new/focused tests pass. Any unrelated broad-suite failures must
be reported with file/test names and reason.

- [ ] **Step 5: Commit**

```powershell
git add docs/wf_cli.md skills/wf-cli/SKILL.md docs/current_roadmap.md docs/historical/superpowers/plans/2026-06-28-draft-invalid-intermediate-authoring.md
git commit -m "docs: archive invalid draft route plan"
```

## Self-Review

- Spec coverage: forward-route persistence, strict save/compile boundaries,
  diagnostics, docs, and repair path are covered.
- Placeholder scan: no placeholders remain.
- Type consistency: task names use current `wf draft add-step`, `handle`,
  `branch`, `compile`, and `validate` vocabulary.
