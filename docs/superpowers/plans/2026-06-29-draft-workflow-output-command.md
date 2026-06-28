# Draft Workflow Output Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class command for editing top-level workflow output bindings without forcing agents to write JSON Patch.

**Architecture:** `WorkflowDraft.output` is top-level workflow output projection and uses input-binding shape: `path` reads from graph input/state/context and `target` writes to the public output payload. Add a focused API method that replaces or merges this list, then expose it through RPC, client, CLI, docs, and skills.

**Tech Stack:** Python 3.14, Typer CLI, Pydantic draft models, JSON-RPC transport, pytest.

---

### Task 1: API Method

**Files:**
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Test: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Write failing API tests**

Add tests that create a draft with empty `output`, call `set_workflow_output_map`, and assert the stored draft has top-level output bindings:

```python
async def test_set_workflow_output_map_replaces_top_level_output(tmp_path: Path) -> None:
    api = _draft_api(tmp_path)
    await api.create_draft_workspace(workspace_id="report", draft=_echo_draft())

    result = await api.set_workflow_output_map(
        workspace_id="report",
        revision=1,
        output_map={"state.echoed": "message"},
    )

    assert result["revision"] == 2
    fetched = await api.get_draft_workspace(workspace_id="report")
    assert fetched["draft"]["output"] == [{"path": "state.echoed", "target": "message"}]
```

Add a second test for merge:

```python
async def test_set_workflow_output_map_merges_top_level_output(tmp_path: Path) -> None:
    api = _draft_api(tmp_path)
    draft = {**_echo_draft(), "output": [{"path": "state.echoed", "target": "message"}]}
    await api.create_draft_workspace(workspace_id="report", draft=draft)

    await api.set_workflow_output_map(
        workspace_id="report",
        revision=1,
        output_map={"state.other": "other"},
        merge=True,
    )

    fetched = await api.get_draft_workspace(workspace_id="report")
    assert fetched["draft"]["output"] == [
        {"path": "state.echoed", "target": "message"},
        {"path": "state.other", "target": "other"},
    ]
```

- [ ] **Step 2: Run tests RED**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_set_workflow_output_map_replaces_top_level_output tests/wf_api/test_drafts_service.py::test_set_workflow_output_map_merges_top_level_output -q
```

Expected: fail because `set_workflow_output_map` does not exist.

- [ ] **Step 3: Implement API method**

In `WorkflowDraftApi`, add:

```python
async def set_workflow_output_map(
    self,
    *,
    workspace_id: str,
    revision: int,
    output_map: dict[str, str],
    merge: bool = False,
) -> dict[str, Any]:
    if merge:
        workspace = self._draft_store().get_workspace(workspace_id)
        existing = {
            str(binding.get("path")): str(binding.get("target"))
            for binding in workspace.draft.get("output", [])
            if isinstance(binding, dict)
            and isinstance(binding.get("path"), str)
            and isinstance(binding.get("target"), str)
        }
        output_map = {**existing, **output_map}
    return await self.patch_draft_workspace(
        workspace_id=workspace_id,
        revision=revision,
        patch=[
            {
                "op": "replace",
                "path": "/output",
                "value": [
                    {"path": source, "target": target}
                    for source, target in output_map.items()
                ],
            }
        ],
    )
```

Add delegates to `WorkflowApi` and `WorkflowDraftSurface`.

- [ ] **Step 4: Run API tests GREEN**

Run the two tests from Step 2. Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py tests/wf_api/test_drafts_service.py
git commit -m "feat: edit workflow output map in draft api"
```

### Task 2: RPC, Client, And CLI

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`
- Test: `tests/wf_cli/test_remote_target.py`
- Test: `tests/wf_cli/test_app.py`

- [ ] **Step 1: Add failing transport and CLI tests**

Add RPC app/client tests that call `workflow.draft_workspaces.set_workflow_output_map` with `{"state.echoed": "message"}`.

Add CLI smoke test:

```python
def test_wf_draft_set_workflow_output_uses_rpc_target(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeDrafts:
        async def set_workflow_output_map(self, **kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"workspace_id": "report", "revision": 2}

    patch_remote_context(monkeypatch, FakeDrafts())
    result = runner.invoke(
        app,
        [
            "--url",
            "http://example.test/rpc",
            "draft",
            "set-workflow-output",
            "report",
            "--revision",
            "1",
            "--map",
            "state.markdown=markdown",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        {
            "workspace_id": "report",
            "revision": 1,
            "output_map": {"state.markdown": "markdown"},
            "merge": False,
        }
    ]
```

- [ ] **Step 2: Run tests RED**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_draft_workspace_focused_edit_methods tests/wf_transport_rpc_http/test_client.py::test_rpc_client_draft_workspace_focused_edit_methods tests/wf_cli/test_remote_target.py::test_wf_draft_set_workflow_output_uses_rpc_target -q
```

Expected: fail because DTO/method/command are missing.

- [ ] **Step 3: Implement transport and CLI**

Add `SetWorkflowOutputMapParams` with `workspace_id`, `revision`, `output_map`, `merge`.

Register RPC method name:

```python
"workflow.draft_workspaces.set_workflow_output_map"
```

Add client method:

```python
async def set_workflow_output_map(
    self, *, workspace_id: str, revision: int, output_map: dict[str, str], merge: bool = False
) -> dict[str, Any]:
    return await self._call(
        "workflow.draft_workspaces.set_workflow_output_map",
        {
            "workspace_id": workspace_id,
            "revision": revision,
            "output_map": output_map,
            "merge": merge,
        },
    )
```

Add CLI:

```python
@app.command("set-workflow-output")
def set_workflow_output(...):
    """Set top-level workflow output projection.

    Repeat --map once per mapping. Example:
    --map state.markdown=markdown --map state.title=title
    """
```

Use the existing `_parse_map_flags` helper. Add `--merge` with the same replace/merge wording used by `set-input` and `set-output`.

- [ ] **Step 4: Run tests GREEN**

Run the tests from Step 2. Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_transport_rpc_http src/wf_cli/commands/drafts.py tests/wf_transport_rpc_http tests/wf_cli
git commit -m "feat: expose workflow output draft command"
```

### Task 3: Docs And Skills

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/workflow_drafts.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Document command**

Add example:

```bash
wf draft set-workflow-output report_ws \
  --revision 8 \
  --map state.markdown=markdown \
  --map state.title=title
```

State clearly: this edits top-level `WorkflowDraft.output`; step-level `wf draft set-output` edits one step's node-output-to-state bindings.

- [ ] **Step 2: Update skills**

Add a rule:

```md
Use `wf draft set-workflow-output` for final workflow output projection.
Use `wf draft set-output` only for step output bindings.
```

- [ ] **Step 3: Verify**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q
uv run ruff check src/wf_api src/wf_cli src/wf_transport_rpc_http tests/wf_api tests/wf_cli tests/wf_transport_rpc_http
uv run basedpyright --level error src/wf_api/drafts.py src/wf_cli/commands/drafts.py src/wf_transport_rpc_http tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
```

- [ ] **Step 4: Commit**

```powershell
git add docs/wf_cli.md docs/workflow_drafts.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md docs/current_roadmap.md
git commit -m "docs: document workflow output draft command"
```

---

## Self-Review

- This plan targets one public UX gap: agents should not need JSON Patch for top-level workflow output.
- It does not change step `set-output` semantics.
- It does not attempt automatic schema projection; that belongs to the separate bind/discoverability plan.
