# Run List API/RPC/CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose persisted stopped workflow runs through a compact, paged `list_runs` API, JSON-RPC method, RPC client method, and `wf run list` CLI command.

**Architecture:** `RunStore.list_runs()` already stores durable run records for `completed`, `failed`, and `interrupted` runs. Add a summary-only read surface in `wf_api`, delegate it through `WorkflowApiSurface`, expose it over JSON-RPC, and add a CLI command that emits JSON like the rest of `wf run`. Do not expose checkpoints, trace entries, deletion, retention, or retry policy in this slice.

**Tech Stack:** Python 3.14, Pydantic v2, Typer, fastapi-jsonrpc, pytest/pytest-asyncio, ruff, basedpyright.

---

## Desired Behavior

`wf run list` should answer “what durable runs exist in this target store?” without requiring a run id.

Output shape:

```json
{
  "runs": [
    {
      "run_id": "run_abc",
      "deployment_id": "echo.personal",
      "artifact_id": "echo",
      "artifact_version": 1,
      "status": "completed",
      "resume_readiness": "not_applicable",
      "diagnostic_count": 0,
      "created_at": "2026-06-11T00:00:00Z",
      "updated_at": "2026-06-11T00:00:01Z"
    }
  ],
  "total": 1,
  "cursor": null,
  "next_cursor": null,
  "limit": 50
}
```

Rules:

- Sort newest first by `updated_at`, then `run_id`.
- Support `status` filter values: `completed`, `failed`, `interrupted`.
- Use offset cursor strings: `cursor="0"`, `cursor="50"`, etc.
- Reject invalid `cursor`, `limit`, and `status` with `ValueError` in `wf_api`.
- Do not include trace entries, checkpoint state, `output`, `error`, or pinned artifact/deployment bodies in list rows.
- Keep `inspect_run` as the detail surface and `read_run_trace` as the bounded trace surface.

## File Structure

- Modify `src/wf_api/runs.py`
  - Add `WorkflowRunApi.list_runs(...)`.
  - Add `_run_summary(record)` and `_cursor_offset(cursor)` helpers.
- Modify `src/wf_api/surface.py`
  - Add `list_runs(...)` to `WorkflowRunSurface`.
- Modify `src/wf_api/service.py`
  - Add `WorkflowApi.list_runs(...)` delegate.
- Modify `src/wf_transport_rpc_http/models.py`
  - Add `ListRunsParams`.
- Modify `src/wf_transport_rpc_http/methods/runs.py`
  - Register `workflow.runs.list`.
- Modify `src/wf_transport_rpc_http/client/runs.py`
  - Add `RpcRunClientMixin.list_runs(...)`.
- Modify `src/wf_cli/commands/runs.py`
  - Add `wf run list`.
- Modify tests:
  - `tests/wf_api/test_run_api.py`
  - `tests/wf_transport_rpc_http/test_app.py`
  - `tests/wf_transport_rpc_http/test_client.py`
  - `tests/wf_cli/test_run_deploy.py` or `tests/wf_cli/test_remote_target.py`, whichever already owns run CLI routing assertions.
- Modify docs:
  - `docs/wf_cli.md`
  - `docs/current_roadmap.md`
  - `docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md`

---

## Task 1: Add `WorkflowRunApi.list_runs`

**Files:**

- Modify: `src/wf_api/runs.py`
- Modify: `tests/wf_api/test_run_api.py`

- [ ] **Step 1: Add failing API tests**

Append these tests to `tests/wf_api/test_run_api.py`. Prefer `async def` for the new tests; existing older tests can remain unchanged.

```python
async def test_run_api_lists_runs_newest_first_with_summary(tmp_path: Path) -> None:
    root = tmp_path / "run_api_list"
    service, _ = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    first = await api.run_deployment(
        deployment_id="echo.personal",
        workflow_input={"text": "first"},
    )
    second = await api.run_deployment(
        deployment_id="echo.personal",
        workflow_input={"text": "second"},
    )

    payload = await api.list_runs()

    assert payload["total"] == 2
    assert payload["cursor"] is None
    assert payload["next_cursor"] is None
    assert payload["limit"] == 50
    assert [row["run_id"] for row in payload["runs"]] == [
        second["run_id"],
        first["run_id"],
    ]
    first_row = payload["runs"][0]
    assert first_row["deployment_id"] == "echo.personal"
    assert first_row["artifact_id"] == "echo"
    assert first_row["artifact_version"] == 1
    assert first_row["status"] == "completed"
    assert first_row["resume_readiness"] == "not_applicable"
    assert first_row["diagnostic_count"] == 0
    assert "trace" not in first_row
    assert "output" not in first_row
    assert "environment" not in first_row


async def test_run_api_lists_runs_with_status_filter_and_offset_cursor(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run_api_list_filter"
    service, _ = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    await api.run_deployment(
        deployment_id="echo.personal",
        workflow_input={"text": "first"},
    )
    await api.run_deployment(
        deployment_id="echo.personal",
        workflow_input={"text": "second"},
    )

    first_page = await api.list_runs(status="completed", limit=1)
    second_page = await api.list_runs(
        status="completed",
        cursor=first_page["next_cursor"],
        limit=1,
    )

    assert first_page["total"] == 2
    assert first_page["next_cursor"] == "1"
    assert len(first_page["runs"]) == 1
    assert second_page["total"] == 2
    assert second_page["cursor"] == "1"
    assert second_page["next_cursor"] is None
    assert len(second_page["runs"]) == 1
    assert first_page["runs"][0]["run_id"] != second_page["runs"][0]["run_id"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"status": "running"}, "status must be one of"),
        ({"cursor": "not-int"}, "cursor must be a non-negative integer offset"),
        ({"cursor": "-1"}, "cursor must be a non-negative integer offset"),
        ({"limit": 0}, "limit must be between 1 and 100"),
        ({"limit": 101}, "limit must be between 1 and 100"),
    ],
)
async def test_run_api_list_runs_rejects_invalid_query(
    tmp_path: Path,
    kwargs: dict[str, object],
    message: str,
) -> None:
    root = tmp_path / "run_api_list_invalid"
    service, _ = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowRunApi(context)

    with pytest.raises(ValueError, match=message):
        await api.list_runs(**kwargs)
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
uv run pytest tests/wf_api/test_run_api.py -q
```

Expected: fail because `WorkflowRunApi` has no `list_runs`.

- [ ] **Step 3: Implement `list_runs` in `src/wf_api/runs.py`**

Add `StoredRunStatus` and `WorkflowRunRecord` to the existing `wf_artifacts` import:

```python
from wf_artifacts import (
    DependencyDiagnostic,
    RunStore,
    StoredRunStatus,
    WorkflowArtifact,
    WorkflowDeployment,
    WorkflowRunRecord,
)
```

Add this method to `WorkflowRunApi`, after `resume_run` and before `inspect_run`:

```python
    async def list_runs(
        self,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return compact persisted run summaries without trace or checkpoint state."""
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        start = _cursor_offset(cursor)
        status_filter: StoredRunStatus | None = None
        if status is not None:
            try:
                status_filter = StoredRunStatus(status)
            except ValueError as exc:
                allowed = ", ".join(item.value for item in StoredRunStatus)
                raise ValueError(f"status must be one of: {allowed}") from exc

        records = self._run_store().list_runs()
        if status_filter is not None:
            records = [record for record in records if record.status == status_filter]
        records.sort(key=lambda record: (record.updated_at, record.id), reverse=True)

        total = len(records)
        end = start + limit
        page = records[start:end]
        return {
            "runs": [_run_summary(record) for record in page],
            "total": total,
            "cursor": cursor,
            "next_cursor": str(end) if end < total else None,
            "limit": limit,
        }
```

Add these helpers near `_trace_range_values`:

```python
def _cursor_offset(cursor: str | None) -> int:
    """Parse the simple offset cursor used by run listing."""
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
    except ValueError as exc:
        raise ValueError("cursor must be a non-negative integer offset") from exc
    if offset < 0:
        raise ValueError("cursor must be a non-negative integer offset")
    return offset


def _run_summary(record: WorkflowRunRecord) -> dict[str, Any]:
    """Return an operator-facing run row without heavy runtime state."""
    environment = record.environment
    return {
        "run_id": record.id,
        "deployment_id": environment.deployment.id,
        "artifact_id": environment.root_artifact.id,
        "artifact_version": environment.root_artifact.version,
        "status": record.status.value,
        "resume_readiness": record.resume_readiness.value,
        "diagnostic_count": len(record.diagnostics),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
```

- [ ] **Step 4: Run API tests**

Run:

```bash
uv run pytest tests/wf_api/test_run_api.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit API slice**

Run:

```bash
git add src/wf_api/runs.py tests/wf_api/test_run_api.py
git commit -m "feat: add workflow run listing API"
```

---

## Task 2: Add Surface And Facade Delegation

**Files:**

- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/service.py`
- Test: `tests/wf_api/test_run_api.py`

- [ ] **Step 1: Add delegation assertion to existing handler delegation test**

In `tests/wf_api/test_run_api.py`, extend `test_run_api_handler_delegation_matches` after the existing inspect assertions:

```python
    handler_list = asyncio.run(handlers.list_runs())
    api_list = asyncio.run(api.list_runs())

    assert handler_list["total"] == api_list["total"]
    assert handler_list["runs"][0]["run_id"] == api_list["runs"][0]["run_id"]
```

Expected: fail because `WorkflowSurfaceHandlers` may not expose `list_runs` yet. If it already delegates through `WorkflowApi`, add a new `WorkflowApi` facade test instead:

```python
from wf_api import WorkflowApi


async def test_workflow_api_facade_lists_runs(tmp_path: Path) -> None:
    root = tmp_path / "workflow_api_list_runs"
    service, _ = _service_with_echo(root)
    context = context_from_service(service)
    api = WorkflowApi(context)
    await api.run_deployment(
        deployment_id="echo.personal",
        workflow_input={"text": "hello"},
    )

    payload = await api.list_runs()

    assert payload["total"] == 1
    assert payload["runs"][0]["deployment_id"] == "echo.personal"
```

- [ ] **Step 2: Add `list_runs` to `WorkflowRunSurface`**

In `src/wf_api/surface.py`, add this method at the top of `WorkflowRunSurface`, before `run_deployment`:

```python
    async def list_runs(
        self,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]: ...
```

- [ ] **Step 3: Add `WorkflowApi.list_runs` delegate**

In `src/wf_api/service.py`, add this under `# -- runs --`, before `run_deployment`:

```python
    async def list_runs(
        self,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self.runs.list_runs(
            status=status,
            cursor=cursor,
            limit=limit,
        )
```

- [ ] **Step 4: Add MCP workflow surface handler delegation if needed**

If Step 1 fails because `WorkflowSurfaceHandlers` lacks `list_runs`, update `src/wf_mcp/workflow_surface/handlers.py` or the current handler module that owns run methods with:

```python
    async def list_runs(
        self,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._api.list_runs(status=status, cursor=cursor, limit=limit)
```

Use the existing handler construction pattern in that file. Do not expose an MCP tool in this task unless the existing run tools are generated from this handler automatically.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/wf_api/test_run_api.py -q
```

Expected: pass.

- [ ] **Step 6: Commit surface slice**

Run:

```bash
git add src/wf_api/surface.py src/wf_api/service.py src/wf_mcp/workflow_surface tests/wf_api/test_run_api.py
git commit -m "feat: expose run listing on workflow surface"
```

If no `wf_mcp/workflow_surface` file changed, omit that path from `git add`.

---

## Task 3: Add JSON-RPC Method And Client

**Files:**

- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/runs.py`
- Modify: `src/wf_transport_rpc_http/client/runs.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add failing RPC app test**

Append to `tests/wf_transport_rpc_http/test_app.py`:

```python
async def test_rpc_run_list_method(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="list_runs_rpc",
        version=1,
        title="List Runs RPC",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={"wf.std": "wf.std"},
    )
    await server.api.save_deployment(
        {
            "id": "list_runs_rpc.default",
            "artifact_id": "list_runs_rpc",
            "artifact_version": 1,
            "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
        }
    )
    started = await server.api.run_deployment(
        deployment_id="list_runs_rpc.default",
        workflow_input={},
    )

    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        payload = await _rpc(
            client,
            "workflow.runs.list",
            {"status": "completed", "limit": 10},
        )

    assert payload["result"]["total"] == 1
    assert payload["result"]["runs"][0]["run_id"] == started["run_id"]
    assert payload["result"]["runs"][0]["deployment_id"] == "list_runs_rpc.default"
    assert "trace" not in payload["result"]["runs"][0]
```

- [ ] **Step 2: Add failing RPC client test**

In `tests/wf_transport_rpc_http/test_client.py`, add a test near existing run client tests:

```python
async def test_rpc_client_lists_runs(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    await server.api.create_artifact_from_plan(
        artifact_id="client_list_runs",
        version=1,
        title="Client List Runs",
        plan=_constant_plan(),
        outcomes=["ok"],
        source_bindings={"wf.std": "wf.std"},
    )
    await server.api.save_deployment(
        {
            "id": "client_list_runs.default",
            "artifact_id": "client_list_runs",
            "artifact_version": 1,
            "bindings": [{"logical_source": "wf.std", "concrete_source": "wf.std"}],
        }
    )
    started = await server.api.run_deployment(
        deployment_id="client_list_runs.default",
        workflow_input={},
    )

    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        client = RpcWorkflowApiClient(base_url="http://test/rpc", http_client=http)
        listed = await client.list_runs(status="completed", limit=5)

    assert listed["total"] == 1
    assert listed["runs"][0]["run_id"] == started["run_id"]
```

If `_constant_plan`, `create_rpc_app`, or `RpcWorkflowApiClient` are already imported under different names, follow the existing file convention.

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_run_list_method tests/wf_transport_rpc_http/test_client.py::test_rpc_client_lists_runs -q
```

Expected: fail because `workflow.runs.list` and client method are missing.

- [ ] **Step 4: Add RPC params model**

In `src/wf_transport_rpc_http/models.py`, add after `TraceRangeParams` or before `StartRunParams`:

```python
class ListRunsParams(RpcParamsModel):
    status: Literal["completed", "failed", "interrupted"] | None = None
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)
```

- [ ] **Step 5: Register JSON-RPC method**

In `src/wf_transport_rpc_http/methods/runs.py`, import `ListRunsParams`:

```python
from ..models import (
    InspectRunParams,
    ListRunsParams,
    ReadRunTraceParams,
    ResumeRunParams,
    StartRunParams,
)
```

Add this method before `workflow.runs.start`:

```python
    @entrypoint.method(name="workflow.runs.list", errors=[WorkflowRpcError])
    async def workflow_runs_list(
        params: ListRunsParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.list_runs(
                status=params.status,
                cursor=params.cursor,
                limit=params.limit,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 6: Add RPC client method**

In `src/wf_transport_rpc_http/client/runs.py`, add this method at the top of `RpcRunClientMixin`:

```python
    async def list_runs(
        self: RpcCaller,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.runs.list",
            {
                "status": status,
                "cursor": cursor,
                "limit": limit,
            },
        )
```

- [ ] **Step 7: Run RPC tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_run_list_method tests/wf_transport_rpc_http/test_client.py::test_rpc_client_lists_runs -q
```

Expected: pass.

- [ ] **Step 8: Commit RPC slice**

Run:

```bash
git add src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/runs.py src/wf_transport_rpc_http/client/runs.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
git commit -m "feat: expose run listing over json rpc"
```

---

## Task 4: Add `wf run list`

**Files:**

- Modify: `src/wf_cli/commands/runs.py`
- Modify: `tests/wf_cli/test_run_deploy.py` or `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add CLI tests**

If `tests/wf_cli/test_run_deploy.py` owns fake run handlers, add:

```python
def test_wf_run_list_emits_json(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeHandlers:
        async def list_runs(self, *, status=None, cursor=None, limit=50):
            captured["status"] = status
            captured["cursor"] = cursor
            captured["limit"] = limit
            return {
                "runs": [
                    {
                        "run_id": "run_1",
                        "deployment_id": "demo.default",
                        "artifact_id": "demo",
                        "artifact_version": 1,
                        "status": "completed",
                        "resume_readiness": "not_applicable",
                        "diagnostic_count": 0,
                        "created_at": "2026-06-11T00:00:00",
                        "updated_at": "2026-06-11T00:00:01",
                    }
                ],
                "total": 1,
                "cursor": None,
                "next_cursor": None,
                "limit": 25,
            }

    monkeypatch.setattr(
        "wf_cli.commands.runs.load_cli_context_from_typer",
        lambda ctx: type("Ctx", (), {"handlers": FakeHandlers(), "verbose": False})(),
    )

    result = CliRunner().invoke(
        app,
        ["list", "--status", "completed", "--limit", "25"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["total"] == 1
    assert payload["runs"][0]["run_id"] == "run_1"
    assert captured == {"status": "completed", "cursor": None, "limit": 25}
```

If that file does not import the `run` Typer app directly, follow the existing pattern in `tests/wf_cli/test_remote_target.py` and assert the command routes through the RPC client.

- [ ] **Step 2: Run failing CLI test**

Run the selected CLI test:

```bash
uv run pytest tests/wf_cli/test_run_deploy.py -q
```

Expected: fail because `wf run list` is missing.

- [ ] **Step 3: Add command to `src/wf_cli/commands/runs.py`**

Add this command before `start_run`:

```python
@app.command("list")
def list_runs(
    ctx: typer.Context,
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            help="Filter by stopped status: completed, failed, or interrupted.",
        ),
    ] = None,
    cursor: Annotated[
        str | None,
        typer.Option("--cursor", help="Offset cursor returned by a previous page."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=100, help="Maximum run summaries."),
    ] = 50,
) -> None:
    """List durable stopped workflow runs without trace entries."""
    context = load_cli_context_from_typer(ctx)
    payload = run_cli_operation(
        context,
        context.handlers.list_runs(status=status, cursor=cursor, limit=limit),
    )
    emit_json(payload)
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_run_deploy.py tests/wf_cli/test_remote_target.py -q
```

Expected: pass.

- [ ] **Step 5: Commit CLI slice**

Run:

```bash
git add src/wf_cli/commands/runs.py tests/wf_cli/test_run_deploy.py tests/wf_cli/test_remote_target.py
git commit -m "feat: add wf run list command"
```

Only include the test files that changed.

---

## Task 5: Docs And Verification

**Files:**

- Modify: `docs/wf_cli.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md`
- Move: `docs/superpowers/plans/2026-06-11-run-list-api-rpc-cli.md` to `docs/historical/superpowers/plans/2026-06-11-run-list-api-rpc-cli.md`

- [ ] **Step 1: Update `docs/wf_cli.md`**

Add under the run commands section:

```markdown
### List durable runs

```bash
wf run list --limit 20
wf run list --status interrupted
wf --url http://127.0.0.1:8765/rpc run list --status failed
```

`wf run list` returns compact stopped-run summaries from the target store. It
does not include trace entries or checkpoint state. Use `wf run inspect <run_id>`
for one run summary and `wf run trace <run_id> --from 0 --limit 25` for bounded
debug detail.
```

- [ ] **Step 2: Update roadmap**

In `docs/current_roadmap.md`, under “Priority 2: Durable Run/Resume Hardening”, add:

```markdown
- Completed: paged `wf run list` exposes compact persisted stopped-run
  summaries without trace or checkpoint state. Implementation:
  [`run list API/RPC/CLI`](historical/superpowers/plans/2026-06-11-run-list-api-rpc-cli.md).
```

- [ ] **Step 3: Update persisted run/resume spec**

In `docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md`, update the section that says public listing is missing. Replace it with:

```markdown
- `RunStore` can list runs, and the public workflow API exposes compact paged
  run listing. Checkpoint listing remains intentionally private for now.
```

Also add a short operation note near the `inspect_run`/`read_run_trace` sections:

```markdown
### `list_runs`

Returns paged compact summaries for stopped durable runs. The list payload
contains run id, deployment id, artifact id/version, status, resume readiness,
diagnostic count, and timestamps. It never returns trace entries, checkpoint
state, runtime output, or pinned environment bodies.
```

- [ ] **Step 4: Move completed plan**

Run:

```bash
git mv docs/superpowers/plans/2026-06-11-run-list-api-rpc-cli.md docs/historical/superpowers/plans/2026-06-11-run-list-api-rpc-cli.md
```

- [ ] **Step 5: Run focused verification**

Run:

```bash
uv run pytest tests/wf_api/test_run_api.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_run_deploy.py tests/wf_cli/test_remote_target.py -q
uv run ruff check src/wf_api/runs.py src/wf_api/surface.py src/wf_api/service.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/runs.py src/wf_transport_rpc_http/client/runs.py src/wf_cli/commands/runs.py tests/wf_api/test_run_api.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_run_deploy.py tests/wf_cli/test_remote_target.py
uv run ruff format --check src/wf_api/runs.py src/wf_api/surface.py src/wf_api/service.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/runs.py src/wf_transport_rpc_http/client/runs.py src/wf_cli/commands/runs.py tests/wf_api/test_run_api.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_run_deploy.py tests/wf_cli/test_remote_target.py
uv run basedpyright --level error src/wf_api src/wf_transport_rpc_http src/wf_cli tests/wf_api/test_run_api.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_run_deploy.py tests/wf_cli/test_remote_target.py
git diff --check
```

Expected:

- Focused tests pass.
- Ruff check passes.
- Ruff format check passes.
- Basedpyright reports 0 errors for changed files, or only explicitly documented unrelated pre-existing errors.
- `git diff --check` reports no whitespace errors; CRLF warnings on Windows are acceptable.

- [ ] **Step 6: Final commit**

Run:

```bash
git add docs/wf_cli.md docs/current_roadmap.md docs/superpowers/specs/2026-06-03-persisted-run-resume-contract.md docs/historical/superpowers/plans/2026-06-11-run-list-api-rpc-cli.md
git commit -m "docs: record run listing surface"
```

If code files remain uncommitted because earlier task commits were skipped, include all changed files in one final commit:

```bash
git add src tests docs
git commit -m "feat: add durable run listing"
```

---

## Acceptance Criteria

- `WorkflowRunApi.list_runs()` returns compact summaries, sorted newest first.
- `WorkflowApiSurface` includes `list_runs`.
- JSON-RPC method `workflow.runs.list` works.
- `RpcWorkflowApiClient.list_runs()` works.
- `wf run list` works for local and remote targets.
- Listing never includes trace entries, checkpoint state, output payloads, or pinned environment bodies.
- Invalid `status`, `cursor`, and `limit` are rejected.
- Docs state that `inspect` and bounded `trace` remain the detail surfaces.

