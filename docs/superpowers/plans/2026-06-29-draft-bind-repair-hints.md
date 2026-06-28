# Draft Bind Repair Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make schema-aware `wf draft bind` discoverable from validation output for workflow input, state, and workflow output projection errors.

**Architecture:** Draft validation already enriches diagnostics through `_with_workspace_repair_hints()` in `src/wf_api/drafts.py`. Extend `_draft_repair_hint()` beyond `invalid_destination_path` so agents get concrete `wf draft bind` or `wf draft set-workflow-output` commands instead of falling to JSON Patch.

**Tech Stack:** Python 3.14, validation diagnostics, Typer CLI help/docs, pytest.

---

### Task 1: Repair Hint For Missing Workflow Output Schema

**Files:**
- Modify: `src/wf_api/drafts.py`
- Test: `tests/wf_api/test_drafts_service.py`
- Test: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Write failing tests**

Add a draft with top-level output binding `{"path": "state.markdown", "target": "markdown"}` and empty `output_schema.properties`. Validate the workspace and assert the diagnostic has:

```python
assert diagnostic["code"] == "invalid_workflow_output_field"
assert "wf draft bind" in diagnostic["repair_hint"] or "wf draft set-workflow-output" in diagnostic["repair_hint"]
```

If the source came from a capability local output in the same step, prefer a `wf draft bind ... --from local.markdown --to output.markdown` hint. If the diagnostic lacks step/local context, use:

```text
wf draft set-workflow-output <workspace> --revision <n> --map state.markdown=markdown
```

- [ ] **Step 2: Run tests RED**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_validate_draft_workspace_hints_workflow_output_projection -q
```

Expected: fail because no repair hint is present.

- [ ] **Step 3: Implement hint branch**

In `_draft_repair_hint`, add handling for:

```python
if diagnostic.get("code") == "invalid_workflow_output_field":
    path = diagnostic.get("path")
    # For output[N].target diagnostics, tell the user how to edit top-level output.
    return (
        f"wf draft set-workflow-output {workspace_id} --revision {revision} "
        "--map <input.or.state.path>=<output_field>"
    )
```

Keep this generic if details do not include enough fields. Do not invent source paths.

- [ ] **Step 4: Run tests GREEN**

Run the test from Step 2. Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_api/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
git commit -m "fix: hint workflow output draft repairs"
```

### Task 2: Repair Hint For Undeclared Workflow Input Used By Step Input

**Files:**
- Modify: `src/wf_artifacts/drafts/api.py`
- Modify: `src/wf_api/drafts.py`
- Test: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Add diagnostic details**

When core reports `invalid_source_path` for a step input path like `steps.wait.input[0].path`, draft diagnostics should include enough details to build a hint:

```python
{
    "step_id": "wait",
    "source_path": "input.simulate",
    "target_field": "simulate",
}
```

Write a failing test that validates a draft using `input.simulate` without declaring `input_schema.properties.simulate` and asserts those details exist.

- [ ] **Step 2: Run test RED**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_validate_draft_workspace_details_invalid_input_source_path -q
```

Expected: fail because details are missing or incomplete.

- [ ] **Step 3: Add repair hint**

In `_draft_repair_hint`, if code is `invalid_source_path`, details include a step id, and `source_path` starts with `input.`, return:

```text
wf draft bind <workspace> --revision <n> --step <step_id> --from input.<field> --to local.<target_field>
```

This command declares the workflow input schema field from the capability input field and merges the step input binding.

- [ ] **Step 4: Run tests GREEN**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_validate_draft_workspace_details_invalid_input_source_path tests/wf_api/test_drafts_service.py::test_validate_draft_workspace_hints_input_schema_projection -q
```

- [ ] **Step 5: Commit**

```powershell
git add src/wf_artifacts/drafts/api.py src/wf_api/drafts.py tests/wf_api/test_drafts_service.py
git commit -m "fix: hint workflow input schema repairs"
```

### Task 3: Docs And Skills

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Add repair-hint examples**

Document:

```bash
wf draft bind report_ws --revision 4 --step read --from input.path --to local.path
wf draft bind report_ws --revision 5 --step render --from local.markdown --to output.markdown
wf draft set-workflow-output report_ws --revision 6 --map state.markdown=markdown
```

- [ ] **Step 2: Add skill rule**

Add:

```md
When validation gives a `repair_hint`, run that exact focused command before JSON Patch. For input/output schema errors, prefer `wf draft bind`.
```

- [ ] **Step 3: Verify**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py -q
uv run ruff check src/wf_api src/wf_artifacts tests/wf_api tests/wf_cli
uv run basedpyright --level error src/wf_api/drafts.py src/wf_artifacts/drafts/api.py tests/wf_api/test_drafts_service.py
```

- [ ] **Step 4: Commit**

```powershell
git add docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md docs/current_roadmap.md
git commit -m "docs: teach schema repair hints"
```

---

## Self-Review

- This plan extends existing repair-hint enrichment; it does not add a new schema system.
- It avoids guessing source paths when diagnostics do not carry enough details.
- It keeps JSON Patch as fallback, not the recommended first repair path.
