# Wrapper Draft Next Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add advisory `next_actions` to `wf.workflow.create_draft_workspace_from_capability` so LLM clients can continue safely even when they cannot easily read the docs.

**Architecture:** Keep `wrapper_hints` as the source of truth for scaffold confidence, missing decisions, and mapping warnings. Add a small typed result object that converts those hints into concrete next-tool guidance. `can_save_now` is advisory only; do not block saving or enforce policy in this slice.

**Tech Stack:** Python 3.14, Pydantic v2, FastMCP tool schemas, pytest, ruff, basedpyright.

---

## Scope

Add `next_actions` to `CreateDraftWorkspaceFromCapabilityResult` and handler payloads.

Do:

- Return machine-readable guidance from `create_draft_workspace_from_capability`.
- Make `can_save_now` advisory only.
- Recommend `wf.workflow.patch_draft_workspace` when `wrapper_hints.missing_decisions` is non-empty or confidence is low.
- Recommend `wf.workflow.validate_draft_workspace` when the scaffold looks safe enough to validate.
- Include patch examples for common missing decisions.
- Document the field and add schema tests.

Do not:

- Block `create_artifact_from_workspace`.
- Add a new tool.
- Infer raw MCP `content[0].text` automatically.
- Treat boolean output candidates as real routing semantics.
- Replace `wrapper_hints`; `next_actions` should summarize and guide, not duplicate every hint.

## Files

- Modify: `src/wf_mcp/workflow_surface/models.py`
  - Add typed `WrapperDraftNextActions` and `WrapperDraftPatchExample` Pydantic models.
  - Add `next_actions` field to `CreateDraftWorkspaceFromCapabilityResult`.
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
  - Add helper that derives `next_actions` from `wrapper_hints` and workspace id/revision.
  - Include `next_actions` in `create_draft_workspace_from_capability` result.
- Test: `tests/wf_mcp/workflow_surface/test_drafts.py`
  - Assert high-confidence draft returns validate/save guidance.
  - Assert low-confidence content-block draft returns patch guidance and advisory `can_save_now=false`.
- Test: `tests/wf_mcp/server/test_config.py`
  - Assert output schema exposes `next_actions` with field descriptions.
- Modify: `docs/workflow_capabilities.md`
  - Explain `next_actions` as advisory continuation hints.
- Modify: `docs/wf_mcp_end_to_end_runbook.md`
  - Mention that clients can follow `next_actions` after draft creation.

## Data Shape

Add this output shape:

```json
{
  "next_actions": {
    "can_save_now": true,
    "recommended_next_tool": "wf.workflow.validate_draft_workspace",
    "reason": "Wrapper hints are high confidence and have no missing decisions.",
    "patch_examples": [],
    "warnings": []
  }
}
```

Low-confidence example:

```json
{
  "next_actions": {
    "can_save_now": false,
    "recommended_next_tool": "wf.workflow.patch_draft_workspace",
    "reason": "Review missing wrapper decisions before saving.",
    "patch_examples": [
      {
        "description": "Replace the output bindings after choosing workflow state fields.",
        "tool": "wf.workflow.patch_draft_workspace",
        "request": {
          "workspace_id": "echo_wrapper",
          "revision": 1,
          "patch": [
            {
              "op": "replace",
              "path": "/draft/steps/call/output",
              "value": []
            }
          ]
        }
      }
    ],
    "warnings": [
      "Raw MCP content blocks are not workflow-shaped. Use an explicit wrapper or extraction node."
    ]
  }
}
```

## Task 1: Add Result Models And Schema Test

**Files:**

- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `tests/wf_mcp/server/test_config.py`

- [ ] **Step 1: Add failing schema assertions**

In `tests/wf_mcp/server/test_config.py`, inside the test that already inspects `create_draft_workspace_from_capability` output schema, add:

```python
assert "next_actions" in from_capability_output["properties"]
next_actions_schema = from_capability_output["properties"]["next_actions"]
assert "recommended_next_tool" in next_actions_schema["properties"]
assert "patch_examples" in next_actions_schema["properties"]
assert "advisory" in next_actions_schema["properties"]["can_save_now"]["description"]
```

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_config.py -q
```

Expected: fail because `next_actions` is not in the output schema.

- [ ] **Step 2: Add Pydantic result models**

In `src/wf_mcp/workflow_surface/models.py`, add near `CreateDraftWorkspaceFromCapabilityResult`:

```python
class WrapperDraftPatchExample(BaseModel):
    """Concrete patch-workspace example for a likely next authoring edit."""

    description: str = Field(description="Human-readable reason for this patch.")
    tool: str = Field(description="MCP tool to call for this example.")
    request: dict[str, Any] = Field(
        description="JSON request payload to pass to the tool."
    )


class WrapperDraftNextActions(BaseModel):
    """Advisory continuation hints after bootstrapping a wrapper draft."""

    can_save_now: bool = Field(
        description=(
            "Advisory only. False means the scaffold likely needs review before "
            "saving, but the server does not enforce this."
        )
    )
    recommended_next_tool: str = Field(
        description=(
            "Suggested next MCP tool, usually wf.workflow.validate_draft_workspace "
            "or wf.workflow.patch_draft_workspace."
        )
    )
    reason: str = Field(description="Short explanation for the recommendation.")
    patch_examples: list[WrapperDraftPatchExample] = Field(
        default_factory=list,
        description="Concrete JSON Patch examples for common missing decisions.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking warnings copied from low-confidence wrapper hints.",
    )
```

Then update:

```python
class CreateDraftWorkspaceFromCapabilityResult(DraftWorkspaceResult):
    """Draft workspace result plus wrapper hints and advisory next actions."""

    wrapper_hints: dict[str, Any] = Field(...)
    next_actions: WrapperDraftNextActions = Field(
        description=(
            "Advisory next step guidance derived from wrapper_hints. "
            "The server does not enforce can_save_now."
        )
    )
```

- [ ] **Step 3: Run schema test**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_config.py -q
```

Expected: schema assertion passes, but runtime tests may still fail later until handler returns `next_actions`.

## Task 2: Derive Next Actions In The Handler

**Files:**

- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Modify: `tests/wf_mcp/workflow_surface/test_drafts.py`

- [ ] **Step 1: Add high-confidence behavior test**

In `tests/wf_mcp/workflow_surface/test_drafts.py`, extend `test_workflow_surface_creates_draft_workspace_from_capability_hints`:

```python
next_actions = result["next_actions"]
assert next_actions["can_save_now"] is True
assert next_actions["recommended_next_tool"] == "wf.workflow.validate_draft_workspace"
assert "high confidence" in next_actions["reason"]
assert next_actions["patch_examples"] == []
assert next_actions["warnings"] == []
```

Run:

```powershell
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py::test_workflow_surface_creates_draft_workspace_from_capability_hints -q
```

Expected: fail because handler does not return `next_actions`.

- [ ] **Step 2: Add low-confidence behavior test**

Find or create a content-block capability test near existing wrapper hint tests. Use an output schema shaped like:

```python
content_output_schema = {
    "type": "object",
    "properties": {
        "content": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "text": {"type": "string"},
                },
            },
        }
    },
}
```

Register a NodeSpec/capability with that output schema, call `create_draft_workspace_from_capability`, then assert:

```python
next_actions = result["next_actions"]
assert next_actions["can_save_now"] is False
assert next_actions["recommended_next_tool"] == "wf.workflow.patch_draft_workspace"
assert "missing wrapper decisions" in next_actions["reason"]
assert next_actions["patch_examples"][0]["tool"] == "wf.workflow.patch_draft_workspace"
assert next_actions["patch_examples"][0]["request"]["workspace_id"] == "content_wrapper"
assert next_actions["patch_examples"][0]["request"]["revision"] == result["revision"]
assert next_actions["warnings"]
```

Run:

```powershell
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py -q
```

Expected: fail until implementation exists.

- [ ] **Step 3: Implement helper in handler**

In `src/wf_mcp/workflow_surface/handlers.py`, add a helper near other draft helpers:

```python
def _wrapper_draft_next_actions(
    *,
    workspace_id: str,
    revision: int,
    hints: dict[str, Any],
) -> dict[str, Any]:
    """Convert wrapper_hints into advisory next-tool guidance for MCP clients."""
    confidence = str(hints.get("confidence", "low"))
    missing_decisions = hints.get("missing_decisions")
    notes = [str(note) for note in hints.get("notes", []) if isinstance(note, str)]
    has_missing = isinstance(missing_decisions, list) and len(missing_decisions) > 0
    can_save_now = confidence == "high" and not has_missing
    if can_save_now:
        return {
            "can_save_now": True,
            "recommended_next_tool": "wf.workflow.validate_draft_workspace",
            "reason": "Wrapper hints are high confidence and have no missing decisions.",
            "patch_examples": [],
            "warnings": [],
        }

    return {
        "can_save_now": False,
        "recommended_next_tool": "wf.workflow.patch_draft_workspace",
        "reason": "Review missing wrapper decisions before saving.",
        "patch_examples": _wrapper_draft_patch_examples(
            workspace_id=workspace_id,
            revision=revision,
            hints=hints,
        ),
        "warnings": notes,
    }
```

Add:

```python
def _wrapper_draft_patch_examples(
    *,
    workspace_id: str,
    revision: int,
    hints: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return conservative JSON Patch examples without guessing semantics."""
    examples: list[dict[str, Any]] = []
    missing_decisions = hints.get("missing_decisions")
    if not isinstance(missing_decisions, list):
        return examples
    decision_kinds = {
        str(decision.get("kind"))
        for decision in missing_decisions
        if isinstance(decision, dict)
    }
    if {
        "choose_output_fields",
        "review_nested_output",
    } & decision_kinds:
        examples.append(
            {
                "description": (
                    "Replace output bindings after choosing which capability "
                    "outputs should be written to workflow state."
                ),
                "tool": "wf.workflow.patch_draft_workspace",
                "request": {
                    "workspace_id": workspace_id,
                    "revision": revision,
                    "patch": [
                        {
                            "op": "replace",
                            "path": "/draft/steps/call/output",
                            "value": [],
                        }
                    ],
                },
            }
        )
    if "confirm_boolean_outcomes" in decision_kinds:
        examples.append(
            {
                "description": (
                    "Review boolean output candidates before adding routing; "
                    "do not route on boolean fields automatically."
                ),
                "tool": "wf.workflow.patch_draft_workspace",
                "request": {
                    "workspace_id": workspace_id,
                    "revision": revision,
                    "patch": [],
                },
            }
        )
    return examples
```

Then change the return in `create_draft_workspace_from_capability`:

```python
return {
    **result,
    "wrapper_hints": hints,
    "next_actions": _wrapper_draft_next_actions(
        workspace_id=workspace_id,
        revision=int(result["revision"]),
        hints=hints,
    ),
}
```

- [ ] **Step 4: Run behavior tests**

Run:

```powershell
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py -q
```

Expected: pass.

## Task 3: Document Next Actions

**Files:**

- Modify: `docs/workflow_capabilities.md`
- Modify: `docs/wf_mcp_end_to_end_runbook.md`

- [ ] **Step 1: Update workflow capability docs**

In `docs/workflow_capabilities.md`, near the `wrapper_hints` section, add:

```markdown
`create_draft_workspace_from_capability` also returns `next_actions`.
This is advisory guidance for clients that cannot easily read the full docs.
It summarizes whether the scaffold is safe-looking enough to validate, which
tool to call next, and concrete patch examples for common missing decisions.

`next_actions.can_save_now` is not enforced. A caller can still save a low
confidence draft, but the field exists to make that risk explicit.
```

- [ ] **Step 2: Update runbook**

In `docs/wf_mcp_end_to_end_runbook.md`, near the draft-from-capability example, add:

```markdown
After `create_draft_workspace_from_capability`, inspect `next_actions`.
If `recommended_next_tool` is `wf.workflow.patch_draft_workspace`, apply or
adapt the returned `patch_examples` before saving. If it recommends
`wf.workflow.validate_draft_workspace`, validate the draft before creating an
artifact.
```

- [ ] **Step 3: Grep docs**

Run:

```powershell
rg -n "next_actions|can_save_now|patch_examples" docs/workflow_capabilities.md docs/wf_mcp_end_to_end_runbook.md
```

Expected: all three terms appear.

## Task 4: Final Verification

**Files:**

- All touched files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py tests/wf_mcp/test_workflow_wrapper_hints.py -q
```

Expected: pass.

- [ ] **Step 2: Run touched-file lint and format check**

Run:

```powershell
uv run ruff check src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py
uv run ruff format --check src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py
```

Expected: pass.

- [ ] **Step 3: Run touched-file type check**

Run:

```powershell
uv run basedpyright --level error src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/handlers.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_config.py
```

Expected: `0 errors`.

- [ ] **Step 4: Optional full suite**

Run when time allows:

```powershell
uv run pytest -q
```

Expected current baseline: full suite passes with the existing skip/xfail count.

## Notes For Opencode

- `can_save_now` is advisory. Do not enforce it.
- Do not add a new save gate.
- Do not generate semantic routes from boolean fields.
- Keep patch examples conservative; empty patch examples are acceptable when the missing decision cannot be safely represented.
- Avoid whole-dict assertions. Assert individual fields.
- Existing docs may be long; keep additions short.
