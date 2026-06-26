# Draft Validation Repair Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `wf draft validate` return structured repair hints for common draft authoring failures, starting with missing state fields for step output bindings.

**Architecture:** Preserve low-level draft validation in `wf_artifacts`, but stop flattening core workflow validation into opaque `ValueError` text. Convert `wf_core.validation.ValidationIssue` objects into `DraftDiagnostic` objects with structured `details`, then let `wf_api` add workspace-aware CLI repair hints when validating a stored draft workspace. The first exact hint targets the helper we just added: `wf draft bind-output-to-state`.

**Tech Stack:** Python 3.14, Pydantic DTOs, existing `wf_core` validation reports, existing draft workspace API, pytest, ruff, basedpyright.

---

## Scope

When a draft contains a step output binding like:

```json
{
  "source": {"root": "local", "parts": ["after"]},
  "target": {"root": "state", "parts": ["after"]}
}
```

but `state_schema.properties.after` is missing, `wf draft validate <workspace_id>` should return a diagnostic like:

```json
{
  "code": "invalid_destination_path",
  "path": "nodes[0].output[0].target",
  "step_id": "wait",
  "message": "destination path must start with state. and reference a declared root field",
  "details": {
    "output_field": "after",
    "state_path": "state.after"
  },
  "repair_hint": "wf draft bind-output-to-state browser_ws --revision 5 --step wait --output after --state state.after"
}
```

This slice only adds exact repair hints for stored draft validation. `patch_draft_workspace` may still return diagnostics without exact commands; users and agents should run `wf draft validate` after edits.

Non-goals:

- Do not add auto-fix.
- Do not infer routes.
- Do not parse arbitrary exception strings.
- Do not add nested state path support.
- Do not reimplement JSON Schema validation.

## Files

- Modify: `src/wf_artifacts/drafts/api.py`
  - Add `repair_hint` and `details` to `DraftDiagnostic`.
  - Validate compiled workflows with `workflow.validate_structure()`.
  - Convert core validation issues into draft diagnostics.
- Modify: `src/wf_api/drafts.py`
  - Add workspace-aware repair hints in `validate_draft_workspace`.
- Tests:
  - `tests/artifacts/test_draft_adapter.py`
  - `tests/wf_api/test_drafts_service.py`
- Docs/skills:
  - `docs/wf_cli.md`
  - `skills/wf-cli/SKILL.md`
  - `skills/wf-workflow/references/draft-workspaces.md`
  - `docs/current_roadmap.md`

---

## Task 1: Preserve Core Validation Issues In Draft Diagnostics

**Files:**

- Modify: `src/wf_artifacts/drafts/api.py`
- Modify: `tests/artifacts/test_draft_adapter.py`

- [ ] **Step 1: Write failing low-level draft validation test**

In `tests/artifacts/test_draft_adapter.py`, add this test near the existing `validate_workflow_draft` tests:

```python
def test_validate_workflow_draft_reports_structured_output_destination_issue() -> None:
    draft = {
        "name": "missing_state_field",
        "input_schema": {},
        "state_schema": {"type": "object", "properties": {}},
        "output_schema": {},
        "start": "snap",
        "steps": {
            "snap": {
                "use": "demo.snapshot",
                "output": [
                    {
                        "source": {"root": "local", "parts": ["after"]},
                        "target": {"root": "state", "parts": ["after"]},
                    }
                ],
            }
        },
        "routes": {"snap": {"ok": "__end__"}},
    }

    result = validate_workflow_draft(draft)

    assert result["status"] == "invalid"
    diagnostic = result["diagnostics"][0]
    assert diagnostic["code"] == "invalid_destination_path"
    assert diagnostic["path"] == "nodes[0].output[0].target"
    assert diagnostic["step_id"] == "snap"
    assert diagnostic["details"] == {
        "output_field": "after",
        "state_path": "state.after",
    }
    assert "repair_hint" not in diagnostic
```

- [ ] **Step 2: Run test to verify red**

Run:

```powershell
uv run pytest tests/artifacts/test_draft_adapter.py -q -k "structured_output_destination_issue"
```

Expected: fail because `validate_workflow_draft` currently returns valid or flattens structure errors without these details.

- [ ] **Step 3: Extend `DraftDiagnostic`**

In `src/wf_artifacts/drafts/api.py`, change `DraftDiagnostic` to:

```python
class DraftDiagnostic(BaseModel):
    """Machine-readable reason a keyed draft could not be compiled."""

    code: str
    path: str
    step_id: str | None = None
    message: str
    repair_hint: str | None = None
    details: dict[str, Any] = {}
```

Keep `details` as a plain JSON object. Do not add a specific typed model yet; draft diagnostics cover several validation families.

- [ ] **Step 4: Add core issue conversion helpers**

In `src/wf_artifacts/drafts/api.py`, add imports:

```python
import re

from wf_core.models.steps import OutputBinding
from wf_core.models.workflow import Workflow
from wf_core.validation.issues import ValidationIssue, ValidationIssueCode
```

Add these helpers after `_diagnostic_from_exception`:

```python
_NODE_OUTPUT_TARGET_RE = re.compile(r"^nodes\[(?P<node_index>\d+)\]\.output\[(?P<output_index>\d+)\]\.target$")


def _diagnostics_from_workflow_issues(workflow: Workflow) -> list[DraftDiagnostic]:
    report = workflow.validate_structure()
    return [_diagnostic_from_issue(workflow, issue) for issue in report.errors]


def _diagnostic_from_issue(
    workflow: Workflow,
    issue: ValidationIssue,
) -> DraftDiagnostic:
    step_id = _step_id_for_issue_path(workflow, issue.path)
    return DraftDiagnostic(
        code=str(issue.code),
        path=issue.path,
        step_id=step_id,
        message=issue.message,
        details=_details_for_issue(workflow, issue),
    )


def _step_id_for_issue_path(workflow: Workflow, path: str) -> str | None:
    match = re.match(r"^nodes\[(?P<node_index>\d+)\]", path)
    if match is None:
        return None
    node_index = int(match.group("node_index"))
    if node_index >= len(workflow.nodes):
        return None
    node_id = getattr(workflow.nodes[node_index], "id", None)
    return node_id if isinstance(node_id, str) else None


def _details_for_issue(
    workflow: Workflow,
    issue: ValidationIssue,
) -> dict[str, Any]:
    if issue.code is not ValidationIssueCode.INVALID_DESTINATION_PATH:
        return {}
    match = _NODE_OUTPUT_TARGET_RE.match(issue.path)
    if match is None:
        return {}
    node_index = int(match.group("node_index"))
    output_index = int(match.group("output_index"))
    if node_index >= len(workflow.nodes):
        return {}
    outputs = getattr(workflow.nodes[node_index], "output", None)
    if not isinstance(outputs, list) or output_index >= len(outputs):
        return {}
    binding = outputs[output_index]
    if not isinstance(binding, OutputBinding):
        return {}
    output_field = _single_local_field(binding)
    if output_field is None:
        return {}
    return {
        "output_field": output_field,
        "state_path": str(binding.target),
    }


def _single_local_field(binding: OutputBinding) -> str | None:
    parts = getattr(binding.source, "parts", None)
    root = getattr(binding.source, "root", None)
    if root != "local" or not isinstance(parts, list) or len(parts) != 1:
        return None
    field = parts[0]
    return field if isinstance(field, str) else None
```

- [ ] **Step 5: Validate compiled workflow structure**

In `validate_workflow_draft`, replace:

```python
    try:
        compiled_plan = compile_workflow_draft(draft)
    except (ValidationError, KeyError, ValueError) as exc:
        return _invalid_result(_diagnostic_from_exception(exc))
```

with:

```python
    try:
        parsed = WorkflowDraft.model_validate(draft)
        workflow = build_workflow_from_draft(parsed)
    except (ValidationError, KeyError, ValueError) as exc:
        return _invalid_result(_diagnostic_from_exception(exc))
    diagnostics = _diagnostics_from_workflow_issues(workflow)
    if diagnostics:
        return _invalid_result(*diagnostics)
    compiled_plan = workflow.model_dump(mode="json", by_alias=True, exclude={"node_defs"})
```

Then update `_invalid_result` to accept multiple diagnostics:

```python
def _invalid_result(*diagnostics: DraftDiagnostic) -> JsonObject:
    return {
        "status": "invalid",
        "diagnostics": [item.model_dump(mode="json", exclude_none=True) for item in diagnostics],
    }
```

Do not change `compile_workflow_draft`; it should remain a compiler that raises on model/adapter failures and returns raw workflow JSON.

- [ ] **Step 6: Run low-level tests to verify green**

Run:

```powershell
uv run pytest tests/artifacts/test_draft_adapter.py -q -k "structured_output_destination_issue or validate_workflow_draft"
```

Expected: selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add src/wf_artifacts/drafts/api.py tests/artifacts/test_draft_adapter.py
git commit -m "feat: expose structured draft validation issues"
```

---

## Task 2: Add Workspace-Aware Repair Hints In Draft API

**Files:**

- Modify: `src/wf_api/drafts.py`
- Modify: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Write failing repair hint test**

In `tests/wf_api/test_drafts_service.py`, add this test near `test_validate_draft_workspace_refreshes_status`:

```python
@pytest.mark.asyncio
async def test_validate_draft_workspace_suggests_bind_output_to_state(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_repair_hint")
    api, service = _draft_api(artifact_store)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="snapshot_ws",
        draft={
            "name": "snapshot",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "snap",
            "steps": {
                "snap": {
                    "use": "demo.personal.snapshot_tool",
                    "input": [],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["after"]},
                            "target": {"root": "state", "parts": ["after"]},
                        }
                    ],
                }
            },
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    payload = await api.validate_draft_workspace(workspace_id="snapshot_ws")

    diagnostic = payload["diagnostics"][0]
    assert diagnostic["code"] == "invalid_destination_path"
    assert diagnostic["step_id"] == "snap"
    assert diagnostic["repair_hint"] == (
        "wf draft bind-output-to-state snapshot_ws --revision 1 "
        "--step snap --output after --state state.after"
    )
```

- [ ] **Step 2: Run test to verify red**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "suggests_bind_output_to_state"
```

Expected: fail because `repair_hint` is missing.

- [ ] **Step 3: Add repair hint enrichment helpers**

In `src/wf_api/drafts.py`, add this helper near `_state_root_field`:

```python
def _with_workspace_repair_hints(
    payload: dict[str, Any],
    *,
    workspace_id: str,
    revision: int,
) -> dict[str, Any]:
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return payload
    enriched = []
    changed = False
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            enriched.append(diagnostic)
            continue
        repaired = dict(diagnostic)
        hint = _draft_repair_hint(
            repaired,
            workspace_id=workspace_id,
            revision=revision,
        )
        if hint is not None:
            repaired["repair_hint"] = hint
            changed = True
        enriched.append(repaired)
    if not changed:
        return payload
    return {**payload, "diagnostics": enriched}


def _draft_repair_hint(
    diagnostic: Mapping[str, Any],
    *,
    workspace_id: str,
    revision: int,
) -> str | None:
    if diagnostic.get("code") != "invalid_destination_path":
        return None
    step_id = diagnostic.get("step_id")
    details = diagnostic.get("details")
    if not isinstance(step_id, str) or not isinstance(details, dict):
        return None
    output_field = details.get("output_field")
    state_path = details.get("state_path")
    if not isinstance(output_field, str) or not isinstance(state_path, str):
        return None
    return (
        f"wf draft bind-output-to-state {workspace_id} --revision {revision} "
        f"--step {step_id} --output {output_field} --state {state_path}"
    )
```

This helper belongs in `wf_api`, not `wf_artifacts`, because command names and workspace revisions are product-surface concerns.

- [ ] **Step 4: Enrich `validate_draft_workspace` diagnostics before saving**

In `WorkflowDraftApi.validate_draft_workspace`, replace:

```python
        validation = await self.validate_draft(draft=workspace.draft)
```

with:

```python
        validation = _with_workspace_repair_hints(
            await self.validate_draft(draft=workspace.draft),
            workspace_id=workspace_id,
            revision=workspace.revision,
        )
```

This stores enriched diagnostics in the workspace summary so repeated inspection shows the same hint.

- [ ] **Step 5: Run API tests to verify green**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "suggests_bind_output_to_state or validate_draft_workspace"
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_api/drafts.py tests/wf_api/test_drafts_service.py
git commit -m "feat: add draft validation repair hints"
```

---

## Task 3: CLI/RPC Smoke And Docs

**Files:**

- Modify: `tests/wf_cli/test_remote_target.py`
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-06-26-draft-validation-repair-hints.md` to `docs/historical/superpowers/plans/2026-06-26-draft-validation-repair-hints.md`

- [ ] **Step 1: Extend CLI/RPC draft validation smoke test**

In `tests/wf_cli/test_remote_target.py`, update
`test_wf_remote_draft_artifact_deploy_lifecycle`. After the existing successful
`validated` assertion block, add a second invalid draft workspace:

```python
    invalid_created = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "create-from-capability",
            "repair_ws",
            "wf.std.constant",
            "--name",
            "repair_constant",
        ],
    )
    assert invalid_created.exit_code == 0, invalid_created.output

    invalid_patch = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "set-output",
            "repair_ws",
            "--revision",
            "1",
            "--step",
            "call",
            "--map",
            "value=state.missing",
        ],
    )
    assert invalid_patch.exit_code == 0, invalid_patch.output

    invalid_validated = runner.invoke(
        app,
        [*base_args, "draft", "validate", "repair_ws"],
    )
    assert invalid_validated.exit_code == 0, invalid_validated.output
    assert '"status": "invalid"' in invalid_validated.output
    assert "bind-output-to-state repair_ws --revision 2" in invalid_validated.output
    assert "--step call --output value --state state.missing" in invalid_validated.output
```

This test uses the existing `_patch_rpc_client_to_server` setup already present
in `test_wf_remote_draft_artifact_deploy_lifecycle`, so it proves the CLI
preserves the repair hint returned by the RPC-backed API path.

- [ ] **Step 2: Run CLI smoke test**

Run:

```powershell
uv run pytest tests/wf_cli/test_remote_target.py -q -k "repair_hints or draft_validate"
```

Expected: pass.

- [ ] **Step 3: Update CLI docs**

In `docs/wf_cli.md`, near draft validation docs, add:

```markdown
Draft validation diagnostics may include `repair_hint` commands. Treat these as
the next focused command to try, not as proof that the draft is fixed. Re-run
`wf draft validate <workspace_id>` after applying a hint.
```

- [ ] **Step 4: Update skills**

In `skills/wf-cli/SKILL.md`, add under draft rules:

```markdown
When `wf draft validate` returns a `repair_hint`, prefer running that focused
command before writing JSON Patch manually. Re-run `wf draft validate` after the
repair.
```

In `skills/wf-workflow/references/draft-workspaces.md`, add:

```markdown
Validation repair hints are product guidance. If a diagnostic suggests
`bind-output-to-state`, use it before hand-editing `state_schema` or step output
bindings.
```

- [ ] **Step 5: Update roadmap**

In `docs/current_roadmap.md`, add:

```markdown
- Completed: draft validation now preserves structured core validation issues
  and adds exact `bind-output-to-state` repair hints for missing state fields.
```

- [ ] **Step 6: Move plan to historical**

Run:

```powershell
Move-Item docs\superpowers\plans\2026-06-26-draft-validation-repair-hints.md docs\historical\superpowers\plans\2026-06-26-draft-validation-repair-hints.md
```

- [ ] **Step 7: Run final verification**

Run:

```powershell
uv run pytest tests/artifacts/test_draft_adapter.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py -q -k "structured_output_destination_issue or suggests_bind_output_to_state or repair_hints or validate_draft_workspace"
uv run ruff check src/wf_artifacts/drafts/api.py src/wf_api/drafts.py tests/artifacts/test_draft_adapter.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
uv run basedpyright --level error src/wf_artifacts/drafts/api.py src/wf_api/drafts.py tests/artifacts/test_draft_adapter.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
```

Expected:

- Focused tests pass.
- Ruff reports `All checks passed!`.
- Basedpyright reports `0 errors`.

- [ ] **Step 8: Commit**

```powershell
git add -A
git commit -m "docs: record draft validation repair hints"
```

---

## Self-Review Notes

- This plan intentionally returns structured validation issues before generating repair hints. Regex-parsing flattened exception text would be brittle and would hide useful issue codes.
- Exact CLI repair hints are added in `wf_api` because only that layer knows the workspace id and revision.
- The first repair hint only targets `invalid_destination_path` for node output bindings with a single top-level local output field.
- This plan does not change `bind-output-to-state`; it only makes validation point agents toward it.
