# Draft Bind Repair Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make schema-aware `wf draft bind` correctly support workflow output projection and make focused bind repairs discoverable from validation output.

**Architecture:** Node output bindings can only target workflow state. Therefore `local.x -> output.y` must lower atomically into `local.x -> state.y` plus top-level `state.y -> output.y`, while projecting the capability field schema into both state and output schemas. Draft validation already enriches diagnostics through `_with_workspace_repair_hints()` in `src/wf_api/drafts.py`; extend those hints after the bind behavior is correct.

**Tech Stack:** Python 3.14, validation diagnostics, Typer CLI help/docs, pytest.

---

### Task 1: Make `bind local -> output` Produce Valid Workflow Output

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Test: `tests/wf_api/test_drafts_service.py`
- Test: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Write failing tests**

Add a capability-backed `render` step whose capability output schema declares `markdown`. Call:

```python
result = await authoring.bind_draft(
    workspace_id="report",
    revision=1,
    step_id="render",
    source_path="local.markdown",
    target_path="output.markdown",
)
```

Assert the edit is valid and lowered through state:

```python
assert result["status"] == "valid"
workspace = await drafts.get_draft_workspace(workspace_id="report", include_draft=True)
assert workspace["draft"]["steps"]["render"]["output"] == [
    {"source": "markdown", "target": "state.markdown"}
]
assert workspace["draft"]["output"] == [
    {"path": "state.markdown", "target": "markdown"}
]
assert workspace["draft"]["state_schema"]["properties"]["markdown"]["type"] == "string"
assert workspace["draft"]["output_schema"]["properties"]["markdown"]["type"] == "string"
```

- [ ] **Step 2: Run tests RED**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_bind_draft_local_output_to_workflow_output_lowers_through_state -q
```

Expected: fail because current code writes an illegal `output.*` node destination.

- [ ] **Step 3: Implement hint branch**

In `WorkflowDraftAuthoringApi.bind_draft`, split the existing local-output branch:

```python
if source_root == "local" and target_root == "output":
    output_parts = target_parts
    state_path = f"state.{'.'.join(output_parts)}"
    # Project the capability output field into state_schema and output_schema.
    # Merge the step local->state binding and top-level state->output binding
    # in one revision-checked patch.
```

Use `project_property_to_schema_path` for both schemas so `$defs` are preserved. Do not create a node output binding with an `output.*` target; `OutputBinding.target` is `StatePath`.

- [ ] **Step 4: Run tests GREEN**

Run the test from Step 2. Expected: pass with `status: valid`.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
git commit -m "fix: lower workflow output binds through state"
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
When validation gives a `repair_hint`, run that exact focused command before JSON Patch. Use `wf draft bind local.x -> output.y` when one capability output should become public workflow output; it creates the required state intermediary and schemas atomically.
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
