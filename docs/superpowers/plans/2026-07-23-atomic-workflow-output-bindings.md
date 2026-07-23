# Atomic Workflow Output Bindings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one revision-checked canonical workflow-output binding replacement operation across Python, JSON-RPC, MCP, and CLI, with nested schema projection, literal validation, and unchanged empty-list fallback semantics.

**Architecture:** Keep semantic authoring in `WorkflowDraftAuthoringApi`, where revision precedence and atomic patches already live. Reuse the existing `InputBinding` union and deepen `wf_api.schema_projection` only enough to give literal validation neutral diagnostic labels. RPC, MCP, and CLI pass the ordered canonical list without lowering through the compatibility map.

**Tech Stack:** Python 3.14, Pydantic 2, JSON Schema Draft 2020-12, Typer, FastAPI JSON-RPC, FastMCP, pytest, Ruff, basedpyright.

## Global Constraints

- Do not change persisted `WorkflowDraft.output`, core `Workflow.output`, runtime output projection, or end-node behavior.
- Empty canonical bindings restore the existing same-name state fallback; they do not mean an always-empty public output.
- Reuse `InputPathBinding | InputValueBinding`; do not add another binding model.
- Do not infer JSON Schema from literal values or `context.*` paths.
- Input/state path projection and literal validation must stay in `wf_api.schema_projection` helpers.
- Preserve binding order exactly and reject equal or ancestor/descendant output targets.
- Check revision before semantic path/schema inspection; retain the mutation-time revision guard.
- Keep `set_workflow_output_map(...)` and `--merge --map` as compatibility-only behavior.
- Python baseline is 3.14. Use current syntax and add comments around non-obvious reference/root behavior.
- Scope tests to the files named by each task; run the complete plan matrix only in Task 5.

---

### Task 1: Canonical Python Authoring And Runtime Proof

**Files:**
- Modify: `src/wf_api/schema_projection.py`
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `tests/wf_api/test_schema_projection.py`
- Modify: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Consumes: `InputBinding`, `InputPathBinding`, `InputValueBinding`, `GraphSourcePath`, `LocalPath`, `schema_fragment_at_path(...)`, `schema_path_exists(...)`, `project_schema_path_to_schema_path(...)`, and `validate_json_value_at_schema_path(...)`.
- Produces: `WorkflowDraftAuthoringApi.set_workflow_output_bindings(*, workspace_id: str, revision: int, bindings: Sequence[InputBinding]) -> dict[str, Any]`.
- Produces: `validate_json_value_at_schema_path(..., schema_label: str = "capability input schema") -> None`, preserving existing callers through the default.

- [ ] **Step 1: Write failing neutral-label and referenced-target schema tests**

Add tests in `tests/wf_api/test_schema_projection.py` that pin the shared helper contract:

```python
def test_validate_json_value_uses_caller_schema_label() -> None:
    with pytest.raises(
        ValueError,
        match="workflow output schema",
    ):
        validate_json_value_at_schema_path(
            schema={
                "type": "object",
                "properties": {"format": {"type": "string"}},
            },
            parts=("missing",),
            value="markdown",
            label="bindings[0].value",
            schema_label="workflow output schema",
        )


def test_project_schema_path_updates_output_target_through_local_ref() -> None:
    projected = project_schema_path_to_schema_path(
        target_schema={
            "type": "object",
            "properties": {"report": {"$ref": "#/$defs/Report"}},
            "$defs": {
                "Report": {"type": "object", "properties": {}}
            },
        },
        source_schema={
            "type": "object",
            "properties": {"title": {"type": "string"}},
        },
        source_parts=("title",),
        target_parts=("report", "title"),
        allow_existing_equivalent=True,
    )

    assert projected["properties"]["report"] == {"$ref": "#/$defs/Report"}
    assert projected["$defs"]["Report"]["properties"]["title"] == {
        "type": "string"
    }
```

The second test protects the target-side `$ref` behavior introduced by the step-output slice while this operation begins relying on it directly.

- [ ] **Step 2: Run the schema tests and verify the neutral label test fails**

Run:

```bash
uv run pytest tests/wf_api/test_schema_projection.py -q
```

Expected: the existing referenced-target test passes and the new
`schema_label` call fails because the helper does not yet accept that keyword.

- [ ] **Step 3: Generalize the literal-validation diagnostic label**

Change `validate_json_value_at_schema_path(...)` in
`src/wf_api/schema_projection.py` without adding a second validator:

```python
def validate_json_value_at_schema_path(
    *,
    schema: JsonObject,
    parts: Sequence[str],
    value: object,
    label: str,
    schema_label: str = "capability input schema",
) -> None:
    """Validate one JSON-compatible literal against a selected schema path."""
    fragment = schema_fragment_at_path(
        schema,
        parts,
        label=schema_label,
    )
    path = ".".join(parts) or "."
    try:
        Draft202012Validator(fragment).validate(value)
    except ValidationError as exc:
        raise ValueError(
            f"{label} does not satisfy schema at {path!r}: {exc.message}"
        ) from exc
```

Run the schema test file again. Expected: PASS.

- [ ] **Step 4: Write failing canonical authoring tests**

In `tests/wf_api/test_drafts_service.py`, add a helper draft whose input, state,
and output schemas contain nested fields and whose output list initially is
empty. Add tests with these exact behavioral assertions:

```python
@pytest.mark.asyncio
async def test_set_workflow_output_bindings_projects_nested_paths_and_literals(
    tmp_path: Path,
) -> None:
    draft_api, service, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "workflow_outputs"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["state_schema"] = {
        "type": "object",
        "properties": {
            "report": {
                "type": "object",
                "properties": {"title": {"type": "string"}},
            }
        },
    }
    draft["output_schema"] = {
        "type": "object",
        "properties": {"format": {"type": "string"}},
    }
    draft["output"] = []
    await draft_api.create_draft_workspace(workspace_id="report", draft=draft)

    result = await authoring.set_workflow_output_bindings(
        workspace_id="report",
        revision=1,
        bindings=[
            InputPathBinding(
                path=GraphSourcePath.state("report", "title"),
                target=LocalPath.of("report", "title"),
            ),
            InputPathBinding(
                path=GraphSourcePath.state("report", "title"),
                target=LocalPath.of("audit", "title"),
            ),
            InputValueBinding(
                target=LocalPath.of("format"),
                value="markdown",
            ),
        ],
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="report",
        include_draft=True,
    )

    assert result["revision"] == 2
    assert inspected["draft"]["output"] == [
        {"path": "state.report.title", "target": "report.title"},
        {"path": "state.report.title", "target": "audit.title"},
        {"value": "markdown", "target": "format"},
    ]
    assert inspected["draft"]["output_schema"]["properties"]["report"][
        "properties"
    ]["title"] == {"type": "string"}
    assert inspected["draft"]["output_schema"]["properties"]["audit"][
        "properties"
    ]["title"] == {"type": "string"}
```

Add focused tests for the remaining contract, using field-level assertions:

- exact replacement and stable ordering;
- exact no-op with unchanged revision;
- `[]` clearing `/output` without deleting `output_schema`;
- nested `input.*` projection;
- whole `input` or `state` projection into one nested target;
- declared `context.*` target accepted without schema inference;
- missing context target rejected;
- literal string, object, array, and explicit `null` validation;
- literal target missing from `output_schema` rejected;
- root path target accepted only for an exactly equal complete schema;
- root literal requires a mapping and validates the complete output schema;
- root target overlaps any other target;
- duplicate and ancestor/descendant targets rejected;
- missing source reported before target overlap;
- incompatible existing target rejected;
- stale revision wins over every semantic error and leaves the draft unchanged.

Use one parameterized error test shaped like:

```python
@pytest.mark.parametrize(
    ("bindings", "message"),
    [
        (
            [
                InputPathBinding(
                    path=GraphSourcePath.state("missing"),
                    target=LocalPath.of("missing"),
                )
            ],
            r"bindings\[0\]\.path 'state\.missing' is not declared",
        ),
        (
            [
                InputValueBinding(
                    target=LocalPath.of("missing"),
                    value="x",
                )
            ],
            r"bindings\[0\]\.target 'missing' is not declared",
        ),
        (
            [
                InputPathBinding(
                    path=GraphSourcePath.state("report"),
                    target=LocalPath.of("report"),
                ),
                InputValueBinding(
                    target=LocalPath.of("report", "format"),
                    value="markdown",
                ),
            ],
            r"bindings\[0\]\.target 'report' overlaps bindings\[1\]",
        ),
    ],
)
async def test_set_workflow_output_bindings_rejects_without_mutation(
    tmp_path: Path,
    bindings: list[InputBinding],
    message: str,
) -> None:
    # Create the draft, snapshot include_draft=True, assert the error, then
    # assert the complete inspected workspace still equals the snapshot.
```

- [ ] **Step 5: Run focused authoring tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -q -k "workflow_output_bindings"
```

Expected: FAIL because `WorkflowDraftAuthoringApi` has no canonical workflow
output method.

- [ ] **Step 6: Implement the canonical authoring operation**

In `src/wf_api/draft_authoring.py`, import `Mapping`, `InputBinding`,
`InputPathBinding`, `InputValueBinding`, `GraphSourcePath`, `LocalPath`, and the
shared schema helpers. Add focused private helpers rather than embedding all
path logic in the method:

```python
def _workflow_source_schema(
    draft: Mapping[str, Any],
    path: GraphSourcePath,
) -> dict[str, Any] | None:
    """Return the declared graph-source schema, or None for context paths."""
    if path.root == "input":
        key = "input_schema"
    elif path.root == "state":
        key = "state_schema"
    else:
        return None
    value = draft.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"draft {key} must be an object")
    return value


def _overlapping_workflow_output_targets_error(
    bindings: Sequence[InputBinding],
) -> ValueError:
    for left_index, left in enumerate(bindings):
        for right_index in range(left_index + 1, len(bindings)):
            right = bindings[right_index]
            if paths_overlap(left.target, right.target):
                return ValueError(
                    f"bindings[{left_index}].target {str(left.target)!r} "
                    f"overlaps bindings[{right_index}].target "
                    f"{str(right.target)!r}"
                )
    raise AssertionError("overlap error requested without overlapping targets")
```

Implement the method on `WorkflowDraftAuthoringApi` with this ordering:

```python
async def set_workflow_output_bindings(
    self,
    *,
    workspace_id: str,
    revision: int,
    bindings: Sequence[InputBinding],
) -> dict[str, Any]:
    """Replace canonical workflow output bindings atomically."""
    checked = self._workspace_if_revision_matches(
        workspace_id=workspace_id,
        revision=revision,
    )
    if isinstance(checked, dict):
        return checked
    workspace = checked
    output_schema = _draft_schema(workspace.draft, "output_schema")

    source_schemas: dict[int, dict[str, Any]] = {}
    source_fragments: dict[int, dict[str, Any]] = {}
    for index, binding in enumerate(bindings):
        if not isinstance(binding, InputPathBinding):
            continue
        source_schema = _workflow_source_schema(workspace.draft, binding.path)
        if source_schema is None:
            continue
        try:
            source_schemas[index] = source_schema
            source_fragments[index] = schema_fragment_at_path(
                source_schema,
                binding.path.parts,
                label=f"workflow {binding.path.root} schema",
            )
        except ValueError as exc:
            raise ValueError(
                f"bindings[{index}].path {str(binding.path)!r} "
                f"is not declared: {exc}"
            ) from exc

    if has_overlapping_paths(binding.target for binding in bindings):
        raise _overlapping_workflow_output_targets_error(bindings)

    projected = output_schema
    for index, binding in enumerate(bindings):
        target_parts = binding.target.parts
        if isinstance(binding, InputPathBinding):
            source_schema = source_schemas.get(index)
            if source_schema is None:
                if not schema_path_exists(projected, target_parts):
                    raise ValueError(
                        f"bindings[{index}].path {str(binding.path)!r} "
                        "requires a declared output target"
                    )
                continue
            if not target_parts:
                if projected != source_fragments[index]:
                    raise ValueError(
                        f"bindings[{index}].target '.' already has an "
                        "incompatible schema"
                    )
                continue
            projected = project_schema_path_to_schema_path(
                target_schema=projected,
                source_schema=source_schema,
                source_parts=binding.path.parts,
                target_parts=target_parts,
                allow_existing_equivalent=True,
            )
            continue

        if not isinstance(binding, InputValueBinding):
            raise TypeError(f"unsupported workflow output binding {binding!r}")
        if not target_parts and not isinstance(binding.value, Mapping):
            raise ValueError(
                f"bindings[{index}].value for root target must be an object"
            )
        if not schema_path_exists(projected, target_parts):
            raise ValueError(
                f"bindings[{index}].target {str(binding.target)!r} is not declared"
            )
        validate_json_value_at_schema_path(
            schema=projected,
            parts=target_parts,
            value=binding.value,
            label=f"bindings[{index}].value",
            schema_label="workflow output schema",
        )

    payload = [binding.model_dump(mode="json") for binding in bindings]
    if workspace.draft.get("output", []) == payload and projected == output_schema:
        return summarize_draft_workspace(workspace)

    patch: list[dict[str, Any]] = []
    if projected != output_schema:
        patch.append({"op": "replace", "path": "/output_schema", "value": projected})
    patch.append({"op": "replace", "path": "/output", "value": payload})
    return await self.drafts.patch_draft_workspace(
        workspace_id=workspace_id,
        revision=revision,
        patch=patch,
    )
```

Do not copy this mechanically if an existing helper provides the same behavior;
reuse it. Preserve the specified validation order and wrap projection failures
with `bindings[index]` context.

- [ ] **Step 7: Add compile-and-execute coverage**

Add a test that creates a valid draft, invokes the new authoring method, compiles
with `compile_draft_workspace`, runs through `WfMcpService.run_workflow_from_plan`,
and asserts:

```python
assert run.error is None
assert run.output == {
    "report": {"title": "Thesis"},
    "audit": {"title": "Thesis"},
    "format": "markdown",
}
```

Add a second execution assertion for a cleared explicit list: declare a
top-level output field matching state, clear bindings, compile/run, and prove the
existing implicit fallback still returns that state field.

- [ ] **Step 8: Run Task 1 verification**

Run:

```bash
uv run pytest tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py -q
uv run ruff check src/wf_api/schema_projection.py src/wf_api/draft_authoring.py tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py
uv run basedpyright --level error src/wf_api/schema_projection.py src/wf_api/draft_authoring.py
```

Expected: all pass. If the installed basedpyright does not accept file paths,
run the repository-wide `uv run basedpyright --level error` instead.

- [ ] **Step 9: Review and commit Task 1**

Review the Task 1 diff against the spec, especially root-target equality,
context behavior, stale-revision precedence, and no mutation on errors. Then:

```bash
git add src/wf_api/schema_projection.py src/wf_api/draft_authoring.py tests/wf_api/test_schema_projection.py tests/wf_api/test_drafts_service.py
git commit -m "feat: replace canonical workflow output bindings"
```

---

### Task 2: Public API And JSON-RPC Transport

**Files:**
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`

**Interfaces:**
- Consumes: Task 1's `WorkflowDraftAuthoringApi.set_workflow_output_bindings(...)`.
- Produces: `WorkflowApiSurface.set_workflow_output_bindings(...)`, `WorkflowApi.set_workflow_output_bindings(...)`, `SetWorkflowOutputBindingsParams`, JSON-RPC method `workflow.draft_workspaces.set_workflow_output_bindings`, and `RpcWorkflowApiClient.set_workflow_output_bindings(...)`.

- [ ] **Step 1: Write failing RPC model and endpoint tests**

In `tests/wf_transport_rpc_http/test_app.py`, add an end-to-end request using a
real local server:

```python
async def test_rpc_set_workflow_output_bindings_preserves_union_and_order(
    tmp_path,
) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        created = await _rpc(
            client,
            "workflow.draft_workspaces.create_from_capability",
            {
                "workspace_id": "output_ws",
                "capability_name": "wf.std.constant",
                "name": "output_test",
            },
        )
        result = await _rpc(
            client,
            "workflow.draft_workspaces.set_workflow_output_bindings",
            {
                "workspace_id": "output_ws",
                "revision": created["result"]["revision"],
                "bindings": [
                    {"path": "state.value", "target": "value"},
                    {"path": "state.value", "target": "audit.value"},
                ],
            },
        )

    assert result["result"]["revision"] == 2
```

Use a fixture with a declared literal target for a second request and assert the
stored list preserves a path binding followed by a value binding. Add malformed
requests proving `path` plus `value`, missing `target`, extra fields, and invalid
roots fail with JSON-RPC `-32602` before semantic logic.

- [ ] **Step 2: Write the failing remote client test**

In `tests/wf_transport_rpc_http/test_client.py`, add:

```python
async def test_rpc_client_set_workflow_output_bindings_preserves_union_order(
    rpc_client,
    calls,
) -> None:
    bindings: list[InputBinding] = [
        InputPathBinding(
            path=GraphSourcePath.state("value"),
            target=LocalPath.of("value"),
        ),
        InputValueBinding(
            target=LocalPath.of("format"),
            value="markdown",
        ),
    ]

    await rpc_client.set_workflow_output_bindings(
        workspace_id="ws",
        revision=3,
        bindings=bindings,
    )

    assert calls[-1]["method"] == (
        "workflow.draft_workspaces.set_workflow_output_bindings"
    )
    assert calls[-1]["params"]["bindings"] == [
        {"path": "state.value", "target": "value"},
        {"value": "markdown", "target": "format"},
    ]
```

Adapt the fixture names to the existing client test harness; keep the assertions
field-level.

- [ ] **Step 3: Run RPC tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q -k "workflow_output_bindings"
```

Expected: FAIL because the params model, endpoint, and client method are absent.

- [ ] **Step 4: Add the public surface and local service delegation**

Add this method to `WorkflowApiSurface` in `src/wf_api/surface.py`:

```python
async def set_workflow_output_bindings(
    self,
    *,
    workspace_id: str,
    revision: int,
    bindings: Sequence[InputBinding],
) -> dict[str, Any]: ...
```

Add the concrete method to `WorkflowApi` in `src/wf_api/service.py`:

```python
async def set_workflow_output_bindings(
    self,
    *,
    workspace_id: str,
    revision: int,
    bindings: Sequence[InputBinding],
) -> dict[str, Any]:
    return await self.draft_authoring.set_workflow_output_bindings(
        workspace_id=workspace_id,
        revision=revision,
        bindings=bindings,
    )
```

Keep `set_workflow_output_map(...)` unchanged and adjacent as the compatibility
surface.

- [ ] **Step 5: Add the typed RPC request, endpoint, and client**

In `src/wf_transport_rpc_http/models.py`:

```python
class SetWorkflowOutputBindingsParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    bindings: list[InputBinding]
```

Register the endpoint in `src/wf_transport_rpc_http/methods/drafts.py` adjacent
to `set_workflow_output_map`:

```python
@entrypoint.method(
    name="workflow.draft_workspaces.set_workflow_output_bindings",
    errors=[WorkflowRpcError],
)
async def workflow_draft_workspaces_set_workflow_output_bindings(
    params: SetWorkflowOutputBindingsParams = RpcParams(),
) -> dict[str, Any]:
    try:
        return await server.api.set_workflow_output_bindings(
            workspace_id=params.workspace_id,
            revision=params.revision,
            bindings=params.bindings,
        )
    except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
        raise_workflow_rpc_error(exc)
```

Add the client method in `src/wf_transport_rpc_http/client/drafts.py`:

```python
async def set_workflow_output_bindings(
    self: RpcCaller,
    *,
    workspace_id: str,
    revision: int,
    bindings: Sequence[InputBinding],
) -> dict[str, Any]:
    return await self._call(
        "workflow.draft_workspaces.set_workflow_output_bindings",
        {
            "workspace_id": workspace_id,
            "revision": revision,
            "bindings": [
                binding.model_dump(mode="json") for binding in bindings
            ],
        },
    )
```

Export `SetWorkflowOutputBindingsParams` from
`src/wf_transport_rpc_http/__init__.py` in both import and `__all__` lists.

- [ ] **Step 6: Run Task 2 verification**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q
uv run basedpyright --level error
```

Expected: all pass and every `WorkflowApiSurface` implementation conforms.

- [ ] **Step 7: Review and commit Task 2**

Review request validation, canonical order, and local/remote interface parity.
Then:

```bash
git add src/wf_api/surface.py src/wf_api/service.py src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/client/drafts.py src/wf_transport_rpc_http/__init__.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py
git commit -m "feat: expose workflow output bindings over rpc"
```

---

### Task 3: MCP Workflow Surface

**Files:**
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_mcp/proxy/runtime.py`
- Modify: `tests/wf_mcp/workflow_surface/test_drafts.py`
- Modify: `tests/wf_mcp/server/test_tools.py`
- Modify: `tests/wf_mcp/server/test_config.py`

**Interfaces:**
- Consumes: Task 2's public `set_workflow_output_bindings(...)` method and the existing `DraftInputBindings` alias.
- Produces: `SetWorkflowOutputBindingsRequest` and MCP tool `wf.workflow.set_workflow_output_bindings`.

- [ ] **Step 1: Write failing MCP request-model tests**

In `tests/wf_mcp/workflow_surface/test_drafts.py`, add:

```python
def test_set_workflow_output_bindings_request_preserves_union_order() -> None:
    request = SetWorkflowOutputBindingsRequest.model_validate(
        {
            "workspace_id": "ws",
            "revision": 2,
            "bindings": [
                {"path": "state.title", "target": "report.title"},
                {"value": "markdown", "target": "format"},
            ],
        }
    )

    assert [binding.model_dump(mode="json") for binding in request.bindings] == [
        {"path": "state.title", "target": "report.title"},
        {"value": "markdown", "target": "format"},
    ]
```

Add a malformed-record test with both `path` and `value`, and assert Pydantic
rejects the extra union field.

- [ ] **Step 2: Write failing tool-registration and invocation tests**

Extend the fake handler in `tests/wf_mcp/server/test_tools.py` with a call log for
`set_workflow_output_bindings`. Assert the tool inventory includes the new name,
then invoke the actual FastMCP tool through the existing test helper:

```python
result = await call_tool(
    server,
    "wf.workflow.set_workflow_output_bindings",
    {
        "request": {
            "workspace_id": "ws",
            "revision": 4,
            "bindings": [
                {"path": "state.title", "target": "report.title"},
                {"value": "markdown", "target": "format"},
            ],
        }
    },
)

assert result.isError is False
assert handler.calls[-1]["bindings"][0].path == GraphSourcePath.state("title")
assert handler.calls[-1]["bindings"][1].value == "markdown"
```

Update config/discovery expectations so the public tool count/name inventory is
explicit rather than only asserting a count.

- [ ] **Step 3: Run MCP tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_tools.py tests/wf_mcp/server/test_config.py -q -k "workflow_output_bindings or tools or config"
```

Expected: FAIL because the request and tool do not exist.

- [ ] **Step 4: Add the MCP request and tool**

In `src/wf_mcp/workflow_surface/models.py`:

```python
class SetWorkflowOutputBindingsRequest(BaseModel):
    """Replace the complete canonical workflow-output binding list."""

    workspace_id: WorkspaceId
    revision: int = Field(ge=1, description="Expected current workspace revision.")
    bindings: DraftInputBindings
```

In `src/wf_mcp/workflow_surface/tools.py`, register adjacent to the map tool:

```python
@server.tool(
    name="wf.workflow.set_workflow_output_bindings",
    title="Set Workflow Output Bindings",
    description=(
        "Replace the complete ordered workflow-output binding list with "
        "canonical path/value records."
    ),
)
async def set_workflow_output_bindings(
    request: SetWorkflowOutputBindingsRequest,
) -> DraftWorkspaceResult:
    return DraftWorkspaceResult.model_validate(
        await handlers.set_workflow_output_bindings(
            workspace_id=request.workspace_id,
            revision=request.revision,
            bindings=request.bindings,
        )
    )
```

Add the new name to the explicit workflow proxy allow-list in
`src/wf_mcp/proxy/runtime.py`. Preserve the existing map tool.

- [ ] **Step 5: Run Task 3 verification**

Run:

```bash
uv run pytest tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_tools.py tests/wf_mcp/server/test_config.py -q
uv run basedpyright --level error
```

Expected: all pass.

- [ ] **Step 6: Review and commit Task 3**

Review actual tool invocation, discovery visibility, request validation, and
ordered union preservation. Then:

```bash
git add src/wf_mcp/workflow_surface/models.py src/wf_mcp/workflow_surface/tools.py src/wf_mcp/proxy/runtime.py tests/wf_mcp/workflow_surface/test_drafts.py tests/wf_mcp/server/test_tools.py tests/wf_mcp/server/test_config.py
git commit -m "feat: expose workflow output bindings to mcp"
```

---

### Task 4: Canonical CLI Replacement

**Files:**
- Modify: `src/wf_cli/commands/draft_options.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `tests/wf_cli/test_app.py`
- Modify: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: Task 2's local/remote `set_workflow_output_bindings(...)` method.
- Produces: canonical `wf draft set-workflow-output` modes `--map`, `--value`, `--bindings-file`, and `--clear`; preserves compatibility-only `--merge --map`.

- [ ] **Step 1: Write failing parser tests**

In `tests/wf_cli/test_app.py`, add parser tests proving:

```python
def test_parse_workflow_output_flags_preserves_path_then_literal_order() -> None:
    bindings = [
        *parse_workflow_output_binding_flags(
            [
                "state.title=report.title",
                "state.title=audit.title",
            ]
        ),
        *parse_workflow_output_value_flags(
            ['format="markdown"', "optional=null"]
        ),
    ]

    assert [binding.model_dump(mode="json") for binding in bindings] == [
        {"path": "state.title", "target": "report.title"},
        {"path": "state.title", "target": "audit.title"},
        {"value": "markdown", "target": "format"},
        {"value": None, "target": "optional"},
    ]
```

Add bindings-file tests for a mixed canonical array and malformed unions. Pin
compact `typer.BadParameter` messages for invalid graph roots, `local.`-prefixed
targets, invalid JSON, and non-array files.

- [ ] **Step 2: Extract shared input-shaped CLI parsers**

In `src/wf_cli/commands/draft_options.py`, avoid duplicating the step-input
parser. Extract private helpers parameterized only by audience wording:

```python
def _parse_input_path_binding_flags(
    values: list[str] | None,
    *,
    target_label: str,
) -> list[InputPathBinding]:
    # Parse GRAPH_SOURCE=LOCAL_TARGET in caller order, reject local.-prefixed
    # targets, and construct typed bindings.


def _parse_input_value_binding_flags(
    values: list[str] | None,
    *,
    target_label: str,
) -> list[InputValueBinding]:
    # Parse LOCAL_TARGET=JSON, preserving explicit null and embedded '='.
```

Keep existing public step-input parser names as wrappers. Add workflow-output
wrappers with accurate messages:

```python
def parse_workflow_output_binding_flags(
    values: list[str] | None,
) -> list[InputPathBinding]:
    return _parse_input_path_binding_flags(
        values,
        target_label="workflow-output",
    )


def parse_workflow_output_value_flags(
    values: list[str] | None,
) -> list[InputValueBinding]:
    return _parse_input_value_binding_flags(
        values,
        target_label="workflow-output",
    )


def parse_workflow_output_bindings_file(path: Path) -> list[InputBinding]:
    """Read an ordered canonical workflow-output binding list."""
    try:
        return _INPUT_BINDINGS_ADAPTER.validate_python(
            parse_json_file(path, option_name="--bindings-file")
        )
    except ValidationError as exc:
        raise validation_error_as_bad_parameter(exc) from exc
```

Do not change accepted step-input syntax or its existing error assertions.

- [ ] **Step 3: Write failing command tests**

Add local CLI tests that use a fake handler with separate canonical and map call
logs. Cover:

```python
result = runner.invoke(
    app,
    [
        "draft",
        "set-workflow-output",
        "report_ws",
        "--revision",
        "4",
        "--map",
        "state.title=report.title",
        "--map",
        "state.title=audit.title",
        "--value",
        'format="markdown"',
    ],
)

assert result.exit_code == 0, result.output
assert [binding.model_dump(mode="json") for binding in canonical_calls[0][
    "bindings"
]] == [
    {"path": "state.title", "target": "report.title"},
    {"path": "state.title", "target": "audit.title"},
    {"value": "markdown", "target": "format"},
]
assert map_calls == []
```

Add tests for:

- `--bindings-file` exact order;
- `--clear` sending `bindings=[]`;
- no selected mode failing before `load_cli_context`;
- `--bindings-file` and `--clear` mutually exclusive with convenience flags;
- `--merge --value`, `--merge --bindings-file`, and `--merge --clear` rejected;
- `--merge --map` invoking only `set_workflow_output_map(..., merge=True)`;
- help text naming canonical replacement, literals, fallback, export, and lossy
  compatibility behavior.

In `tests/wf_cli/test_remote_target.py`, add a real JSON-RPC-target test and
assert the captured method is
`workflow.draft_workspaces.set_workflow_output_bindings` with the exact ordered
mixed binding list. Keep a remote compatibility test for `--merge --map`.

- [ ] **Step 4: Run CLI tests and verify they fail**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q -k "workflow_output"
```

Expected: parser tests or command tests fail because canonical modes are absent.

- [ ] **Step 5: Replace the command's default path while retaining compatibility**

Update imports and the `set_workflow_output` Typer command in
`src/wf_cli/commands/drafts.py`. Parse modes before loading context:

```python
has_maps = bool(mapping)
has_values = bool(literal_values)
has_file = bindings_file is not None
has_convenience = has_maps or has_values

if not has_convenience and not has_file and not clear:
    raise typer.BadParameter(
        "provide --map, --value, --bindings-file, or --clear"
    )
if has_file and (has_convenience or clear):
    raise typer.BadParameter(
        "--bindings-file is mutually exclusive with --map, --value, and --clear"
    )
if clear and has_convenience:
    raise typer.BadParameter(
        "--clear is mutually exclusive with --map and --value"
    )
if merge and (has_values or has_file or clear):
    raise typer.BadParameter(
        "--merge is supported only for compatibility map-only edits"
    )

if merge:
    output_map = _parse_map_flags(mapping)
    bindings = None
else:
    output_map = None
    bindings = (
        parse_workflow_output_bindings_file(bindings_file)
        if bindings_file is not None
        else []
        if clear
        else [
            *parse_workflow_output_binding_flags(mapping),
            *parse_workflow_output_value_flags(literal_values),
        ]
    )

context = load_cli_context(ctx)
operation = (
    context.handlers.set_workflow_output_map(
        workspace_id=workspace_id,
        revision=revision,
        output_map=output_map,
        merge=True,
    )
    if merge
    else context.handlers.set_workflow_output_bindings(
        workspace_id=workspace_id,
        revision=revision,
        bindings=bindings,
    )
)
emit_json(run_cli_operation(context, operation))
```

Use assertions or explicit branches to satisfy basedpyright narrowing without
`cast(Any, ...)`. Rewrite the docstring/help so `--clear` explicitly says it
restores implicit same-name state fallback rather than promising empty output.

- [ ] **Step 6: Run Task 4 verification**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
uv run basedpyright --level error
```

Expected: all pass.

- [ ] **Step 7: Review and commit Task 4**

Review mode exclusivity, parsing-before-context, flag ordering, local/remote
parity, and compatibility isolation. Then:

```bash
git add src/wf_cli/commands/draft_options.py src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
git commit -m "feat: replace workflow output bindings from cli"
```

---

### Task 5: Documentation, Issue State, Review, And Final Verification

**Files:**
- Modify: `ISSUES.md`
- Modify: `docs/wf_cli.md`
- Modify: `docs/workflow_drafts.md`
- Modify: `docs/workflow_capabilities.md`
- Modify: `docs/wf_mcp_operator_manual.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `docs/current_roadmap.md`
- Move: `docs/superpowers/plans/2026-07-23-atomic-workflow-output-bindings.md` to `docs/historical/superpowers/plans/2026-07-23-atomic-workflow-output-bindings.md`

**Interfaces:**
- Consumes: verified behavior from Tasks 1-4.
- Produces: current user/agent documentation, accurate issue state, completed roadmap entry, archived checked plan, and final review evidence.

- [ ] **Step 1: Update issue state without closing compatibility-map loss**

In `ISSUES.md`:

- check the focused workflow-output literal binding issue;
- check the nested workflow-output schema projection issue;
- leave compatibility step input/output map loss open;
- preserve focused step update and TypeScript parity as open;
- state that canonical workflow-output replacement preserves path/value union
  order while `set_workflow_output_map` remains compatibility-only.

- [ ] **Step 2: Update live CLI and workflow docs**

Update `docs/wf_cli.md` and `docs/workflow_drafts.md` with all canonical modes:

```bash
wf draft set-workflow-output WS --revision 4 \
  --map state.report.title=report.title \
  --value format='"markdown"'

wf draft inspect WS --include-draft |
  jq '.draft.output' > output-bindings.json

wf draft set-workflow-output WS --revision 5 \
  --bindings-file output-bindings.json

wf draft set-workflow-output WS --revision 6 --clear
```

Explain:

- path/value bindings are canonical ordered records;
- nested input/state sources project missing nested output schemas;
- literals and context paths require declared output targets;
- `--clear` restores implicit same-name state fallback;
- `--merge --map` is compatibility-only and potentially lossy.

Update operation inventories in `docs/workflow_capabilities.md` and
`docs/wf_mcp_operator_manual.md` with both
`workflow.draft_workspaces.set_workflow_output_bindings` and
`wf.workflow.set_workflow_output_bindings`.

- [ ] **Step 3: Update agent instruction surfaces**

Update `skills/wf-cli/SKILL.md` and the two `wf-workflow` references with the
same canonical examples and decision rule:

```text
Use set-workflow-output without --merge when replacing the complete public
output projection. Use --bindings-file when exact path/value interleaving must
round-trip. Use --merge --map only when a lossy compatibility edit is acceptable.
```

Do not direct agents to implementation files or tests.

- [ ] **Step 4: Update roadmap and archive the checked plan**

Add a completed milestone to `docs/current_roadmap.md` linking to:

```text
historical/superpowers/plans/2026-07-23-atomic-workflow-output-bindings.md
```

Mark every completed checkbox in this plan, then move it to the historical path.
Search for the old active-plan path and update any live links:

```bash
rg -n "2026-07-23-atomic-workflow-output-bindings" docs skills README.md
```

- [ ] **Step 5: Run the complete focused matrix**

Run:

```bash
uv run pytest \
  tests/wf_api/test_schema_projection.py \
  tests/wf_api/test_drafts_service.py \
  tests/wf_transport_rpc_http/test_app.py \
  tests/wf_transport_rpc_http/test_client.py \
  tests/wf_mcp/workflow_surface/test_drafts.py \
  tests/wf_mcp/server/test_tools.py \
  tests/wf_mcp/server/test_config.py \
  tests/wf_cli/test_app.py \
  tests/wf_cli/test_remote_target.py \
  -q
```

Expected: PASS with only already-known dependency deprecation warnings.

If the Windows `uv.exe` app alias is broken, use the repository environment:

```powershell
.venv\Scripts\python.exe -m pytest -n 0 `
  tests/wf_api/test_schema_projection.py `
  tests/wf_api/test_drafts_service.py `
  tests/wf_transport_rpc_http/test_app.py `
  tests/wf_transport_rpc_http/test_client.py `
  tests/wf_mcp/workflow_surface/test_drafts.py `
  tests/wf_mcp/server/test_tools.py `
  tests/wf_mcp/server/test_config.py `
  tests/wf_cli/test_app.py `
  tests/wf_cli/test_remote_target.py `
  -q
```

- [ ] **Step 6: Run static verification**

Run:

```bash
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
git diff --check
```

Expected: all clean. Remove only verified workspace-local `.pytest-*` temporary
directories before Ruff if an interrupted pytest run left generated fixture
files under the repository root.

- [ ] **Step 7: Run independent whole-slice review**

Review from the pre-plan implementation base through `HEAD` against
`docs/superpowers/specs/2026-07-23-atomic-workflow-output-bindings-design.md`.
Require findings first with severity and file/line references. Specifically ask
the reviewer to inspect:

- implicit fallback after `[]`;
- literal no-inference behavior;
- context target requirements;
- root target equality and overlap;
- nested `$ref` projection;
- stale revision and no-op semantics;
- path/value ordering through RPC, MCP, and CLI;
- compatibility `--merge --map` isolation;
- live docs and issue truthfulness.

Fix all Critical and Important findings, rerun affected tests/static checks, and
repeat focused review until both Standards and Spec pass.

- [ ] **Step 8: Commit documentation and any final review fixes**

Commit the documentation/archive change:

```bash
git add ISSUES.md docs skills
git commit -m "docs: complete atomic workflow output bindings"
```

If review fixes modify production/tests, commit them separately with a scoped
message after rerunning verification. Finish with:

```bash
git status --short
git log --oneline -10
```

Expected: clean worktree and a readable task-level commit sequence.
