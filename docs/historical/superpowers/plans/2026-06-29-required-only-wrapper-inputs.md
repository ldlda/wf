# Required-Only Wrapper Inputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop draft wrapper creation from auto-binding optional capability inputs that may be absent from workflow run input.

**Architecture:** Wrapper hints are generated in `src/wf_api/wrapper_hints.py` and consumed by draft creation. Change the default input map policy to bind required capability input fields, plus safe optional fields that have defaults if current behavior depends on them. Surface omitted optional fields in notes or missing decisions so agents can explicitly bind them with `wf draft bind`.

**Tech Stack:** Python 3.14, Pydantic JSON Schema, wrapper hints, draft creation tests.

---

### Task 1: Define Required-Only Input Map Policy

**Files:**
- Modify: `src/wf_api/wrapper_hints.py`
- Test: `tests/wf_api/test_wrapper_hints.py` or `tests/wf_api/test_drafts_service.py`

- [x] **Step 1: Write failing test**

Create an input schema with required `text` and optional `path`:

```python
input_schema = {
    "type": "object",
    "required": ["text"],
    "properties": {
        "text": {"type": "string"},
        "path": {"type": "string"},
    },
}
```

Assert wrapper hints include only:

```python
assert hints["input_map"] == {"input.text": "text"}
assert "path" in hints["missing_decisions"] or any("path" in note for note in hints["notes"])
```

- [x] **Step 2: Run test RED**

Run:

```powershell
uv run pytest tests/wf_api/test_wrapper_hints.py::test_wrapper_hints_only_auto_bind_required_inputs -q
```

Expected: fail because optional `path` is currently auto-bound.

- [x] **Step 3: Implement required-only policy**

In wrapper hint input-map generation, compute:

```python
required_fields = set(input_schema.get("required", []))
input_map = {
    f"input.{name}": name
    for name in input_properties
    if name in required_fields
}
```

If optional fields are omitted, add a note:

```python
f"Optional input {name!r} is not auto-bound; bind it explicitly if needed."
```

Do not bind optional fields merely because they are present in the capability schema.

- [x] **Step 4: Run test GREEN**

Run the test from Step 2. Expected: pass.

- [x] **Step 5: Prepare for the integration commit**

```powershell
git add src/wf_api/wrapper_hints.py tests/wf_api/test_wrapper_hints.py
git commit -m "fix: avoid auto-binding optional wrapper inputs"
```

### Task 2: Draft Creation Regression

**Files:**
- Test: `tests/wf_api/test_drafts_service.py`
- Test: `tests/wf_cli/test_remote_target.py`

- [x] **Step 1: Add draft creation regression**

Use the browser-click or report source fixture. Create a draft from a capability with optional input fields and assert omitted optional fields are not in step input bindings.

Expected shape:

```python
assert {"path": "input.path", "target": "path"} not in workspace["draft"]["steps"]["call"]["input"]
```

- [x] **Step 2: Add CLI smoke**

For `wf draft create <id> --capability local.report.read_notes`, assert output JSON wrapper hints mention optional omitted input rather than creating a binding that later fails at run time.

- [x] **Step 3: Run tests**

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_create_draft_from_capability_does_not_bind_optional_inputs tests/wf_cli/test_remote_target.py::test_wf_draft_create_reports_optional_inputs_without_binding -q
```

- [x] **Step 4: Prepare for the integration commit**

```powershell
git add tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
git commit -m "test: cover required-only wrapper input binding"
```

### Task 3: Docs And Skills

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `docs/current_roadmap.md`

- [x] **Step 1: Document policy**

Add:

```md
Draft wrapper creation auto-binds required capability inputs only. Optional inputs must be bound explicitly with `wf draft bind` or `wf draft set-input --merge`.
```

- [x] **Step 2: Give explicit repair example**

Add:

```bash
wf draft bind report_ws --revision 2 --step call --from input.path --to local.path
```

- [x] **Step 3: Verify**

Run:

```powershell
uv run pytest tests/wf_api/test_wrapper_hints.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py -q
uv run ruff check src/wf_api tests/wf_api tests/wf_cli
uv run basedpyright --level error src/wf_api/wrapper_hints.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
```

- [x] **Step 4: Prepare for the integration commit**

```powershell
git add docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md docs/current_roadmap.md
git commit -m "docs: document required-only wrapper input policy"
```

---

## Self-Review

- This plan targets one observed failure: optional `input.path` was auto-bound and caused a run-time missing input error.
- It preserves explicit binding through `wf draft bind` and `wf draft set-input --merge`.
- It does not remove optional inputs from capability schemas; it only stops auto-wiring them.
