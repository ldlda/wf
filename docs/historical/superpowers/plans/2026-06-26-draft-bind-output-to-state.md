# Draft Bind Output To State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one focused draft operation that binds a step output to a root state field and declares the matching state schema in the same revision-checked edit.

**Architecture:** Compose existing draft primitives instead of adding new schema semantics. The helper should reuse `project_output_property_to_state_schema()` for schema projection and `_draft_output_bindings_payload()` for output-map serialization, then patch `/state_schema` and `/steps/<step>/output` together. Route editing already exists as `set-route`; this slice deliberately does not infer or mutate routes.

**Tech Stack:** Python 3.14, existing draft workspace API, existing JSON Schema projection helper backed by `jsonschema`, Typer CLI, JSON-RPC transport, FastMCP workflow tools, pytest, ruff, basedpyright.

---

## Product Shape

Add this command:

```powershell
wf draft bind-output-to-state <workspace_id> `
  --revision <n> `
  --step <step_id> `
  --output <output_field> `
  --state state.<field>
```

Example:

```powershell
wf draft bind-output-to-state browser_ws `
  --revision 5 `
  --step wait `
  --output after `
  --state state.after
```

Behavior:

1. Read the draft step named by `--step`.
2. Read that step's `use` capability.
3. Find the top-level capability output field named by `--output`.
4. Project that output field schema into `draft.state_schema.properties.<field>`.
5. Preserve existing output bindings for the step.
6. Add or update the output binding `local.<output_field> -> state.<field>`.
7. Patch state schema and step output map in one workspace revision.

Non-goals:

- Do not infer routes. Use existing `wf draft set-route`.
- Do not add steps. That is a later `add-step-from-capability` style helper.
- Do not support nested destination fields such as `state.after.clicked`.
- Do not implement JSON Schema resolving. Reuse `project_output_property_to_state_schema()`.

## Files

- Modify: `src/wf_api/drafts.py`
  - Add `WorkflowDraftApi.bind_output_to_state`.
- Modify: `src/wf_api/service.py`
  - Add facade delegate.
- Modify: `src/wf_api/surface.py`
  - Add method to `WorkflowDraftSurface`.
- Modify: `src/wf_transport_rpc_http/models.py`
  - Add `BindOutputToStateParams`.
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
  - Register `workflow.draft_workspaces.bind_output_to_state`.
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
  - Add RPC client method.
- Modify: `src/wf_mcp/workflow_surface/models.py`
  - Add `BindOutputToStateRequest`.
- Modify: `src/wf_mcp/workflow_surface/tools.py`
  - Register `wf.workflow.bind_output_to_state`.
- Modify: `src/wf_cli/commands/drafts.py`
  - Add `wf draft bind-output-to-state`.
- Modify docs/skills:
  - `docs/wf_cli.md`
  - `skills/wf-cli/SKILL.md`
  - `skills/wf-workflow/references/draft-workspaces.md`
  - `skills/wf-workflow/references/workflow-lifecycle.md`
  - `docs/current_roadmap.md`
- Tests:
  - `tests/wf_api/test_drafts_service.py`
  - `tests/wf_transport_rpc_http/test_app.py`
  - `tests/wf_transport_rpc_http/test_client.py`
  - `tests/wf_cli/test_app.py`
  - `tests/wf_cli/test_remote_target.py`
  - `tests/wf_mcp/server/test_config.py`

---

## Task 1: API Helper

**Files:**

- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Write failing API tests**

In `tests/wf_api/test_drafts_service.py`, add these tests after `test_add_state_schema_from_output_rejects_nested_state_path`:

```python
@pytest.mark.asyncio
async def test_bind_output_to_state_projects_schema_and_merges_output_map(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_output_state")
    api, service = _draft_api(artifact_store)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="snapshot_ws",
        draft={
            "name": "snapshot",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {
                "type": "object",
                "properties": {"before": {"type": "object"}},
            },
            "output_schema": {"type": "object", "properties": {}},
            "start": "snap",
            "steps": {
                "snap": {
                    "use": "demo.personal.snapshot_tool",
                    "input": [],
                    "output": [
                        {
                            "source": {"root": "local", "parts": ["before"]},
                            "target": {"root": "state", "parts": ["before"]},
                        }
                    ],
                }
            },
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    updated = await api.bind_output_to_state(
        workspace_id="snapshot_ws",
        revision=1,
        step_id="snap",
        output_field="after",
        state_path="state.after",
    )
    fetched = await api.get_draft_workspace(
        workspace_id="snapshot_ws",
        include_draft=True,
    )

    draft = fetched["draft"]
    assert updated["revision"] == 2
    assert draft["state_schema"]["properties"]["after"]["$ref"] == "#/$defs/_Snapshot"
    assert draft["state_schema"]["$defs"]["_Snapshot"]["properties"]["clicked"] == {
        "title": "Clicked",
        "type": "boolean",
    }
    assert draft["steps"]["snap"]["output"] == [
        {
            "source": {"root": "local", "parts": ["before"]},
            "target": {"root": "state", "parts": ["before"]},
        },
        {
            "source": {"root": "local", "parts": ["after"]},
            "target": {"root": "state", "parts": ["after"]},
        },
    ]


@pytest.mark.asyncio
async def test_bind_output_to_state_rejects_nested_state_path(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_nested_state")
    api, service = _draft_api(artifact_store)
    service.register_connection(
        ConnectionConfig(id="demo.personal", server="demo", account="personal")
    )
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="snapshot_ws",
        draft={
            "name": "snapshot",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "snap",
            "steps": {
                "snap": {
                    "use": "demo.personal.snapshot_tool",
                    "input": [],
                    "output": [],
                }
            },
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    with pytest.raises(ValueError, match="state_path must name one root field"):
        await api.bind_output_to_state(
            workspace_id="snapshot_ws",
            revision=1,
            step_id="snap",
            output_field="after",
            state_path="state.after.clicked",
        )
```

- [ ] **Step 2: Run API tests to verify red**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "bind_output_to_state"
```

Expected: failure because `WorkflowDraftApi.bind_output_to_state` does not exist.

- [ ] **Step 3: Implement `WorkflowDraftApi.bind_output_to_state`**

In `src/wf_api/drafts.py`, add this method immediately after `add_state_schema_from_output`:

```python
    async def bind_output_to_state(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        """Declare a state field from a step output and bind that output to it.

        This is the common draft-authoring repair for validation errors where a
        step writes to ``state.x`` before ``state_schema.properties.x`` exists.
        It deliberately edits only one root state field and one step output map.
        Route changes remain explicit through ``set_draft_route``.
        """
        workspace = self._draft_store().get_workspace(workspace_id)
        step = _draft_step(workspace.draft, step_id)
        capability_name = step.get("use")
        if not isinstance(capability_name, str) or not capability_name:
            raise ValueError(
                f"draft step {step_id!r} does not declare a capability use"
            )

        state_field = _state_root_field(state_path)
        spec = self.context.specs.get_qualified_spec(capability_name)
        output_schema = (
            spec.output_schema_contract or spec.output_model.model_json_schema()
        )
        state_schema = workspace.draft.get("state_schema", {})
        if not isinstance(state_schema, dict):
            raise ValueError("draft state_schema must be an object")
        projected = project_output_property_to_state_schema(
            state_schema=state_schema,
            output_schema=output_schema,
            output_field=output_field,
            state_field=state_field,
        )
        output_map = {
            **self._step_output_map(workspace_id=workspace_id, step_id=step_id),
            output_field: state_path,
        }
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": "/state_schema",
                    "value": projected,
                },
                {
                    "op": "replace",
                    "path": f"/steps/{_escape_json_pointer(step_id)}/output",
                    "value": _draft_output_bindings_payload(output_map),
                },
            ],
        )
```

- [ ] **Step 4: Add facade and protocol methods**

In `src/wf_api/service.py`, add this method immediately after `add_state_schema_from_output`:

```python
    async def bind_output_to_state(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        return await self.drafts.bind_output_to_state(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            output_field=output_field,
            state_path=state_path,
        )
```

In `src/wf_api/surface.py`, add this protocol method immediately after `add_state_schema_from_output`:

```python
    async def bind_output_to_state(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]: ...
```

- [ ] **Step 5: Run API tests to verify green**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "bind_output_to_state or add_state_schema_from_output"
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py tests/wf_api/test_drafts_service.py
git commit -m "feat: bind draft outputs to state"
```

---

## Task 2: RPC Client And Server Surface

**Files:**

- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add failing RPC tests**

In `tests/wf_transport_rpc_http/test_app.py`, extend the existing draft focused-edit test that asserts `"workflow.draft_workspaces.add_state_from_output"` with a second RPC call:

```python
        state_bound = await client.request(
            "workflow.draft_workspaces.bind_output_to_state",
            {
                "workspace_id": workspace_id,
                "revision": state_added["result"]["revision"],
                "step_id": "snap",
                "output_field": "after",
                "state_path": "state.after",
            },
        )
        assert state_bound["result"]["revision"] == state_added["result"]["revision"] + 1
```

If the file does not already have a suitable `snapshot` draft fixture, add a focused test that mirrors `test_rpc_draft_workspace_focused_edit_methods` and uses the existing helper style in that file.

In `tests/wf_transport_rpc_http/test_client.py`, add this assertion beside the existing `client.add_state_schema_from_output(...)` test:

```python
        state_bound = await client.bind_output_to_state(
            workspace_id=workspace_id,
            revision=state_added["revision"],
            step_id="snap",
            output_field="after",
            state_path="state.after",
        )
        assert state_bound["revision"] == state_added["revision"] + 1
```

- [ ] **Step 2: Run RPC tests to verify red**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q -k "bind_output_to_state or add_state_from_output"
```

Expected: failures because RPC params, method, and client method do not exist.

- [ ] **Step 3: Add RPC params**

In `src/wf_transport_rpc_http/models.py`, add after `AddStateFromOutputParams`:

```python
class BindOutputToStateParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    output_field: str = Field(min_length=1)
    state_path: str = Field(min_length=1)
```

- [ ] **Step 4: Register RPC method**

In `src/wf_transport_rpc_http/methods/drafts.py`, import `BindOutputToStateParams` and add this method immediately after `workflow_draft_workspaces_add_state_from_output`:

```python
    @entrypoint.method(
        name="workflow.draft_workspaces.bind_output_to_state",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_bind_output_to_state(
        params: BindOutputToStateParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.bind_output_to_state(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                output_field=params.output_field,
                state_path=params.state_path,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

- [ ] **Step 5: Add RPC client method**

In `src/wf_transport_rpc_http/client/drafts.py`, add immediately after `add_state_schema_from_output`:

```python
    async def bind_output_to_state(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.bind_output_to_state",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "output_field": output_field,
                "state_path": state_path,
            },
        )
```

- [ ] **Step 6: Run RPC tests to verify green**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q -k "bind_output_to_state or add_state_from_output"
```

Expected: selected tests pass.

- [ ] **Step 7: Commit**

```powershell
git add src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
git commit -m "feat: expose output-state binding over rpc"
```

---

## Task 3: MCP Workflow Tool

**Files:**

- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `tests/wf_mcp/server/test_config.py`

- [ ] **Step 1: Add failing MCP schema assertion**

In `tests/wf_mcp/server/test_config.py`, add `"wf.workflow.bind_output_to_state"` beside `"wf.workflow.add_state_from_output"` in the tool-name assertions.

- [ ] **Step 2: Run test to verify red**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_config.py -q
```

Expected: failure because the tool is not registered.

- [ ] **Step 3: Add MCP request model**

In `src/wf_mcp/workflow_surface/models.py`, add after `AddStateFromOutputRequest`:

```python
class BindOutputToStateRequest(BaseModel):
    """Typed MCP request for binding one step output to one root state field."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    step_id: str = Field(description="Draft step id whose capability output is used.")
    output_field: str = Field(
        description="Top-level output field to bind, for example after."
    )
    state_path: str = Field(
        description="Root state path to declare and bind, for example state.after."
    )
```

- [ ] **Step 4: Register MCP tool**

In `src/wf_mcp/workflow_surface/tools.py`, import `BindOutputToStateRequest` and add this tool immediately after `add_state_from_output`:

```python
    @server.tool(
        name="wf.workflow.bind_output_to_state",
        title="Bind Output To State",
        description=(
            "Declare one root state field from a draft step capability output "
            "schema and bind local.<output> to that state path."
        ),
    )
    async def bind_output_to_state(
        request: BindOutputToStateRequest,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.bind_output_to_state(
                workspace_id=request.workspace_id,
                revision=request.revision,
                step_id=request.step_id,
                output_field=request.output_field,
                state_path=request.state_path,
            )
        )
```

- [ ] **Step 5: Run MCP test to verify green**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_config.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py tests/wf_mcp/server/test_config.py
git commit -m "feat: add mcp output-state binding tool"
```

---

## Task 4: CLI Command

**Files:**

- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `tests/wf_cli/test_app.py`
- Modify: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add failing CLI tests**

In `tests/wf_cli/test_app.py`, add:

```python
def test_wf_draft_bind_output_to_state_help_explains_composed_edit() -> None:
    result = runner.invoke(app, ["draft", "bind-output-to-state", "--help"])

    assert result.exit_code == 0
    assert "state schema" in result.stdout
    assert "output binding" in result.stdout
    assert "validate" in result.stdout
```

In `tests/wf_cli/test_remote_target.py`, add a remote-target assertion following the existing `test_wf_draft_add_state_from_output_uses_rpc_target` pattern:

```python
def test_wf_draft_bind_output_to_state_uses_rpc_target(
    remote_target: RemoteTargetFixture,
) -> None:
    result = remote_target.invoke(
        [
            "draft",
            "bind-output-to-state",
            "snapshot_ws",
            "--revision",
            "1",
            "--step",
            "snap",
            "--output",
            "after",
            "--state",
            "state.after",
        ]
    )

    assert result.exit_code == 0
    assert remote_target.calls[-1]["method"] == (
        "workflow.draft_workspaces.bind_output_to_state"
    )
```

If `remote_target` uses a different helper shape in this file, mirror the nearby `add-state-from-output` test exactly and only change the command plus expected RPC method.

- [ ] **Step 2: Run CLI tests to verify red**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -k "bind_output_to_state or bind-output-to-state"
```

Expected: failures because command does not exist.

- [ ] **Step 3: Add CLI command**

In `src/wf_cli/commands/drafts.py`, add this command immediately after `add_state_from_output`:

```python
@app.command("bind-output-to-state")
def bind_output_to_state(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    output_field: Annotated[
        str,
        typer.Option("--output", help="Top-level capability output field."),
    ],
    state_path: Annotated[
        str,
        typer.Option("--state", help="Root state path, for example state.after."),
    ],
) -> None:
    """Declare state schema and bind one step output to that state field.

    This is the common command to run before validation when a step output
    should write to a new state field. It copies the selected capability output
    field schema into state_schema and merges the output binding
    local.<output> -> state.<field>.

    Run `wf draft validate <workspace_id>` after this command.
    """
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.bind_output_to_state(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                output_field=output_field,
                state_path=state_path,
            ),
        )
    )
```

- [ ] **Step 4: Run CLI tests to verify green**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -k "bind_output_to_state or bind-output-to-state"
```

Expected: selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
git commit -m "feat: add draft output-state binding cli"
```

---

## Task 5: Docs, Skills, And Verification

**Files:**

- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-06-26-draft-bind-output-to-state.md` to `docs/historical/superpowers/plans/2026-06-26-draft-bind-output-to-state.md`

- [ ] **Step 1: Update CLI docs**

In `docs/wf_cli.md`, near the `add-state-from-output` section, add:

````markdown
### Bind A Step Output To State

Use `bind-output-to-state` when a step output should become workflow state and
the state schema should match that capability output field.

```powershell
wf draft bind-output-to-state concat_ws --revision 6 --step call --output value --state state.value
wf draft validate concat_ws
```

The command combines two common edits:

- It copies the selected capability output field schema into the root state
  field.
- It merges the output binding `local.<output> -> state.<field>` for the step.

Use `set-route` separately for outcome routing.
````

- [ ] **Step 2: Update `wf-cli` skill**

In `skills/wf-cli/SKILL.md`, add the command near the draft command examples:

```markdown
wf draft bind-output-to-state <workspace_id> --revision <n> --step <step_id> --output <field> --state state.<field>
```

Add this rule near the schema-first rules:

```markdown
Prefer `draft bind-output-to-state` when a step output should write to a new
root state field. It declares the matching state schema and merges the output
binding in one revision-checked edit. Use `draft add-state-from-output` only
when you need the schema declaration without changing bindings.
```

- [ ] **Step 3: Update workflow skill references**

In `skills/wf-workflow/references/draft-workspaces.md`, add:

```markdown
- `bind_output_to_state`

  Declares one root state field from a step capability output schema and merges
  `local.<output> -> state.<field>` into that step's output map. Prefer this
  over manual JSON Patch when validation says a state output target is missing
  from `state_schema`.

```powershell
wf draft bind-output-to-state <workspace_id> --revision <n> --step <step_id> --output <field> --state state.<field>
wf draft validate <workspace_id>
```
```

In `skills/wf-workflow/references/workflow-lifecycle.md`, update the draft authoring guidance:

```markdown
Use focused commands for common repairs: `set-route` for outcome routing,
`set-input --merge` for input bindings, `set-output --merge` for output-only
binding edits, `add-state-from-output` for schema-only edits, and
`bind-output-to-state` when a capability output should become state.
```

- [ ] **Step 4: Update roadmap**

In `docs/current_roadmap.md`, add a completed bullet near the draft helper work:

```markdown
- Completed: `wf draft bind-output-to-state` composes state schema projection
  with output binding merge, reducing manual draft patch repairs in agent
  challenge runs.
```

- [ ] **Step 5: Move plan to historical**

Run:

```powershell
Move-Item docs\superpowers\plans\2026-06-26-draft-bind-output-to-state.md docs\historical\superpowers\plans\2026-06-26-draft-bind-output-to-state.md
```

- [ ] **Step 6: Run focused verification**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py -q -k "bind_output_to_state or bind-output-to-state or add_state_from_output"
uv run ruff check src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py src/wf_cli/commands/drafts.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py src/wf_transport_rpc_http/client/drafts.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/models.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
uv run basedpyright --level error src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py src/wf_cli/commands/drafts.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py src/wf_transport_rpc_http/client/drafts.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/models.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
```

Expected:

- Focused tests pass.
- Ruff reports `All checks passed!`.
- Basedpyright reports `0 errors`.

- [ ] **Step 7: Commit**

```powershell
git add -A
git commit -m "docs: record draft output-state binding helper"
```

---

## Self-Review Notes

- This plan does not add route composition because `set-route` already exists and route inference is a separate product decision.
- This plan does not add nested state schema projection. It keeps the same root-field constraint as `add-state-from-output`.
- This plan does not implement new JSON Schema behavior. It reuses `project_output_property_to_state_schema()`.
- The command name is `bind-output-to-state`, not `connect-output`, because the operation specifically declares state schema and binds one output to state.
