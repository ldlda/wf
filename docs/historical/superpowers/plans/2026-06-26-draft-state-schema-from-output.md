# Draft State Schema From Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a focused draft helper that projects a capability output field schema into a draft workspace state schema, including local `$defs` / `definitions`, so agents do not hand-patch whole `state_schema` documents when chaining tools.

**Architecture:** Implement schema projection in `wf_api`, then expose it through the same draft-workspace surfaces as other focused edit helpers: `WorkflowApi`, JSON-RPC, RPC client, MCP workflow tool, and `wf draft` CLI. The helper is capability-aware: it reads the selected draft step's `use` capability, finds one top-level output property schema, copies it into `state_schema.properties`, and merges local schema definitions with conflict checks. Do **not** implement a custom JSON Schema resolver; use `jsonschema.Draft202012Validator.check_schema` for schema validity and preserve local `$defs` / `definitions` wholesale instead of rewriting `$ref`.

**Tech Stack:** Python 3.14, Pydantic models, `jsonschema>=4.26`, Typer CLI, JSON-RPC transport, FastMCP tool registration, pytest, ruff, basedpyright.

---

## Scope

Build this command shape:

```powershell
wf draft add-state-from-output <workspace_id> `
  --revision <n> `
  --step <step_id> `
  --output <output_field> `
  --state state.<field>
```

Example:

```powershell
wf draft add-state-from-output browser_ws `
  --revision 2 `
  --step wait `
  --output after `
  --state state.after
```

This helper only declares a root state field from one top-level capability output property. It does **not** add a step, route, input map, or output map. It does **not** infer business semantics. It should preserve the existing revision-checked draft editing contract.

## Files

- Create: `src/wf_api/schema_projection.py`
  - Own pure helpers for projecting one output property schema into a draft state schema.
- Modify: `src/wf_api/drafts.py`
  - Add `WorkflowDraftApi.add_state_schema_from_output`.
- Modify: `src/wf_api/service.py`
  - Delegate `WorkflowApi.add_state_schema_from_output`.
- Modify: `src/wf_api/surface.py`
  - Add method to `WorkflowDraftSurface`.
- Modify: `src/wf_transport_rpc_http/models.py`
  - Add `AddStateFromOutputParams`.
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
  - Register `workflow.draft_workspaces.add_state_from_output`.
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
  - Add client method.
- Modify: `src/wf_mcp/workflow_surface/models.py`
  - Add `AddStateFromOutputRequest`.
- Modify: `src/wf_mcp/workflow_surface/tools.py`
  - Register `wf.workflow.add_state_from_output`.
- Modify: `src/wf_cli/commands/drafts.py`
  - Add `wf draft add-state-from-output`.
- Modify: docs/skills:
  - `docs/wf_cli.md`
  - `skills/wf-cli/SKILL.md`
  - `skills/wf-workflow/references/draft-workspaces.md`
  - `skills/wf-workflow/references/workflow-lifecycle.md`
  - `docs/current_roadmap.md`
- Tests:
  - `tests/wf_api/test_schema_projection.py`
  - `tests/wf_api/test_drafts_service.py`
  - `tests/wf_transport_rpc_http/test_app.py`
  - `tests/wf_transport_rpc_http/test_client.py`
  - `tests/wf_cli/test_remote_target.py`
  - `tests/wf_mcp/server/test_config.py`

---

## Task 1: Pure Schema Projection Helper

**Files:**
- Create: `src/wf_api/schema_projection.py`
- Create: `tests/wf_api/test_schema_projection.py`

- [ ] **Step 1: Write failing projection tests**

Create `tests/wf_api/test_schema_projection.py`:

```python
from __future__ import annotations

import pytest

from wf_api.schema_projection import project_output_property_to_state_schema


def test_project_output_property_copies_schema_and_defs() -> None:
    state_schema = {
        "type": "object",
        "properties": {"before": {"type": "object"}},
    }
    output_schema = {
        "type": "object",
        "properties": {
            "after": {"$ref": "#/$defs/Snapshot"},
        },
        "$defs": {
            "Snapshot": {
                "type": "object",
                "properties": {"clicked": {"type": "boolean"}},
                "required": ["clicked"],
            }
        },
    }

    projected = project_output_property_to_state_schema(
        state_schema=state_schema,
        output_schema=output_schema,
        output_field="after",
        state_field="after",
    )

    assert projected["properties"]["before"] == {"type": "object"}
    assert projected["properties"]["after"] == {"$ref": "#/$defs/Snapshot"}
    assert projected["$defs"]["Snapshot"]["properties"]["clicked"] == {
        "type": "boolean"
    }
    assert "after" not in state_schema["properties"]


def test_project_output_property_rejects_missing_output_field() -> None:
    with pytest.raises(ValueError, match="output field 'after'"):
        project_output_property_to_state_schema(
            state_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            output_field="after",
            state_field="after",
        )


def test_project_output_property_rejects_conflicting_defs() -> None:
    with pytest.raises(ValueError, match=r"conflicting \$defs.Snapshot"):
        project_output_property_to_state_schema(
            state_schema={
                "type": "object",
                "properties": {},
                "$defs": {"Snapshot": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"after": {"$ref": "#/$defs/Snapshot"}},
                "$defs": {"Snapshot": {"type": "object"}},
            },
            output_field="after",
            state_field="after",
        )


def test_project_output_property_rejects_invalid_projected_schema() -> None:
    with pytest.raises(ValueError, match="projected state_schema is not valid"):
        project_output_property_to_state_schema(
            state_schema={"type": "object", "properties": {}},
            output_schema={
                "type": "object",
                "properties": {"after": {"type": "definitely-not-jsonschema"}},
            },
            output_field="after",
            state_field="after",
        )
```

- [ ] **Step 2: Run tests to verify red**

Run:

```powershell
uv run pytest tests/wf_api/test_schema_projection.py -q
```

Expected: import failure because `wf_api.schema_projection` does not exist.

- [ ] **Step 3: Implement pure helper**

Create `src/wf_api/schema_projection.py`:

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any

from jsonschema import Draft202012Validator, SchemaError

JsonObject = dict[str, Any]


def project_output_property_to_state_schema(
    *,
    state_schema: JsonObject,
    output_schema: JsonObject,
    output_field: str,
    state_field: str,
) -> JsonObject:
    """Project one capability output property schema into workflow state schema.

    Capability output schemas may use local references such as
    ``{"$ref": "#/$defs/Snapshot"}``. Copying only the property schema would
    create dangling references, so this helper also merges local definition
    blocks and rejects conflicting definition names.
    """
    _check_schema("state_schema", state_schema)
    _check_schema("output_schema", output_schema)
    output_properties = output_schema.get("properties")
    if not isinstance(output_properties, dict) or output_field not in output_properties:
        raise ValueError(f"output field {output_field!r} is not declared")
    output_property = output_properties[output_field]
    if not isinstance(output_property, dict):
        raise ValueError(f"output field {output_field!r} is not a JSON Schema object")

    projected = deepcopy(state_schema)
    projected.setdefault("type", "object")
    properties = projected.setdefault("properties", {})
    if not isinstance(properties, dict):
        raise ValueError("state_schema.properties must be an object")
    properties[state_field] = deepcopy(output_property)

    _merge_definition_block(projected, output_schema, "$defs")
    _merge_definition_block(projected, output_schema, "definitions")
    _check_schema("projected state_schema", projected)
    return projected


def _check_schema(name: str, schema: JsonObject) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"{name} is not valid JSON Schema: {exc.message}") from exc


def _merge_definition_block(
    target_schema: JsonObject,
    source_schema: JsonObject,
    key: str,
) -> None:
    source_defs = source_schema.get(key)
    if source_defs is None:
        return
    if not isinstance(source_defs, dict):
        raise ValueError(f"output_schema.{key} must be an object")
    target_defs = target_schema.setdefault(key, {})
    if not isinstance(target_defs, dict):
        raise ValueError(f"state_schema.{key} must be an object")
    for name, definition in source_defs.items():
        if name in target_defs and target_defs[name] != definition:
            raise ValueError(f"conflicting {key}.{name}")
        target_defs[name] = deepcopy(definition)
```

- [ ] **Step 4: Run tests to verify green**

Run:

```powershell
uv run pytest tests/wf_api/test_schema_projection.py -q
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_api/schema_projection.py tests/wf_api/test_schema_projection.py
git commit -m "feat: project capability output schemas into state"
```

---

## Task 2: API Draft Helper

**Files:**
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `tests/wf_api/test_drafts_service.py`

- [ ] **Step 1: Write failing API test**

In `tests/wf_api/test_drafts_service.py`, add imports:

```python
from pydantic import BaseModel
from wf_authoring import node
```

Add test-local models and spec near `_echo_draft()`:

```python
class _Snapshot(BaseModel):
    clicked: bool


class _SnapshotOutput(BaseModel):
    after: _Snapshot


@node(name="snapshot_tool")
def _snapshot_tool() -> _SnapshotOutput:
    return _SnapshotOutput(after=_Snapshot(clicked=True))
```

Add this test:

```python
@pytest.mark.asyncio
async def test_add_state_schema_from_output_copies_output_property_defs(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_state_from_output")
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

    updated = await api.add_state_schema_from_output(
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

    state_schema = fetched["draft"]["state_schema"]
    assert updated["revision"] == 2
    assert state_schema["properties"]["after"]["$ref"] == "#/$defs/_Snapshot"
    assert state_schema["$defs"]["_Snapshot"]["properties"]["clicked"] == {
        "title": "Clicked",
        "type": "boolean",
    }
```

Add a second test:

```python
@pytest.mark.asyncio
async def test_add_state_schema_from_output_rejects_nested_state_path(
    tmp_path: Path,
) -> None:
    artifact_store = FileWorkflowArtifactStore(tmp_path / "drafts_nested_state_output")
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
        await api.add_state_schema_from_output(
            workspace_id="snapshot_ws",
            revision=1,
            step_id="snap",
            output_field="after",
            state_path="state.after.clicked",
        )
```

- [ ] **Step 2: Run tests to verify red**

Run:

```powershell
uv run pytest tests/wf_api/test_drafts_service.py::test_add_state_schema_from_output_copies_output_property_defs tests/wf_api/test_drafts_service.py::test_add_state_schema_from_output_rejects_nested_state_path -q
```

Expected: missing `add_state_schema_from_output` method.

- [ ] **Step 3: Implement API helper**

In `src/wf_api/drafts.py`, import:

```python
from .schema_projection import project_output_property_to_state_schema
```

Add method to `WorkflowDraftApi` after `set_step_output_map`:

```python
    async def add_state_schema_from_output(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        workspace = self._draft_store().get_workspace(workspace_id)
        step = _draft_step(workspace.draft, step_id)
        capability_name = step.get("use")
        if not isinstance(capability_name, str) or not capability_name:
            raise ValueError(f"draft step {step_id!r} does not declare a capability use")
        state_field = _state_root_field(state_path)
        spec = self.context.specs.get_qualified_spec(capability_name)
        output_schema = spec.output_schema_contract or spec.output_model.model_json_schema()
        state_schema = workspace.draft.get("state_schema", {})
        if not isinstance(state_schema, dict):
            raise ValueError("draft state_schema must be an object")
        projected = project_output_property_to_state_schema(
            state_schema=state_schema,
            output_schema=output_schema,
            output_field=output_field,
            state_field=state_field,
        )
        return await self.patch_draft_workspace(
            workspace_id=workspace_id,
            revision=revision,
            patch=[
                {
                    "op": "replace",
                    "path": "/state_schema",
                    "value": projected,
                }
            ],
        )
```

Add helper near `_path_text`:

```python
def _state_root_field(value: str) -> str:
    path = StatePath.parse(value)
    if len(path.parts) != 1:
        raise ValueError("state_path must name one root field, such as state.after")
    return path.parts[0]
```

In `src/wf_api/service.py`, add delegate near other draft helpers:

```python
    async def add_state_schema_from_output(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        return await self.drafts.add_state_schema_from_output(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            output_field=output_field,
            state_path=state_path,
        )
```

In `src/wf_api/surface.py`, add to `WorkflowDraftSurface` after output map:

```python
    async def add_state_schema_from_output(
        self,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]: ...
```

- [ ] **Step 4: Run tests to verify green**

Run:

```powershell
uv run pytest tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py::test_add_state_schema_from_output_copies_output_property_defs tests/wf_api/test_drafts_service.py::test_add_state_schema_from_output_rejects_nested_state_path -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py tests/wf_api/test_drafts_service.py
git commit -m "feat: add draft state schema helper"
```

---

## Task 3: JSON-RPC And Client Surface

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`

- [ ] **Step 1: Add failing RPC app test**

In `tests/wf_transport_rpc_http/test_app.py`, add a focused assertion inside or near `test_rpc_draft_workspace_focused_edit_methods`:

```python
        state_added = await _rpc(
            client,
            "workflow.draft_workspaces.add_state_from_output",
            {
                "workspace_id": "focused_ws",
                "revision": 7,
                "step_id": "call",
                "output_field": "value",
                "state_path": "state.extra_value",
            },
        )
```

Then update expected revisions after the existing merge assertions:

```python
    assert state_added["result"]["revision"] == 8
    assert (
        draft["state_schema"]["properties"]["extra_value"]
        == draft["state_schema"]["properties"]["value"]
    )
```

If `focused_ws` uses `wf.std.constant`, its output schema has top-level `value`; this checks projection without new fixtures.

- [ ] **Step 2: Add failing RPC client test**

In `tests/wf_transport_rpc_http/test_client.py`, inside `test_rpc_client_draft_workspace_focused_edit_methods`, call:

```python
        state_added = await client.add_state_schema_from_output(
            workspace_id="client_focused_ws",
            revision=7,
            step_id="call",
            output_field="value",
            state_path="state.extra_value",
        )
```

Assert:

```python
    assert state_added["revision"] == 8
```

- [ ] **Step 3: Run tests to verify red**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_draft_workspace_focused_edit_methods tests/wf_transport_rpc_http/test_client.py::test_rpc_client_draft_workspace_focused_edit_methods -q
```

Expected: method/model/client attribute missing.

- [ ] **Step 4: Implement JSON-RPC wiring**

In `src/wf_transport_rpc_http/models.py`, add:

```python
class AddStateFromOutputParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    output_field: str = Field(min_length=1)
    state_path: str = Field(min_length=1)
```

In `src/wf_transport_rpc_http/methods/drafts.py`, import `AddStateFromOutputParams` and register:

```python
    @entrypoint.method(
        name="workflow.draft_workspaces.add_state_from_output",
        errors=[WorkflowRpcError],
    )
    async def workflow_draft_workspaces_add_state_from_output(
        params: AddStateFromOutputParams = RpcParams(),
    ) -> dict[str, Any]:
        try:
            return await server.api.add_state_schema_from_output(
                workspace_id=params.workspace_id,
                revision=params.revision,
                step_id=params.step_id,
                output_field=params.output_field,
                state_path=params.state_path,
            )
        except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
            raise_workflow_rpc_error(exc)
```

In `src/wf_transport_rpc_http/client/drafts.py`, add:

```python
    async def add_state_schema_from_output(
        self: RpcCaller,
        *,
        workspace_id: str,
        revision: int,
        step_id: str,
        output_field: str,
        state_path: str,
    ) -> dict[str, Any]:
        return await self._call(
            "workflow.draft_workspaces.add_state_from_output",
            {
                "workspace_id": workspace_id,
                "revision": revision,
                "step_id": step_id,
                "output_field": output_field,
                "state_path": state_path,
            },
        )
```

- [ ] **Step 5: Run tests to verify green**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_app.py::test_rpc_draft_workspace_focused_edit_methods tests/wf_transport_rpc_http/test_client.py::test_rpc_client_draft_workspace_focused_edit_methods -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
git commit -m "feat: expose draft state schema helper over rpc"
```

---

## Task 4: MCP Workflow Tool Surface

**Files:**
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `tests/wf_mcp/server/test_config.py`

- [ ] **Step 1: Write failing schema exposure test**

In `tests/wf_mcp/server/test_config.py`, near existing focused workflow tool schema assertions, add:

```python
            state_from_output_schema = tools_by_name[
                "wf.workflow.add_state_from_output"
            ].inputSchema
            state_request = state_from_output_schema["properties"]["request"]
            assert "output_field" in state_request["properties"]
            assert "state_path" in state_request["properties"]
```

- [ ] **Step 2: Run test to verify red**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_config.py -q
```

Expected: missing tool.

- [ ] **Step 3: Add request model and tool**

In `src/wf_mcp/workflow_surface/models.py`, add:

```python
class AddStateFromOutputRequest(BaseModel):
    """Typed MCP request for declaring a state field from a step output schema."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    step_id: str = Field(description="Draft step id whose capability output is used.")
    output_field: str = Field(
        description="Top-level output field to copy, for example after."
    )
    state_path: str = Field(
        description="Root state path to declare, for example state.after."
    )
```

In `src/wf_mcp/workflow_surface/tools.py`, import `AddStateFromOutputRequest` and register after `set_step_output_map`:

```python
    @server.tool(
        name="wf.workflow.add_state_from_output",
        title="Add State From Output",
        description=(
            "Declare one root state field by copying a draft step capability output "
            "field schema, including local $defs/definitions when present."
        ),
    )
    async def add_state_from_output(
        request: AddStateFromOutputRequest,
    ) -> DraftWorkspaceResult:
        return DraftWorkspaceResult.model_validate(
            await handlers.add_state_schema_from_output(
                workspace_id=request.workspace_id,
                revision=request.revision,
                step_id=request.step_id,
                output_field=request.output_field,
                state_path=request.state_path,
            )
        )
```

- [ ] **Step 4: Run test to verify green**

Run:

```powershell
uv run pytest tests/wf_mcp/server/test_config.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py tests/wf_mcp/server/test_config.py
git commit -m "feat: expose draft state schema helper to mcp"
```

---

## Task 5: CLI Command And Help

**Files:**
- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `tests/wf_cli/test_remote_target.py`
- Modify: `tests/wf_cli/test_app.py`

- [ ] **Step 1: Add failing CLI behavior test**

In `tests/wf_cli/test_remote_target.py`, inside `test_wf_draft_focused_edit_commands_use_rpc_target`, add after map merge calls:

```python
    state_added = runner.invoke(
        app,
        [
            *base_args,
            "draft",
            "add-state-from-output",
            "focused_ws",
            "--revision",
            "7",
            "--step",
            "call",
            "--output",
            "value",
            "--state",
            "state.extra_value",
        ],
    )
```

Update the assertions:

```python
    assert state_added.exit_code == 0, state_added.output
```

Update inspected revision if needed, and assert:

```python
    assert "extra_value" in draft["state_schema"]["properties"]
```

- [ ] **Step 2: Add failing CLI help test**

In `tests/wf_cli/test_app.py`, add:

```python
def test_wf_draft_add_state_from_output_help_explains_schema_copy() -> None:
    result = runner.invoke(app, ["draft", "add-state-from-output", "--help"])

    assert result.exit_code == 0
    help_text = " ".join(result.output.split())
    assert "capability output field schema" in help_text
    assert "$defs" in help_text
    assert "draft validate" in help_text
```

- [ ] **Step 3: Run tests to verify red**

Run:

```powershell
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_draft_focused_edit_commands_use_rpc_target tests/wf_cli/test_app.py::test_wf_draft_add_state_from_output_help_explains_schema_copy -q
```

Expected: missing command.

- [ ] **Step 4: Implement CLI command**

In `src/wf_cli/commands/drafts.py`, add after `set-output`:

```python
@app.command("add-state-from-output")
def add_state_from_output(
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
    """Copy one capability output field schema into draft state_schema.

    Use this before mapping a step output into a new state field. The command
    reads the selected draft step's capability output schema, copies the
    requested output property schema, and preserves local $defs/definitions so
    JSON Schema refs remain valid.

    Run `wf draft validate <workspace_id>` after adding state schema fields.
    """
    context = load_cli_context(ctx)
    emit_json(
        run_cli_operation(
            context,
            context.handlers.add_state_schema_from_output(
                workspace_id=workspace_id,
                revision=revision,
                step_id=step_id,
                output_field=output_field,
                state_path=state_path,
            ),
        )
    )
```

- [ ] **Step 5: Run tests to verify green**

Run:

```powershell
uv run pytest tests/wf_cli/test_remote_target.py::test_wf_draft_focused_edit_commands_use_rpc_target tests/wf_cli/test_app.py::test_wf_draft_add_state_from_output_help_explains_schema_copy -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_cli/commands/drafts.py tests/wf_cli/test_remote_target.py tests/wf_cli/test_app.py
git commit -m "feat: add draft state schema cli helper"
```

---

## Task 6: Docs, Skills, And Final Verification

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `docs/current_roadmap.md`

- [ ] **Step 1: Update `docs/wf_cli.md`**

Under Draft Workspaces focused edit commands, add:

```markdown
wf draft add-state-from-output concat_ws --revision 5 --step call --output value --state state.value
```

Add this paragraph:

```markdown
Before mapping a step output to a new state field, the state schema must declare
that root field. `add-state-from-output` copies the selected step capability's
top-level output property schema into `state_schema.properties`, including local
`$defs` / `definitions` blocks needed by `$ref` schemas. It only declares the
state field; still run `set-output` or `draft patch` to write values into that
field, then run `wf draft validate`.
```

- [ ] **Step 2: Update skills**

In `skills/wf-cli/SKILL.md`, add command:

```bash
wf draft add-state-from-output <workspace_id> --revision <n> --step <step_id> --output <field> --state state.<field>
```

Add rule:

```markdown
If mapping `LOCAL_SOURCE=state.new_field`, declare the state field first with
`draft add-state-from-output` when the schema should match a capability output
field. Do not hand-copy `$defs` unless the helper cannot express the shape.
```

In `skills/wf-workflow/references/draft-workspaces.md`, add the same command and explain:

```markdown
Use `add-state-from-output` when the target state field should reuse a capability
output schema. This prevents dangling `$ref` values by copying local `$defs` /
`definitions` with the selected property schema.
```

In `skills/wf-workflow/references/workflow-lifecycle.md`, update step 5:

```markdown
- Before output-mapping into a new state field, declare it with
  `add-state-from-output` when it should mirror a capability output property.
```

- [ ] **Step 3: Update roadmap**

In `docs/current_roadmap.md`, add under Product Smoke/Status UX completed bullets:

```markdown
- Completed: `wf draft add-state-from-output` projects capability output
  property schemas into draft state schemas, preserving `$defs` / `definitions`
  for schema refs and reducing brittle whole-`state_schema` patches.
```

- [ ] **Step 4: Run final verification**

Run:

```powershell
uv run pytest tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py::test_rpc_draft_workspace_focused_edit_methods tests/wf_transport_rpc_http/test_client.py::test_rpc_client_draft_workspace_focused_edit_methods tests/wf_cli/test_remote_target.py::test_wf_draft_focused_edit_commands_use_rpc_target tests/wf_cli/test_app.py::test_wf_draft_add_state_from_output_help_explains_schema_copy tests/wf_mcp/server/test_config.py -q
uv run ruff check src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py src/wf_cli/commands/drafts.py tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py tests/wf_cli/test_app.py tests/wf_mcp/server/test_config.py
uv run ruff format --check src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py src/wf_cli/commands/drafts.py tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py tests/wf_cli/test_app.py tests/wf_mcp/server/test_config.py
uv run basedpyright --level error src/wf_api/schema_projection.py src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py src/wf_cli/commands/drafts.py tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_remote_target.py tests/wf_cli/test_app.py tests/wf_mcp/server/test_config.py
```

Expected:

- pytest passes
- ruff clean
- ruff format clean
- basedpyright 0 errors

- [ ] **Step 5: Commit docs**

```powershell
git add docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/draft-workspaces.md skills/wf-workflow/references/workflow-lifecycle.md docs/current_roadmap.md
git commit -m "docs: document draft state schema helper"
```

---

## Self-Review Checklist

- This plan does not add a naive `add-state-field`; it projects real capability output schemas.
- The first slice copies local `$defs` / `definitions` wholesale with conflict checks. It does not try to rewrite refs or do semantic JSON Schema compatibility.
- The helper is root-state-field only. Nested state paths are rejected with a clear error.
- Revision checks stay in the existing `patch_draft_workspace` path.
- The helper is exposed consistently across API, JSON-RPC, RPC client, MCP tool, and CLI.
- Docs tell agents to run `wf draft validate` after schema/map edits.
