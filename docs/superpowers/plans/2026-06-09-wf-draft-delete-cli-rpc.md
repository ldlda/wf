# wf Draft Delete CLI/RPC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing `delete_draft_workspace` operation through the workflow surface, JSON-RPC HTTP transport, RPC client, and `wf draft delete`.

**Architecture:** Draft deletion already exists in `wf_api`; this slice is transport and CLI plumbing. Keep the operation idempotent and safe: require `--confirm` at the CLI and do not add artifact/deployment deletion in this plan.

**Tech Stack:** Python 3.14, Typer, fastapi-jsonrpc, pytest, pytest-asyncio, ruff, basedpyright.

---

## Files

- Modify `src/wf_api/surface.py` to add `delete_draft_workspace` to `WorkflowDraftSurface`.
- Modify `src/wf_transport_rpc_http/models.py` to add `DeleteDraftWorkspaceParams`.
- Modify `src/wf_transport_rpc_http/methods/drafts.py` to register `workflow.draft_workspaces.delete`.
- Modify `src/wf_transport_rpc_http/client/drafts.py` to add `RpcDraftClientMixin.delete_draft_workspace`.
- Modify `src/wf_cli/commands/drafts.py` to add `wf draft delete <workspace_id> --confirm`.
- Add or update RPC/client tests under `tests/wf_transport_rpc_http/`.
- Add CLI tests under `tests/wf_cli/`.
- Update `docs/wf_cli.md` after behavior is implemented.
- Update `docs/current_roadmap.md` after behavior is implemented.

## Task 1: Surface And RPC Tests

**Files:**
- Test: `tests/wf_transport_rpc_http/test_client.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Modify: `src/wf_api/surface.py`

- [ ] **Step 1: Add a static surface assertion**

Add a small static conformance check near existing surface/client tests:

```python
from wf_api.surface import WorkflowDraftSurface
from wf_transport_rpc_http import RpcWorkflowApiClient


def test_rpc_client_satisfies_draft_surface_static_shape() -> None:
    _: type[WorkflowDraftSurface] = RpcWorkflowApiClient
```

If the exact test file already has this pattern, extend the existing assertion instead of adding a duplicate test.

- [ ] **Step 2: Add a client deletion test**

Create a draft workspace, delete it through the RPC client, then verify the workspace is gone or the delete result is idempotent. Use existing local/static server helpers in `tests/wf_transport_rpc_http/test_client.py`.

Expected assertion shape:

```python
deleted = await client.delete_draft_workspace(workspace_id="delete-me")
assert deleted["workspace_id"] == "delete-me"
assert deleted["deleted"] is True

deleted_again = await client.delete_draft_workspace(workspace_id="delete-me")
assert deleted_again["workspace_id"] == "delete-me"
assert deleted_again["deleted"] is False
```

- [ ] **Step 3: Add an app-level JSON-RPC method test**

In `tests/wf_transport_rpc_http/test_app.py`, call the method by name:

```python
payload = await rpc_call(
    app,
    "workflow.draft_workspaces.delete",
    {"workspace_id": "delete-me"},
)
assert payload["workspace_id"] == "delete-me"
assert payload["deleted"] is True
```

Use the existing RPC helper names in that file. Do not invent a second helper if one already exists.

- [ ] **Step 4: Run the failing focused tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_app.py -q
```

Expected: FAIL because `WorkflowDraftSurface.delete_draft_workspace`, `DeleteDraftWorkspaceParams`, RPC method, and client method do not exist yet.

- [ ] **Step 5: Add the surface method**

In `src/wf_api/surface.py`, add this method to `WorkflowDraftSurface` after `validate_draft_workspace`:

```python
    async def delete_draft_workspace(
        self,
        *,
        workspace_id: str,
    ) -> dict[str, Any]: ...
```

Run the same focused tests again. Expected: still FAIL, now at transport/client missing pieces.

## Task 2: RPC Params, Method, And Client

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`

- [ ] **Step 1: Add params model**

In `src/wf_transport_rpc_http/models.py`, add:

```python
class DeleteDraftWorkspaceParams(RpcModel):
    workspace_id: str = Field(min_length=1)
```

Use the same base class and imports as adjacent draft params. If `Field` is already imported, reuse it.

- [ ] **Step 2: Register JSON-RPC method**

In `src/wf_transport_rpc_http/methods/drafts.py`, import `DeleteDraftWorkspaceParams` and add this method near the other `workflow.draft_workspaces.*` methods:

```python
    @entrypoint.method(
        name="workflow.draft_workspaces.delete", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_delete(
        params: DeleteDraftWorkspaceParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.delete_draft_workspace(
                workspace_id=params.workspace_id,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 3: Add RPC client method**

In `src/wf_transport_rpc_http/client/drafts.py`, add:

```python
    async def delete_draft_workspace(
        self: RpcCaller,
        *,
        workspace_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.delete",
            {"workspace_id": workspace_id},
        )
```

- [ ] **Step 4: Run focused RPC/client tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_app.py -q
```

Expected: PASS for the new RPC/client tests.

## Task 3: CLI Command

**Files:**
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_remote_target.py` or `tests/wf_cli/test_drafts.py`

- [ ] **Step 1: Add CLI tests first**

Add tests covering both the confirm guard and successful deletion. Follow existing CLI test patterns for `CliRunner`.

Required assertions:

```python
result = runner.invoke(app, ["draft", "delete", "delete-me"])
assert result.exit_code != 0
assert "confirm" in (result.stdout + result.output).lower()
```

And for the success case:

```python
result = runner.invoke(app, ["draft", "delete", "delete-me", "--confirm"])
assert result.exit_code == 0
payload = json.loads(result.stdout)
assert payload["workspace_id"] == "delete-me"
assert payload["deleted"] is True
```

If the file already uses remote RPC monkeypatch helpers, use those helpers so the test proves `load_cli_context_from_typer` and the RPC client path both work.

- [ ] **Step 2: Run CLI tests and confirm failure**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py tests/wf_cli/test_drafts.py -q
```

If `tests/wf_cli/test_drafts.py` does not exist, omit it from the command. Expected: FAIL because `wf draft delete` is not registered.

- [ ] **Step 3: Implement command**

In `src/wf_cli/commands/drafts.py`, add:

```python
@app.command("delete")
def delete_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help="Required confirmation for deleting a draft workspace.",
        ),
    ] = False,
) -> None:
    """Delete a stored draft workspace."""
    if not confirm:
        raise typer.BadParameter("pass --confirm to delete a draft workspace")
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.delete_draft_workspace(workspace_id=workspace_id),
        )
    )
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py tests/wf_cli/test_drafts.py -q
```

Expected: PASS. If only one of those files exists, run the file that exists.

## Task 4: Docs And Roadmap

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Document the command**

In `docs/wf_cli.md`, add a short cleanup example near draft commands or the product-smoke/runbook area:

```bash
wf draft delete smoke_ws_20260609 --confirm
```

State that draft deletion removes only the draft workspace. It does not delete artifacts, deployments, or runs.

- [ ] **Step 2: Update roadmap status**

In `docs/current_roadmap.md`, change the draft-delete item from planned to completed and keep artifact deletion as a separate policy/store slice.

## Task 5: Final Verification

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_app.py tests/wf_cli -q
```

Expected: PASS.

- [ ] **Step 2: Run lint and types**

Run:

```bash
uv run ruff check src tests docs
uv run ruff format --check src tests docs
uv run basedpyright --level error src tests/wf_transport_rpc_http tests/wf_cli
```

Expected: all clean. If `ruff format --check docs` reports Markdown preview-mode limitations, note it in the report and run `uv run ruff format --check src tests` instead.

- [ ] **Step 3: Optional manual smoke against a running server**

If `wf-rpc-server` is already running:

```bash
uv run wf --url http://127.0.0.1:8765/rpc draft create-from-capability delete_smoke_ws wf.std.constant --name delete_smoke
uv run wf --url http://127.0.0.1:8765/rpc draft delete delete_smoke_ws --confirm
uv run wf --url http://127.0.0.1:8765/rpc draft inspect delete_smoke_ws
```

Expected: create succeeds, delete returns JSON with `deleted: true`, inspect returns a compact expected error that the workspace is missing.

