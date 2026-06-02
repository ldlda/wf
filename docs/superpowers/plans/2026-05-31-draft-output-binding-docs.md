# Draft Output Binding Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clarify the two different `output` binding shapes in workflow drafts so MCP/LLM clients stop applying step-level `source`/`target` bindings to top-level workflow output projection.

**Architecture:** This is docs-only for now. The core model is internally coherent: step-level `output` uses `OutputBinding` (`source` local -> `target` state), while top-level workflow `output` uses input-binding shape (`path` graph -> `target` local output payload). Update the main draft docs, runbook, and schema-facing descriptions to teach this explicitly without changing runtime behavior.

**Tech Stack:** Markdown docs, Pydantic field descriptions, pytest schema/docs tests, ruff, basedpyright.

---

## Scope

Do:

- Add a clear “Two Outputs, Different Shapes” docs section.
- Show exact JSON for both step-level output and top-level workflow output.
- Explain the legacy fallback: empty top-level `output` projects same-name top-level state fields.
- Update MCP model field descriptions so schema viewers see “uses `path`, not `source`” for top-level output.
- Add docs/test assertions that this guidance is exported.

Do not:

- Rename fields to `writes` / `returns`.
- Change validation behavior.
- Remove legacy same-name output fallback.
- Add automatic MCP content block extraction.

## Files

- Modify: `docs/workflow_drafts.md`
  - Add the primary explanation and examples.
- Modify: `docs/wf_mcp_end_to_end_runbook.md`
  - Add a short warning in the draft patching section.
- Modify: `docs/workflow_capabilities.md`
  - Mention that `next_actions.patch_examples` may include top-level output projection examples.
- Modify: `src/wf_artifacts/drafts/models.py`
  - Improve `WorkflowDraft.output` field description.
- Modify: `src/wf_core/models/workflow.py`
  - Improve `Workflow.output` field description.
- Modify: `tests/wf_mcp/server/test_docs.py`
  - Assert exported docs include the new guidance.
- Modify if needed: `tests/wf_mcp/server/test_config.py`
  - Assert schema descriptions include “path, not source” if exposed in tool schema.

## Task 1: Document The Two Output Shapes

**Files:**

- Modify: `docs/workflow_drafts.md`

- [ ] **Step 1: Add docs section**

After the “Important details” list or before “Explicit Outputs And Error Outcomes”, add:

```markdown
## Two Outputs, Different Shapes

Drafts have two fields named `output`, but they do different jobs.

### Step-Level `steps.<id>.output`

Step output writes a node's local return payload into workflow state. It uses
`source` / `target`:

```json
{
  "source": { "root": "local", "parts": ["text"] },
  "target": { "root": "state", "parts": ["result_text"] }
}
```

Read this as:

```text
node output.text -> state.result_text
```

### Top-Level `output`

Top-level workflow output projects graph values into the final public workflow
output payload. It uses input-binding shape: `path` / `target`, not
`source` / `target`.

```json
{
  "path": { "root": "state", "parts": ["result_text"] },
  "target": { "root": "local", "parts": ["result_text"] }
}
```

Read this as:

```text
state.result_text -> workflow output.result_text
```

If top-level `output` is empty, the runtime keeps the legacy same-name fallback:
for every field in `output_schema`, it copies the top-level state field with the
same name when present. That fallback is convenient, but explicit output
projection is clearer for new workflows.

```

- [ ] **Step 2: Run grep check**

Run:

```powershell
rg -n "Two Outputs, Different Shapes|path.*not.*source|state.result_text -> workflow output.result_text" docs/workflow_drafts.md
```

Expected: all terms appear.

## Task 2: Update Runbook Warning And Example

**Files:**

- Modify: `docs/wf_mcp_end_to_end_runbook.md`

- [ ] **Step 1: Add warning near draft patching section**

Near “Patch Or Validate The Workspace”, add:

```markdown
When patching output bindings, keep the two levels separate:

- Step-level `steps.<id>.output` uses `source` local -> `target` state.
- Top-level `output` uses `path` graph -> `target` local output payload.

For explicit final output projection from state, use:

```json
{
  "path": { "root": "state", "parts": ["result_text"] },
  "target": { "root": "local", "parts": ["result_text"] }
}
```

Do not use `source` at top level. `source` belongs to step output bindings.

```

- [ ] **Step 2: Run grep check**

Run:

```powershell
rg -n "Do not use `source` at top level|steps.<id>.output|result_text" docs/wf_mcp_end_to_end_runbook.md
```

Expected: all terms appear.

## Task 3: Update Field Descriptions

**Files:**

- Modify: `src/wf_artifacts/drafts/models.py`
- Modify: `src/wf_core/models/workflow.py`

- [ ] **Step 1: Update `WorkflowDraft.output` field description**

Change:

```python
output: list[InputBinding] = Field(default_factory=list)
```

to:

```python
output: list[InputBinding] = Field(
    default_factory=list,
    description=(
        "Top-level workflow output projection. Uses input-binding shape: "
        "`path` reads from input/state/context and `target` writes to the "
        "local public output payload. Do not use step output `source` here."
    ),
)
```

- [ ] **Step 2: Update `Workflow.output` field description**

In `src/wf_core/models/workflow.py`, extend the `output` description to include:

```python
"Use `path`, not `source`; `source` belongs to step-level node output bindings."
```

Keep the existing legacy fallback explanation.

- [ ] **Step 3: Run focused schema/type checks**

Run:

```powershell
uv run basedpyright --level error src/wf_artifacts/drafts/models.py src/wf_core/models/workflow.py
uv run ruff check src/wf_artifacts/drafts/models.py src/wf_core/models/workflow.py
uv run ruff format --check src/wf_artifacts/drafts/models.py src/wf_core/models/workflow.py
```

Expected: pass.

## Task 4: Add Exported Docs Test

**Files:**

- Modify: `tests/wf_mcp/server/test_docs.py`

- [ ] **Step 1: Add docs resource assertion**

In the docs resource test that reads workflow authoring/draft docs, assert:

```python
assert "Two Outputs, Different Shapes" in text
assert "Do not use step output `source` here" in text or "Do not use `source` at top level" in text
```

Use the existing variable names in the file. Do not assert whole payload dict equality.

- [ ] **Step 2: Run focused docs test**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_docs.py -q
```

Expected: pass.

## Task 5: Optional Schema Description Test

**Files:**

- Modify if needed: `tests/wf_mcp/server/test_config.py`

- [ ] **Step 1: Inspect whether draft output field description is exposed**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_config.py -q
```

If this test already inspects `create_draft_workspace` request schemas, add:

```python
output_description = minimal_request["properties"]["output"]["description"]
assert "path" in output_description
assert "source" in output_description
```

If the schema nests the description differently, skip this test change and rely
on `test_docs.py`.

## Task 6: Final Verification

**Files:**

- All touched docs and Python files.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_docs.py tests/wf_mcp/server/test_config.py -q
```

Expected: pass.

- [ ] **Step 2: Run touched-file lint/type checks**

Run:

```powershell
uv run ruff check src/wf_artifacts/drafts/models.py src/wf_core/models/workflow.py tests/wf_mcp/server/test_docs.py tests/wf_mcp/server/test_config.py
uv run ruff format --check src/wf_artifacts/drafts/models.py src/wf_core/models/workflow.py tests/wf_mcp/server/test_docs.py tests/wf_mcp/server/test_config.py
uv run basedpyright --level error src/wf_artifacts/drafts/models.py src/wf_core/models/workflow.py tests/wf_mcp/server/test_docs.py tests/wf_mcp/server/test_config.py
```

Expected: pass.

- [ ] **Step 3: Optional full suite**

Run when time allows:

```powershell
uv run pytest -q
```

Expected current baseline: full suite passes with the existing skip/xfail count.

## Notes For Opencode

- This is docs/description work only.
- Do not rename model fields.
- Do not remove fallback same-name projection.
- Do not auto-extract MCP content blocks.
- The exact mental model to teach is:

```text
steps.call.output: local node output -> workflow state
workflow output: input/state/context graph path -> public output payload
```
