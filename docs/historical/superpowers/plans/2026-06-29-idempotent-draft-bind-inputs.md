# Idempotent Draft Bind Inputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `wf draft bind --from input.x --to local.x` and `wf draft bind --from state.x --to local.x` safe when the workflow schema path is already declared, while preserving real schema-conflict failures.

**Architecture:** Extend the existing semantic authoring service instead of adding another command. `bind_draft` already owns capability-aware schema projection and step input/output map mutation; this slice changes only the input-side projection policy to skip schema projection when the graph source path already exists, then updates CLI/help/skills so agents understand `bind` versus `set-input`.

**Tech Stack:** Python 3.14, pytest, Typer CLI, existing `wf_api.draft_authoring.WorkflowDraftAuthoringApi`, existing TOML path strings.

---

## Context

Recent debug challenge runs succeeded but repeatedly reported this UX issue:

```text
wf draft bind <workspace> --revision 1 --step call --from input.text --to local.text
ValueError: schema path 'text' already exists
```

The command is semantically valid as a repair/idempotent operation: the draft already has `input_schema.properties.text`, and the caller still wants the step input map `input.text -> local.text`.

This is different from conflicting schema projection. If the workflow schema already has `text` with incompatible shape, this slice deliberately does **not** attempt semantic compatibility. The behavior should be:

- If `input.text` / `state.text` is missing, project it from the capability input field schema and set the step input map.
- If `input.text` / `state.text` already exists, skip projection and set the step input map.
- If an ancestor path is invalid, such as `state.session` being a string while binding `state.session.text`, keep failing.
- If the local input field does not exist on the capability, keep failing.

## File Map

- Modify `src/wf_api/draft_authoring.py`
  - Reuse or add a tiny `_schema_path_exists(...)` helper near the existing path helpers.
  - In `WorkflowDraftAuthoringApi.bind_draft`, for `target_root == "local"` and `source_root in {"input", "state"}`, skip `project_property_to_schema_path(...)` when the graph source schema path already exists.
- Modify `src/wf_cli/commands/drafts.py`
  - Clarify `bind` help: use it when schema projection may be needed; for pure map replacement/merge, use `set-input`.
- Modify `tests/wf_api/test_drafts_service.py`
  - Add regression tests for idempotent input and state binds.
- Modify `tests/wf_cli/test_app.py`
  - Add/extend bind help assertion.
- Modify `docs/wf_cli.md`
  - Document idempotent bind behavior and `set-input` guidance.
- Modify `skills/wf-cli/SKILL.md`
  - Teach agents: use `set-input --merge` for pure map edits; use `bind` when the schema may need projection or when following a repair hint.
- Modify `skills/wf-workflow/references/draft-workspaces.md`
  - Mirror the same authoring guidance.
- Modify `docs/current_roadmap.md`
  - Add a short completed bullet once implemented.

---

### Task 1: Add API Regression Tests

**Files:**
- Modify: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Add an input-schema idempotency regression test**

Add this test near `test_bind_draft_workflow_input_to_step_input_projects_input_schema`:

```python
@pytest.mark.asyncio
async def test_bind_draft_workflow_input_to_step_input_reuses_existing_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_bind_existing_input_schema"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="bind_ws",
        draft=_echo_draft(),
    )

    result = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=1,
        step_id="echo",
        source_path="input.text",
        target_path="local.text",
    )
    workspace = await api.get_draft_workspace(
        workspace_id="bind_ws", include_draft=True
    )

    assert result["status"] == "valid", result["diagnostics"]
    assert result["revision"] == 2
    assert workspace["draft"]["steps"]["echo"]["input"] == [
        {"target": "text", "path": "input.text"}
    ]
```

- [ ] **Step 2: Add a state-schema idempotency regression test**

Add this test near the input-schema test:

```python
@pytest.mark.asyncio
async def test_bind_draft_workflow_state_to_step_input_reuses_existing_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_bind_existing_state_schema"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    draft = {
        **_echo_draft(),
        "state_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
        "steps": {
            "echo": {
                "use": "demo.personal.echo_tool",
                "input": [],
                "output": [],
            }
        },
    }
    await api.create_draft_workspace(workspace_id="bind_ws", draft=draft)

    result = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=1,
        step_id="echo",
        source_path="state.text",
        target_path="local.text",
    )
    workspace = await api.get_draft_workspace(
        workspace_id="bind_ws", include_draft=True
    )

    assert result["status"] == "valid", result["diagnostics"]
    assert result["revision"] == 2
    assert workspace["draft"]["steps"]["echo"]["input"] == [
        {"target": "text", "path": "state.text"}
    ]
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "bind_draft_workflow_input_to_step_input_reuses_existing_schema or bind_draft_workflow_state_to_step_input_reuses_existing_schema"
```

Expected before implementation: both tests fail with `ValueError: schema path 'text' already exists`.

- [ ] **Step 4: Commit failing tests**

```powershell
git add tests/wf_api/test_drafts_service.py
git commit -m "test: cover idempotent draft input bind"
```

---

### Task 2: Make Input-Side `bind_draft` Idempotent

**Files:**
- Modify: `src/wf_api/draft_authoring.py`

- [ ] **Step 1: Add or reuse a schema-path existence helper**

If `_schema_path_exists` already exists in `src/wf_api/draft_authoring.py`, reuse it. If it does not, add this near `_local_parts`:

```python
def _schema_path_exists(schema: Mapping[str, Any], parts: Sequence[str]) -> bool:
    current: Any = schema
    for part in parts:
        if not isinstance(current, Mapping):
            return False
        properties = current.get("properties")
        if not isinstance(properties, Mapping) or part not in properties:
            return False
        current = properties[part]
    return True
```

Make sure imports include `Mapping`:

```python
from collections.abc import Mapping, Sequence
```

- [ ] **Step 2: Skip projection for already-declared graph source paths**

In `WorkflowDraftAuthoringApi.bind_draft`, inside:

```python
if target_root == "local" and source_root in {"input", "state"}:
```

replace the unconditional projection:

```python
projected = project_property_to_schema_path(
    target_schema=target_schema,
    source_schema=input_schema,
    source_field=local_field,
    target_parts=source_parts,
)
```

with:

```python
if _schema_path_exists(target_schema, source_parts):
    projected = target_schema
else:
    projected = project_property_to_schema_path(
        target_schema=target_schema,
        source_schema=input_schema,
        source_field=local_field,
        target_parts=source_parts,
    )
```

Keep the patch shape unchanged:

```python
{"op": "replace", "path": f"/{schema_key}", "value": projected}
```

This may write the same schema back. That is acceptable for this slice because the operation still intentionally mutates the step input map and bumps the workspace revision.

- [ ] **Step 3: Run API tests**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "bind_draft_workflow_input_to_step_input"
```

Expected: projection and idempotency tests pass.

- [ ] **Step 4: Run broader draft focused tests**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_api/test_schema_projection.py -q -k "bind_draft or project_output_property or set_workflow_output_map or add_step_projects_explicit_optional_workflow_inputs"
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit implementation**

```powershell
git add src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
git commit -m "fix: make draft input bind idempotent"
```

---

### Task 3: Clarify CLI Help And Agent-Facing Docs

**Files:**
- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `tests/wf_cli/test_app.py`
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update CLI bind help text**

In `src/wf_cli/commands/drafts.py`, update the `bind_draft` docstring from:

```python
"""Bind a capability step path and project the matching schema.

Direction matters. Use input/state -> local for step inputs and local ->
state/output for step outputs. Run `wf draft validate <workspace_id>` after
this command.
"""
```

to:

```python
"""Bind a capability step path and project missing schema when needed.

Direction matters. Use input/state -> local for step inputs and local ->
state/output for step outputs. If the workflow schema field already exists,
the command reuses it and updates the step binding. For pure input-map edits
where schema is already known, `wf draft set-input --merge` is also valid.
Run `wf draft validate <workspace_id>` after this command.
"""
```

- [ ] **Step 2: Update CLI help test**

In `tests/wf_cli/test_app.py`, find `test_wf_draft_bind_help_explains_direction` and add assertions:

```python
help_text = " ".join(result.output.split())
assert "project missing schema" in help_text
assert "set-input --merge" in help_text
```

Keep existing assertions.

- [ ] **Step 3: Update `docs/wf_cli.md`**

In the “Bind A Step Path” section, add this paragraph after the direction explanation:

```markdown
If the workflow schema field already exists, `bind` reuses it and only updates
the step binding. Use `set-input --merge` for pure input-map edits when no
schema projection is needed.
```

- [ ] **Step 4: Update `skills/wf-cli/SKILL.md`**

Replace the current optional-input guidance with:

```markdown
Draft creation auto-binds required capability inputs only. Optional inputs are
reported in wrapper-hint notes; bind them explicitly only when the workflow
should expose them. Use `wf draft bind --from input.x --to local.x` for an
existing step when schema projection may be needed; it is safe if the schema
field already exists. Use `wf draft set-input --merge --map input.x=x` for a
pure input-map edit when the workflow schema is already declared.
```

- [ ] **Step 5: Update `skills/wf-workflow/references/draft-workspaces.md`**

Add this after the `set-input` direction paragraph:

```markdown
`bind input.x -> local.x` is schema-aware and idempotent when `input.x` is
already declared. Use it for repair hints or schema projection. Use
`set-input --merge --map input.x=x` when you only need to update a step input
map.
```

- [ ] **Step 6: Update roadmap**

Add a short completed bullet under the draft/CLI section of `docs/current_roadmap.md`:

```markdown
- Completed: `wf draft bind` now reuses existing workflow input/state schema
  fields when binding to step-local inputs, avoiding redundant-schema failures
  found by debug challenge runs.
```

- [ ] **Step 7: Run docs/help tests**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py::test_wf_draft_bind_help_explains_direction -q
```

Expected: pass.

- [ ] **Step 8: Commit docs/help**

```powershell
git add src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md docs/current_roadmap.md
git commit -m "docs: clarify draft bind input behavior"
```

---

### Task 4: Verification And Live Smoke

**Files:**
- No source edits expected.

- [ ] **Step 1: Run focused verification**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py::test_wf_draft_bind_help_explains_direction -q
uv run ruff check src/wf_api/draft_authoring.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py
uv run ruff format --check src/wf_api/draft_authoring.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py
uv run basedpyright --level error src/wf_api/draft_authoring.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py
```

Expected:

- pytest selected tests pass
- ruff check has no errors
- ruff format reports files already formatted
- basedpyright reports 0 errors

- [ ] **Step 2: Run live RPC smoke if server is running**

If the user has `wf-rpc-server --config wf.config.json --host 127.0.0.1 --port 8765` running, use this smoke:

```powershell
$id = 'smoke_bind_idem_' + (Get-Date -Format 'HHmmss')
uv run wf draft create $id --capability everything.default.echo --name $id
uv run wf draft bind $id --revision 1 --step call --from input.message --to local.message
uv run wf draft validate $id
uv run wf draft inspect $id --include-draft
```

Expected:

- `draft bind` returns `status: valid`, not `ValueError: schema path 'message' already exists`.
- inspect shows step `call.input` contains `{"path": "input.message", "target": "message"}`.

- [ ] **Step 3: Archive this plan after implementation**

Move this plan to historical:

```powershell
git mv docs/superpowers/plans/2026-06-29-idempotent-draft-bind-inputs.md docs/historical/superpowers/plans/2026-06-29-idempotent-draft-bind-inputs.md
git commit -m "docs: archive idempotent draft bind plan"
```

---

## Self-Review

- Spec coverage: This plan covers the observed duplicate-schema UX issue for `input/state -> local` binds, help/docs guidance, and live smoke. It does not implement composite object binding such as `state.title=report.title`; that is a separate data-shaping feature.
- Placeholder scan: No `TBD`, `TODO`, or vague “add tests” steps remain.
- Type consistency: The plan uses existing names: `WorkflowDraftAuthoringApi.bind_draft`, `_schema_path_exists`, `project_property_to_schema_path`, `wf draft bind`, and `wf draft set-input --merge`.

