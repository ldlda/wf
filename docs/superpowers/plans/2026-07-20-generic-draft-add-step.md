# Generic Draft Step Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add typed draft-step insertion across the Python application API, JSON-RPC client/server, and a discoverable `wf draft add` CLI subgroup while closing interrupt and subgraph draft-model gaps.

**Architecture:** `wf_artifacts.drafts` remains the canonical persisted authoring model; the generic API accepts a validated `DraftStep` plus a separate map-key `step_id` and lowers one atomic semantic edit into JSON Patch. Python RPC carries the same typed shape, while type-specific Typer commands construct draft models and delegate through the protocol-neutral `WorkflowApiSurface`. Capability composition remains a specialized helper because it also projects schemas and bindings.

**Tech Stack:** Python 3.14, Pydantic v2, Typer, fastapi-jsonrpc, pytest/pytest-asyncio, Ruff, basedpyright.

## Global Constraints

- Follow `docs/superpowers/specs/2026-07-20-generic-draft-add-step-design.md`.
- Use `DraftStep`, not the core `Step` union, at draft/API/RPC boundaries.
- Keep `step_id` separate because draft identifiers are keys in `WorkflowDraft.steps`.
- Preserve one revision increment for step insertion plus requested incoming/outgoing routes.
- Preserve `add_step_from_capability` behavior, especially schema projection and complete multi-outcome routing.
- Remove `wf draft add-step`; do not add a compatibility alias without a real caller.
- Do not add TypeScript/Effect RPC parity or code generation in this slice.
- Structured conditions, clauses, cases, and schemas enter the CLI through JSON files.
- Add docstrings/comments around alias serialization, route validation, and other non-obvious seams.
- Use focused tests during tasks; run the full Python quality gate only in Task 7.

## File Map

- `src/wf_artifacts/drafts/models.py`: persisted draft variants, including typed interrupt contracts and subgraph payloads.
- `src/wf_artifacts/drafts/adapter.py`: lower draft variants into core nodes without artifact loading.
- `src/wf_api/draft_authoring.py`: generic semantic insertion, route validation, and `RouteSource`.
- `src/wf_api/service.py`, `src/wf_api/surface.py`: concrete and protocol-neutral public API methods.
- `src/wf_transport_rpc_http/models.py`: typed RPC parameter models.
- `src/wf_transport_rpc_http/methods/drafts.py`: JSON-RPC method registration.
- `src/wf_transport_rpc_http/client/drafts.py`: remote implementation of the same surface.
- `src/wf_cli/commands/draft_options.py`: shared parsing helpers used by existing and new draft commands.
- `src/wf_cli/commands/draft_add.py`: `wf draft add` Typer subgroup and variant construction.
- `src/wf_cli/commands/drafts.py`: subgroup registration and removal of the flat command.
- `tests/artifacts/test_draft_models.py`, `tests/artifacts/test_draft_adapter.py`: model/adapter parity.
- `tests/wf_api/test_drafts_service.py`: semantic application behavior and atomicity.
- `tests/wf_transport_rpc_http/test_app.py`, `tests/wf_transport_rpc_http/test_client.py`: transport round trips.
- `tests/wf_cli/test_app.py`, `tests/wf_cli/test_remote_target.py`: command UX and local/remote delegation.
- `docs/wf_cli.md`, `docs/wf_api_architecture.md`, `docs/current_roadmap.md`, `skills/wf-cli/SKILL.md`, `skills/wf-workflow/references/*.md`, `ISSUES.md`: live documentation and issue closure.

---

### Task 1: Complete Draft Interrupt And Subgraph Parity

**Files:**
- Modify: `src/wf_artifacts/drafts/models.py`
- Modify: `src/wf_artifacts/drafts/adapter.py`
- Modify: `src/wf_artifacts/drafts/__init__.py` if it exports individual variants
- Test: `tests/artifacts/test_draft_models.py`
- Test: `tests/artifacts/test_draft_adapter.py`

**Interfaces:**
- Produces: `DraftSubgraphPayload`, `DraftSubgraphStep`, expanded `DraftInterruptPayload`, and updated `DraftStep`.
- Produces: adapter lowering to `InterruptNode` and `SubgraphNode` with contracts intact.

- [ ] **Step 1: Write failing model tests for typed interrupt contracts**

Add a draft containing:

```python
"review": {
    "interrupt": {
        "kind": "issue_review",
        "request_schema": {
            "type": "object",
            "properties": {"issues": {"type": "array"}},
            "required": ["issues"],
        },
        "resume_schema": {
            "type": "object",
            "properties": {"selected": {"type": "array"}},
            "required": ["selected"],
        },
        "outcomes": ["submitted", "cancelled"],
    }
}
```

Assert the parsed fields and `model_dump(mode="json", by_alias=True)` preserve both schemas.

- [ ] **Step 2: Write failing model tests for subgraph boundaries**

Cover both workflow reference forms:

```python
{"subgraph": {"workflow": {"name": "child"}, "outcomes": ["ok"]}}
{"subgraph": {
    "workflow": {"artifact_id": "child_report", "version": 2},
    "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}}},
    "output_schema": {"type": "object", "properties": {"report": {"type": "string"}}},
    "input": [{"target": "topic", "path": "state.topic"}],
    "output": [{"source": "report", "target": "state.report"}],
    "outcomes": ["ok", "error"],
}}
```

Assert `DraftSubgraphStep` is selected and aliases round-trip.

- [ ] **Step 3: Run model tests and confirm red**

Run: `uv run pytest tests/artifacts/test_draft_models.py -q`

Expected: failures for forbidden interrupt schema fields and unknown `subgraph` kind.

- [ ] **Step 4: Implement the draft model fields and union member**

Import `SchemaRef` and `WorkflowRef`, add `subgraph` to `STEP_KIND_KEYS`, add the payload/step classes from the approved design, and append `DraftSubgraphStep` to `DraftStep`. Add to `DraftInterruptPayload`:

```python
request_schema: SchemaRef | None = None
resume_schema: SchemaRef | None = None
```

Add a field validator that accepts `None` and rejects a supplied schema unless
`schema.type == "object"`. This keeps untyped interrupts untyped while
validating explicit contracts at draft parse time.

- [ ] **Step 5: Write failing adapter tests**

Assert `build_workflow_from_draft` produces:

```python
assert review.request_schema == request_schema
assert review.resume_schema == resume_schema
assert child.workflow.artifact_id == "child_report"
assert child.workflow.version == 2
assert child.input_schema == input_schema
assert child.output_schema == output_schema
assert child.outcomes == ["ok", "error"]
```

- [ ] **Step 6: Implement adapter lowering**

Build interrupt keyword arguments so `request_schema`/`resume_schema` are
omitted when `None`; passing object defaults would incorrectly set
`has_explicit_contract`. For subgraphs, append a direct core node because
adapting a draft must not resolve an artifact:

```python
node = SubgraphNode(
    id=step_id,
    type="subgraph",
    **step.subgraph.model_dump(),
)
builder.nodes.append(node)
return node
```

Use an explicit `isinstance(step, DraftSubgraphStep)` branch before the final `TypeError`.

- [ ] **Step 7: Verify and commit**

Run:

```bash
uv run pytest tests/artifacts/test_draft_models.py tests/artifacts/test_draft_adapter.py -q
uv run basedpyright src/wf_artifacts tests/artifacts --level error
```

Expected: both pass.

Commit:

```bash
git add src/wf_artifacts/drafts tests/artifacts/test_draft_models.py tests/artifacts/test_draft_adapter.py
git commit -m "feat: complete draft step model parity"
```

---

### Task 2: Add Atomic Generic Draft-Step Insertion

**Files:**
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_api/__init__.py` if `RouteSource` is publicly exported
- Test: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Consumes: `DraftStep` including `DraftSubgraphStep` from Task 1.
- Produces: `RouteSource` and `WorkflowApiSurface.add_step(*, workspace_id, revision, step_id, step, incoming, routes)`.

- [ ] **Step 1: Rename the internal route value object**

Replace `DraftOutcomeRef` with:

```python
@dataclass(frozen=True)
class RouteSource:
    """One source step/outcome pair used for atomic route edits."""

    step_id: str
    outcome: str = DEFAULT_OK_OUTCOME
```

Update `handle_draft`, `WorkflowApi.handle_draft`, imports, and existing tests. Do not retain an alias because all callers are repository-owned.

- [ ] **Step 2: Write failing parameterized insertion tests**

Parameterize the nine payloads (`use`, `foreach`, `interrupt`, `join`, `end`, `when`, `choose`, `match`, `subgraph`). For each, call:

```python
step_adapter = TypeAdapter(DraftStep)
result = await api.add_step(
    workspace_id="draft_ws",
    revision=1,
    step_id="new_step",
    step=step_adapter.validate_python(step_payload),
)
```

Use a Pydantic `TypeAdapter(DraftStep)` in the test and assert revision `2` plus the canonical dumped payload under `draft.steps.new_step`.

- [ ] **Step 3: Write failing atomic routing/error tests**

Cover:

- `incoming=RouteSource("existing", "ok")` plus outgoing routes in one revision;
- unknown incoming source;
- duplicate id;
- unknown route outcome;
- routes supplied for `end`, `when`, `choose`, and `match`;
- incomplete but valid route subsets accepted;
- each failure leaves revision and draft bytes unchanged.

- [ ] **Step 4: Implement declared-outcome validation**

Add a private helper with exhaustive `isinstance` branches:

```python
def _draft_step_route_outcomes(self, step: DraftStep) -> set[str] | None:
    if isinstance(step, DraftUseStep):
        return set(self._outcomes_for_capability(step.use) or ("ok",))
    if isinstance(step, DraftForeachStep):
        outcomes = {"loop", "done"}
        if step.foreach.item_error.action in {"skip", "collect"}:
            outcomes.add("completed_with_errors")
        return outcomes
    if isinstance(step, DraftInterruptStep):
        return set(step.interrupt.outcomes)
    if isinstance(step, DraftJoinStep):
        return {"done"}
    if isinstance(step, DraftSubgraphStep):
        return set(step.subgraph.outcomes)
    if isinstance(step, (DraftEndStep, DraftWhenStep, DraftChooseStep, DraftMatchStep)):
        return None
    raise TypeError(f"unsupported draft step {type(step)!r}")
```

`None` means top-level routes are forbidden, not unknown.

- [ ] **Step 5: Implement `WorkflowDraftAuthoringApi.add_step`**

Build a patch only after all checks pass:

```python
patch = [{
    "op": "add",
    "path": f"/steps/{escape_json_pointer(step_id)}",
    "value": step.model_dump(mode="json", by_alias=True),
}]
if routes is not None:
    patch.append({
        "op": "add",
        "path": f"/routes/{escape_json_pointer(step_id)}",
        "value": routes,
    })
if incoming is not None:
    source_routes = draft_routes.get(incoming.step_id)
    if source_routes is None:
        # JSON Patch cannot add a nested outcome until its parent route map exists.
        patch.append({
            "op": "add",
            "path": f"/routes/{escape_json_pointer(incoming.step_id)}",
            "value": {incoming.outcome: step_id},
        })
    else:
        patch.append({
            "op": "add",
            "path": (
                f"/routes/{escape_json_pointer(incoming.step_id)}/"
                f"{escape_json_pointer(incoming.outcome)}"
            ),
            "value": step_id,
        })
return await self.drafts.patch_draft_workspace(
    workspace_id=workspace_id,
    revision=revision,
    patch=patch,
)
```

Check `steps`, `routes`, duplicate id, incoming source existence, forbidden routes, and unknown route keys before this call.

- [ ] **Step 6: Expose the method through service and surface**

Use the exact signature from the design in both `WorkflowApi` and `WorkflowApiSurface`. The service method delegates to `self.draft_authoring.add_step` without converting the typed step back to a raw dict.

- [ ] **Step 7: Verify and commit**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -q
uv run basedpyright src/wf_api tests/wf_api/test_drafts_service.py --level error
```

Commit:

```bash
git add src/wf_api tests/wf_api/test_drafts_service.py
git commit -m "feat: add atomic generic draft step insertion"
```

---

### Task 3: Expose Generic Insertion Through Python JSON-RPC

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

**Interfaces:**
- Consumes: `WorkflowApiSurface.add_step`, `DraftStep`, and `RouteSource` from Task 2.
- Produces: method `workflow.draft_workspaces.add_step` and remote client parity.

- [ ] **Step 1: Write failing RPC parameter tests**

Add:

```python
class RouteSourceParams(RpcParamsModel):
    step_id: str = Field(min_length=1)
    outcome: str = Field(default="ok", min_length=1)


class AddDraftStepParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    step: DraftStep
    incoming: RouteSourceParams | None = None
    routes: dict[str, str] | None = None
```

Before implementation, tests should attempt to import the models and validate a foreach alias (`as`), a when alias (`if`), typed interrupt schemas, and a subgraph artifact reference. Add malformed tests for unknown/multiple kind keys and blank route-source fields.

- [ ] **Step 2: Implement parameter models and canonical serialization tests**

Import `DraftStep` from `wf_artifacts.drafts`. Assert:

```python
dumped = params.model_dump(mode="json", by_alias=True)
assert dumped["step"]["foreach"]["as"] == "item"
assert "as_" not in dumped["step"]["foreach"]
```

- [ ] **Step 3: Write a failing server round-trip test**

Call `workflow.draft_workspaces.add_step` against a temporary store with a typed interrupt step, incoming source, and routes. Assert one revision increment and preserved request/resume schemas. Add a malformed RPC request and assert the workspace is unchanged.

- [ ] **Step 4: Register the method**

Add to `methods/drafts.py`:

```python
@entrypoint.method(
    name="workflow.draft_workspaces.add_step",
    errors=[WorkflowRpcError],
)
async def workflow_draft_workspaces_add_step(
    params: AddDraftStepParams = RpcParams(),
) -> dict[str, Any]:
    try:
        incoming = (
            None
            if params.incoming is None
            else RouteSource(
                step_id=params.incoming.step_id,
                outcome=params.incoming.outcome,
            )
        )
        return await server.api.add_step(
            workspace_id=params.workspace_id,
            revision=params.revision,
            step_id=params.step_id,
            step=params.step,
            incoming=incoming,
            routes=params.routes,
        )
    except (ValueError, KeyError, LookupError, FileNotFoundError) as exc:
        raise_workflow_rpc_error(exc)
```

- [ ] **Step 5: Write failing client request-shape tests**

Use the existing recording transport fixture. Assert exact method name and payload:

```python
assert request["method"] == "workflow.draft_workspaces.add_step"
assert request["params"]["step"]["when"]["if"]["op"] == "exists"
assert request["params"]["incoming"] == {"step_id": "lookup", "outcome": "ok"}
```

Parameterize all nine variants so alias/schema/reference fields cannot be dropped.

- [ ] **Step 6: Implement the client method**

The client accepts typed values and dumps aliases explicitly:

```python
async def add_step(
    self: RpcCaller,
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    step: DraftStep,
    incoming: RouteSource | None = None,
    routes: dict[str, str] | None = None,
) -> dict[str, Any]:
    return await self._call(
        "workflow.draft_workspaces.add_step",
        {
            "workspace_id": workspace_id,
            "revision": revision,
            "step_id": step_id,
            "step": step.model_dump(mode="json", by_alias=True),
            "incoming": (
                None
                if incoming is None
                else {"step_id": incoming.step_id, "outcome": incoming.outcome}
            ),
            "routes": routes,
        },
    )
```

- [ ] **Step 7: Verify and commit**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py -q
uv run basedpyright src/wf_transport_rpc_http tests/wf_transport_rpc_http --level error
```

Commit:

```bash
git add src/wf_transport_rpc_http tests/wf_transport_rpc_http
git commit -m "feat: expose generic draft steps over rpc"
```

---

### Task 4: Establish The `wf draft add` Command Boundary

**Files:**
- Create: `src/wf_cli/commands/draft_options.py`
- Create: `src/wf_cli/commands/draft_add.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: `WorkflowApiSurface.add_step` and existing `add_step_from_capability`.
- Produces: `draft_add.app` registered as `wf draft add` and migrated `capability` command.

- [ ] **Step 1: Write failing command-tree tests**

Assert:

```python
result = runner.invoke(app, ["draft", "add", "--help"])
assert result.exit_code == 0
for name in ("capability", "interrupt", "foreach", "join", "end", "when", "choose", "match", "subgraph"):
    assert name in result.output

removed = runner.invoke(app, ["draft", "add-step", "--help"])
assert removed.exit_code != 0
```

- [ ] **Step 2: Extract only shared parser helpers**

Move `_parse_assignment_flags`, `_parse_map_flags`, `_parse_output_map_flags`, `_parse_step_input_map_flags`, and `_parse_route_flags` from `drafts.py` into `draft_options.py`. Add:

```python
def parse_json_file(path: Path, *, option_name: str) -> Any:
    """Read one structured CLI value and report file/JSON failures as option errors."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise typer.BadParameter(f"{option_name}: cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{option_name}: invalid JSON in {path}: {exc.msg}") from exc


def route_source(from_step: str | None, from_outcome: str | None) -> RouteSource | None:
    if from_step is None:
        if from_outcome is not None:
            raise typer.BadParameter("--from-outcome requires --from-step")
        return None
    return RouteSource(step_id=from_step, outcome=from_outcome or "ok")
```

Keep imports updated so existing draft commands retain identical parsing.

- [ ] **Step 3: Create and register the subgroup**

In `draft_add.py`:

```python
app = typer.Typer(
    name="add",
    help="Add one typed step to a draft workspace.",
    no_args_is_help=True,
)
```

In `drafts.py`, import `draft_add` and register `app.add_typer(draft_add.app, name="add")` after constructing the draft app.

- [ ] **Step 4: Move the capability command without changing behavior**

Register the existing body as `@app.command("capability")`. Keep all current
capability options and call `context.handlers.add_step_from_capability` with
`workspace_id`, `revision`, `step_id`, `capability_name`, incoming route
fields, parsed routes, input map, and output bindings exactly as the removed
command does. Its docstring must state that it also projects schemas/bindings
and recommend `wf draft validate`.

- [ ] **Step 5: Verify local and remote capability behavior**

Update old CLI tests from:

```text
wf draft add-step WORKSPACE --revision REVISION --step STEP --capability QUALIFIED_NAME
```

to:

```text
wf draft add capability WORKSPACE --revision REVISION --step STEP --capability QUALIFIED_NAME
```

Keep assertions on request payload, projected schemas, route errors, and revision unchanged. Add a remote test proving it still calls `workflow.draft_workspaces.add_step_from_capability`, not generic insertion.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
uv run basedpyright src/wf_cli tests/wf_cli --level error
```

Commit:

```bash
git add src/wf_cli/commands tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
git commit -m "feat: group draft add commands"
```

---

### Task 5: Add Interrupt, Foreach, Join, And End Commands

**Files:**
- Modify: `src/wf_cli/commands/draft_add.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: generic `add_step`, parsing helpers, and concrete draft models.
- Produces: four type-specific commands with local/remote parity.

- [ ] **Step 1: Add a private command dispatcher and failing delegation tests**

Use one helper so every command has identical transport behavior:

```python
def _submit_step(
    ctx: typer.Context,
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    step: DraftStep,
    from_step: str | None,
    from_outcome: str | None,
    routes: dict[str, str] | None,
) -> None:
    context = load_cli_context(ctx)
    emit_json(run_cli_operation(
        context,
        context.handlers.add_step(
            workspace_id=workspace_id,
            revision=revision,
            step_id=step_id,
            step=step,
            incoming=route_source(from_step, from_outcome),
            routes=routes,
        ),
    ))
```

Tests must invoke both local fake handlers and `--url` RPC targets and assert the concrete model received by `add_step`.

- [ ] **Step 2: Implement `interrupt` with schema and binding validation**

Construct:

```python
DraftInterruptStep(interrupt=DraftInterruptPayload(
    kind=kind,
    request_schema=(
        SchemaRef.model_validate(parse_json_file(request_schema_file, option_name="--request-schema-file"))
        if request_schema_file else None
    ),
    resume_schema=(
        SchemaRef.model_validate(parse_json_file(resume_schema_file, option_name="--resume-schema-file"))
        if resume_schema_file else None
    ),
    request=[
        InputPathBinding(path=source, target=target)
        for source, target in parse_map_flags(request).items()
    ],
    resume=[
        OutputBinding(source=source, target=target)
        for source, target in parse_output_map_flags(resume).items()
    ],
    outcomes=outcomes or ["submitted"],
))
```

Use the repository's existing binding payload/model helpers rather than duplicating path conversion. Tests cover two outcomes, both schemas, aliases, duplicate flags, malformed files, and no API call after parse failure.

- [ ] **Step 3: Implement `foreach` and validate policy relationships**

Construct `DraftForeachPayload` from `--over`, `--as`, `--mode`, and:

```python
item_error = ForeachItemErrorPolicy(action=item_error, collect_to=collect_to)
concurrent = (
    ForeachConcurrentPolicy(
        max_active=max_active,
        max_outstanding=max_outstanding,
    )
    if max_active is not None or max_outstanding is not None
    else None
)
```

Reject concurrent limits in serial mode with `typer.BadParameter`; rely on Pydantic to require `collect_to` for collect behavior. Route tests cover `loop`, `done`, and `completed_with_errors`.

- [ ] **Step 4: Implement `join` and `end`**

`join` constructs `DraftJoinStep(join={})` and accepts routes. `end` constructs `DraftEndStep(end=DraftEndPayload(outcome=outcome))`, exposes no `--route`, and passes `routes=None`.

- [ ] **Step 5: Pin per-command help and error surfaces**

For each command assert `--help` lists its own fields and does not list unrelated fields. Specifically:

- interrupt has schema/request/resume/outcome flags, not foreach policy flags;
- foreach has concurrency flags, not schema flags;
- join has only common routing flags;
- end has `--outcome` but no `--route`.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
uv run ruff check src/wf_cli/commands/draft_add.py tests/wf_cli
uv run basedpyright src/wf_cli/commands/draft_add.py tests/wf_cli --level error
```

Commit:

```bash
git add src/wf_cli/commands/draft_add.py tests/wf_cli
git commit -m "feat: add draft control step commands"
```

---

### Task 6: Add Decision And Subgraph Commands

**Files:**
- Modify: `src/wf_cli/commands/draft_add.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: `_submit_step`, JSON-file parsing, and draft models from prior tasks.
- Produces: `when`, `choose`, `match`, and `subgraph` commands.

- [ ] **Step 1: Write failing `when` tests and implement the command**

Given `condition.json`:

```json
{"op":"exists","path":"state.report"}
```

Invoke `wf draft add when WORKSPACE --revision 1 --step decide --condition-file condition.json --then publish --otherwise revise`. Parse with `Condition.model_validate(parse_json_file(condition_file, option_name="--condition-file"))`, then construct:

```python
DraftWhenStep(when=DraftWhenPayload(
    if_=condition,
    then=then,
    otherwise=otherwise,
))
```

The command must not expose `--route` because targets are embedded.

- [ ] **Step 2: Write failing `choose` tests and implement the command**

`--clauses-file` contains a JSON array. Validate with
`TypeAdapter(list[DraftChooseClause]).validate_python(value)`, then construct
`DraftChooseStep(choose=DraftChoosePayload(clauses=clauses, default=default))`.
Tests cover ordered clauses, canonical `if` alias output, an empty array, a
non-array document, and no generic routes.

- [ ] **Step 3: Write failing `match` tests and implement the command**

`--cases-file` contains a JSON array. Validate with
`TypeAdapter(list[DraftMatchCase])`, then construct:

```python
DraftMatchStep(match=DraftMatchPayload(
    value=value,
    cases=cases,
    default=default,
))
```

Tests preserve scalar `equals` values (`str`, `int`, `bool`, `None`) and ordered targets.

- [ ] **Step 4: Write failing subgraph reference tests**

Cover:

- `--workflow-name child`;
- `--artifact-id child_report --artifact-version 2`;
- neither reference form;
- both forms;
- artifact id without version and version without artifact id.

All invalid combinations must fail before `add_step` is called.

- [ ] **Step 5: Implement subgraph construction**

Build the reference explicitly:

```python
if workflow_name is not None:
    if artifact_id is not None or artifact_version is not None:
        raise typer.BadParameter(
            "--workflow-name cannot be combined with --artifact-id/--artifact-version"
        )
    workflow = WorkflowRef(name=workflow_name)
else:
    if artifact_id is None or artifact_version is None:
        raise typer.BadParameter(
            "use --workflow-name or both --artifact-id and --artifact-version"
        )
    workflow = WorkflowRef(artifact_id=artifact_id, version=artifact_version)
```

Then construct `DraftSubgraphPayload` with optional schema files, canonical input/output bindings, outcomes defaulting to `['ok']`, and description. Pass repeatable routes through `_submit_step`.

- [ ] **Step 6: Verify all nine commands and remote parity**

Add a parameterized remote test that invokes every generic command and asserts method `workflow.draft_workspaces.add_step`, canonical step payload aliases, incoming route source, and routes. Keep capability in a separate assertion because it intentionally calls the composed method.

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
uv run ruff check src/wf_cli/commands tests/wf_cli
uv run basedpyright src/wf_cli/commands tests/wf_cli --level error
```

- [ ] **Step 7: Commit**

```bash
git add src/wf_cli/commands/draft_add.py tests/wf_cli
git commit -m "feat: add draft decision and subgraph commands"
```

---

### Task 7: Migrate Live Documentation And Close The Slice

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `docs/wf_api_architecture.md`
- Modify: `docs/current_roadmap.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/draft-workspaces.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `ISSUES.md`
- Move after all checks pass: `docs/superpowers/plans/2026-07-20-generic-draft-add-step.md` to `docs/historical/superpowers/plans/2026-07-20-generic-draft-add-step.md`

**Interfaces:**
- Consumes: all implemented commands and method names.
- Produces: accurate live docs and a clean, archived implementation record.

- [ ] **Step 1: Search live references before editing**

Run:

```powershell
rg -n -F 'wf draft add-step' docs skills README.md ISSUES.md --glob '!docs/historical/**'
rg -n -F 'add_step_from_capability' docs skills --glob '!docs/historical/**'
```

Classify each reference: migrate command examples; retain API references when they describe the composed capability helper; do not rewrite thesis/history solely for naming.

- [ ] **Step 2: Update user-facing CLI and skill documentation**

Document the command tree and at least these complete examples:

```bash
wf draft add capability report_ws --revision 1 --step render \
  --capability local.report.render --route ok=__end__

wf draft add interrupt report_ws --revision 2 --step review \
  --kind issue_review --request-schema-file request.schema.json \
  --resume-schema-file resume.schema.json \
  --outcome submitted --outcome cancelled \
  --from-step draft_issues --from-outcome ok \
  --route submitted=create_issues --route cancelled=revision_requested

wf draft add when report_ws --revision 3 --step decide \
  --condition-file has-report.json --then publish --otherwise revise
```

Explain that `when`/`choose`/`match` embed targets and do not accept `--route`, while invalid intermediate drafts remain saveable and should be checked with `wf draft validate`.

- [ ] **Step 3: Update API architecture and roadmap**

Document `workflow.draft_workspaces.add_step`, the `DraftStep` boundary, separate map-key `step_id`, atomic route wiring, and the continued role of `add_step_from_capability`. Mark the roadmap slice complete only after verification.

- [ ] **Step 4: Resolve tracked issues honestly**

Change the three items in `ISSUES.md` to checked entries only if tests prove:

```markdown
- [x] Dedicated draft CLI subcommands cover every draft step kind.
- [x] Draft interrupts preserve request and resume schemas.
- [x] Draft subgraphs preserve workflow references and boundary contracts.
```

Add any newly discovered out-of-scope defects as unchecked, reproducible statements.

- [ ] **Step 5: Run focused regression suites**

```bash
uv run pytest tests/artifacts/test_draft_models.py tests/artifacts/test_draft_adapter.py tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
```

Expected: all pass.

- [ ] **Step 6: Run the repository quality gate**

```bash
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
git diff --check
```

If formatting fails, run `uv run ruff format`, inspect the diff, and rerun all four checks. Do not claim the full `uv run pytest -q` suite unless it is actually run; the focused matrix above is the required test gate for this slice.

- [ ] **Step 7: Review and archive**

Run the `requesting-code-review` skill against the design/spec and this plan. Fix Critical/Important findings, rerun affected checks, tick completed plan checkboxes, then move the plan to the matching historical path and update live links.

- [ ] **Step 8: Commit documentation and issue closure**

```bash
git add docs skills ISSUES.md
git commit -m "docs: complete generic draft step authoring"
```
