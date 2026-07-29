# Draft Document Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export exact draft documents and import them into existing revisioned workspaces through local or remote CLI.

**Architecture:** Add a full-document workspace replacement operation that structurally validates and semantically revalidates the imported draft before one atomic store replacement. Expose it through the protocol-neutral API and Python JSON-RPC client, while export reuses existing full draft inspection.

**Tech Stack:** Python 3.14, Pydantic, revisioned file store, FastAPI JSON-RPC, Typer, pytest.

## Global Constraints

- Import updates an existing workspace; it does not create or rename one.
- Import requires an explicit expected revision.
- Export contains only the stored `draft` JSON object.
- Imported drafts receive fresh semantic status and diagnostics.
- Structurally invalid imports and revision conflicts do not mutate.
- Semantically invalid but structurally valid drafts remain repairable and are persisted with diagnostics.
- Do not use `replace_validated_draft_document` for whole-document import.
- Do not add TypeScript RPC contracts in this slice.

---

### Task 1: Add Full-Document Workspace Replacement

**Files:**
- Modify: `src/wf_artifacts/draft_workspaces/api.py`
- Modify: `src/wf_artifacts/draft_workspaces/__init__.py`
- Modify: `src/wf_artifacts/__init__.py`
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Test: `tests/artifacts/test_draft_workspaces.py`
- Test: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Produces: `replace_draft_workspace_document`
- Produces: `WorkflowDraftApi.replace_draft_workspace_document`
- Produces: `WorkflowApi.replace_draft_workspace_document`
- Produces: `WorkflowDraftSurface.replace_draft_workspace_document`

- [ ] **Step 1: Write failing artifact-layer tests**

Add tests proving:

```python
result = replace_draft_workspace_document(
    store,
    workspace_id="echo_draft",
    revision=1,
    draft=replacement,
    node_defs_for_draft=lambda _draft: [],
)
assert result["revision"] == 2
assert store.get_workspace("echo_draft").draft["name"] == "replacement"
```

Also add tests for:

- identical draft returns revision 1;
- stale revision returns `revision_conflict`;
- structural Pydantic failure raises without mutation;
- semantically invalid routes are persisted at revision 2 with
  `status == "invalid"` and fresh diagnostics.

- [ ] **Step 2: Run artifact tests and verify RED**

Run:

```bash
uv run pytest tests/artifacts/test_draft_workspaces.py -k "replace_draft_workspace_document" -q
```

Expected: collection fails because the operation is not defined.

- [ ] **Step 3: Implement the artifact operation**

Add:

```python
def replace_draft_workspace_document(
    store: DraftWorkspaceStore,
    *,
    workspace_id: str,
    revision: int,
    draft: JsonObject,
    node_defs_for_draft: NodeDefsForDraft,
) -> JsonObject:
    """Replace and semantically revalidate one complete draft document."""
```

Implementation order:

1. load workspace;
2. return `_revision_conflict_payload` when stale;
3. call `WorkflowDraft.model_validate(draft)` for structural validation;
4. return current summary when `draft == workspace.draft`;
5. call `validate_workflow_draft(draft, node_defs=node_defs_for_draft(draft))`;
6. canonicalize only when validation status is valid;
7. create the next workspace with incremented revision, fresh draft, status,
   diagnostics, and timestamp;
8. replace with `expected_revision=revision`;
9. translate store races through `_revision_conflict_payload`.

Export the function through both artifact package `__init__.py` files.

- [ ] **Step 4: Write and run API façade tests**

In `tests/wf_api/test_drafts_service.py`, add one test that registers a
capability, imports a draft using it, and asserts current capability definitions
drive validation. Add a semantically invalid import test proving diagnostics
are refreshed instead of copied from the old workspace.

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -k "replace_draft_workspace_document" -q
```

Expected before façade implementation: FAIL with missing method.

- [ ] **Step 5: Thread the operation through API and surface**

Add this signature to `WorkflowDraftApi`, `WorkflowApi`, and
`WorkflowDraftSurface`:

```python
async def replace_draft_workspace_document(
    *,
    workspace_id: str,
    revision: int,
    draft: dict[str, Any],
) -> dict[str, Any]:
    """Replace and semantically revalidate one complete workspace draft."""
```

`WorkflowDraftApi` delegates to the artifact operation with
`node_defs_for_draft=self._node_defs_for_draft`. `WorkflowApi` delegates to
`self.drafts`.

- [ ] **Step 6: Run focused tests and commit**

Run:

```bash
uv run pytest tests/artifacts/test_draft_workspaces.py tests/wf_api/test_drafts_service.py -k "replace_draft_workspace_document" -q
```

Expected: all selected tests pass.

Commit:

```bash
git add src/wf_artifacts src/wf_api tests/artifacts/test_draft_workspaces.py tests/wf_api/test_drafts_service.py
git commit -m "feat: replace complete draft documents safely"
```

### Task 2: Expose Full Replacement Through Python JSON-RPC

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

**Interfaces:**
- Produces: `ReplaceDraftWorkspaceDocumentParams`
- Produces RPC method: `workflow.draft_workspaces.replace_document`
- Produces client method: `RpcDraftClientMixin.replace_draft_workspace_document`

- [ ] **Step 1: Write failing RPC application test**

Create a workspace, then call:

```python
result = await _rpc(
    client,
    "workflow.draft_workspaces.replace_document",
    {
        "workspace_id": "report",
        "revision": 1,
        "draft": replacement,
    },
)
assert result["result"]["revision"] == 2
```

Inspect the workspace with `include_draft=True` and assert exact imported
content. Add a malformed `draft=[]` request test that expects JSON-RPC parameter
validation failure without mutation.

- [ ] **Step 2: Run RPC application tests and verify RED**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py -k "replace_document" -q
```

Expected: method-not-found failure.

- [ ] **Step 3: Add the request model and RPC method**

Add:

```python
class ReplaceDraftWorkspaceDocumentParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    draft: dict[str, Any]
```

Export it from `wf_transport_rpc_http.__init__`. Register
`workflow.draft_workspaces.replace_document` in `methods/drafts.py`, delegating
to `server.api.replace_draft_workspace_document` and using the existing
`WorkflowRpcError` translation.

- [ ] **Step 4: Write failing client request test**

In `test_client.py`, assert:

```python
await client.replace_draft_workspace_document(
    workspace_id="report",
    revision=4,
    draft=draft,
)
assert calls[-1] == {
    "method": "workflow.draft_workspaces.replace_document",
    "params": {
        "workspace_id": "report",
        "revision": 4,
        "draft": draft,
    },
}
```

- [ ] **Step 5: Implement the remote client method**

Add the exact `WorkflowDraftSurface` signature to `RpcDraftClientMixin` and
delegate through `_call("workflow.draft_workspaces.replace_document", params)`.
Do not normalize or lower the draft through another model in the client.

- [ ] **Step 6: Run transport tests and commit**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -k "replace_document" -q
```

Expected: all selected tests pass.

Commit:

```bash
git add src/wf_transport_rpc_http tests/wf_transport_rpc_http
git commit -m "feat: expose draft document replacement over rpc"
```

### Task 3: Add Draft Export CLI

**Files:**
- Modify: `src/wf_cli/io.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Produces: `write_json_file(path, payload, *, force)`
- Produces CLI command: `wf draft export WORKSPACE --output PATH [--force]`

- [ ] **Step 1: Write failing local export tests**

Using a fake handler whose `get_draft_workspace` returns:

```python
{"workspace_id": "report", "revision": 4, "draft": expected_draft}
```

Assert:

- `wf draft export report --output draft.json` exits 0;
- the file parses to `expected_draft`;
- text is indented, sorted, UTF-8, and ends with `\n`;
- handler receives `include_draft=True`;
- existing output fails without `--force`;
- `--force` replaces it;
- a missing parent reports a CLI error.

- [ ] **Step 2: Run export tests and verify RED**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py -k "draft_export" -q
```

Expected: command-not-found failure.

- [ ] **Step 3: Add the file writer and command**

In `wf_cli.io`, add:

```python
def write_json_file(
    path: Path,
    payload: Any,
    *,
    force: bool,
) -> None:
    """Write formatted JSON while refusing accidental replacement."""
```

Use exclusive mode (`"x"`) unless `force=True`, use UTF-8 and newline
translation explicitly, write `json.dumps(payload, indent=2, sort_keys=True)`
plus `"\n"`, and translate `FileExistsError`/`OSError` to `CliInputError`.

Add the Typer command:

```python
@app.command("export")
def export_draft(
    ctx: typer.Context,
    workspace_id: Annotated[
        str,
        typer.Argument(help="Draft workspace id."),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", help="Destination JSON file."),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Replace an existing destination file."),
    ] = False,
) -> None:
```

Fetch with `include_draft=True`, require `payload["draft"]` to be a dictionary,
and call `write_json_file`. Do not call `emit_json`.

- [ ] **Step 4: Add remote-target export test**

Use the existing remote target fixture and assert the RPC request is
`workflow.draft_workspaces.get` with `include_draft: true`. Assert the resulting
file contains only the draft, not workspace metadata.

- [ ] **Step 5: Run CLI tests and commit**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -k "draft_export" -q
```

Expected: all selected tests pass.

Commit:

```bash
git add src/wf_cli/io.py src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
git commit -m "feat: export draft documents"
```

### Task 4: Add Revision-Checked Draft Import CLI

**Files:**
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: `parse_json_object_file(path, option_name="--file")`
- Consumes: `WorkflowDraftSurface.replace_draft_workspace_document`
- Produces CLI command: `wf draft import WORKSPACE --revision N --file PATH`

- [ ] **Step 1: Write failing local import tests**

Assert the command:

```text
wf draft import report --revision 4 --file draft.json
```

passes the parsed object unchanged to:

```python
replace_draft_workspace_document(
    workspace_id="report",
    revision=4,
    draft=expected_draft,
)
```

Add CLI-input tests for missing files, malformed JSON, and JSON arrays. Assert
these fail before `load_cli_context` is called.

- [ ] **Step 2: Run import tests and verify RED**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py -k "draft_import" -q
```

Expected: command-not-found failure.

- [ ] **Step 3: Implement the import command**

Add:

```python
@app.command("import")
def import_draft(
    ctx: typer.Context,
    workspace_id: Annotated[
        str,
        typer.Argument(help="Draft workspace id."),
    ],
    revision: Annotated[
        int,
        typer.Option("--revision", min=1, help="Expected workspace revision."),
    ],
    input_file: Annotated[
        Path,
        typer.Option("--file", help="Draft JSON document to import."),
    ],
) -> None:
```

Parse with `parse_json_object_file(input_file, option_name="--file")` before
loading context. Call the full replacement handler and emit its summary:

```python
draft = parse_json_object_file(input_file, option_name="--file")
context = load_cli_context(ctx)
emit_json(
    run_cli_operation(
        context,
        context.handlers.replace_draft_workspace_document(
            workspace_id=workspace_id,
            revision=revision,
            draft=draft,
        ),
    )
)
```

- [ ] **Step 4: Add remote import and round-trip tests**

Add a remote-target test asserting method
`workflow.draft_workspaces.replace_document` and exact draft payload.

Add one round-trip test:

1. export source workspace;
2. import the file into a different existing workspace;
3. inspect the destination with `include_draft=True`;
4. assert destination `draft` equals the exported object;
5. assert destination workspace ID remains unchanged.

- [ ] **Step 5: Run CLI tests and commit**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -k "draft_import or draft_export or draft_transfer" -q
```

Expected: all selected tests pass.

Commit:

```bash
git add src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
git commit -m "feat: import draft documents"
```

### Task 5: Update User Documentation And Verify The Slice

**Files:**
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-29-safe-compatibility-merges.md`
- Move: `docs/superpowers/plans/2026-07-29-draft-document-transfer.md`

**Interfaces:**
- Documents: safe map merge, export, and revision-checked import

- [ ] **Step 1: Update CLI skill examples**

Add a concise transfer sequence:

```bash
uv run wf draft export report --output report-draft.json
uv run wf draft import restored --revision 1 --file report-draft.json
uv run wf draft validate restored
```

State that exported files contain only the draft document and that import
targets an already existing workspace. State that semantic-invalid imports are
stored with diagnostics for repair.

- [ ] **Step 2: Update roadmap and archive completed plans**

Add one completed roadmap item linking to both historical plan paths. Move both
plans under:

```text
docs/historical/superpowers/plans/
```

Update any references found by:

```bash
rg -n "2026-07-29-(safe-compatibility-merges|draft-document-transfer)" docs skills
```

- [ ] **Step 3: Run focused and static verification**

Run:

```bash
uv run pytest tests/artifacts/test_draft_workspaces.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
git diff --check
```

Expected: all tests pass, formatting is unchanged, Ruff reports no issues,
basedpyright reports zero errors, and diff check is clean.

- [ ] **Step 4: Review the combined implementation**

Invoke the repository code-review workflow against the pre-slice commit. Fix
Critical and Important findings, rerun the affected focused tests, and record
any intentionally deferred Minor findings in the final report.

- [ ] **Step 5: Commit documentation and plan archival**

```bash
git add skills/wf-cli/SKILL.md docs/current_roadmap.md docs/superpowers/plans docs/historical/superpowers/plans
git commit -m "docs: complete safe draft transfer"
```
