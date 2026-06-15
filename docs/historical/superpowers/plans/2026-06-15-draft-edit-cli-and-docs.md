# Draft Edit CLI And Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose focused draft edit helpers through RPC/CLI, add `wf deploy create` as an alias for `wf deploy save`, and document draft vs raw-plan authoring shapes clearly.

**Architecture:** `WorkflowApi` already has focused draft helper methods (`set_draft_name`, `set_draft_route`, `set_step_input_map`, `set_step_output_map`). This plan projects those methods through the transport-facing `WorkflowDraftSurface`, JSON-RPC, and CLI, then updates docs/skills so agents understand the two authoring formats: draft workspaces (`steps/routes/use`) and raw plans (`nodes/edges/node`). `deploy create` is only an alias; `deploy save` remains canonical.

**Tech Stack:** Python 3.14, Typer, FastAPI JSON-RPC, Pydantic, pytest, basedpyright, ruff.

---

## File Structure

- Modify `src/wf_api/surface.py`: add focused draft helper methods to the transport-facing protocol.
- Modify `src/wf_transport_rpc_http/models.py`: add RPC parameter models for focused draft edits.
- Modify `src/wf_transport_rpc_http/methods/drafts.py`: register JSON-RPC methods.
- Modify `src/wf_transport_rpc_http/client/drafts.py`: add RPC client methods.
- Modify `src/wf_cli/commands/drafts.py`: add `set-name`, `set-route`, `set-input`, and `set-output`.
- Modify `src/wf_cli/commands/deployments.py`: add `create` alias for existing deployment save logic.
- Modify tests under `tests/wf_transport_rpc_http/` and `tests/wf_cli/`.
- Modify docs: `docs/wf_cli.md`, `docs/workflow_drafts.md`, `docs/workflow_artifacts.md`, `skills/wf-cli/SKILL.md`, `skills/wf-workflow/SKILL.md`, `skills/wf-workflow/references/workflow-lifecycle.md`, `skills/wf-workflow/references/draft-workspaces.md`, and `examples/agent_challenges/browser_click_challenge/prompt.md`.

---

### Task 1: Expose Focused Draft Edit Helpers Through RPC

**Files:**
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add RPC app tests first**

Add this test to `tests/wf_transport_rpc_http/test_app.py` near existing draft workspace tests:

```python
async def test_rpc_draft_workspace_focused_edit_methods(client) -> None:
    created = await _rpc(
        client,
        "workflow.draft_workspaces.create_from_capability",
        {
            "workspace_id": "focused_ws",
            "capability_name": "wf.std.constant",
            "name": "focused_initial",
        },
    )
    assert created["result"]["workspace_id"] == "focused_ws"

    named = await _rpc(
        client,
        "workflow.draft_workspaces.set_name",
        {
            "workspace_id": "focused_ws",
            "revision": 1,
            "name": "focused_renamed",
        },
    )
    routed = await _rpc(
        client,
        "workflow.draft_workspaces.set_route",
        {
            "workspace_id": "focused_ws",
            "revision": 2,
            "step_id": "call",
            "outcome": "ok",
            "target": "__end__",
        },
    )
    input_mapped = await _rpc(
        client,
        "workflow.draft_workspaces.set_step_input_map",
        {
            "workspace_id": "focused_ws",
            "revision": 3,
            "step_id": "call",
            "input_map": {"input.value": "value"},
        },
    )
    output_mapped = await _rpc(
        client,
        "workflow.draft_workspaces.set_step_output_map",
        {
            "workspace_id": "focused_ws",
            "revision": 4,
            "step_id": "call",
            "output_map": {"value": "state.value"},
        },
    )
    fetched = await _rpc(
        client,
        "workflow.draft_workspaces.get",
        {"workspace_id": "focused_ws", "include_draft": True},
    )

    assert named["result"]["revision"] == 2
    assert routed["result"]["revision"] == 3
    assert input_mapped["result"]["revision"] == 4
    assert output_mapped["result"]["revision"] == 5
    draft = fetched["result"]["draft"]
    assert draft["name"] == "focused_renamed"
    assert draft["routes"]["call"]["ok"] == "__end__"
    assert draft["steps"]["call"]["input"] == [
        {
            "target": {"root": "local", "parts": ["value"]},
            "path": {"root": "input", "parts": ["value"]},
        }
    ]
    assert draft["steps"]["call"]["output"] == [
        {
            "source": {"root": "local", "parts": ["value"]},
            "target": {"root": "state", "parts": ["value"]},
        }
    ]
```

- [ ] **Step 2: Add RPC client tests first**

Add this test to `tests/wf_transport_rpc_http/test_client.py` near existing draft client tests:

```python
async def test_rpc_client_draft_workspace_focused_edit_methods(client) -> None:
    await client.create_draft_workspace_from_capability(
        workspace_id="client_focused_ws",
        capability_name="wf.std.constant",
        name="client_initial",
    )

    named = await client.set_draft_name(
        workspace_id="client_focused_ws",
        revision=1,
        name="client_renamed",
    )
    routed = await client.set_draft_route(
        workspace_id="client_focused_ws",
        revision=2,
        step_id="call",
        outcome="ok",
        target="__end__",
    )
    input_mapped = await client.set_step_input_map(
        workspace_id="client_focused_ws",
        revision=3,
        step_id="call",
        input_map={"input.value": "value"},
    )
    output_mapped = await client.set_step_output_map(
        workspace_id="client_focused_ws",
        revision=4,
        step_id="call",
        output_map={"value": "state.value"},
    )

    assert named["revision"] == 2
    assert routed["revision"] == 3
    assert input_mapped["revision"] == 4
    assert output_mapped["revision"] == 5
```

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_draft_workspace_focused_edit_methods tests/wf_transport_rpc_http/test_client.py::test_rpc_client_draft_workspace_focused_edit_methods -q
```

Expected: FAIL because RPC methods/client methods do not exist.

- [ ] **Step 4: Add focused edit methods to `WorkflowDraftSurface`**

In `src/wf_api/surface.py`, add these methods after `patch_draft_workspace`:

```python
    async def set_draft_name(
        self,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> dict[str, Any]: ...

    async def set_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> dict[str, Any]: ...

    async def set_step_input_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]: ...

    async def set_step_output_map(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]: ...
```

- [ ] **Step 5: Add RPC params**

In `src/wf_transport_rpc_http/models.py`, add these classes after `PatchDraftWorkspaceParams`:

```python
class SetDraftNameParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    name: str = Field(min_length=1)


class SetDraftRouteParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    target: str = Field(min_length=1)


class SetStepInputMapParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    input_map: dict[str, str]


class SetStepOutputMapParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    output_map: dict[str, str]
```

Also add these classes to the `from .models import (...)` block and `__all__` in `src/wf_transport_rpc_http/__init__.py`:

```python
SetDraftNameParams,
SetDraftRouteParams,
SetStepInputMapParams,
SetStepOutputMapParams,
```

- [ ] **Step 6: Register RPC methods**

In `src/wf_transport_rpc_http/methods/drafts.py`, import the new params and register methods after `workflow_draft_workspaces_patch`:

```python
    @entrypoint.method(
        name="workflow.draft_workspaces.set_name", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_set_name(
        params: SetDraftNameParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.set_draft_name(
                workspace_id=params.workspace_id,
                revision=params.revision,
                name=params.name,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.set_route", errors=[WorkflowRpcError]
    )
    async def workflow_draft_workspaces_set_route(
        params: SetDraftRouteParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.set_draft_route(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                outcome=params.outcome,
                target=params.target,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.set_step_input_map",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_set_step_input_map(
        params: SetStepInputMapParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.set_step_input_map(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                input_map=params.input_map,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)

    @entrypoint.method(
        name="workflow.draft_workspaces.set_step_output_map",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_set_step_output_map(
        params: SetStepOutputMapParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.set_step_output_map(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                output_map=params.output_map,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 7: Add RPC client methods**

In `src/wf_transport_rpc_http/client/drafts.py`, add methods after `patch_draft_workspace`:

```python
    async def set_draft_name(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        name: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_name",
            {"workspace_id": workspace_id, "revision": revision, "name": name},
        )

    async def set_draft_route(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
        target: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_route",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "outcome": outcome,
                "target": target,
            },
        )

    async def set_step_input_map(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        input_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_step_input_map",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "input_map": input_map,
            },
        )

    async def set_step_output_map(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_map: dict[str, str],
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.set_step_output_map",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "output_map": output_map,
            },
        )
```

- [ ] **Step 8: Run focused RPC tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_draft_workspace_focused_edit_methods tests/wf_transport_rpc_http/test_client.py::test_rpc_client_draft_workspace_focused_edit_methods -q
```

Expected: PASS.

- [ ] **Step 9: Commit RPC surface**

```bash
git add src/wf_api/surface.py src/wf_transport_rpc_http tests/wf_transport_rpc_http
git commit -m "feat: expose focused draft edits over rpc"
```

---

### Task 2: Add CLI Focused Draft Edit Commands And Deploy Alias

**Files:**
- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `src/wf_cli/commands/deployments.py`
- Test: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add CLI tests first**

Add this test to `tests/wf_cli/test_remote_target.py` near the existing remote draft lifecycle test:

```python
def test_wf_draft_focused_edit_commands_use_rpc_target(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()
    base_args = ["--config", str(config_path), "--url", "http://test/rpc"]

    created = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "create-from-capability",
            "focused_ws",
            "wf.std.constant",
            "--name",
            "focused_initial",
        ],
    )
    assert created.exit_code == 0, created.output

    named = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "set-name",
            "focused_ws",
            "--revision",
            "1",
            "--name",
            "focused_renamed",
        ],
    )
    routed = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "set-route",
            "focused_ws",
            "--revision",
            "2",
            "--step",
            "call",
            "--outcome",
            "ok",
            "--to",
            "__end__",
        ],
    )
    input_mapped = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "set-input",
            "focused_ws",
            "--revision",
            "3",
            "--step",
            "call",
            "--map",
            "input.value=value",
        ],
    )
    output_mapped = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "set-output",
            "focused_ws",
            "--revision",
            "4",
            "--step",
            "call",
            "--map",
            "value=state.value",
        ],
    )
    inspected = runner.invoke(
        app,
        [*base_args, "draft", "inspect", "focused_ws", "--include-draft"],
    )

    assert named.exit_code == 0, named.output
    assert routed.exit_code == 0, routed.output
    assert input_mapped.exit_code == 0, input_mapped.output
    assert output_mapped.exit_code == 0, output_mapped.output
    assert inspected.exit_code == 0, inspected.output
    payload = json.loads(inspected.output)
    draft = payload["draft"]
    assert draft["name"] == "focused_renamed"
    assert draft["routes"]["call"]["ok"] == "__end__"
    assert draft["steps"]["call"]["input"] == [
        {
            "target": {"root": "local", "parts": ["value"]},
            "path": {"root": "input", "parts": ["value"]},
        }
    ]
    assert draft["steps"]["call"]["output"] == [
        {
            "source": {"root": "local", "parts": ["value"]},
            "target": {"root": "state", "parts": ["value"]},
        }
    ]
```

Add this deploy alias test near deployment CLI tests:

```python
def test_wf_deploy_create_alias_saves_deployment(monkeypatch, tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    asyncio.run(
        server.api.create_artifact_from_plan(
            artifact_id="alias_artifact",
            version=1,
            title="Alias Artifact",
            plan=_constant_plan(),
            outcomes=("ok",),
        )
    )
    _patch_rpc_client_to_server(monkeypatch, server)
    config_path = tmp_path / "wf.json"
    config_path.write_text('{"version": 1}', encoding="utf-8")
    runner = CliRunner()

    created = runner.invoke(
        app,
        [
            "--config",
            str(config_path),
            "--url",
            "http://test/rpc",
            "deploy",
            "create",
            "alias_artifact.default",
            "--artifact",
            "alias_artifact",
            "--version",
            "1",
        ],
    )

    assert created.exit_code == 0, created.output
    payload = json.loads(created.output)
    assert payload["deployment_id"] == "alias_artifact.default"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_draft_focused_edit_commands_use_rpc_target tests/wf_cli/test_remote_target.py::test_wf_deploy_create_alias_saves_deployment -q
```

Expected: FAIL because commands do not exist.

- [ ] **Step 3: Add map parsing helper**

In `src/wf_cli/commands/drafts.py`, add a private helper near the existing command helpers. Do not reuse `parse_bindings` here: invalid `--map` input should mention `--map`, not `--binding`.

```python
def _parse_map_flags(values: list[str] | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values or []:
        source, separator, target = item.partition("=")
        if separator != "=" or not source or not target:
            raise typer.BadParameter("--map must use source=target")
        if source in parsed:
            raise typer.BadParameter(f"duplicate --map for {source!r}")
        parsed[source] = target
    return parsed
```

- [ ] **Step 4: Add focused draft commands**

In `src/wf_cli/commands/drafts.py`, add these commands after `patch_draft()`:

```python
@app.command("set-name")
def set_draft_name(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    name: Annotated[str, typer.Option("--name", help="New draft workflow name.")],
) -> None:
    """Set the draft workflow name without writing JSON Patch manually."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_draft_name(
                workspace_id=workspace_id,
                revision=revision,
                name=name,
            ),
        )
    )


@app.command("set-route")
def set_draft_route(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    outcome: Annotated[str, typer.Option("--outcome", help="Step outcome.")],
    target: Annotated[
        str, typer.Option("--to", help="Target step id or __end__.")
    ],
) -> None:
    """Set one route: steps.<step> outcome -> target."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_draft_route(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                outcome=outcome,
                target=target,
            ),
        )
    )


@app.command("set-input")
def set_step_input_map(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--map",
            help="Input binding SOURCE=LOCAL_TARGET. Repeatable. Example: input.text=text",
        ),
    ] = None,
) -> None:
    """Replace one step's input map without writing JSON Patch manually."""
    input_map = _parse_map_flags(mapping)
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_step_input_map(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                input_map=input_map,
            ),
        )
    )


@app.command("set-output")
def set_step_output_map(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--map",
            help="Output binding LOCAL_SOURCE=STATE_TARGET. Repeatable. Example: text=state.text",
        ),
    ] = None,
) -> None:
    """Replace one step's output map without writing JSON Patch manually."""
    output_map = _parse_map_flags(mapping)
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.set_step_output_map(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                output_map=output_map,
            ),
        )
    )
```

- [ ] **Step 5: Add deployment alias without duplicating implementation**

In `src/wf_cli/commands/deployments.py`, extract the save implementation into a helper:

```python
def _save_deployment_command(
    ctx: typer.Context,
    *,
    deployment_id: str | None,
    artifact_id: str | None,
    version: int | None,
    binding: list[str] | None,
    input_json: str | None,
    input_file: Path | None,
) -> None:
    try:
        if input_json is not None or input_file is not None:
            payload = parse_json_input(input_json=input_json, input_file=input_file)
        else:
            payload = _deployment_payload_from_flags(
                deployment_id=deployment_id,
                artifact_id=artifact_id,
                version=version,
                bindings=binding or [],
            )
    except CliInputError as exc:
        raise typer.BadParameter(str(exc)) from exc
    context = load_cli_context(ctx)
    emit_json(run_cli_operation(context, context.handlers.save_deployment(payload)))
```

Then make existing `save_deployment()` call `_save_deployment_command(...)`.

Add alias command after `save_deployment()`:

```python
@app.command("create")
def create_deployment(
    ctx: typer.Context,
    deployment_id: Annotated[str | None, typer.Argument(help="Deployment id.")] = None,
    artifact_id: Annotated[
        str | None, typer.Option("--artifact", help="Artifact id.")
    ] = None,
    version: Annotated[
        int | None, typer.Option("--version", min=1, help="Artifact version.")
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option("--binding", help="Logical=concrete source binding. Repeatable."),
    ] = None,
    input_json: Annotated[
        str | None, typer.Option("--input", help="Full deployment JSON object.")
    ] = None,
    input_file: Annotated[
        Path | None,
        typer.Option("--input-file", help="Path to full deployment JSON object."),
    ] = None,
) -> None:
    """Alias for `deploy save`; creates or updates a deployment record."""
    _save_deployment_command(
        ctx,
        deployment_id=deployment_id,
        artifact_id=artifact_id,
        version=version,
        binding=binding,
        input_json=input_json,
        input_file=input_file,
    )
```

- [ ] **Step 6: Run focused CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_draft_focused_edit_commands_use_rpc_target tests/wf_cli/test_remote_target.py::test_wf_deploy_create_alias_saves_deployment -q
```

Expected: PASS.

- [ ] **Step 7: Commit CLI changes**

```bash
git add src/wf_cli/commands/drafts.py src/wf_cli/commands/deployments.py tests/wf_cli/test_remote_target.py
git commit -m "feat: add focused draft cli edits"
```

---

### Task 3: Documentation, Skills, And Challenge Prompt

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/workflow_drafts.md`
- Modify: `docs/workflow_artifacts.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/SKILL.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `examples/agent_challenges/browser_click_challenge/prompt.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update `docs/wf_cli.md` draft commands**

In the Draft Workspaces section, after `wf draft patch`, add:

```markdown
Focused draft edit commands cover common graph edits without writing RFC 6902
patches directly:

```bash
wf draft set-name concat_ws --revision 1 --name concat_ws_v2
wf draft set-route concat_ws --revision 2 --step call --outcome ok --to __end__
wf draft set-input concat_ws --revision 3 --step call --map input.items=items --map input.separator=separator
wf draft set-output concat_ws --revision 4 --step call --map value=state.value
```

`set-input` maps graph source paths to node-local input fields:
`input.text=text` means `input.text -> local.text`.

`set-output` maps node-local output fields to workflow state paths:
`text=state.text` means `local.text -> state.text`.
```

In the Deployments section, add:

```markdown
`wf deploy create` is accepted as an alias for `wf deploy save`; docs use
`save` as the canonical verb because deployments are mutable records.
```

In the Artifacts section near `artifact create-from-plan`, add:

```markdown
`artifact create-from-plan` expects the raw workflow plan shape (`nodes`,
`edges`, `node`). It does not accept draft workspace shape (`steps`, `routes`,
`use`).
```

- [ ] **Step 2: Update `docs/workflow_drafts.md`**

Add a section after "Workspace Flow":

```markdown
## Focused Edit Commands

For routine edits, prefer focused commands over hand-written JSON Patch:

```bash
wf draft set-name <workspace_id> --revision <n> --name <name>
wf draft set-route <workspace_id> --revision <n> --step <step_id> --outcome ok --to <target_step_or___end__>
wf draft set-input <workspace_id> --revision <n> --step <step_id> --map input.text=text
wf draft set-output <workspace_id> --revision <n> --step <step_id> --map text=state.text
```

Use `draft patch` when these focused commands do not cover the structural edit.
```

Add a short warning:

```markdown
Drafts are not raw workflow plans. Drafts use `steps`, `routes`, and step field
`use`. Raw plans use `nodes`, `edges`, and node field `node`.
```

- [ ] **Step 3: Update `docs/workflow_artifacts.md`**

Add a subsection near raw artifact creation concepts:

```markdown
### Raw Plan Import

`wf artifact create-from-plan` imports a complete raw workflow plan. This is an
advanced/compiler path, not the interactive draft authoring path.

Raw plans use execution-model fields such as:

- `nodes`
- `edges`
- node field `node`

Draft workspaces use authoring fields such as:

- `steps`
- `routes`
- step field `use`

Do not pass draft JSON to `artifact create-from-plan`; save drafts with
`wf draft save`.
```

- [ ] **Step 4: Update skills**

In `skills/wf-cli/SKILL.md`, add commands to Core Commands:

```bash
wf draft set-name <workspace_id> --revision <n> --name <name>
wf draft set-route <workspace_id> --revision <n> --step <step_id> --outcome <outcome> --to <target>
wf draft set-input <workspace_id> --revision <n> --step <step_id> --map input.text=text
wf draft set-output <workspace_id> --revision <n> --step <step_id> --map text=state.text
wf deploy create <deployment_id> --artifact <artifact_id> --version <n>
```

Add rule:

```markdown
- Do not confuse draft shape with raw plan shape: drafts use `steps/routes/use`;
  raw plans use `nodes/edges/node`.
```

In `skills/wf-workflow/SKILL.md`, add:

```markdown
- Prefer focused draft edit commands before hand-writing JSON Patch.
- Use `artifact create-from-plan` only for complete raw plans; do not pass draft
  JSON to it.
```

In `skills/wf-workflow/references/workflow-lifecycle.md`, add focused draft commands in the primary path and add the same draft-vs-raw warning.

In `skills/wf-workflow/references/draft-workspaces.md`, add the focused command examples and map direction notes.

- [ ] **Step 5: Update challenge prompt**

In `examples/agent_challenges/browser_click_challenge/prompt.md`, replace the acceptable authoring path text with:

```markdown
Two product-facing authoring paths are acceptable:

- draft path: create a draft from one capability, use focused draft edit
  commands or your own RFC 6902 JSON Patch, then validate/save/deploy/run it;
- raw-plan path: write your own complete raw workflow plan file and use
  `wf artifact create-from-plan` before deploy/run.

Do not mix the formats. Drafts use `steps`, `routes`, and step field `use`.
Raw plans use `nodes`, `edges`, and node field `node`. Do not pass draft JSON to
`wf artifact create-from-plan`.

The deployment command is `wf deploy save`; `wf deploy create` is accepted as an
alias.
```

- [ ] **Step 6: Update roadmap**

In `docs/current_roadmap.md`, add:

```markdown
- Completed: focused draft edit helpers are exposed through RPC/CLI, and
  `wf deploy create` is accepted as an alias for `wf deploy save`. Docs now
  distinguish draft shape from raw plan shape for agent authoring.
```

- [ ] **Step 7: Run docs tests**

Run:

```bash
uv run pytest tests/docs -q
```

Expected: PASS.

- [ ] **Step 8: Commit docs**

```bash
git add docs skills examples/agent_challenges/browser_click_challenge/prompt.md
git commit -m "docs: clarify draft and raw plan authoring paths"
```

---

### Task 4: Final Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run focused suites**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py tests/docs -q
```

Expected: PASS.

- [ ] **Step 2: Run lint**

Run:

```bash
uv run ruff check src/wf_api/surface.py src/wf_transport_rpc_http src/wf_cli/commands/drafts.py src/wf_cli/commands/deployments.py tests/wf_transport_rpc_http tests/wf_cli/test_remote_target.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_api/surface.py src/wf_transport_rpc_http src/wf_cli/commands/drafts.py src/wf_cli/commands/deployments.py tests/wf_transport_rpc_http tests/wf_cli/test_remote_target.py
```

Expected: 0 errors.

- [ ] **Step 4: Check workspace**

Run:

```bash
git status --short
git diff --check
```

Expected: only intentional changes before final commit; no whitespace errors.

---

## Self-Review

- Spec coverage: Covers focused draft CLI helpers, deploy alias, and docs explaining draft vs raw plan shape.
- Placeholder scan: No placeholder steps remain.
- Type consistency: Uses existing `WorkflowApi` method names and established JSON-RPC naming under `workflow.draft_workspaces.*`. CLI map direction matches existing `input_map`/`output_map` tests in `tests/wf_api/test_drafts_service.py`.
