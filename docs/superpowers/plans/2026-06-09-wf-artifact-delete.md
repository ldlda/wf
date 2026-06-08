# wf Artifact Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe `wf artifact delete <artifact_id> <version> --confirm` that deletes unreferenced artifact versions and refuses to delete artifact versions still referenced by deployments.

**Architecture:** Artifact deletion starts at `WorkflowArtifactStore`, because deployments live beside artifacts and can reference `(artifact_id, version)`. The API checks blockers before deleting; RPC and CLI expose the same safe semantics without cascade behavior.

**Tech Stack:** Python 3.14, Pydantic models, Typer, fastapi-jsonrpc, pytest, pytest-asyncio, ruff, basedpyright.

---

## Contract

Implement the policy in [`artifact delete policy`](../specs/2026-06-09-artifact-delete-policy.md):

- Delete only one artifact version.
- Reject deletion when one or more deployments reference that artifact version.
- Return blocking deployment ids in the response.
- Require `--confirm` at the CLI.
- Do not cascade-delete deployments.
- Do not delete runs or draft workspaces.

## Files

- Modify `src/wf_artifacts/store.py` for store primitives.
- Modify `src/wf_api/artifacts.py` for API policy and event recording.
- Modify `src/wf_api/surface.py` to add `delete_artifact`.
- Modify `src/wf_transport_rpc_http/models.py` for params.
- Modify `src/wf_transport_rpc_http/methods/artifacts.py` for JSON-RPC method.
- Modify `src/wf_transport_rpc_http/client/artifacts.py` for RPC client.
- Modify `src/wf_cli/commands/artifacts.py` for CLI command.
- Test `tests/artifacts/test_store.py`.
- Test `tests/wf_api/test_artifact_api.py`.
- Test `tests/wf_transport_rpc_http/test_app.py` and `tests/wf_transport_rpc_http/test_client.py`.
- Test `tests/wf_cli/test_remote_target.py` or a focused artifact CLI test file.
- Update `docs/wf_cli.md`.
- Update `docs/current_roadmap.md`.

## Task 1: Store Primitives

**Files:**
- Modify: `src/wf_artifacts/store.py`
- Test: `tests/artifacts/test_store.py`

- [ ] **Step 1: Add failing tests for artifact delete**

In `tests/artifacts/test_store.py`, add:

```python
def test_file_store_deletes_one_artifact_version(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    store.save_artifact(artifact(1))
    store.save_artifact(artifact(2))

    store.delete_artifact("summarize_docs", 1)

    with pytest.raises(KeyError, match="unknown workflow artifact"):
        store.get_artifact("summarize_docs", 1)
    assert store.get_artifact("summarize_docs", 2).version == 2


def test_file_store_delete_artifact_missing_version_raises_key_error(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)

    with pytest.raises(KeyError, match="unknown workflow artifact"):
        store.delete_artifact("summarize_docs", 1)


def test_file_store_finds_deployments_for_artifact_version(tmp_path) -> None:
    store = FileWorkflowArtifactStore(tmp_path)
    store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.work",
            artifact_id="summarize_docs",
            artifact_version=1,
        )
    )
    store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.personal",
            artifact_id="summarize_docs",
            artifact_version=1,
        )
    )
    store.save_deployment(
        WorkflowDeployment(
            id="summarize_docs.v2",
            artifact_id="summarize_docs",
            artifact_version=2,
        )
    )

    blockers = store.deployments_for_artifact("summarize_docs", 1)

    assert [deployment.id for deployment in blockers] == [
        "summarize_docs.personal",
        "summarize_docs.work",
    ]
```

- [ ] **Step 2: Run store tests and verify failure**

Run:

```bash
uv run pytest tests/artifacts/test_store.py -q
```

Expected: FAIL because `delete_artifact` and `deployments_for_artifact` do not exist.

- [ ] **Step 3: Add abstract store methods**

In `WorkflowArtifactStore`, add:

```python
    def delete_artifact(self, artifact_id: str, version: int) -> None:
        raise NotImplementedError

    def deployments_for_artifact(
        self, artifact_id: str, version: int
    ) -> list[WorkflowDeployment]:
        raise NotImplementedError
```

- [ ] **Step 4: Implement file store methods**

In `FileWorkflowArtifactStore`, add:

```python
    def delete_artifact(self, artifact_id: str, version: int) -> None:
        """Remove one immutable artifact version from the store."""
        path = self._artifact_dir(artifact_id) / self._artifact_filename(version)
        if not path.exists():
            raise KeyError(f"unknown workflow artifact {artifact_id}@{version}")
        path.unlink()

    def deployments_for_artifact(
        self, artifact_id: str, version: int
    ) -> list[WorkflowDeployment]:
        """Return deployments that currently reference one artifact version."""
        return [
            deployment
            for deployment in self.list_deployments()
            if deployment.artifact_id == artifact_id
            and deployment.artifact_version == version
        ]
```

Keep sorting behavior from `list_deployments()`; do not add separate sort logic.

- [ ] **Step 5: Run store tests**

Run:

```bash
uv run pytest tests/artifacts/test_store.py -q
```

Expected: PASS.

## Task 2: wf_api Artifact Delete Policy

**Files:**
- Modify: `src/wf_api/artifacts.py`
- Modify: `src/wf_api/surface.py`
- Test: `tests/wf_api/test_artifact_api.py`

- [ ] **Step 1: Add failing API tests**

In `tests/wf_api/test_artifact_api.py`, add tests near `test_inspect_artifact_returns_stable_fields`:

```python
def test_delete_artifact_deletes_unreferenced_version(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_delete")
    api, _service = _artifact_api(artifact_store)
    artifact_store.save_artifact(_echo_artifact())

    result = asyncio.run(api.delete_artifact(artifact_id="echo", version=1))

    assert result["artifact_id"] == "echo"
    assert result["version"] == 1
    assert result["deleted"] is True
    assert result["blocked_by_deployments"] == []
    with pytest.raises(KeyError, match="unknown workflow artifact"):
        artifact_store.get_artifact("echo", 1)


def test_delete_artifact_rejects_referenced_version(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "artifacts_delete_blocked")
    api, _service = _artifact_api(artifact_store)
    artifact_store.save_artifact(_echo_artifact())
    artifact_store.save_deployment(
        WorkflowDeployment(
            id="echo.default",
            artifact_id="echo",
            artifact_version=1,
        )
    )

    result = asyncio.run(api.delete_artifact(artifact_id="echo", version=1))

    assert result["artifact_id"] == "echo"
    assert result["version"] == 1
    assert result["deleted"] is False
    assert result["blocked_by_deployments"] == ["echo.default"]
    assert artifact_store.get_artifact("echo", 1).id == "echo"
```

Add imports if missing:

```python
import pytest
from wf_artifacts import WorkflowDeployment
```

If `pytest` is already imported in the file after prior edits, do not duplicate it.

- [ ] **Step 2: Run API tests and verify failure**

Run:

```bash
uv run pytest tests/wf_api/test_artifact_api.py -q
```

Expected: FAIL because `WorkflowArtifactApi.delete_artifact` does not exist.

- [ ] **Step 3: Add surface method**

In `src/wf_api/surface.py`, add to `WorkflowArtifactSurface`:

```python
    async def delete_artifact(
        self,
        *,
        artifact_id: str,
        version: int,
    ) -> dict[str, Any]: ...
```

- [ ] **Step 4: Implement API method**

In `src/wf_api/artifacts.py`, add after `inspect_artifact`:

```python
    async def delete_artifact(
        self, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        store = self._artifact_store()
        blockers = store.deployments_for_artifact(artifact_id, version)
        blocker_ids = [deployment.id for deployment in blockers]
        if blocker_ids:
            return {
                "artifact_id": artifact_id,
                "version": version,
                "deleted": False,
                "blocked_by_deployments": blocker_ids,
            }
        store.delete_artifact(artifact_id, version)
        self.context.events.record_workflow_event(
            "workflow_artifact_deleted",
            capability_id=f"{artifact_id}@{version}",
            payload={"artifact_id": artifact_id, "version": version},
        )
        return {
            "artifact_id": artifact_id,
            "version": version,
            "deleted": True,
            "blocked_by_deployments": [],
        }
```

If review objects to the `capability_id` string, use `artifact_capability_id` only if constructing a fake artifact is not required. Do not load the artifact after deletion just to build an event id.

- [ ] **Step 5: Run API tests**

Run:

```bash
uv run pytest tests/wf_api/test_artifact_api.py -q
```

Expected: PASS.

## Task 3: JSON-RPC And Client

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/artifacts.py`
- Modify: `src/wf_transport_rpc_http/client/artifacts.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add failing RPC/client tests**

In `tests/wf_transport_rpc_http/test_app.py`, add an app-level method test that saves an artifact then calls:

```python
payload = await _rpc(
    client,
    "workflow.artifacts.delete",
    {"artifact_id": "delete_artifact", "version": 1},
)
assert payload["result"]["artifact_id"] == "delete_artifact"
assert payload["result"]["version"] == 1
assert payload["result"]["deleted"] is True
assert payload["result"]["blocked_by_deployments"] == []
```

In `tests/wf_transport_rpc_http/test_client.py`, add a client method test:

```python
deleted = await client.delete_artifact(artifact_id="delete_artifact", version=1)
assert deleted["deleted"] is True
```

Use existing helpers in those files for building/saving artifacts. If no helper exists, create the artifact through `client.save_artifact(...)` using the existing artifact test payload pattern.

- [ ] **Step 2: Run RPC tests and verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q
```

Expected: FAIL because params/method/client method do not exist.

- [ ] **Step 3: Add params model**

In `src/wf_transport_rpc_http/models.py`, add:

```python
class DeleteArtifactParams(RpcParamsModel):
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)
```

- [ ] **Step 4: Register RPC method**

In `src/wf_transport_rpc_http/methods/artifacts.py`, import `DeleteArtifactParams` and add:

```python
    @entrypoint.method(name="workflow.artifacts.delete", errors=[WorkflowRpcError])
    async def workflow_artifacts_delete(
        params: DeleteArtifactParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.delete_artifact(
                artifact_id=params.artifact_id,
                version=params.version,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 5: Add client method**

In `src/wf_transport_rpc_http/client/artifacts.py`, add:

```python
    async def delete_artifact(
        self: RpcCaller, *, artifact_id: str, version: int
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.artifacts.delete",
            {"artifact_id": artifact_id, "version": version},
        )
```

- [ ] **Step 6: Run RPC/client tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q
```

Expected: PASS.

## Task 4: CLI Command

**Files:**
- Modify: `src/wf_cli/commands/artifacts.py`
- Test: `tests/wf_cli/test_remote_target.py` or `tests/wf_cli/test_artifacts.py`

- [ ] **Step 1: Add CLI tests**

Add tests for:

1. Missing `--confirm` fails.
2. Confirmed delete succeeds.
3. Referenced artifact returns `deleted: false` and blocker ids.

Minimum assertions:

```python
result = runner.invoke(app, [*base_args, "artifact", "delete", "echo", "1"])
assert result.exit_code != 0
assert "confirm" in result.output.lower()
```

Success:

```python
result = runner.invoke(
    app, [*base_args, "artifact", "delete", "echo", "1", "--confirm"]
)
assert result.exit_code == 0, result.output
payload = json.loads(result.output)
assert payload["artifact_id"] == "echo"
assert payload["version"] == 1
assert payload["deleted"] is True
```

Blocked:

```python
payload = json.loads(result.output)
assert payload["deleted"] is False
assert payload["blocked_by_deployments"] == ["echo.default"]
```

- [ ] **Step 2: Run CLI tests and verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py -q
```

Expected: FAIL because `wf artifact delete` does not exist.

- [ ] **Step 3: Implement command**

In `src/wf_cli/commands/artifacts.py`, add:

```python
@app.command("delete")
def delete_artifact(
    ctx: typer.Context,
    artifact_id: Annotated[str, typer.Argument(help="Artifact id.")],
    version: Annotated[int, typer.Argument(min=1, help="Artifact version.")],
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help="Required confirmation for deleting an artifact version.",
        ),
    ] = False,
) -> None:
    """Delete one unreferenced artifact version."""
    if not confirm:
        raise typer.BadParameter("pass --confirm to delete an artifact version")
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.delete_artifact(
                artifact_id=artifact_id,
                version=version,
            ),
        )
    )
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py -q
```

Expected: PASS.

## Task 5: Docs And Roadmap

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-09-artifact-delete-policy.md`

- [ ] **Step 1: Document command**

In `docs/wf_cli.md`, add:

```bash
wf artifact delete smoke_artifact_20260609 1 --confirm
```

State that the command refuses to delete artifact versions referenced by deployments, and users should delete deployments first with `wf deploy delete <deployment_id>`.

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, mark artifact delete complete under Priority 1 after implementation. Keep the artifact-delete policy spec linked as current behavior if it remains accurate.

- [ ] **Step 3: Update policy spec status**

At the top of `docs/superpowers/specs/2026-06-09-artifact-delete-policy.md`, add:

```markdown
## Status

Implemented: `wf artifact delete <artifact_id> <version> --confirm` deletes
unreferenced artifact versions and rejects versions referenced by deployments.
```

## Task 6: Final Verification

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/artifacts/test_store.py tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py -q
```

Expected: PASS.

- [ ] **Step 2: Run changed-file lint/type checks**

Run:

```bash
uv run ruff check src/wf_artifacts/store.py src/wf_api/artifacts.py src/wf_api/surface.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/artifacts.py src/wf_transport_rpc_http/client/artifacts.py src/wf_cli/commands/artifacts.py tests/artifacts/test_store.py tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py docs/current_roadmap.md docs/wf_cli.md docs/superpowers/specs/2026-06-09-artifact-delete-policy.md
uv run basedpyright --level error src/wf_artifacts/store.py src/wf_api/artifacts.py src/wf_api/surface.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/artifacts.py src/wf_transport_rpc_http/client/artifacts.py src/wf_cli/commands/artifacts.py tests/artifacts/test_store.py tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py
```

Expected: PASS. If global ruff reports unrelated pre-existing errors, scope the final report to changed-file lint and list the unrelated files separately.

- [ ] **Step 3: Optional manual smoke**

Against a running server:

```bash
uv run wf --url http://127.0.0.1:8765/rpc artifact delete smoke_artifact_20260609 1 --confirm
```

Expected:

- If the deployment still exists: `deleted: false` with `blocked_by_deployments`.
- After `wf deploy delete smoke_deploy_20260609`: `deleted: true`.

