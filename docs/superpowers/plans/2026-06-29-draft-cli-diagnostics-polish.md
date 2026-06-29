# Draft CLI Diagnostics Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce agent retries by rejecting `set-input` local-target syntax mistakes early, adding actionable route-outcome repair guidance, and pinning repeated `bind` behavior.

**Architecture:** Keep each diagnostic at the layer with enough information to explain it correctly. The Typer adapter can identify `local.x` as an invalid `set-input` target before loading CLI context; `WorkflowDraftAuthoringApi.add_step_from_capability` owns declared capability outcomes and should produce route repair guidance; `bind_draft` behavior is already implemented and only needs a re-invocation regression.

**Tech Stack:** Python 3.14, Typer, pytest, existing `wf_api` semantic draft authoring and `wf_cli` command adapters.

---

## Scope

This plan implements three challenge-derived follow-ups:

1. `wf draft set-input --map input.text=local.text` fails immediately with a compact correction: local targets are bare names, so use `input.text=text`.
2. `wf draft add-step --route error=fail` for a capability that only declares `ok` reports declared, missing, and unknown outcomes plus an explicit remove/add repair.
3. Repeating a successful `wf draft bind input.x -> local.x` with the next revision remains valid and preserves one input binding.

This plan does **not** implement composite data shaping such as `state.title -> local.report.title` or synthesize a `state.report` object.

## File Map

- Modify `src/wf_cli/commands/drafts.py`
  - Add `_parse_step_input_map_flags` beside `_parse_map_flags`.
  - Use it only in `set_step_input_map`.
- Modify `tests/wf_cli/test_app.py`
  - Add a CLI parse-level regression for `input.text=local.text`.
  - Extend `set-input --help` assertions with a bare-target example.
- Modify `src/wf_api/draft_authoring.py`
  - Extract or inline a small route mismatch message builder.
  - Include actionable repair text for missing/unknown outcomes.
- Modify `tests/wf_api/test_drafts_service.py`
  - Add single-outcome unknown-route repair coverage.
  - Add repeated-bind coverage.
- Modify `docs/wf_cli.md`
- Modify `skills/wf-cli/SKILL.md`
- Modify `skills/wf-workflow/references/draft-workspaces.md`
- Modify `docs/current_roadmap.md`
  - Mark these three roadmap bullets complete after implementation.

---

### Task 1: Reject `local.x` Targets In `set-input`

**Files:**
- Modify: `tests/wf_cli/test_app.py`
- Modify: `src/wf_cli/commands/drafts.py`

- [ ] **Step 1: Write the failing CLI regression test**

Add near `test_wf_draft_map_help_explains_replace_merge_and_validate`:

```python
def test_wf_draft_set_input_rejects_local_prefixed_target() -> None:
    result = runner.invoke(
        app,
        [
            "draft",
            "set-input",
            "report_ws",
            "--revision",
            "1",
            "--step",
            "render",
            "--map",
            "input.text=local.text",
        ],
    )

    assert result.exit_code == 2
    output = " ".join(result.output.split())
    assert "bare local field" in output
    assert "input.text=text" in output
    assert "input.text=local.text" in output
```

This test must fail before implementation because the command currently proceeds to context loading instead of rejecting the map shape.

- [ ] **Step 2: Run the test to verify red state**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py::test_wf_draft_set_input_rejects_local_prefixed_target -q
```

Expected before implementation: failure because the compact bare-target diagnostic is absent.

- [ ] **Step 3: Add a command-specific parser**

In `src/wf_cli/commands/drafts.py`, add after `_parse_map_flags`:

```python
def _parse_step_input_map_flags(values: list[str] | None) -> dict[str, str]:
    """Parse graph-source to bare-local input mappings for one draft step."""
    parsed = _parse_map_flags(values)
    for source, target in parsed.items():
        if target.startswith("local."):
            bare_target = target.removeprefix("local.")
            raise typer.BadParameter(
                "--map target must be a bare local field; "
                f"use {source}={bare_target}, not {source}={target}"
            )
    return parsed
```

This deliberately rejects only the common unquoted `local.` prefix mistake. Do not reject quoted TOML local field names that merely contain punctuation.

- [ ] **Step 4: Route `set-input` through the new parser**

In `set_step_input_map`, replace:

```python
input_map = _parse_map_flags(mapping)
```

with:

```python
input_map = _parse_step_input_map_flags(mapping)
```

Do not change `set-output` or `set-workflow-output`; their target grammars differ.

- [ ] **Step 5: Improve `set-input` help text**

Extend the `set_step_input_map` docstring with:

```text
Targets are bare node-local field names. Use `--map input.text=text`, not
`--map input.text=local.text`.
```

In `test_wf_draft_map_help_explains_replace_merge_and_validate`, add:

```python
assert "input.text=text" in input_help
assert "input.text=local.text" in input_help
```

- [ ] **Step 6: Run CLI tests**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py -q -k "set_input_rejects_local_prefixed_target or map_help_explains_replace_merge_and_validate"
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py
git commit -m "fix: explain draft set-input local targets"
```

---

### Task 2: Add Actionable Route Outcome Repairs

**Files:**
- Modify: `tests/wf_api/test_drafts_service.py`
- Modify: `src/wf_api/draft_authoring.py`

- [ ] **Step 1: Add the single-outcome regression test**

Add near `test_add_step_from_capability_rejects_unknown_routes_for_multi_outcome`:

```python
@pytest.mark.asyncio
async def test_add_step_rejects_unknown_single_outcome_route_with_repair(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(
        tmp_path / "drafts_unknown_single_outcome"
    )
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="unknown_single",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError) as exc_info:
        await authoring.add_step_from_capability(
            workspace_id="unknown_single",
            revision=1,
            step_id="second",
            capability_name="demo.personal.echo_tool",
            routes={"ok": "__end__", "error": "fail"},
        )

    message = str(exc_info.value)
    assert "declared outcomes ('ok',)" in message
    assert "unknown routes ['error']" in message
    assert "remove --route entries for ['error']" in message
```

- [ ] **Step 2: Strengthen the existing multi-outcome test**

Change the existing context manager to capture the exception and assert:

```python
message = str(exc_info.value)
assert "declared outcomes ('ok', 'skipped')" in message
assert "unknown routes ['typo']" in message
assert "remove --route entries for ['typo']" in message
```

- [ ] **Step 3: Run tests to verify red state**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "unknown_single_outcome_route_with_repair or rejects_unknown_routes_for_multi_outcome"
```

Expected before implementation: tests fail because the message has no compact repair phrase.

- [ ] **Step 4: Build route mismatch and repair fragments**

In `WorkflowDraftAuthoringApi.add_step_from_capability`, replace the current `details` list and error construction with:

```python
details = [
    f"declared_outcomes={declared_outcomes!r}",
    f"missing_outcomes={sorted(missing_outcomes)!r}",
    f"unknown_outcomes={sorted(unknown_outcomes)!r}",
]
repairs: list[str] = []
if unknown_outcomes:
    repairs.append(
        f"remove --route entries for {sorted(unknown_outcomes)!r}"
    )
if missing_outcomes:
    repairs.append(
        f"add --route OUTCOME=TARGET for {sorted(missing_outcomes)!r}"
    )
raise ValueError(
    f"capability {capability_name!r} declares outcomes "
    f"{declared_outcomes}, but routes has missing routes "
    f"{sorted(missing_outcomes)} and unknown routes "
    f"{sorted(unknown_outcomes)}; "
    + ", ".join(details)
    + "; repair: "
    + "; ".join(repairs)
)
```

Keep this in the semantic authoring layer because only it knows the live capability outcomes.

- [ ] **Step 5: Run focused route tests**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "add_step_from_capability and route"
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
git commit -m "fix: add draft route repair guidance"
```

---

### Task 3: Pin Repeated Bind Behavior

**Files:**
- Modify: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Add the re-invocation regression**

Add after `test_bind_draft_workflow_input_to_step_input_reuses_existing_schema`:

```python
@pytest.mark.asyncio
async def test_bind_draft_workflow_input_to_step_input_can_repeat(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_repeat")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(workspace_id="bind_ws", draft=_echo_draft())

    first = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=1,
        step_id="echo",
        source_path="input.text",
        target_path="local.text",
    )
    second = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=first["revision"],
        step_id="echo",
        source_path="input.text",
        target_path="local.text",
    )
    workspace = await api.get_draft_workspace(
        workspace_id="bind_ws", include_draft=True
    )

    assert first["status"] == "valid"
    assert second["status"] == "valid"
    assert second["revision"] == 3
    assert workspace["draft"]["steps"]["echo"]["input"] == [
        {"target": "text", "path": "input.text"}
    ]
```

This test documents current revision semantics: repeated semantic edits are safe but still consume a revision. Changing no-op revision behavior is out of scope.

- [ ] **Step 2: Run the regression**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_bind_draft_workflow_input_to_step_input_can_repeat -q
```

Expected: pass without production changes.

- [ ] **Step 3: Commit**

```powershell
git add tests/wf_api/test_drafts_service.py
git commit -m "test: pin repeated draft bind behavior"
```

---

### Task 4: Update Live Docs And Skills

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update `docs/wf_cli.md`**

Add these points in the focused draft editing sections:

```markdown
`set-input` targets are bare node-local field names: write
`--map input.text=text`, not `--map input.text=local.text`.

When `add-step --route` rejects an outcome, use the declared outcomes and
repair text from the error. Remove unknown route entries and add one route for
each missing declared outcome.
```

- [ ] **Step 2: Update `skills/wf-cli/SKILL.md`**

Add concise agent rules:

```markdown
- `set-input --map` is `GRAPH_SOURCE=BARE_LOCAL_FIELD`; never prefix the target
  with `local.`.
- For `add-step --route`, route only outcomes reported by `wf cap inspect` or
  the command error's `declared_outcomes` field.
```

- [ ] **Step 3: Update draft workspace reference**

In `skills/wf-workflow/references/draft-workspaces.md`, add the same map grammar and route repair guidance beside the existing `set-input` and `add-step` examples.

- [ ] **Step 4: Mark roadmap bullets complete**

In `docs/current_roadmap.md`, move these three items from the planned follow-up list into completed wording:

```markdown
- Completed: `wf draft set-input` rejects `local.x` targets before RPC and
  shows the equivalent bare-target mapping.
- Completed: `wf draft add-step --route` errors include declared outcomes and
  direct add/remove repair guidance.
- Completed: repeated idempotent `wf draft bind input/state -> local` behavior
  is covered by regression tests.
```

Leave the composite-binding/data-shaping item planned.

- [ ] **Step 5: Commit docs**

```powershell
git add docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md docs/current_roadmap.md
git commit -m "docs: record draft CLI diagnostic guidance"
```

---

### Task 5: Verification And Archive

**Files:**
- Move: `docs/superpowers/plans/2026-06-29-draft-cli-diagnostics-polish.md`
- To: `docs/historical/superpowers/plans/2026-06-29-draft-cli-diagnostics-polish.md`

- [ ] **Step 1: Run focused tests**

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py -q -k "bind_draft or add_step or set_input or map_help"
```

Expected: all selected tests pass.

- [ ] **Step 2: Run static checks**

```powershell
uv run ruff check src/wf_api/draft_authoring.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py
uv run ruff format --check src/wf_api/draft_authoring.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py
uv run basedpyright --level error src/wf_api/draft_authoring.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py
```

Expected: no lint, formatting, or type errors.

- [ ] **Step 3: Run live smoke when the RPC server is available**

```powershell
uv run wf draft set-input smoke --revision 1 --step call --map input.text=local.text
```

Expected: exit code 2 with a compact correction containing `input.text=text`, before any RPC workspace lookup.

For route repair, use a disposable draft and a known single-outcome capability:

```powershell
$id = 'smoke_route_' + (Get-Date -Format 'HHmmss')
uv run wf draft create $id --capability wf.std.constant --name $id
uv run wf draft add-step $id --revision 1 --step second --capability wf.std.constant --route ok=__end__ --route error=fail
```

Expected: the error lists declared `ok`, identifies unknown `error`, and says to remove the unknown route entry.

- [ ] **Step 4: Archive the plan**

```powershell
git mv docs/superpowers/plans/2026-06-29-draft-cli-diagnostics-polish.md docs/historical/superpowers/plans/2026-06-29-draft-cli-diagnostics-polish.md
git add docs/historical/superpowers/plans/2026-06-29-draft-cli-diagnostics-polish.md
git commit -m "docs: archive draft CLI diagnostics plan"
```

---

## Self-Review

- Spec coverage: all three small roadmap follow-ups map to explicit tests and implementation tasks.
- Scope boundary: composite object/data-shaping semantics remain separate.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: the plan uses current symbols and command names: `_parse_map_flags`, `set_step_input_map`, `WorkflowDraftAuthoringApi.add_step_from_capability`, `bind_draft`, `wf draft set-input`, and `wf draft add-step`.

