# Draft Add Step From Capability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a focused draft helper that inserts one capability-backed step, optional route wiring, input bindings, and output-to-state schema/binding projection in one revision-checked operation.

**Architecture:** Build one API operation on `WorkflowDraftApi` that composes existing draft primitives without calling multiple revision-mutating helpers. The operation constructs one JSON Patch against the current draft, reuses existing binding payload helpers, and reuses `project_output_property_to_state_schema()` for `$defs` / `definitions` preservation. Expose the operation through WorkflowApi, JSON-RPC, RPC client, MCP workflow tool, CLI, docs, and skills.

**Tech Stack:** Python 3.14, Pydantic RPC DTOs, Typer CLI, existing `wf_api` draft service, existing JSON Patch draft workspace storage, pytest, ruff, basedpyright.

---

## Scope

This slice is explicit, not magic.

The helper **does**:

- Add `steps.<step_id>` with `{"use": capability_name, "input": [...], "output": [...]}`.
- Add `routes.<step_id>.<outcome> = target` for the new step.
- Optionally add `routes.<from_step>.<from_outcome> = step_id` to splice the step after an existing step.
- Accept repeated input bindings as `SOURCE=LOCAL_TARGET`, same direction as `wf draft set-input`.
- Accept repeated output-to-state bindings as `LOCAL_OUTPUT=STATE_TARGET`, and for each one:
  - copy that output property schema into `state_schema.properties.<field>`,
  - preserve local `$defs` / `definitions`,
  - add the step output binding `local.<output> -> state.<field>`.
- Return the normal updated workspace payload and diagnostics.

The helper **does not**:

- Guess missing inputs or outputs.
- Auto-wire top-level workflow output.
- Support non-capability/control steps.
- Hide validation. Agents should still run `wf draft validate <workspace_id>`.

CLI target shape:

```bash
wf draft add-step-from-capability <workspace_id> \
  --revision <n> \
  --step wait \
  --capability local.browser_click.wait_for_click \
  --from-step open \
  --from-outcome ok \
  --outcome ok \
  --to collect \
  --input state.session=session \
  --bind-output after=state.after
```

Terminology:

- `--from-step/--from-outcome`: optional incoming edge from an existing step to the new step.
- `--outcome/--to`: outgoing edge from the new step to another step or `__end__`.
- `--input SOURCE=LOCAL`: graph source to node-local input target.
- `--bind-output LOCAL=STATE`: node-local output field to state path, with schema projection.

---

## Files

- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_api/test_drafts_service.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`
- Test: `tests/wf_mcp/server/test_config.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`
- Modify docs/skills: `docs/wf_cli.md`, `skills/wf-cli/SKILL.md`, `skills/wf-workflow/references/draft-workspaces.md`, `skills/wf-workflow/references/workflow-lifecycle.md`, `docs/current_roadmap.md`

---

## Task 1: API Operation

**Files:**

- Modify: `src/wf_api/drafts.py`
- Test: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Write failing API test for adding a fully wired step**

Add this test near the existing draft helper tests in `tests/wf_api/test_drafts_service.py`:

```python
@pytest.mark.asyncio
async def test_add_step_from_capability_wires_route_inputs_and_state_outputs(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_add_step")
    api, service = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", echo_tool, _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    result = await api.add_step_from_capability(
        workspace_id="echo_ws",
        revision=1,
        step_id="snap",
        capability_name="demo.personal.snapshot_tool",
        route_from_step="echo",
        route_from_outcome="ok",
        route_outcome="ok",
        route_to="__end__",
        input_map={},
        bind_outputs={"after": "state.after"},
    )

    assert result["revision"] == 2
    assert result["status"] == "valid"
    draft = result["draft"]
    assert draft["steps"]["snap"]["use"] == "demo.personal.snapshot_tool"
    assert draft["routes"]["echo"]["ok"] == "snap"
    assert draft["routes"]["snap"]["ok"] == "__end__"
    assert draft["steps"]["snap"]["output"] == [
        {
            "source": {"root": "local", "parts": ["after"]},
            "target": {"root": "state", "parts": ["after"]},
        }
    ]
    assert draft["state_schema"]["properties"]["after"]["$ref"] == "#/$defs/_Snapshot"
    assert draft["state_schema"]["$defs"]["_Snapshot"]["properties"]["clicked"] == {
        "title": "Clicked",
        "type": "boolean",
    }
```

- [ ] **Step 2: Write failing API test for duplicate step rejection**

Add:

```python
@pytest.mark.asyncio
async def test_add_step_from_capability_rejects_existing_step_id(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_add_step_duplicate")
    api, _service = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(
        workspace_id="echo_ws",
        draft=_echo_draft(),
    )

    with pytest.raises(ValueError, match="draft step 'echo' already exists"):
        await api.add_step_from_capability(
            workspace_id="echo_ws",
            revision=1,
            step_id="echo",
            capability_name="demo.personal.echo_tool",
            route_from_step=None,
            route_from_outcome="ok",
            route_outcome="ok",
            route_to="__end__",
            input_map={},
            bind_outputs={},
        )
```

- [ ] **Step 3: Run failing API tests**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -q -k "add_step_from_capability"
```

Expected: fail because `WorkflowDraftApi.add_step_from_capability` does not exist.

- [ ] **Step 4: Implement API helper**

In `src/wf_api/drafts.py`, add this method to `WorkflowDraftApi` after `bind_output_to_state`:

```python
    async def add_step_from_capability(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        capability_name: str,
        route_from_step: str | None = None,
        route_from_outcome: str = DEFAULT_OK_OUTCOME,
        route_outcome: str = DEFAULT_OK_OUTCOME,
        route_to: str = "__end__",
        input_map: dict[str, str] | None = None,
        bind_outputs: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Add one capability step plus explicit route/map/schema wiring.

        This is a composed authoring helper for agents.  It edits the draft in
        one revision so callers do not have to interleave add-step, route,
        input-map, state-schema, and output-map operations by hand.
        """
        workspace = self._draft_store().get_workspace(workspace_id)
        steps = workspace.draft.get("steps")
        if not isinstance(steps, dict):
            raise ValueError("draft steps must be an object")
        if step_id in steps:
            raise ValueError(f"draft step {step_id!r} already exists")

        spec = self.context.specs.get_qualified_spec(capability_name)
        output_schema = (
            spec.output_schema_contract or spec.output_model.model_json_schema()
        )
        state_schema = workspace.draft.get("state_schema", {})
        if not isinstance(state_schema, dict):
            raise ValueError("draft state_schema must be an object")

        input_map = input_map or {}
        bind_outputs = bind_outputs or {}
        projected_state_schema = state_schema
        for output_field, state_path in bind_outputs.items():
            state_field = _state_root_field(state_path)
            projected_state_schema = project_output_property_to_state_schema(
                state_schema=projected_state_schema,
                output_schema=output_schema,
                output_field=output_field,
                state_field=state_field,
            )

        patch: list[dict[str, Any]] = [
            {
                "op": "add",
                "path": f"/steps/{_escape_json_pointer(step_id)}",
                "value": {
                    "use": capability_name,
                    "input": _draft_input_bindings_payload(input_map, {}),
                    "output": _draft_output_bindings_payload(bind_outputs),
                },
            },
            {
                "op": "add",
                "path": f"/routes/{_escape_json_pointer(step_id)}",
                "value": {route_outcome: route_to},
            },
        ]
        if projected_state_schema != state_schema:
            patch.insert(
                0,
                {
                    "op": "replace",
                    "path": "/state_schema",
                    "value": projected_state_schema,
                },
            )
        if route_from_step is not None:
            patch.append(
                {
                    "op": "add",
                    "path": (
                        f"/routes/{_escape_json_pointer(route_from_step)}/"
                        f"{_escape_json_pointer(route_from_outcome)}"
                    ),
                    "value": step_id,
                }
            )

        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )
```

- [ ] **Step 5: Run API tests**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -q -k "add_step_from_capability"
```

Expected: pass.

- [ ] **Step 6: Commit API task**

```bash
git add src/wf_api/drafts.py tests/wf_api/test_drafts_service.py
git commit -m "feat: add draft step capability helper"
```

---

## Task 2: API Surface, Facade, RPC, And Client

**Files:**

- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add failing RPC app test**

In `tests/wf_transport_rpc_http/test_app.py`, extend the existing focused draft edit test or add a new test near it:

```python
async def test_rpc_draft_workspace_add_step_from_capability(
    app_client,
    rpc_server,
) -> None:
    await app_client.post_json(
        method="workflow.draft_workspaces.create_from_capability",
        params={
            "workspace_id": "add_step_ws",
            "capability_name": "fixture.default.echo",
            "name": "add_step",
        },
    )

    response = await app_client.post_json(
        method="workflow.draft_workspaces.add_step_from_capability",
        params={
            "workspace_id": "add_step_ws",
            "revision": 1,
            "step_id": "second",
            "capability_name": "fixture.default.echo",
            "route_from_step": "call",
            "route_from_outcome": "ok",
            "route_outcome": "ok",
            "route_to": "__end__",
            "input_map": {"input.text": "text"},
            "bind_outputs": {"text": "state.second_text"},
        },
    )

    result = response["result"]
    assert result["revision"] == 2
    assert result["draft"]["steps"]["second"]["use"] == "fixture.default.echo"
    assert result["draft"]["routes"]["call"]["ok"] == "second"
    assert result["draft"]["routes"]["second"]["ok"] == "__end__"
```

Adjust fixture capability names only if this file uses a different fixture id; keep the assertion shape.

- [ ] **Step 2: Add failing RPC client test**

In `tests/wf_transport_rpc_http/test_client.py`, add near existing draft client tests:

```python
async def test_rpc_client_draft_workspace_add_step_from_capability(
    rpc_client,
) -> None:
    result = await rpc_client.add_step_from_capability(
        workspace_id="add_step_ws",
        revision=1,
        step_id="second",
        capability_name="fixture.default.echo",
        route_from_step="call",
        route_from_outcome="ok",
        route_outcome="ok",
        route_to="__end__",
        input_map={"input.text": "text"},
        bind_outputs={"text": "state.second_text"},
    )

    assert result["ok"] is True
```

If this test file uses a fake transport that records method names instead of returning real workspace data, assert that the recorded method is `workflow.draft_workspaces.add_step_from_capability` and the params contain `bind_outputs`.

- [ ] **Step 3: Run failing RPC tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q -k "add_step_from_capability"
```

Expected: fail because RPC DTO/method/client do not exist.

- [ ] **Step 4: Add surface and facade method**

In `src/wf_api/surface.py`, add to `WorkflowDraftSurface`:

```python
    async def add_step_from_capability(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        capability_name: str,
        route_from_step: str | None = None,
        route_from_outcome: str = "ok",
        route_outcome: str = "ok",
        route_to: str = "__end__",
        input_map: dict[str, str] | None = None,
        bind_outputs: dict[str, str] | None = None,
    ) -> dict[str, Any]: ...
```

In `src/wf_api/service.py`, add the delegate near other draft delegates:

```python
    async def add_step_from_capability(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        capability_name: str,
        route_from_step: str | None = None,
        route_from_outcome: str = "ok",
        route_outcome: str = "ok",
        route_to: str = "__end__",
        input_map: dict[str, str] | None = None,
        bind_outputs: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self.drafts.add_step_from_capability(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            capability_name=capability_name,
            route_from_step=route_from_step,
            route_from_outcome=route_from_outcome,
            route_outcome=route_outcome,
            route_to=route_to,
            input_map=input_map,
            bind_outputs=bind_outputs,
        )
```

- [ ] **Step 5: Add RPC DTO**

In `src/wf_transport_rpc_http/models.py`, add near `BindOutputToStateParams`:

```python
class AddStepFromCapabilityParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    capability_name: str = Field(min_length=1)
    route_from_step: str | None = None
    route_from_outcome: str = Field(default="ok", min_length=1)
    route_outcome: str = Field(default="ok", min_length=1)
    route_to: str = Field(default="__end__", min_length=1)
    input_map: dict[str, str] = Field(default_factory=dict)
    bind_outputs: dict[str, str] = Field(default_factory=dict)
```

Also export it from `src/wf_transport_rpc_http/__init__.py` if that file exports param models.

- [ ] **Step 6: Register RPC method**

In `src/wf_transport_rpc_http/methods/drafts.py`, import `AddStepFromCapabilityParams` and add:

```python
    @entrypoint.method(
        name="workflow.draft_workspaces.add_step_from_capability",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_add_step_from_capability(
        params: AddStepFromCapabilityParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.add_step_from_capability(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                capability_name=params.capability_name,
                route_from_step=params.route_from_step,
                route_from_outcome=params.route_from_outcome,
                route_outcome=params.route_outcome,
                route_to=params.route_to,
                input_map=params.input_map,
                bind_outputs=params.bind_outputs,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 7: Add RPC client method**

In `src/wf_transport_rpc_http/client/drafts.py`, add:

```python
    async def add_step_from_capability(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        capability_name: str,
        route_from_step: str | None = None,
        route_from_outcome: str = "ok",
        route_outcome: str = "ok",
        route_to: str = "__end__",
        input_map: dict[str, str] | None = None,
        bind_outputs: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "workflow.draft_workspaces.add_step_from_capability",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "capability_name": capability_name,
                "route_from_step": route_from_step,
                "route_from_outcome": route_from_outcome,
                "route_outcome": route_outcome,
                "route_to": route_to,
                "input_map": input_map or {},
                "bind_outputs": bind_outputs or {},
            },
        )
```

- [ ] **Step 8: Run RPC tests**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q -k "add_step_from_capability"
```

Expected: pass.

- [ ] **Step 9: Commit RPC task**

```bash
git add src/wf_api/surface.py src/wf_api/service.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py src/wf_transport_rpc_http/__init__.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
git commit -m "feat: expose draft add-step helper over rpc"
```

---

## Task 3: MCP Workflow Tool

**Files:**

- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Test: `tests/wf_mcp/server/test_config.py`

- [ ] **Step 1: Add failing MCP tool schema test**

In `tests/wf_mcp/server/test_config.py`, extend the workflow tool schema assertion:

```python
    assert "wf.workflow.add_step_from_capability" in tools_by_name
    add_step_schema = tools_by_name["wf.workflow.add_step_from_capability"][
        "inputSchema"
    ]
    request_schema = add_step_schema["properties"]["request"]
    assert "capability_name" in str(request_schema)
    assert "bind_outputs" in str(request_schema)
```

Keep the exact helper variables used in the existing test file.

- [ ] **Step 2: Run failing MCP test**

Run:

```bash
uv run pytest tests/wf_mcp/server/test_config.py -q -k "workflow"
```

Expected: fail because the tool is missing.

- [ ] **Step 3: Add MCP request model**

In `src/wf_mcp/workflow_surface/models.py`, add near other draft request models:

```python
class AddStepFromCapabilityRequest(BaseModel):
    workspace_id: str = Field(description="Draft workspace id.")
    revision: int = Field(ge=1, description="Expected workspace revision.")
    step_id: str = Field(description="New draft step id.")
    capability_name: str = Field(description="Qualified capability name.")
    route_from_step: str | None = Field(
        default=None,
        description="Optional existing step whose outcome should route to the new step.",
    )
    route_from_outcome: str = Field(
        default="ok",
        description="Outcome on route_from_step that should route to the new step.",
    )
    route_outcome: str = Field(
        default="ok",
        description="Outcome emitted by the new step.",
    )
    route_to: str = Field(
        default="__end__",
        description="Target step id or __end__ for the new step outcome.",
    )
    input_map: dict[str, str] = Field(
        default_factory=dict,
        description="Graph source path to node-local target field.",
    )
    bind_outputs: dict[str, str] = Field(
        default_factory=dict,
        description="Node-local output field to state path with schema projection.",
    )
```

- [ ] **Step 4: Register MCP tool**

In `src/wf_mcp/workflow_surface/tools.py`, import the request model and register:

```python
    @mcp.tool(
        name="wf.workflow.add_step_from_capability",
        description=(
            "Add one capability-backed draft step with explicit route, input, "
            "and output-to-state binding hints."
        ),
    )
    async def add_step_from_capability(
        request: AddStepFromCapabilityRequest,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult(
            result=await handlers.add_step_from_capability(
                workspace_id=request.workspace_id,
                revision=request.revision,
                step_id=request.step_id,
                capability_name=request.capability_name,
                route_from_step=request.route_from_step,
                route_from_outcome=request.route_from_outcome,
                route_outcome=request.route_outcome,
                route_to=request.route_to,
                input_map=request.input_map,
                bind_outputs=request.bind_outputs,
            )
        )
```

Use the exact result wrapper pattern already used by adjacent draft tools.

- [ ] **Step 5: Run MCP test**

Run:

```bash
uv run pytest tests/wf_mcp/server/test_config.py -q -k "workflow"
```

Expected: pass.

- [ ] **Step 6: Commit MCP task**

```bash
git add src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py tests/wf_mcp/server/test_config.py
git commit -m "feat: expose draft add-step helper to mcp"
```

---

## Task 4: CLI Command

**Files:**

- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add failing CLI help test**

In `tests/wf_cli/test_app.py`, add:

```python
def test_wf_draft_add_step_from_capability_help_explains_explicit_wiring(
    runner,
) -> None:
    result = runner.invoke(app, ["draft", "add-step-from-capability", "--help"])

    assert result.exit_code == 0
    assert "--from-step" in result.output
    assert "--bind-output" in result.output
    assert "does not guess" in result.output
```

Adjust fixture names if this file uses a different runner/app setup.

- [ ] **Step 2: Add failing CLI remote routing test**

In `tests/wf_cli/test_remote_target.py`, add near draft remote target tests:

```python
def test_wf_draft_add_step_from_capability_uses_rpc_target(
    cli_runner,
    remote_context,
) -> None:
    result = cli_runner.invoke(
        app,
        [
            "--rpc-url",
            remote_context.url,
            "draft",
            "add-step-from-capability",
            "add_step_ws",
            "--revision",
            "1",
            "--step",
            "second",
            "--capability",
            "fixture.default.echo",
            "--from-step",
            "call",
            "--from-outcome",
            "ok",
            "--outcome",
            "ok",
            "--to",
            "__end__",
            "--input",
            "input.text=text",
            "--bind-output",
            "text=state.second_text",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "second" in result.output
```

Adapt fixture names and expected output shape to this test file’s existing helper conventions.

- [ ] **Step 3: Run failing CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -k "add_step_from_capability"
```

Expected: fail because CLI command is missing.

- [ ] **Step 4: Add CLI command**

In `src/wf_cli/commands/drafts.py`, add after `bind_output_to_state`:

```python
@app.command("add-step-from-capability")
def add_step_from_capability(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="New draft step id.")],
    capability_name: Annotated[
        str, typer.Option("--capability", help="Qualified capability name.")
    ],
    route_from_step: Annotated[
        str | None,
        typer.Option(
            "--from-step",
            help="Optional existing step whose outcome should route to this step.",
        ),
    ] = None,
    route_from_outcome: Annotated[
        str,
        typer.Option("--from-outcome", help="Outcome on --from-step."),
    ] = "ok",
    route_outcome: Annotated[
        str,
        typer.Option("--outcome", help="Outcome emitted by the new step."),
    ] = "ok",
    route_to: Annotated[
        str,
        typer.Option("--to", help="Target step id or __end__ for the new step."),
    ] = "__end__",
    input_mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--input",
            help="Input binding SOURCE=LOCAL_TARGET. Repeat for multiple inputs.",
        ),
    ] = None,
    output_mapping: Annotated[
        list[str] | None,
        typer.Option(
            "--bind-output",
            help=(
                "Output binding LOCAL_OUTPUT=STATE_TARGET with state schema "
                "projection. Repeat for multiple outputs."
            ),
        ),
    ] = None,
) -> None:
    """Add one capability step with explicit route, input, and output wiring.

    This command does not guess missing maps. Pass the route and bindings you
    want, then run `wf draft validate <workspace_id>`.
    """
    input_map = _parse_map_flags(input_mapping)
    bind_outputs = _parse_map_flags(output_mapping)
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.add_step_from_capability(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                capability_name=capability_name,
                route_from_step=route_from_step,
                route_from_outcome=route_from_outcome,
                route_outcome=route_outcome,
                route_to=route_to,
                input_map=input_map,
                bind_outputs=bind_outputs,
            ),
        )
    )
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -k "add_step_from_capability"
```

Expected: pass.

- [ ] **Step 6: Commit CLI task**

```bash
git add src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
git commit -m "feat: add draft add-step cli"
```

---

## Task 5: Docs, Skills, Roadmap

**Files:**

- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update CLI docs**

In `docs/wf_cli.md`, add a short section near other draft focused helpers:

````markdown
### Add A Capability Step To A Draft

Use `wf draft add-step-from-capability` when adding a new capability-backed step
to an existing draft. The command is explicit: it does not guess missing maps.

```bash
wf draft add-step-from-capability report_ws \
  --revision 3 \
  --step render \
  --capability local.report.render_markdown_report \
  --from-step extract \
  --from-outcome ok \
  --outcome ok \
  --to __end__ \
  --input state.title=title \
  --bind-output markdown=state.markdown
```

Run `wf draft validate report_ws` after adding the step. If validation returns
a `repair_hint`, prefer the focused helper in that hint before JSON Patch.
````

- [ ] **Step 2: Update CLI skill**

In `skills/wf-cli/SKILL.md`, add a rule under draft workflow guidance:

```markdown
- To add a capability step, prefer `wf draft add-step-from-capability` over raw
  JSON Patch when the route, input bindings, and output-to-state bindings are
  known. It is explicit and does not guess missing maps.
```

- [ ] **Step 3: Update workflow draft reference**

In `skills/wf-workflow/references/draft-workspaces.md`, add the command to the focused helper list and CLI block:

```markdown
- `add_step_from_capability`
```

```bash
wf draft add-step-from-capability <workspace_id> --revision <n> --step <step_id> --capability <qualified_name> --from-step <prev> --from-outcome ok --outcome ok --to <next-or-__end__> --input input.text=text --bind-output result=state.result
```

Add this explanatory paragraph:

```markdown
Use `add-step-from-capability` when inserting a new capability step. It can set
the incoming edge, outgoing edge, input map, and output-to-state schema/binding
in one revision. It still requires explicit choices; if you do not know a map,
inspect the capability or run validation rather than guessing.
```

- [ ] **Step 4: Update workflow lifecycle skill**

In `skills/wf-workflow/references/workflow-lifecycle.md`, add after the draft patch/edit step:

```markdown
When adding a new capability-backed step, prefer:

```bash
wf draft add-step-from-capability ...
wf draft validate <workspace_id>
```

Use raw `wf draft patch` only when changing structure that no focused helper
covers.
```
```

Fix fence nesting if this lands inside another code block.

- [ ] **Step 5: Update roadmap**

In `docs/current_roadmap.md`, add under Priority 1 completed draft UX bullets:

```markdown
- Completed: `wf draft add-step-from-capability` inserts one explicit
  capability-backed step with route, input, and output-to-state schema/binding
  wiring in a single revision, reducing brittle JSON Patch authoring for
  multi-step workflows.
```

- [ ] **Step 6: Commit docs task**

```bash
git add docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md skills/wf-workflow/references/workflow-lifecycle.md docs/current_roadmap.md
git commit -m "docs: document draft add-step helper"
```

---

## Task 6: Final Verification

**Files:**

- All files changed above.

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py -q -k "add_step_from_capability or focused_edit or workflow"
```

Expected: all selected tests pass.

- [ ] **Step 2: Run ruff**

Run:

```bash
uv run ruff check src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py src/wf_transport_rpc_http/__init__.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Run format check**

Run:

```bash
uv run ruff format --check src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py src/wf_transport_rpc_http/__init__.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py
```

Expected: all files already formatted.

- [ ] **Step 4: Run typecheck**

Run:

```bash
uv run basedpyright --level error src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py src/wf_transport_rpc_http/__init__.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py
```

Expected: `0 errors, 0 warnings, 0 notes`.

- [ ] **Step 5: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. CRLF warnings on Windows are acceptable.

- [ ] **Step 6: Commit final verification note if docs changed after review**

Only if verification required doc fixes:

```bash
git add <changed-files>
git commit -m "fix: polish draft add-step helper docs"
```

---

## Self-Review Notes

- This plan covers API, facade, protocol, RPC, client, MCP, CLI, docs, skills, and roadmap.
- The helper is deliberately explicit and does not infer missing bindings.
- The operation edits the draft in one revision, avoiding revision conflicts caused by chaining multiple helper calls.
- Schema projection uses the existing `project_output_property_to_state_schema()` helper rather than hand-rolling JSON Schema reference handling.
- The command names avoid overloaded `after`; `--from-step` and `--to` mirror graph edge direction.
