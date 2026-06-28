# Draft Remove Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add focused draft remove commands for routes, steps, and step bindings so agents can recover from bad draft edits without raw JSON Patch.

**Architecture:** Implement semantic remove helpers in `WorkflowDraftAuthoringApi`, delegate through `WorkflowApi`, and expose the same operations through RPC, MCP, and CLI. Removal persists structurally patchable edits and may return `status: "invalid"`; save/compile remain strict.

**Tech Stack:** Python 3.14, Typer, Pydantic, JSON-RPC transport, MCP workflow surface, pytest, Ruff, basedpyright.

---

## File Structure

- Modify `src/wf_api/draft_authoring.py`: add `remove_draft_route`, `remove_draft_step`, and `remove_draft_binding`.
- Modify `src/wf_api/service.py`: add facade delegates.
- Modify `src/wf_api/surface.py`: add protocol methods.
- Modify `src/wf_transport_rpc_http/models.py`: add params DTOs.
- Modify `src/wf_transport_rpc_http/methods/drafts.py`: add JSON-RPC methods.
- Modify `src/wf_transport_rpc_http/client/drafts.py`: add RPC client methods.
- Modify `src/wf_transport_rpc_http/__init__.py`: export DTOs if nearby draft DTOs are exported there.
- Modify `src/wf_mcp/workflow_surface/models.py`: add MCP request models.
- Modify `src/wf_mcp/workflow_surface/tools.py`: add MCP tools.
- Modify `src/wf_cli/commands/drafts.py`: add `remove-route`, `remove-step`, and `remove-binding`.
- Modify `tests/wf_api/test_drafts_service.py`: API behavior tests.
- Modify `tests/wf_transport_rpc_http/test_app.py`: JSON-RPC method tests.
- Modify `tests/wf_transport_rpc_http/test_client.py`: RPC client tests.
- Modify `tests/wf_mcp/server/test_config.py`: MCP tool registration assertions.
- Modify `tests/wf_cli/test_app.py`: CLI help assertions.
- Modify `tests/wf_cli/test_remote_target.py`: CLI/RPC routing smoke tests.
- Modify `docs/wf_cli.md`, `skills/wf-cli/SKILL.md`, and `skills/wf-workflow/references/draft-workspaces.md`: public guidance.
- Modify `docs/current_roadmap.md`: mark completion.

### Task 1: API Remove Helpers

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Test: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Write API tests**

Add these tests to `tests/wf_api/test_drafts_service.py` near the existing
branch/handle/add-step tests:

```python
@pytest.mark.asyncio
async def test_remove_draft_route_persists_invalid_workspace(tmp_path: Path) -> None:
    api = _draft_api(FileWorkflowArtifactStore(tmp_path / "remove_route"))
    await api.create_draft_workspace(
        workspace_id="route_ws",
        draft={
            "name": "route_ws",
            "start": "echo",
            "steps": {
                "echo": {"use": "demo.personal.echo_tool", "input": [], "output": []}
            },
            "routes": {"echo": {"ok": "__end__"}},
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
        },
    )

    result = await api.remove_draft_route(
        workspace_id="route_ws",
        revision=1,
        step_id="echo",
        outcome="ok",
    )

    assert result["revision"] == 2
    assert result["status"] == "invalid"
    fetched = await api.get_draft_workspace(
        workspace_id="route_ws",
        include_draft=True,
    )
    assert fetched["draft"]["routes"]["echo"] == {}
```

```python
@pytest.mark.asyncio
async def test_remove_draft_step_removes_outgoing_routes_not_inbound_routes(
    tmp_path: Path,
) -> None:
    api = _draft_api(FileWorkflowArtifactStore(tmp_path / "remove_step"))
    await api.create_draft_workspace(
        workspace_id="step_ws",
        draft={
            "name": "step_ws",
            "start": "first",
            "steps": {
                "first": {"use": "demo.personal.echo_tool", "input": [], "output": []},
                "second": {"use": "demo.personal.echo_tool", "input": [], "output": []},
            },
            "routes": {
                "first": {"ok": "second"},
                "second": {"ok": "__end__"},
            },
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
        },
    )

    result = await api.remove_draft_step(
        workspace_id="step_ws",
        revision=1,
        step_id="second",
    )

    assert result["revision"] == 2
    assert result["status"] == "invalid"
    assert any(
        item["code"] == "unknown_edge_destination"
        for item in result["diagnostics"]
    )
    fetched = await api.get_draft_workspace(
        workspace_id="step_ws",
        include_draft=True,
    )
    assert "second" not in fetched["draft"]["steps"]
    assert "second" not in fetched["draft"]["routes"]
    assert fetched["draft"]["routes"]["first"]["ok"] == "second"
```

```python
@pytest.mark.asyncio
async def test_remove_draft_binding_removes_input_and_output_bindings(
    tmp_path: Path,
) -> None:
    api = _draft_api(FileWorkflowArtifactStore(tmp_path / "remove_binding"))
    await api.create_draft_workspace(
        workspace_id="binding_ws",
        draft={
            "name": "binding_ws",
            "start": "echo",
            "steps": {
                "echo": {
                    "use": "demo.personal.echo_tool",
                    "input": [
                        {"path": "input.message", "target": "message"},
                        {"path": "input.extra", "target": "extra"},
                    ],
                    "output": [
                        {"source": "echoed", "target": "state.echoed"},
                        {"source": "debug", "target": "state.debug"},
                    ],
                }
            },
            "routes": {"echo": {"ok": "__end__"}},
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
        },
    )

    result = await api.remove_draft_binding(
        workspace_id="binding_ws",
        revision=1,
        step_id="echo",
        inputs=("message",),
        outputs=("debug",),
    )

    assert result["revision"] == 2
    fetched = await api.get_draft_workspace(
        workspace_id="binding_ws",
        include_draft=True,
    )
    assert fetched["draft"]["steps"]["echo"]["input"] == [
        {"path": "input.extra", "target": "extra"}
    ]
    assert fetched["draft"]["steps"]["echo"]["output"] == [
        {"source": "echoed", "target": "state.echoed"}
    ]
```

```python
@pytest.mark.asyncio
async def test_remove_missing_draft_element_is_noop(tmp_path: Path) -> None:
    api = _draft_api(FileWorkflowArtifactStore(tmp_path / "remove_noop"))
    await api.create_draft_workspace(
        workspace_id="noop_ws",
        draft={
            "name": "noop_ws",
            "start": "echo",
            "steps": {
                "echo": {"use": "demo.personal.echo_tool", "input": [], "output": []}
            },
            "routes": {"echo": {"ok": "__end__"}},
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
        },
    )

    result = await api.remove_draft_route(
        workspace_id="noop_ws",
        revision=1,
        step_id="echo",
        outcome="missing",
    )

    assert result["revision"] == 1
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_remove_draft_route_persists_invalid_workspace tests/wf_api/test_drafts_service.py::test_remove_draft_step_removes_outgoing_routes_not_inbound_routes tests/wf_api/test_drafts_service.py::test_remove_draft_binding_removes_input_and_output_bindings tests/wf_api/test_drafts_service.py::test_remove_missing_draft_element_is_noop -q
```

Expected: failures because the methods do not exist.

- [ ] **Step 3: Implement API helpers**

In `src/wf_api/draft_authoring.py`, add these methods to
`WorkflowDraftAuthoringApi` after `handle_draft`:

```python
    async def remove_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
    ) -> dict[str, Any]:
        """Remove one route; missing routes are revision-checked no-ops."""
        workspace = self.drafts._draft_store().get_workspace(workspace_id)
        draft_routes = workspace.draft.get("routes", {})
        if not isinstance(draft_routes, dict):
            raise ValueError("draft routes must be an object")
        step_routes = draft_routes.get(step_id, {})
        if not isinstance(step_routes, dict):
            raise ValueError(f"routes for step {step_id!r} must be an object")
        if outcome not in step_routes:
            checked = self._workspace_if_revision_matches(
                workspace_id=workspace_id,
                revision=revision,
            )
            if isinstance(checked, dict):
                return checked
            return summarize_draft_workspace(checked)
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "remove",
                    "path": (
                        f"/routes/{escape_json_pointer(step_id)}/"
                        f"{escape_json_pointer(outcome)}"
                    ),
                }
            ],
        )

    async def remove_draft_step(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
    ) -> dict[str, Any]:
        """Remove a step and its own route map; inbound routes are left explicit."""
        workspace = self.drafts._draft_store().get_workspace(workspace_id)
        steps = workspace.draft.get("steps", {})
        if not isinstance(steps, dict):
            raise ValueError("draft steps must be an object")
        if step_id not in steps:
            checked = self._workspace_if_revision_matches(
                workspace_id=workspace_id,
                revision=revision,
            )
            if isinstance(checked, dict):
                return checked
            return summarize_draft_workspace(checked)
        patch = [
            {
                "op": "remove",
                "path": f"/steps/{escape_json_pointer(step_id)}",
            }
        ]
        routes = workspace.draft.get("routes", {})
        if isinstance(routes, dict) and step_id in routes:
            patch.append(
                {
                    "op": "remove",
                    "path": f"/routes/{escape_json_pointer(step_id)}",
                }
            )
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )

    async def remove_draft_binding(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        inputs: Sequence[str] = (),
        outputs: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Remove selected local input/output bindings from one draft step."""
        if not inputs and not outputs:
            raise ValueError("pass at least one input or output binding to remove")
        workspace = self.drafts._draft_store().get_workspace(workspace_id)
        step = draft_step(workspace.draft, step_id)
        current_inputs = step.get("input", [])
        current_outputs = step.get("output", [])
        if not isinstance(current_inputs, list):
            raise ValueError(f"input bindings for step {step_id!r} must be a list")
        if not isinstance(current_outputs, list):
            raise ValueError(f"output bindings for step {step_id!r} must be a list")
        input_targets = set(inputs)
        output_sources = set(outputs)
        next_inputs = [
            item for item in current_inputs if item.get("target") not in input_targets
        ]
        next_outputs = [
            item for item in current_outputs if item.get("source") not in output_sources
        ]
        if next_inputs == current_inputs and next_outputs == current_outputs:
            checked = self._workspace_if_revision_matches(
                workspace_id=workspace_id,
                revision=revision,
            )
            if isinstance(checked, dict):
                return checked
            return summarize_draft_workspace(checked)
        patch: list[dict[str, Any]] = []
        if next_inputs != current_inputs:
            patch.append(
                {
                    "op": "replace",
                    "path": f"/steps/{escape_json_pointer(step_id)}/input",
                    "value": next_inputs,
                }
            )
        if next_outputs != current_outputs:
            patch.append(
                {
                    "op": "replace",
                    "path": f"/steps/{escape_json_pointer(step_id)}/output",
                    "value": next_outputs,
                }
            )
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=patch,
        )
```

If `draft_step` is not imported in `draft_authoring.py`, import it from
`wf_api.draft_payloads`.

- [ ] **Step 4: Add service and protocol delegates**

In `src/wf_api/service.py`, add methods mirroring `branch_draft` and
`handle_draft`:

```python
    async def remove_draft_route(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
    ) -> dict[str, Any]:
        return await self._draft_authoring.remove_draft_route(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            outcome=outcome,
        )

    async def remove_draft_step(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
    ) -> dict[str, Any]:
        return await self._draft_authoring.remove_draft_step(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
        )

    async def remove_draft_binding(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        inputs: Sequence[str] = (),
        outputs: Sequence[str] = (),
    ) -> dict[str, Any]:
        return await self._draft_authoring.remove_draft_binding(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            inputs=inputs,
            outputs=outputs,
        )
```

Import `Sequence` from `collections.abc` if it is not already available in
`service.py`. In `src/wf_api/surface.py`, add the same async method signatures
to `WorkflowDraftSurface`.

- [ ] **Step 5: Run API tests**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_remove_draft_route_persists_invalid_workspace tests/wf_api/test_drafts_service.py::test_remove_draft_step_removes_outgoing_routes_not_inbound_routes tests/wf_api/test_drafts_service.py::test_remove_draft_binding_removes_input_and_output_bindings tests/wf_api/test_drafts_service.py::test_remove_missing_draft_element_is_noop -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_api/draft_authoring.py src/wf_api/service.py src/wf_api/surface.py tests/wf_api/test_drafts_service.py
git commit -m "feat: add draft remove authoring helpers"
```

### Task 2: RPC And Client Surface

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add RPC DTOs**

In `src/wf_transport_rpc_http/models.py`, near other draft params, add:

```python
class RemoveDraftRouteParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)


class RemoveDraftStepParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)


class RemoveDraftBindingParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
```

Export these names from `src/wf_transport_rpc_http/__init__.py` if adjacent
draft DTOs are exported there.

- [ ] **Step 2: Register RPC methods**

In `src/wf_transport_rpc_http/methods/drafts.py`, add methods:

```python
workflow.draft_workspaces.remove_route
workflow.draft_workspaces.remove_step
workflow.draft_workspaces.remove_binding
```

Each method should call the corresponding `server.api` method and wrap
`ValueError`, `KeyError`, `LookupError`, and `FileNotFoundError` with
`raise_workflow_rpc_error`, matching `branch` and `handle`.

- [ ] **Step 3: Add RPC client methods**

In `src/wf_transport_rpc_http/client/drafts.py`, add:

```python
    async def remove_draft_route(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        outcome: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.remove_route",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "outcome": outcome,
            },
        )

    async def remove_draft_step(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.remove_step",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
            },
        )

    async def remove_draft_binding(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        inputs: list[str] | None = None,
        outputs: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.remove_binding",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "inputs": inputs or [],
                "outputs": outputs or [],
            },
        )
```

Each should call the method names from Step 2.

- [ ] **Step 4: Add transport tests**

In `tests/wf_transport_rpc_http/test_app.py`, extend the draft focused-edit
test or add a new test that calls `workflow.draft_workspaces.remove_route` and
asserts the route is absent after inspect.

In `tests/wf_transport_rpc_http/test_client.py`, add a client test that calls
`client.remove_draft_binding(...)` and asserts the request method/payload match:

```python
assert calls[-1]["method"] == "workflow.draft_workspaces.remove_binding"
assert calls[-1]["params"]["inputs"] == ["message"]
```

- [ ] **Step 5: Run transport tests**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_transport_rpc_http tests/wf_transport_rpc_http
git commit -m "feat: expose draft remove helpers over rpc"
```

### Task 3: MCP And CLI Surface

**Files:**
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_mcp/server/test_config.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Add MCP request models and tools**

In `src/wf_mcp/workflow_surface/models.py`, add request models equivalent to
the RPC DTOs:

```python
class RemoveDraftRouteRequest(BaseModel):
    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    step_id: str = Field(description="Draft step id whose route should be removed.")
    outcome: str = Field(description="Outcome label to remove from the step route map.")


class RemoveDraftStepRequest(BaseModel):
    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    step_id: str = Field(description="Draft step id to remove.")


class RemoveDraftBindingRequest(BaseModel):
    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    step_id: str = Field(description="Draft step id whose bindings should be removed.")
    inputs: list[str] = Field(
        default_factory=list,
        description="Local input target names to remove.",
    )
    outputs: list[str] = Field(
        default_factory=list,
        description="Local output source names to remove.",
    )
```

In `src/wf_mcp/workflow_surface/tools.py`, register tools:

```text
wf.workflow.remove_draft_route
wf.workflow.remove_draft_step
wf.workflow.remove_draft_binding
```

Use descriptions that state removal may return `status: invalid` and should be
followed by validation.

- [ ] **Step 2: Add CLI commands**

In `src/wf_cli/commands/drafts.py`, add:

```python
@app.command("remove-route")
def remove_draft_route(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step: Annotated[str, typer.Option("--step", help="Draft step id.")],
    outcome: Annotated[str, typer.Option("--outcome", help="Outcome route to remove.")],
) -> None:
    """Remove one route from a draft step."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.remove_draft_route(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step,
                outcome=outcome,
            ),
        )
    )

@app.command("remove-step")
def remove_draft_step(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step: Annotated[str, typer.Option("--step", help="Draft step id.")],
) -> None:
    """Remove one step and its outgoing draft route map."""
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.remove_draft_step(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step,
            ),
        )
    )

@app.command("remove-binding")
def remove_draft_binding(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step: Annotated[str, typer.Option("--step", help="Draft step id.")],
    input_name: Annotated[
        list[str] | None,
        typer.Option("--input", help="Local input target to remove. Repeatable."),
    ] = None,
    output_name: Annotated[
        list[str] | None,
        typer.Option("--output", help="Local output source to remove. Repeatable."),
    ] = None,
) -> None:
    """Remove selected input/output bindings from one draft step.

    Removal may return status: invalid. Run `wf draft validate` after cleanup.
    """
    if not input_name and not output_name:
        raise typer.BadParameter("pass at least one --input or --output")
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.remove_draft_binding(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step,
                inputs=input_name or [],
                outputs=output_name or [],
            ),
        )
    )
```

CLI option shape:

```text
wf draft remove-route WORKSPACE --revision N --step STEP --outcome OUTCOME
wf draft remove-step WORKSPACE --revision N --step STEP
wf draft remove-binding WORKSPACE --revision N --step STEP --input LOCAL --output LOCAL
```

For `remove-binding`, accept repeated `--input` and repeated `--output`.
Raise `typer.BadParameter("pass at least one --input or --output")` when both
are empty.

- [ ] **Step 3: Add tests**

In `tests/wf_mcp/server/test_config.py`, assert the three MCP tool names are
registered.

In `tests/wf_cli/test_app.py`, assert `wf draft remove-binding --help` mentions:

```text
--input
--output
status: invalid
```

In `tests/wf_cli/test_remote_target.py`, add one RPC routing smoke that invokes:

```python
[
    *base_args,
    "draft",
    "remove-route",
    "route_ws",
    "--revision",
    "1",
    "--step",
    "call",
    "--outcome",
    "ok",
]
```

Assert exit code 0 and JSON `revision` is advanced when the route existed.

- [ ] **Step 4: Run MCP/CLI tests**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_config.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
```

Expected: PASS, except unrelated pre-existing broad test failures must be
reported with names and reasons.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_mcp src/wf_cli tests/wf_mcp tests/wf_cli
git commit -m "feat: add draft remove cli and mcp tools"
```

### Task 4: Docs, Roadmap, And Final Verification

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-06-28-draft-remove-commands.md`

- [ ] **Step 1: Update user docs**

In `docs/wf_cli.md`, under draft workspace commands, add:

````markdown
### Remove Draft Elements

Use remove commands to back out one bad route, step, or binding without writing
JSON Patch:

```bash
wf draft remove-route report_ws --revision 8 --step extract --outcome ok
wf draft remove-step report_ws --revision 9 --step render
wf draft remove-binding report_ws --revision 10 --step render --input title
wf draft remove-binding report_ws --revision 11 --step render --output markdown
```

Removal may leave the workspace `status: invalid`. That is normal for
intermediate authoring. Run `wf draft validate`, then repair routes or bindings
before saving or compiling.
````

In `skills/wf-cli/SKILL.md`, add a rule:

```markdown
- To undo a bad draft edit, prefer `wf draft remove-route`,
  `wf draft remove-step`, or `wf draft remove-binding` over JSON Patch.
```

In `skills/wf-workflow/references/draft-workspaces.md`, add:

```markdown
Remove commands are for recovery. They do not delete schema fields and
`remove-step` does not remove inbound routes. Validate after removal and repair
the resulting diagnostics explicitly.
```

- [ ] **Step 2: Update roadmap**

Add a completed bullet under Priority 1:

```markdown
- Completed: draft workspaces expose focused remove commands for routes, steps,
  and step bindings so agents can recover from bad edits without raw JSON Patch.
```

- [ ] **Step 3: Archive this plan**

Move this file to:

```text
docs/historical/superpowers/plans/2026-06-28-draft-remove-commands.md
```

- [ ] **Step 4: Run final verification**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_mcp/server/test_config.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/docs -q
uv run ruff check src/wf_api/draft_authoring.py src/wf_transport_rpc_http src/wf_mcp/workflow_surface src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
uv run ruff format --check src/wf_api/draft_authoring.py src/wf_transport_rpc_http src/wf_mcp/workflow_surface src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
uv run basedpyright --level error src/wf_api/draft_authoring.py src/wf_transport_rpc_http src/wf_mcp/workflow_surface src/wf_cli/commands/drafts.py tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
```

Expected: all focused tests pass. Document any unrelated pre-existing failures
by test name and reason.

- [ ] **Step 5: Commit**

```powershell
git add docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md docs/current_roadmap.md docs/historical/superpowers/plans/2026-06-28-draft-remove-commands.md
git commit -m "docs: document draft remove commands"
```

## Self-Review

- Spec coverage: route removal, step removal, binding removal, no-op behavior,
  invalid intermediate semantics, docs, and all public surfaces are covered.
- Placeholder scan: no TODO/TBD/fill-in placeholders remain.
- Type consistency: method names use `remove_draft_*`; CLI names use
  `remove-*`; RPC method names use `workflow.draft_workspaces.remove_*`.
