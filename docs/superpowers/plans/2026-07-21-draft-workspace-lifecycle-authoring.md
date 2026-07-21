# Draft Workspace Lifecycle Authoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let local and remote `wf` callers create capability-free draft workspaces, select a forward-referenced entry point, and atomically replace workflow schemas and outcomes without raw JSON Patch.

**Architecture:** `WorkflowDraftApi` owns the capability-neutral lifecycle operations because they only construct or patch the canonical draft document. `WorkflowApi` and `WorkflowDraftSurface` expose that deep interface; JSON-RPC server/client adapters carry the same typed fields; Typer keeps the existing capability bootstrap while adding the empty-create branch and focused metadata commands. Invalid intermediate drafts remain persisted with diagnostics, and all mutations flow through the existing revisioned workspace patch implementation.

**Tech Stack:** Python 3.14, Pydantic v2, Typer, fastapi-jsonrpc, httpx ASGI transport, pytest/pytest-asyncio, Ruff, basedpyright.

## Global Constraints

- Follow `docs/superpowers/specs/2026-07-21-draft-workspace-lifecycle-authoring-design.md`.
- Preserve the existing `wf draft create WORKSPACE --capability QUALIFIED_NAME` behavior.
- Capability-free creation stores `start: ""`, `steps: {}`, `routes: {}`, and `output: []`; it is an honest invalid revision-1 workspace, not a placeholder workflow.
- Empty object schema defaults are `{"type": "object", "properties": {}}` and must not share mutable dictionary instances.
- `set_draft_contract` replaces supplied complete top-level fields; it never deep-merges JSON Schema.
- State reducer declarations remain metadata inside the replacement state schema.
- `set_draft_start` permits forward references and relies on normal draft diagnostics.
- Supplied outcomes must be non-empty, non-blank, and unique; preserve their caller-defined order.
- Request-envelope errors are rejected before workspace lookup and do not
  mutate or consume a revision. Revision precedence applies after the request
  envelope is valid and before validation of current workspace content.
- Valid semantic edits use one canonical `patch_draft_workspace` call and consume exactly one revision.
- MCP tools and the TypeScript Effect RPC package are out of scope.
- Add docstrings/comments around the intentionally invalid skeleton and whole-schema replacement seam.
- Use focused tests during tasks; run the scoped Python quality gate in Task 5.

## File Map

- `src/wf_api/drafts.py`: empty skeleton construction, outcome validation, start edit, and atomic contract edit.
- `src/wf_api/service.py`: concrete `WorkflowApi` delegation.
- `src/wf_api/surface.py`: transport-facing lifecycle interface.
- `src/wf_transport_rpc_http/models.py`: request envelopes and cross-field validation.
- `src/wf_transport_rpc_http/methods/drafts.py`: three JSON-RPC method registrations.
- `src/wf_transport_rpc_http/__init__.py`: public request-model exports.
- `src/wf_transport_rpc_http/client/drafts.py`: remote implementation of `WorkflowDraftSurface`.
- `src/wf_cli/commands/draft_options.py`: reusable JSON-object schema-file parser.
- `src/wf_cli/commands/drafts.py`: dual-mode create plus `set-start` and `set-contract`.
- `tests/wf_api/test_drafts_service.py`: canonical lifecycle and revision behavior.
- `tests/wf_transport_rpc_http/test_app.py`: JSON-RPC registration and server dispatch.
- `tests/wf_transport_rpc_http/test_client.py`: client payloads and complete remote lifecycle.
- `tests/wf_cli/test_app.py`: command help, input validation, and handler arguments.
- `tests/wf_cli/test_remote_target.py`: real CLI-to-ASGI remote parity.
- `docs/workflow_drafts.md`, `skills/wf-cli/SKILL.md`, `skills/wf-workflow/SKILL.md`, `docs/current_roadmap.md`, `ISSUES.md`: live documentation and issue closure.

---

### Task 1: Add Canonical Draft Lifecycle Operations

**Files:**
- Modify: `src/wf_api/drafts.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Test: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Produces: `WorkflowDraftSurface.create_empty_draft_workspace(...)`.
- Produces: `WorkflowDraftSurface.set_draft_start(...)`.
- Produces: `WorkflowDraftSurface.set_draft_contract(...)`.
- Consumes: existing `WorkflowDraftApi.create_draft_workspace` and `patch_draft_workspace` revision semantics.

- [ ] **Step 1: Write failing empty-workspace API tests**

Add tests using `_draft_api(...)`, then construct the facade explicitly with
`facade = WorkflowApi(authoring.context)`. Pin the complete stored shape, not
only summary fields:

```python
created = await facade.create_empty_draft_workspace(
    workspace_id="control_first",
    name="control_first",
    title="Control First",
)
stored = await facade.get_draft_workspace(
    workspace_id="control_first",
    include_draft=True,
)

assert created["revision"] == 1
assert created["status"] == "invalid"
assert created["diagnostics"]
assert stored["draft"] == {
    "name": "control_first",
    "input_schema": {"type": "object", "properties": {}},
    "state_schema": {"type": "object", "properties": {}},
    "output_schema": {"type": "object", "properties": {}},
    "outcomes": ["ok"],
    "output": [],
    "start": "",
    "steps": {},
    "routes": {},
}
```

Add a second test with custom schemas, ordered outcomes, reducer metadata under a state property, and title. Assert the stored payload equals the supplied dictionaries. Mutate one original schema after creation and assert the other defaults/stored schemas did not change.

- [ ] **Step 2: Write failing conflict and envelope-validation tests**

Cover:

- duplicate workspace id returns `status == "conflict"` and diagnostic code `workspace_exists`;
- a non-object custom schema rejects before workspace creation;
- empty outcomes reject before workspace creation;
- blank outcomes reject before workspace creation;
- duplicate outcomes reject before workspace creation.

For each rejected envelope, assert `list_draft_workspaces()` remains empty.

- [ ] **Step 3: Write failing start and contract edit tests**

Cover these behaviors:

```python
forward = await facade.set_draft_start(
    workspace_id="control_first",
    revision=1,
    step_id="gate",
)
assert forward["revision"] == 2
assert forward["status"] == "invalid"

contract = await facade.set_draft_contract(
    workspace_id="control_first",
    revision=2,
    state_schema=state_schema_with_reducer,
    output_schema=output_schema,
    outcomes=("submitted", "cancelled"),
)
assert contract["revision"] == 3
```

Fetch the full draft and assert input schema is unchanged, supplied fields are complete replacements, reducer metadata is intact, and outcomes preserve order. Also test:

- empty contract call raises `ValueError` without mutation;
- blank `set_draft_start` step ids raise `ValueError` without mutation;
- non-object replacement schemas raise `ValueError` without mutation;
- empty, blank, and duplicate outcomes raise `ValueError` without mutation;
- stale `set_draft_start` returns `revision_conflict` without mutation;
- stale `set_draft_contract` returns `revision_conflict` without mutation.

Use otherwise-valid stale requests in those two tests. Invalid request
envelopes are expected to fail before revision lookup.

- [ ] **Step 4: Run the focused API tests and confirm red**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -q
```

Expected: new tests fail because `WorkflowApi` and `WorkflowDraftSurface` do not expose the three lifecycle methods.

- [ ] **Step 5: Implement lifecycle validation and mutation in `WorkflowDraftApi`**

Add small private helpers in `src/wf_api/drafts.py`:

```python
def _empty_object_schema() -> dict[str, Any]:
    """Return one fresh unconstrained object schema for an empty draft."""
    return {"type": "object", "properties": {}}


def _validated_workflow_outcomes(outcomes: Sequence[str]) -> list[str]:
    """Return ordered public outcomes after rejecting unusable contracts."""
    values = list(outcomes)
    if not values:
        raise ValueError("workflow outcomes must contain at least one value")
    if any(not value.strip() for value in values):
        raise ValueError("workflow outcomes must not contain blank values")
    if len(set(values)) != len(values):
        raise ValueError("workflow outcomes must be unique")
    return values
```

Add a small `_validated_schema_object(value, field_name=...)` guard that returns a
schema dictionary and rejects non-dictionaries. Use it for every supplied
schema in empty creation and contract replacement; type annotations do not
replace runtime validation for same-process callers.

Implement `create_empty_draft_workspace` by constructing the exact skeleton from the design and delegating once to `create_draft_workspace`. Do not validate it into `WorkflowDraft` first: the empty start is intentionally invalid and the workspace layer owns diagnostic persistence.

Implement `set_draft_start` as one `replace /start` patch after rejecting an
empty or whitespace-only id. Implement `set_draft_contract` by building a patch
in stable input/state/output/outcomes order and rejecting an empty patch before
reading the workspace:

```python
patch: list[dict[str, Any]] = []
if input_schema is not None:
    patch.append({"op": "replace", "path": "/input_schema", "value": input_schema})
# state_schema and output_schema follow in the same pattern.
if outcomes is not None:
    patch.append({
        "op": "replace",
        "path": "/outcomes",
        "value": _validated_workflow_outcomes(outcomes),
    })
if not patch:
    raise ValueError("set_draft_contract requires at least one contract field")
return await self.patch_draft_workspace(..., patch=patch)
```

- [ ] **Step 6: Expose exact delegation through `WorkflowApi` and `WorkflowDraftSurface`**

Add all three signatures from the design to the protocol and facade. Use `Sequence[str]` in Python interfaces; convert only at serialization/storage seams. Keep method names identical across concrete and protocol types.

- [ ] **Step 7: Verify and commit Task 1**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py -q
uv run basedpyright src/wf_api tests/wf_api --level error
```

Expected: both pass.

Commit:

```bash
git add src/wf_api/drafts.py src/wf_api/service.py src/wf_api/surface.py tests/wf_api/test_drafts_service.py
git commit -m "feat: add draft lifecycle authoring operations"
```

---

### Task 2: Expose Lifecycle Operations Through JSON-RPC

**Files:**
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/drafts.py`
- Modify: `src/wf_transport_rpc_http/__init__.py`
- Test: `tests/wf_transport_rpc_http/test_app.py`

**Interfaces:**
- Consumes: the three `WorkflowDraftSurface` methods from Task 1.
- Produces: `CreateEmptyDraftWorkspaceParams`, `SetDraftStartParams`, and `SetDraftContractParams`.
- Produces: JSON-RPC methods `workflow.draft_workspaces.create_empty`, `.set_start`, and `.set_contract`.

- [ ] **Step 1: Write failing RPC registration and dispatch tests**

Extend the draft RPC app tests to call:

```python
created = await _rpc(client, "workflow.draft_workspaces.create_empty", {
    "workspace_id": "rpc_control",
    "name": "rpc_control",
    "title": "RPC Control",
})
started = await _rpc(client, "workflow.draft_workspaces.set_start", {
    "workspace_id": "rpc_control",
    "revision": 1,
    "step_id": "gate",
})
contracted = await _rpc(client, "workflow.draft_workspaces.set_contract", {
    "workspace_id": "rpc_control",
    "revision": 2,
    "state_schema": {"type": "object", "properties": {}},
    "outcomes": ["error"],
})
```

Assert method results use revisions 1, 2, and 3; creation and the forward start are invalid but persisted; inspection shows the replaced contract.

- [ ] **Step 2: Write failing RPC envelope tests**

Use `_rpc` to submit:

- `set_contract` with no optional field;
- empty outcomes;
- duplicate outcomes;
- blank `step_id`;
- non-object schema payload.

Assert each returns a JSON-RPC parameter/error response and inspection proves the workspace revision did not change.

- [ ] **Step 3: Run the focused server tests and confirm red**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py -q
```

Expected: unknown-method failures for the three new method names.

- [ ] **Step 4: Implement typed request models**

In `models.py`, import `Self` from `typing`, then add Pydantic request models
with `Field(min_length=1)` for ids/names, `revision >= 1`, optional schema
dictionaries, ordered outcomes, and model validators:

```python
class SetDraftContractParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    input_schema: dict[str, Any] | None = None
    state_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    outcomes: list[str] | None = None

    @model_validator(mode="after")
    def validate_contract_edit(self) -> Self:
        fields = (
            self.input_schema,
            self.state_schema,
            self.output_schema,
            self.outcomes,
        )
        if all(value is None for value in fields):
            raise ValueError("set_contract requires at least one contract field")
        if self.outcomes is not None:
            _validate_outcomes(self.outcomes)
        return self
```

Use a shared local outcome validator for create and set-contract request models. The API repeats validation deliberately because same-process callers do not pass through Pydantic RPC models.

- [ ] **Step 5: Register three thin server methods**

Import the models in `methods/drafts.py`. Each handler catches the same expected exception set as neighboring draft methods and delegates exact fields to `server.api` without rebuilding draft JSON inside the transport adapter.

Re-export the three request models from `wf_transport_rpc_http.__init__` and add
them to `__all__`, matching the package's existing public DTO convention.

- [ ] **Step 6: Verify and commit Task 2**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_app.py -q
uv run basedpyright src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/__init__.py tests/wf_transport_rpc_http/test_app.py --level error
```

Expected: both pass.

Commit:

```bash
git add src/wf_transport_rpc_http/models.py src/wf_transport_rpc_http/methods/drafts.py src/wf_transport_rpc_http/__init__.py tests/wf_transport_rpc_http/test_app.py
git commit -m "feat: expose draft lifecycle rpc methods"
```

---

### Task 3: Add Remote Client Parity And Lifecycle Coverage

**Files:**
- Modify: `src/wf_transport_rpc_http/client/drafts.py`
- Test: `tests/wf_transport_rpc_http/test_client.py`

**Interfaces:**
- Consumes: the JSON-RPC methods from Task 2.
- Produces: `RpcDraftClientMixin` implementations satisfying the expanded `WorkflowDraftSurface`.

- [ ] **Step 1: Write failing request-payload tests**

Follow the existing lightweight recording-client pattern and assert exact methods and params for all three calls. Pin that tuples become ordered JSON lists:

```python
assert request == {
    "method": "workflow.draft_workspaces.set_contract",
    "params": {
        "workspace_id": "ws",
        "revision": 3,
        "input_schema": None,
        "state_schema": state_schema,
        "output_schema": None,
        "outcomes": ["ok", "error"],
    },
}
```

- [ ] **Step 2: Write the failing complete remote lifecycle test**

Against an in-process `create_rpc_app(server)` and real `RpcWorkflowApiClient`:

1. create empty `control_first`;
2. add a `DraftJoinStep(join={})` named `gate` with `routes={"done": "finish"}`;
3. set start to `gate`;
4. add `DraftEndStep(end=DraftEndPayload(outcome="error"))` named `finish`;
5. set contract outcomes to `("error",)`;
6. validate and compile the workspace.

Assert the final validation result is valid, revision increased exactly once per
edit, `compile_draft_workspace()` returns a compiled plan whose start is `gate`,
and an inspected full draft contains no capability bootstrap step.

- [ ] **Step 3: Run client tests and confirm red**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_client.py -q
```

Expected: static protocol shape/type failures or missing client methods.

- [ ] **Step 4: Implement the remote mixin methods**

Add direct `_call(...)` methods adjacent to capability-backed creation and existing focused setters. Serialize `Sequence[str]` using `list(outcomes)` and include all optional contract keys explicitly, matching existing client payload conventions.

- [ ] **Step 5: Verify static surface parity and commit Task 3**

Run:

```bash
uv run pytest tests/wf_transport_rpc_http/test_client.py -q
uv run basedpyright src/wf_transport_rpc_http/client/drafts.py tests/wf_transport_rpc_http/test_client.py --level error
```

Expected: tests pass, including `test_rpc_client_satisfies_draft_surface_static_shape`.

Commit:

```bash
git add src/wf_transport_rpc_http/client/drafts.py tests/wf_transport_rpc_http/test_client.py
git commit -m "feat: add remote draft lifecycle client"
```

---

### Task 4: Add Local And Remote CLI Lifecycle Commands

**Files:**
- Modify: `src/wf_cli/commands/draft_options.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Test: `tests/wf_cli/test_app.py`
- Test: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: the expanded `WorkflowDraftSurface` implemented locally and remotely.
- Produces: dual-mode `wf draft create`, `wf draft set-start`, and `wf draft set-contract`.

- [ ] **Step 1: Write failing help and handler-dispatch tests**

Update create help expectations and add new help tests. Pin these options:

```text
draft create: --capability, --name, --title, --input-schema-file,
              --state-schema-file, --output-schema-file, --outcome
draft set-start: --revision, --step
draft set-contract: --revision, three schema-file options, --outcome
```

Use fake handlers to assert:

- create without capability calls `create_empty_draft_workspace` with parsed schemas and ordered outcomes;
- create with capability still calls only `create_draft_workspace_from_capability`;
- set-start forwards workspace/revision/step;
- set-contract preserves omitted fields as `None` and passes ordered outcomes.

- [ ] **Step 2: Write failing CLI validation tests**

Cover:

- create without capability or name;
- capability create combined with schema/outcome options;
- set-contract with no fields;
- malformed JSON schema file;
- schema file containing an array/string/null;
- empty or duplicate outcomes.

Assert concise Click/Typer parameter errors and assert fake handlers receive no call.

- [ ] **Step 3: Write the failing remote CLI lifecycle test**

Use `_patch_rpc_client_to_server` and the `--url http://test/rpc` pattern. Run:

```text
wf draft create control_ws --name control
wf draft add join control_ws --revision 1 --step gate --route done=finish
wf draft set-start control_ws --revision 2 --step gate
wf draft add end control_ws --revision 3 --step finish --outcome error
wf draft set-contract control_ws --revision 4 --outcome error
wf draft validate control_ws
```

Assert every command succeeds, final status is valid, final revision is 5, start is `gate`, outcomes are `['error']`, and steps contain exactly `gate` and `finish`.

- [ ] **Step 4: Run CLI tests and confirm red**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
```

Expected: missing options/commands and missing handler-method failures.

- [ ] **Step 5: Add a reusable JSON-object file parser**

Build on `parse_json_file` in `draft_options.py`:

```python
def parse_json_object_file(path: Path, *, option_name: str) -> dict[str, Any]:
    """Read one JSON object file for a workflow schema option."""
    value = parse_json_file(path, option_name=option_name)
    if not isinstance(value, dict):
        raise typer.BadParameter(f"{option_name}: expected a JSON object")
    return value
```

Do not add schema merging or JSON Schema semantic validation in the CLI.

- [ ] **Step 6: Implement dual-mode create**

Rename the Python function from `create_from_capability` to `create_draft`. Make `--capability` optional. Parse schema files only after checking mode-specific option rules:

```python
if capability_name is not None:
    if any(schema option or outcome is supplied):
        raise typer.BadParameter(
            "schema and outcome options are only valid without --capability"
        )
    operation = context.handlers.create_draft_workspace_from_capability(...)
else:
    if name is None:
        raise typer.BadParameter("--name is required without --capability")
    operation = context.handlers.create_empty_draft_workspace(
        ...,
        outcomes=tuple(outcome or ["ok"]),
    )
```

Keep loading the protocol-neutral CLI context so both branches work locally and remotely.

- [ ] **Step 7: Implement `set-start` and `set-contract`**

Add adjacent focused commands. Reject duplicate/blank outcomes at the CLI edge for concise feedback, while preserving API/RPC validation. `set-contract` must reject an empty option set before loading the context. Pass complete schema dictionaries and `tuple(outcomes)` to the surface.

- [ ] **Step 8: Verify and commit Task 4**

Run:

```bash
uv run pytest tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
uv run basedpyright src/wf_cli tests/wf_cli --level error
```

Expected: both pass and existing capability-create tests remain green.

Commit:

```bash
git add src/wf_cli/commands/draft_options.py src/wf_cli/commands/drafts.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py
git commit -m "feat: add draft lifecycle cli commands"
```

---

### Task 5: Update Live Guidance And Close Implemented Issues

**Files:**
- Modify: `docs/workflow_drafts.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/SKILL.md`
- Modify: `docs/current_roadmap.md`
- Modify: `ISSUES.md`
- Move after all checks pass: `docs/superpowers/plans/2026-07-21-draft-workspace-lifecycle-authoring.md` to `docs/historical/superpowers/plans/2026-07-21-draft-workspace-lifecycle-authoring.md`

**Interfaces:**
- Documents: the exact capability-free CLI lifecycle and whole-contract replacement semantics.
- Closes: only the four implemented items under `Draft workspace lifecycle parity` for empty creation, entry point, workflow outcomes, and workflow schemas/reducer metadata.

- [ ] **Step 1: Update workflow draft documentation**

Add a capability-free flow before the current capability bootstrap flow:

```bash
wf draft create report_ws --name report_workflow
wf draft add join report_ws --revision 1 --step gate --route done=finish
wf draft set-start report_ws --revision 2 --step gate
wf draft add end report_ws --revision 3 --step finish --outcome error
wf draft set-contract report_ws --revision 4 --outcome error
wf draft validate report_ws
```

Explain that revision 1 is intentionally invalid, forward entry points persist with diagnostics, schema files replace whole schemas, and capability binding projection remains preferable when deriving selected fields from a known node contract.

- [ ] **Step 2: Update both agent skills**

Teach agents to choose:

- `wf draft create --capability` for a capability-derived first step and automatic hints;
- `wf draft create --name` for control/interrupt/subgraph-first authoring;
- `set-contract` for explicit whole-schema/outcome replacement;
- `bind` or capability-add projection for selected node-schema fields;
- raw patch only for field-level schema surgery not covered by focused operations.

- [ ] **Step 3: Update roadmap and issues**

Add a completed roadmap item linking to the historical plan path. Check exactly these `ISSUES.md` items:

- capability-free draft workspace creation;
- focused entry-point edit;
- focused workflow outcome declaration;
- focused workflow schema/reducer-metadata replacement.

Leave step metadata, data-shaping, revision consistency, and TypeScript parity unchecked.

- [ ] **Step 4: Run focused functional verification**

Run:

```bash
uv run pytest tests/wf_api/test_drafts_service.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_cli/test_app.py tests/wf_cli/test_remote_target.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run the Python quality gate**

Run:

```bash
uv run ruff check src/wf_api src/wf_transport_rpc_http src/wf_cli tests/wf_api tests/wf_transport_rpc_http tests/wf_cli
uv run ruff format --check src/wf_api src/wf_transport_rpc_http src/wf_cli tests/wf_api tests/wf_transport_rpc_http tests/wf_cli
uv run basedpyright --level error
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 6: Run independent review and fix valid findings**

Review against:

- `docs/superpowers/specs/2026-07-21-draft-workspace-lifecycle-authoring-design.md`;
- preservation of capability-backed create behavior;
- revision/error precedence;
- exact local/remote CLI parity;
- docs and issue closure accuracy.

Re-run the smallest affected test command after each fix, then repeat Steps 4 and 5.

- [ ] **Step 7: Archive the completed plan and commit**

Move the plan only after implementation and verification are complete:

```powershell
Move-Item -LiteralPath 'docs/superpowers/plans/2026-07-21-draft-workspace-lifecycle-authoring.md' -Destination 'docs/historical/superpowers/plans/2026-07-21-draft-workspace-lifecycle-authoring.md'
```

Commit:

```bash
git add docs/workflow_drafts.md skills/wf-cli/SKILL.md skills/wf-workflow/SKILL.md docs/current_roadmap.md ISSUES.md docs/superpowers/plans/2026-07-21-draft-workspace-lifecycle-authoring.md docs/historical/superpowers/plans/2026-07-21-draft-workspace-lifecycle-authoring.md
git commit -m "docs: complete draft lifecycle authoring"
```

If Git reports the active plan path no longer exists, stage the deletion with `git add -A -- docs/superpowers/plans docs/historical/superpowers/plans` rather than recreating it.
