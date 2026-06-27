# Draft Bind From/To Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a general `wf draft bind --from <path> --to <path>` operation that handles capability-aware input/output binding plus schema projection.

**Architecture:** Extend the existing semantic draft authoring service rather than adding another parallel helper. Generalize schema projection in `wf_api.schema_projection`, then expose one `bind_draft` method through API, service, RPC, MCP, and CLI. Remove the recently-added narrow `bind_output_to_state` surface instead of preserving ghost compatibility.

**Tech Stack:** Python 3.14, Pydantic, Typer, JSON-RPC, MCP tool models, `jsonschema.Draft202012Validator`, pytest, basedpyright.

---

## File Map

- Modify `src/wf_api/schema_projection.py`: general schema projection helper with nested target insertion.
- Modify `src/wf_api/draft_authoring.py`: add `bind_draft`, remove `bind_output_to_state`.
- Modify `src/wf_api/service.py` and `src/wf_api/surface.py`: facade/protocol methods.
- Modify `src/wf_transport_rpc_http/models.py`, `methods/drafts.py`, `client/drafts.py`, and `__init__.py`: RPC DTO/method/client/export.
- Modify `src/wf_mcp/workflow_surface/models.py` and `tools.py`: MCP request/tool.
- Modify `src/wf_cli/commands/drafts.py`: add `wf draft bind` and remove `bind-output-to-state`.
- Modify `src/wf_api/drafts.py`: update repair hints from `bind-output-to-state` to `bind`.
- Modify docs and skills: `docs/wf_cli.md`, `docs/current_roadmap.md`, `docs/superpowers/specs/2026-06-27-draft-semantic-authoring-boundary.md`, `skills/wf-cli/SKILL.md`, `skills/wf-workflow/references/draft-workspaces.md`, `skills/wf-workflow/references/workflow-lifecycle.md`.

---

### Task 1: Generalize Schema Projection

**Files:**
- Modify: `src/wf_api/schema_projection.py`
- Test: `tests/wf_api/test_schema_projection.py`

- [ ] **Step 1: Add failing tests for nested insertion and overwrite rejection**

Append tests:

```python
def test_project_schema_property_inserts_nested_path_and_defs() -> None:
    projected = project_property_to_schema_path(
        target_schema={"type": "object", "properties": {}},
        source_schema={
            "type": "object",
            "properties": {"after": {"$ref": "#/$defs/Snapshot"}},
            "$defs": {
                "Snapshot": {
                    "type": "object",
                    "properties": {"clicked": {"type": "boolean"}},
                }
            },
        },
        source_field="after",
        target_parts=("session", "after"),
    )

    assert projected["properties"]["session"]["type"] == "object"
    assert projected["properties"]["session"]["properties"]["after"] == {
        "$ref": "#/$defs/Snapshot"
    }
    assert projected["$defs"]["Snapshot"]["properties"]["clicked"] == {
        "type": "boolean"
    }


def test_project_schema_property_rejects_existing_nested_target() -> None:
    with pytest.raises(ValueError, match="schema path 'session.after' already exists"):
        project_property_to_schema_path(
            target_schema={
                "type": "object",
                "properties": {
                    "session": {
                        "type": "object",
                        "properties": {"after": {"type": "string"}},
                    }
                },
            },
            source_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            source_field="after",
            target_parts=("session", "after"),
        )


def test_project_schema_property_rejects_non_object_ancestor() -> None:
    with pytest.raises(ValueError, match="schema path 'session' is not an object"):
        project_property_to_schema_path(
            target_schema={
                "type": "object",
                "properties": {"session": {"type": "string"}},
            },
            source_schema={
                "type": "object",
                "properties": {"after": {"type": "object"}},
            },
            source_field="after",
            target_parts=("session", "after"),
        )
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
uv run pytest tests/wf_api/test_schema_projection.py -q
```

Expected: failures because `project_property_to_schema_path` does not exist.

- [ ] **Step 3: Implement general helper and keep the root-state convenience function**

In `src/wf_api/schema_projection.py`, add:

```python
def project_property_to_schema_path(
    *,
    target_schema: JsonObject,
    source_schema: JsonObject,
    source_field: str,
    target_parts: tuple[str, ...],
) -> JsonObject:
    """Copy one source property schema into a target JSON Schema object path."""
    if not target_parts:
        raise ValueError("target schema path must not be empty")
    _check_schema("target_schema", target_schema)
    _check_schema("source_schema", source_schema)
    source_properties = source_schema.get("properties")
    if not isinstance(source_properties, dict) or source_field not in source_properties:
        raise ValueError(f"source field {source_field!r} is not declared")
    source_property = source_properties[source_field]
    if not isinstance(source_property, dict):
        raise ValueError(f"source field {source_field!r} is not a JSON Schema object")

    projected = deepcopy(target_schema)
    _ensure_object_schema(projected, "target_schema")
    parent = projected
    for index, part in enumerate(target_parts[:-1]):
        properties = _properties_for_object(parent, ".".join(target_parts[:index]) or "target_schema")
        child = properties.get(part)
        if child is None:
            child = {"type": "object", "properties": {}}
            properties[part] = child
        if not isinstance(child, dict):
            raise ValueError(f"schema path {'.'.join(target_parts[: index + 1])!r} is not an object")
        _ensure_object_schema(child, ".".join(target_parts[: index + 1]))
        parent = child

    properties = _properties_for_object(parent, ".".join(target_parts[:-1]) or "target_schema")
    leaf = target_parts[-1]
    if leaf in properties:
        raise ValueError(f"schema path {'.'.join(target_parts)!r} already exists")
    properties[leaf] = deepcopy(source_property)

    _merge_definition_block(projected, source_schema, "$defs")
    _merge_definition_block(projected, source_schema, "definitions")
    _check_schema("projected target_schema", projected)
    return projected


def _ensure_object_schema(schema: JsonObject, label: str) -> None:
    schema_type = schema.get("type")
    if schema_type is not None and schema_type != "object":
        raise ValueError(f"{label} must be an object schema")
    schema.setdefault("type", "object")


def _properties_for_object(schema: JsonObject, label: str) -> JsonObject:
    properties = schema.setdefault("properties", {})
    if not isinstance(properties, dict):
        raise ValueError(f"{label}.properties must be an object")
    return properties
```

Then rewrite `project_output_property_to_state_schema` as:

```python
def project_output_property_to_state_schema(
    *,
    state_schema: JsonObject,
    output_schema: JsonObject,
    output_field: str,
    state_field: str,
) -> JsonObject:
    """Root state projection convenience wrapper."""
    return project_property_to_schema_path(
        target_schema=state_schema,
        source_schema=output_schema,
        source_field=output_field,
        target_parts=(state_field,),
    )
```

- [ ] **Step 4: Run schema projection tests**

Run:

```powershell
uv run pytest tests/wf_api/test_schema_projection.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_api/schema_projection.py tests/wf_api/test_schema_projection.py
git commit -m "feat: generalize draft schema projection"
```

---

### Task 2: Add API-Level `bind_draft`

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Test: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Add failing API tests**

Add tests:

```python
@pytest.mark.asyncio
async def test_bind_draft_workflow_input_to_step_input_projects_input_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_input")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="bind_ws",
        draft=_echo_draft(),
    )

    result = await authoring.bind_draft(
        workspace_id="bind_ws",
        revision=1,
        step_id="echo",
        source_path="input.message",
        target_path="local.message",
    )
    workspace = await api.get_draft_workspace(workspace_id="bind_ws", include_draft=True)

    assert result["revision"] == 2
    assert workspace["draft"]["input_schema"]["properties"]["message"]["type"] == "string"
    assert workspace["draft"]["steps"]["echo"]["input"] == [
        {"target": "message", "path": "input.message"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_output_to_nested_state_projects_state_schema(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_output_nested")
    api, service, authoring = _draft_api(artifact_store, register_echo=True)
    service.register_specs("demo.personal", _snapshot_tool)
    await api.create_draft_workspace(
        workspace_id="snapshot_ws",
        draft={
            "name": "snapshot",
            "input_schema": {"type": "object", "properties": {}},
            "state_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "object", "properties": {}},
            "start": "snap",
            "steps": {"snap": {"use": "demo.personal.snapshot_tool", "input": [], "output": []}},
            "routes": {"snap": {"ok": "__end__"}},
        },
    )

    result = await authoring.bind_draft(
        workspace_id="snapshot_ws",
        revision=1,
        step_id="snap",
        source_path="local.after",
        target_path="state.session.after",
    )
    workspace = await api.get_draft_workspace(workspace_id="snapshot_ws", include_draft=True)

    assert result["revision"] == 2
    assert (
        workspace["draft"]["state_schema"]["properties"]["session"]["properties"]["after"]["$ref"]
        == "#/$defs/_Snapshot"
    )
    assert workspace["draft"]["steps"]["snap"]["output"] == [
        {"source": "after", "target": "state.session.after"}
    ]


@pytest.mark.asyncio
async def test_bind_draft_rejects_unsupported_direction(tmp_path: Path) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_bind_bad_direction")
    api, _service, authoring = _draft_api(artifact_store, register_echo=True)
    await api.create_draft_workspace(workspace_id="bind_ws", draft=_echo_draft())

    with pytest.raises(ValueError, match="unsupported bind direction"):
        await authoring.bind_draft(
            workspace_id="bind_ws",
            revision=1,
            step_id="echo",
            source_path="input.message",
            target_path="state.message",
        )
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "bind_draft"
```

Expected: failures because `bind_draft` does not exist.

- [ ] **Step 3: Implement `bind_draft`**

In `src/wf_api/draft_authoring.py`, import:

```python
from wf_core.paths import GraphSourcePath, LocalPath
from .schema_projection import (
    project_output_property_to_state_schema,
    project_property_to_schema_path,
)
```

Add helpers:

```python
def _graph_parts(path: str) -> tuple[str, tuple[str, ...]]:
    parsed = GraphSourcePath.parse(path)
    return parsed.root, parsed.parts


def _local_field(path: str) -> str:
    parsed = LocalPath.parse(path)
    if len(parsed.parts) != 1:
        raise ValueError("local path must name one capability field")
    return parsed.parts[0]
```

Add method:

```python
async def bind_draft(
    self,
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    source_path: str,
    target_path: str,
) -> dict[str, Any]:
    """Bind a graph path to/from one capability local field with schema projection."""
    workspace = self.drafts._draft_store().get_workspace(workspace_id)
    step = draft_step(workspace.draft, step_id)
    capability_name = step.get("use")
    if not isinstance(capability_name, str) or not capability_name:
        raise ValueError(f"draft step {step_id!r} does not declare a capability use")
    spec = self.context.specs.get_qualified_spec(capability_name)

    source_root, source_parts = _graph_parts(source_path) if not source_path.startswith("local.") else ("local", LocalPath.parse(source_path).parts)
    target_root, target_parts = _graph_parts(target_path) if not target_path.startswith("local.") else ("local", LocalPath.parse(target_path).parts)

    if target_root == "local" and source_root in {"input", "state"}:
        local_field = _local_field(target_path)
        input_schema = spec.input_schema_contract or spec.input_model.model_json_schema()
        schema_key = "input_schema" if source_root == "input" else "state_schema"
        target_schema = workspace.draft.get(schema_key, {})
        if not isinstance(target_schema, dict):
            raise ValueError(f"draft {schema_key} must be an object")
        projected = project_property_to_schema_path(
            target_schema=target_schema,
            source_schema=input_schema,
            source_field=local_field,
            target_parts=source_parts,
        )
        input_map = {
            **_draft_input_maps(workspace.draft, step_id),
            source_path: local_field,
        }
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {"op": "replace", "path": f"/{schema_key}", "value": projected},
                {
                    "op": "replace",
                    "path": f"/steps/{escape_json_pointer(step_id)}/input",
                    "value": input_bindings_payload(input_map, {}),
                },
            ],
        )

    if source_root == "local" and target_root in {"state", "output"}:
        local_field = _local_field(source_path)
        output_schema = spec.output_schema_contract or spec.output_model.model_json_schema()
        schema_key = "state_schema" if target_root == "state" else "output_schema"
        target_schema = workspace.draft.get(schema_key, {})
        if not isinstance(target_schema, dict):
            raise ValueError(f"draft {schema_key} must be an object")
        projected = project_property_to_schema_path(
            target_schema=target_schema,
            source_schema=output_schema,
            source_field=local_field,
            target_parts=target_parts,
        )
        output_map = {
            **self.drafts._step_output_map(workspace_id=workspace_id, step_id=step_id),
            local_field: target_path,
        }
        return await self.drafts.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {"op": "replace", "path": f"/{schema_key}", "value": projected},
                {
                    "op": "replace",
                    "path": f"/steps/{escape_json_pointer(step_id)}/output",
                    "value": output_bindings_payload(output_map),
                },
            ],
        )

    raise ValueError(f"unsupported bind direction: {source_path!r} -> {target_path!r}")
```

Delete the old `bind_output_to_state` method from `WorkflowDraftAuthoringApi`.
It is superseded by `bind_draft` and should not remain as a compatibility shim.

- [ ] **Step 4: Run API tests**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py -q -k "bind_draft or bind_output_to_state"
```

Expected: new `bind_draft` tests pass. Existing `bind_output_to_state` tests
should be updated or removed in this task because the old method is gone.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
git commit -m "feat: replace narrow draft output bind with general bind"
```

---

### Task 3: Expose Bind Through Facade, RPC, MCP, And CLI

**Files:**
- Modify: `src/wf_api/service.py`, `src/wf_api/surface.py`
- Modify: `src/wf_transport_rpc_http/models.py`, `src/wf_transport_rpc_http/methods/drafts.py`, `src/wf_transport_rpc_http/client/drafts.py`, `src/wf_transport_rpc_http/__init__.py`
- Modify: `src/wf_mcp/workflow_surface/models.py`, `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`, `tests/wf_transport_rpc_http/test_client.py`, `tests/wf_cli/test_app.py`, `tests/wf_cli/test_remote_target.py`, `tests/wf_mcp/server/test_config.py`

- [ ] **Step 1: Add failing surface tests**

In RPC app/client tests, replace existing `bind_output_to_state` coverage with:

```python
{
    "workspace_id": "rpc_ws",
    "revision": 1,
    "step_id": "call",
    "source_path": "local.echoed",
    "target_path": "state.echoed",
}
```

Expected method name:

```text
workflow.draft_workspaces.bind
```

In CLI remote target test, invoke:

```python
[
    "draft",
    "bind",
    "rpc_ws",
    "--revision",
    "1",
    "--step",
    "call",
    "--from",
    "local.echoed",
    "--to",
    "state.echoed",
]
```

In MCP config test, assert:

```python
assert "wf.workflow.bind" in names
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py -q -k "bind"
```

Expected: failures because public bind surfaces do not exist.

- [ ] **Step 3: Add facade and protocol**

In `src/wf_api/surface.py`, add:

```python
async def bind_draft(
    self,
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    source_path: str,
    target_path: str,
) -> dict[str, Any]: ...
```

Remove the old `bind_output_to_state` protocol method.

In `src/wf_api/service.py`, add delegate:

```python
async def bind_draft(
    self,
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    source_path: str,
    target_path: str,
) -> dict[str, Any]:
    return await self.draft_authoring.bind_draft(
        workspace_id=workspace_id,
        revision=revision,
        step_id=step_id,
        source_path=source_path,
        target_path=target_path,
    )
```

Remove the old `bind_output_to_state` facade method.

- [ ] **Step 4: Add RPC model/method/client**

In `src/wf_transport_rpc_http/models.py`:

```python
class BindDraftParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    target_path: str = Field(min_length=1)
```

In `src/wf_transport_rpc_http/methods/drafts.py`:

```python
@entrypoint.method(
    name="workflow.draft_workspaces.bind",
    errors=[WorkflowRpcError],
)
async def workflow_draft_workspaces_bind(
    params: BindDraftParams = RpcParams(),
) -> dict[str, Any]:
    try:
        return await server.api.bind_draft(
            workspace_id=params.workspace_id,
            revision=params.revision,
            step_id=params.step_id,
            source_path=params.source_path,
            target_path=params.target_path,
        )
    except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
        raise_workflow_rpc_error(exc)
```

In `src/wf_transport_rpc_http/client/drafts.py`:

```python
async def bind_draft(
    self,
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    source_path: str,
    target_path: str,
) -> dict[str, Any]:
    return await self._request(
        "workflow.draft_workspaces.bind",
        {
            "workspace_id": workspace_id,
            "revision": revision,
            "step_id": step_id,
            "source_path": source_path,
            "target_path": target_path,
        },
    )
```

Export `BindDraftParams` from `src/wf_transport_rpc_http/__init__.py`.

Remove `BindOutputToStateParams`, the
`workflow.draft_workspaces.bind_output_to_state` RPC method, and
`RpcDraftClientMixin.bind_output_to_state`.

- [ ] **Step 5: Add MCP request/tool**

In `src/wf_mcp/workflow_surface/models.py`:

```python
class BindDraftRequest(BaseModel):
    """Typed MCP request for binding one draft step path with schema projection."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    step_id: str = Field(description="Capability-backed draft step id.")
    source_path: str = Field(description="Source path, for example input.x or local.y.")
    target_path: str = Field(description="Target path, for example local.x or state.y.")
```

In `src/wf_mcp/workflow_surface/tools.py`, register `wf.workflow.bind` beside
the other draft authoring tools.

Remove `BindOutputToStateRequest` and the `wf.workflow.bind_output_to_state`
tool.

- [ ] **Step 6: Add CLI command**

In `src/wf_cli/commands/drafts.py`, add:

```python
@app.command("bind")
def bind_draft(
    ctx: typer.Context,
    workspace_id: Annotated[str, typer.Argument(help="Draft workspace id.")],
    revision: Annotated[
        int, typer.Option("--revision", min=1, help="Expected workspace revision.")
    ],
    step_id: Annotated[str, typer.Option("--step", help="Draft step id.")],
    source_path: Annotated[
        str,
        typer.Option("--from", help="Source path, for example input.x or local.y."),
    ],
    target_path: Annotated[
        str,
        typer.Option("--to", help="Target path, for example local.x or state.y."),
    ],
) -> None:
    """Bind a capability step path and project the matching schema.

    Direction matters. Use input/state -> local for step inputs and local ->
    state/output for step outputs. Run `wf draft validate <workspace_id>` after
    this command.
    """
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.bind_draft(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                source_path=source_path,
                target_path=target_path,
            ),
        )
    )
```

Then remove the old `@app.command("bind-output-to-state")` command.

- [ ] **Step 7: Run surface tests**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py -q -k "bind"
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit**

```powershell
git add src/wf_api/service.py src/wf_api/surface.py src/wf_transport_rpc_http src/wf_mcp/workflow_surface src/wf_cli/commands/drafts.py tests/wf_transport_rpc_http tests/wf_cli tests/wf_mcp
git commit -m "feat: expose general draft bind across transports"
```

---

### Task 4: Update Repair Hints, Docs, And Skills

**Files:**
- Modify: `src/wf_api/drafts.py`
- Modify: `docs/wf_cli.md`, `docs/current_roadmap.md`, `docs/superpowers/specs/2026-06-27-draft-semantic-authoring-boundary.md`
- Modify: `skills/wf-cli/SKILL.md`, `skills/wf-workflow/references/draft-workspaces.md`, `skills/wf-workflow/references/workflow-lifecycle.md`
- Test: `tests/wf_api/test_drafts_service.py`, `tests/wf_cli/test_remote_target.py`

- [ ] **Step 1: Update repair hint tests**

Change expectations from:

```python
"wf draft bind-output-to-state snapshot_ws --revision 1 --step snap --output after --state state.after"
```

to:

```python
"wf draft bind snapshot_ws --revision 1 --step snap --from local.after --to state.after"
```

- [ ] **Step 2: Update repair hint implementation**

In `src/wf_api/drafts.py`, update `_draft_repair_hint` return value:

```python
return (
    f"wf draft bind {workspace_id} --revision {revision} "
    f"--step {step_id} --from local.{output_field} --to {state_path}"
)
```

- [ ] **Step 3: Update docs and skills**

Docs should state:

```markdown
Use `wf draft bind --from ... --to ...` for schema-aware step wiring.
`bind-output-to-state` has been removed; use `bind --from local.<field>
--to state.<field>` instead.
```

Include examples:

```powershell
wf draft bind browser_ws --revision 2 --step click --from input.simulate --to local.simulate
wf draft bind browser_ws --revision 3 --step click --from local.after --to state.after
wf draft bind report_ws --revision 4 --step render --from local.markdown --to output.markdown
```

- [ ] **Step 4: Run tests**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py -q -k "repair_hint or bind"
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_api/drafts.py docs/wf_cli.md docs/current_roadmap.md docs/superpowers/specs/2026-06-27-draft-semantic-authoring-boundary.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md skills/wf-workflow/references/workflow-lifecycle.md tests/wf_api/test_drafts_service.py tests/wf_cli/test_remote_target.py
git commit -m "docs: document general draft bind helper"
```

---

### Task 5: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused test set**

Run:

```powershell
uv run pytest tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py tests/wf_mcp/server/test_config.py -q -k "bind or schema_projection or repair_hint"
```

Expected: all selected tests pass.

- [ ] **Step 2: Run lint, format, and type checks**

Run:

```powershell
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
git diff --check
```

Expected:

- Ruff clean.
- Format clean.
- Basedpyright reports `0 errors`.
- `git diff --check` has no whitespace errors. CRLF warnings are acceptable on Windows.

- [ ] **Step 3: Optional live smoke**

If `wf-rpc-server --config wf.config.json --host 127.0.0.1 --port 8765` is running, run:

```powershell
uv run wf --url http://127.0.0.1:8765/rpc draft bind --help
```

Then create a temporary draft and verify:

```powershell
uv run wf --url http://127.0.0.1:8765/rpc draft bind <workspace_id> --revision <n> --step <step_id> --from local.<field> --to state.<field>
```

Expected: command routes through RPC and returns a revised workspace summary.

- [ ] **Step 4: Commit final cleanup if needed**

```powershell
git status --short
git add <only files changed by cleanup>
git commit -m "fix: polish draft bind implementation"
```

Skip this commit if the tree is already clean after Task 4.

---

## Self-Review Notes

- Spec coverage: tasks cover schema projection, API, transports, CLI, repair hints, docs, and deletion of the old narrow helper.
- Scope control: this removes `bind-output-to-state` because it is recent, narrow, and not a durable external contract.
- Risk: nested schema projection must stay object-property only. Do not support array item projection in this slice.
