# Remote CLI Lifecycle RPC Methods Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `wf` draft/artifact/deploy commands work against `client.target.kind = "rpc_http"` instead of failing fast as local-only commands.

**Architecture:** Extend the fixed JSON-RPC method set, then extend `RpcWorkflowApiClient` to structurally support every `WorkflowApi` method used by the CLI. Only after the client and server both support the methods should the CLI command modules switch from local-only context to target-aware context. Keep this as remote workflow lifecycle support, not source registry/auth/MCP hosting.

**Tech Stack:** Python 3.14, Pydantic v2, fastapi-jsonrpc, httpx, Typer, pytest, ruff, basedpyright.

---

## Scope

In scope:

- Add missing JSON-RPC methods for draft workspace, artifact, and deployment operations used by CLI.
- Add matching `RpcWorkflowApiClient` methods.
- Route `wf draft`, `wf artifact`, and `wf deploy` through `load_cli_context_from_typer`.
- Add remote CLI integration tests for create draft → validate → save artifact → save deployment → validate deployment.
- Keep existing local CLI behavior and old `wf_mcp.config.json` compatibility.

Out of scope:

- Source registry.
- MCP/OpenAPI source config.
- `/mcp` hosting.
- Auth.
- SQL stores.
- Remote docs/schema/explain commands.
- Streaming/progress.

---

## Required Method Coverage

The client must implement every method used by these command modules:

```text
src/wf_cli/commands/drafts.py
  list_draft_workspaces
  get_draft_workspace
  create_draft_workspace_from_capability
  patch_draft_workspace
  validate_draft_workspace
  create_wrapper_from_workspace
  create_artifact_from_workspace

src/wf_cli/commands/artifacts.py
  list_artifacts
  inspect_artifact

src/wf_cli/commands/deployments.py
  validate_deployment
  list_deployments
  inspect_deployment
  save_deployment
  delete_deployment
```

Do not route a command module to target-aware context until the client has the
methods that module calls.

---

## Task 1: Add Missing RPC DTOs and Server Methods for Artifacts/Deployments

**Files:**

- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/app.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`

- [ ] **Step 1: Add focused RPC app tests**

Append a test that seeds an artifact/deployment through `server.api`, then calls:

```text
workflow.artifacts.list
workflow.artifacts.inspect
workflow.deployments.list
workflow.deployments.inspect
workflow.deployments.delete
```

Assertions:

```python
assert listed_artifacts["result"]["nodes"]
assert inspected_artifact["result"]["artifact_id"] == "rpc_lifecycle"
assert listed_deployments["result"]["deployments"]
assert inspected_deployment["result"]["deployment_id"] == "rpc_lifecycle.default"
assert deleted["result"]["deployment_id"] == "rpc_lifecycle.default"
```

Use the existing `_constant_plan()` helper in `tests/wf_transport_rpc_http/test_app.py` if possible. Do not bypass the RPC app for the operations under test.

- [ ] **Step 2: Run the new test and verify method-not-found failures**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_artifact_and_deployment_catalog_methods -q
```

Expected: fail with JSON-RPC method-not-found for the newly required methods.

- [ ] **Step 3: Add DTOs**

In `src/wf_transport_rpc_http/models.py`, add:

```python
class ListArtifactsParams(RpcParamsModel):
    query: str | None = None
    kind: str | None = None
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class InspectArtifactParams(RpcParamsModel):
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)


class ListDeploymentsParams(RpcParamsModel):
    pass


class InspectDeploymentParams(RpcParamsModel):
    deployment_id: str = Field(min_length=1)


class DeleteDeploymentParams(RpcParamsModel):
    deployment_id: str = Field(min_length=1)
```

Export these from `src/wf_transport_rpc_http/__init__.py`.

- [ ] **Step 4: Register artifact/deployment methods**

In `src/wf_transport_rpc_http/app.py`, import the new DTOs and register:

```text
workflow.artifacts.list          -> server.api.list_artifacts
workflow.artifacts.inspect       -> server.api.inspect_artifact
workflow.deployments.list        -> server.api.list_deployments
workflow.deployments.inspect     -> server.api.inspect_deployment
workflow.deployments.delete      -> server.api.delete_deployment
```

Use the same expected-error handling as existing methods:

```python
except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
    raise_workflow_rpc_error(exc)
```

For `ListArtifactsParams.kind`, pass the string through as `kind=params.kind`.
If basedpyright complains because `WorkflowApi.list_artifacts` expects
`ArtifactKind | None`, narrow with:

```python
kind = params.kind if params.kind in {"workflow", "wrapper"} else None
```

and reject invalid values in the DTO if needed.

- [ ] **Step 5: Run focused transport tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py -q
uv run ruff check src/wf_transport_rpc_http tests/wf_transport_rpc_http
uv run basedpyright --level error src/wf_transport_rpc_http tests/wf_transport_rpc_http
```

Expected: tests pass, ruff clean, basedpyright 0 errors.

---

## Task 2: Add Draft Workspace RPC Methods

**Files:**

- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/app.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`

- [ ] **Step 1: Add focused draft workspace RPC test**

Append a test that calls:

```text
workflow.draft_workspaces.create_from_capability
workflow.draft_workspaces.list
workflow.draft_workspaces.get
workflow.draft_workspaces.validate
workflow.draft_workspaces.patch
workflow.draft_workspaces.create_artifact
workflow.draft_workspaces.create_wrapper
```

Use a small patch such as changing the draft name or title through the existing
workspace patch format. Assert:

```python
assert created["result"]["workspace_id"] == "remote_ws"
assert listed["result"]["workspaces"]
assert fetched["result"]["workspace_id"] == "remote_ws"
assert validated["result"]["status"] in {"valid", "invalid"}
assert patched["result"]["revision"] == created["result"]["revision"] + 1
assert artifact["result"]["artifact_id"] == "remote_artifact"
assert wrapper["result"]["artifact_id"] == "remote_wrapper"
```

If wrapper creation requires an output-capable draft and the simple capability
draft cannot satisfy it, keep `create_wrapper` covered by client method tests
and document why the RPC app integration test only covers `create_artifact`.

- [ ] **Step 2: Run the new test and verify method-not-found failures**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_draft_workspace_methods -q
```

Expected: fail with method-not-found for missing workspace methods.

- [ ] **Step 3: Add DTOs**

Add to `src/wf_transport_rpc_http/models.py`:

```python
class ListDraftWorkspacesParams(RpcParamsModel):
    pass


class GetDraftWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    include_draft: bool = False


class PatchDraftWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    patch: list[dict[str, Any]]


class ValidateDraftWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)


class CreateArtifactFromWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    outcomes: list[str]
    kind: str = "workflow"
    description: str | None = None
    required_capabilities: dict[str, dict[str, Any]] | None = None
    source_bindings: dict[str, str] | None = None
    created_from_catalog_version: str | None = None


class CreateWrapperFromWorkspaceParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    outcomes: list[str]
    description: str | None = None
    required_capabilities: dict[str, dict[str, Any]] | None = None
    source_bindings: dict[str, str] | None = None
    created_from_catalog_version: str | None = None
```

Export these from `src/wf_transport_rpc_http/__init__.py`.

- [ ] **Step 4: Register draft workspace methods**

In `src/wf_transport_rpc_http/app.py`, register:

```text
workflow.draft_workspaces.list
workflow.draft_workspaces.get
workflow.draft_workspaces.create_from_capability
workflow.draft_workspaces.patch
workflow.draft_workspaces.validate
workflow.draft_workspaces.create_artifact
workflow.draft_workspaces.create_wrapper
```

Map them to the matching `server.api` methods:

```python
server.api.list_draft_workspaces()
server.api.get_draft_workspace(...)
server.api.create_draft_workspace_from_capability(...)
server.api.patch_draft_workspace(...)
server.api.validate_draft_workspace(...)
server.api.create_artifact_from_workspace(...)
server.api.create_wrapper_from_workspace(...)
```

The existing `workflow.drafts.create_from_capability` method may stay for
backward compatibility. It can call the same API method as
`workflow.draft_workspaces.create_from_capability`.

- [ ] **Step 5: Run focused transport tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py -q
uv run ruff check src/wf_transport_rpc_http tests/wf_transport_rpc_http
uv run basedpyright --level error src/wf_transport_rpc_http tests/wf_transport_rpc_http
```

Expected: tests pass, ruff clean, basedpyright 0 errors.

---

## Task 3: Extend RpcWorkflowApiClient

**Files:**

- Modify: `src/wf_transport_rpc_http/client.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add client tests for the newly exposed methods**

Add tests covering:

```text
list_artifacts / inspect_artifact
list_deployments / inspect_deployment / validate_deployment / delete_deployment
list_draft_workspaces / get_draft_workspace / validate_draft_workspace
create_draft_workspace_from_capability
patch_draft_workspace
create_artifact_from_workspace
create_wrapper_from_workspace if feasible
```

Use `httpx.ASGITransport(app=create_rpc_app(server))` like the existing client
tests. Seed artifacts/deployments through `server.api` where the method under
test is only read/list/inspect. For create/patch workspace tests, call through
the client.

- [ ] **Step 2: Run client tests and verify failures**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_client.py -q
```

Expected: fail because `RpcWorkflowApiClient` lacks the new methods.

- [ ] **Step 3: Implement client methods**

Add one client method for each CLI-used `WorkflowApi` method listed in
"Required Method Coverage".

Wire methods to the JSON-RPC names from Tasks 1-2. Examples:

```python
async def list_artifacts(...):
    return await self._call("workflow.artifacts.list", {...})

async def get_draft_workspace(...):
    return await self._call("workflow.draft_workspaces.get", {...})

async def create_artifact_from_workspace(...):
    return await self._call("workflow.draft_workspaces.create_artifact", {...})
```

Keep signatures close to `WorkflowApi` so basedpyright accepts CLI command
calls without casts.

- [ ] **Step 4: Run client and type checks**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_client.py -q
uv run basedpyright --level error src/wf_transport_rpc_http src/wf_cli
```

Expected: client tests pass and basedpyright reports 0 errors.

---

## Task 4: Route Draft/Artifact/Deploy CLI Through Target-Aware Context

**Files:**

- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `src/wf_cli/commands/artifacts.py`
- Modify: `src/wf_cli/commands/deployments.py`
- Modify: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Write remote CLI lifecycle test**

Add a test that starts an in-process JSON-RPC app and invokes Typer commands
with:

```text
wf --config wf.json --url http://test/rpc draft create-from-capability ...
wf --config wf.json --url http://test/rpc draft validate ...
wf --config wf.json --url http://test/rpc draft save ...
wf --config wf.json --url http://test/rpc artifact inspect ...
wf --config wf.json --url http://test/rpc deploy save ...
wf --config wf.json --url http://test/rpc deploy validate ...
```

Use the same `httpx.AsyncClient` monkeypatch pattern already present in
`tests/wf_cli/test_remote_target.py`.

Assertions:

```python
assert created.exit_code == 0
assert validated.exit_code == 0
assert saved_artifact.exit_code == 0
assert inspected_artifact.exit_code == 0
assert saved_deployment.exit_code == 0
assert validated_deployment.exit_code == 0
```

Also assert key output fragments:

```python
assert '"workspace_id": "remote_ws"' in created.output
assert '"status": "valid"' in validated.output
assert '"artifact_id": "remote_artifact"' in saved_artifact.output
assert '"deployment_id": "remote_artifact.default"' in saved_deployment.output
assert '"status": "runnable"' in validated_deployment.output
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_remote_draft_artifact_deploy_lifecycle -q
```

Expected: fail because command modules still use local-only context.

- [ ] **Step 3: Switch command imports**

In `src/wf_cli/commands/drafts.py`, `artifacts.py`, and `deployments.py`,
replace:

```python
from wf_cli.context import load_local_cli_context_from_typer as load_cli_context
```

with:

```python
from wf_cli.context import load_cli_context_from_typer as load_cli_context
```

Keep the local `load_cli_context` alias name so existing tests that monkeypatch
`wf_cli.commands.<module>.load_cli_context` keep working.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py tests/wf_cli/test_run_deploy.py tests/wf_cli/test_discovery_lifecycle.py -q
uv run basedpyright --level error src/wf_cli src/wf_transport_rpc_http
```

Expected: tests pass and basedpyright reports 0 errors.

---

## Task 5: Documentation and Verification

**Files:**

- Modify: `docs/superpowers/specs/2026-06-03-workflow-config-targets-and-sources.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update spec status**

Update the implementation status to say:

```markdown
- remote JSON-RPC client support now covers capability, draft workspace,
  artifact, deployment, and run CLI commands
- draft/artifact/deploy commands no longer fail fast for `rpc_http` targets
```

Remove or update the older local-only/fail-fast status line.

- [ ] **Step 2: Update roadmap**

Update the roadmap note to say the basic remote CLI lifecycle is wired:

```markdown
selected `wf` commands can target JSON-RPC HTTP
```

should become:

```markdown
the basic `wf` lifecycle can target JSON-RPC HTTP: capability discovery,
draft workspace authoring, artifact/deployment operations, run, inspect, and
bounded trace.
```

- [ ] **Step 3: Run focused verification**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http tests/wf_cli/test_remote_target.py tests/wf_cli/test_run_deploy.py tests/wf_cli/test_discovery_lifecycle.py -q
uv run ruff check src/wf_transport_rpc_http src/wf_cli tests/wf_transport_rpc_http tests/wf_cli
uv run ruff format --check src/wf_transport_rpc_http src/wf_cli tests/wf_transport_rpc_http tests/wf_cli
uv run basedpyright --level error src/wf_transport_rpc_http src/wf_cli tests/wf_transport_rpc_http tests/wf_cli
```

Expected: pass, except basedpyright may still exit non-zero for the known
workspace enumeration warning only when run at full workspace scope. For the
focused command above, expect 0 errors.

- [ ] **Step 4: Run full verification**

Run:

```bash
uv run pytest -q
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
```

Expected:

- pytest passes with current skip/xfail count
- ruff passes
- basedpyright reports `0 errors`; if it exits 1 only due to workspace
  enumeration warning, report that exactly

---

## Self-Review Notes

This plan intentionally adds server RPC methods before client methods and client
methods before CLI routing. That sequence prevents the previous half-migration
problem where commands could receive a partial client.

Do not remove old local tests or monkeypatch seams. The command modules can keep
a local import alias named `load_cli_context` for compatibility with existing
tests, but the imported helper should become target-aware after Task 4.

