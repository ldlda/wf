# Capability Step Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one atomic, presence-aware capability-step update across Python,
JSON-RPC, MCP, and CLI, and let capability-step creation set the same metadata
and canonical literal inputs directly.

**Architecture:** Define a transport-safe `CapabilityStepUpdate` model in
`wf_api`, then keep all semantic mutation in `WorkflowDraftAuthoringApi`.
Extract the existing capability-aware input-binding preflight into one private
implementation reused by set-input, update, and creation. RPC, MCP, and CLI are
adapters that preserve omitted fields, explicit metadata nulls, and canonical
binding order.

**Tech Stack:** Python 3.14, Pydantic 2, Typer, FastAPI JSON-RPC, FastMCP,
pytest, Ruff, basedpyright.

## Global Constraints

- Never change an existing step's `use` capability.
- Preserve routes, output bindings, and unrelated step fields.
- Omitted update fields preserve stored values.
- Explicit metadata `null` clears; explicit `input: null` is invalid.
- Supplied `input` replaces the complete ordered canonical list; `[]` clears.
- Reuse one capability-aware input preflight for set-input, update, and add.
- Stale revision wins over semantic step, capability, path, and schema errors.
- Metadata-only updates must not resolve the capability source.
- Exact no-ops do not increment revision.
- Input clearing does not delete previously projected workflow schemas.
- Keep compatibility `input_map` for real callers, but reject simultaneous
  compatibility and canonical input forms.
- Keep routes and output bindings under their existing focused operations.
- Python baseline is 3.14. Add comments/docstrings around field-presence and
  schema-projection behavior that is not obvious.
- Use scoped tests in each task and the complete focused matrix only in Task 5.

---

### Task 1: Presence-Aware Model And Canonical Authoring

**Files:**
- Create: `src/wf_api/draft_updates.py`
- Modify: `src/wf_api/__init__.py`
- Modify: `src/wf_api/draft_authoring.py`
- Modify: `tests/wf_api/test_drafts_service.py`

**Interfaces:**
- Produces:
  `CapabilityStepUpdate(desc, retry, timeout_seconds, input)`.
- Produces:
  `WorkflowDraftAuthoringApi.update_capability_step(*, workspace_id: str,
  revision: int, step_id: str, update: CapabilityStepUpdate)`.
- Extends:
  `WorkflowDraftAuthoringApi.add_step_from_capability(..., desc=None,
  retry=None, timeout_seconds=None, input_bindings=None)`.
- Preserves:
  `WorkflowDraftAuthoringApi.set_step_input_bindings(...)`.

- [x] **Step 1: Write failing update-model tests**

Add focused tests in `tests/wf_api/test_drafts_service.py`:

```python
def test_capability_step_update_preserves_field_presence() -> None:
    update = CapabilityStepUpdate.model_validate(
        {"desc": None, "retry": 0, "input": []}
    )

    assert update.model_fields_set == {"desc", "retry", "input"}
    assert update.desc is None
    assert update.retry == 0
    assert update.input == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"input": None},
        {"desc": ""},
        {"retry": -1},
        {"timeout_seconds": 0},
    ],
)
def test_capability_step_update_rejects_invalid_patch(payload: object) -> None:
    with pytest.raises(ValidationError):
        CapabilityStepUpdate.model_validate(payload)
```

- [x] **Step 2: Run the model tests red**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -n 0 `
  tests/wf_api/test_drafts_service.py `
  -q -k "capability_step_update_preserves or capability_step_update_rejects" `
  --basetemp=.pytest-capability-update-model-red
```

Expected: collection fails because `CapabilityStepUpdate` does not exist.

- [x] **Step 3: Implement the update model**

Create `src/wf_api/draft_updates.py`:

```python
from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wf_core.models.steps import InputBinding


class CapabilityStepUpdate(BaseModel):
    """Presence-aware patch for one existing capability-backed draft step."""

    model_config = ConfigDict(extra="forbid")

    desc: str | None = Field(default=None, min_length=1)
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
    input: list[InputBinding] | None = None

    @model_validator(mode="after")
    def validate_patch_shape(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("capability step update requires at least one field")
        if "input" in self.model_fields_set and self.input is None:
            raise ValueError("capability step update input must be a list")
        return self
```

Export it from `src/wf_api/__init__.py`. Run the model tests green.

- [x] **Step 4: Write failing semantic update tests**

Add a helper that creates a capability-backed draft step containing:

- `use`;
- path and literal input bindings;
- output bindings;
- `desc`;
- `retry`;
- `timeout_seconds`;
- routes.

Add tests with field-level assertions:

```python
@pytest.mark.asyncio
async def test_update_capability_step_changes_metadata_and_inputs_atomically(
    tmp_path: Path,
) -> None:
    draft_api, _, authoring = _draft_api(
        FileWorkflowArtifactStore(tmp_path / "update_capability"),
        register_echo=True,
    )
    draft = _echo_draft()
    draft["steps"]["echo"].update(
        {
            "desc": "Old description",
            "retry": 1,
            "timeout_seconds": 10,
        }
    )
    await draft_api.create_draft_workspace(workspace_id="echo", draft=draft)

    result = await authoring.update_capability_step(
        workspace_id="echo",
        revision=1,
        step_id="echo",
        update=CapabilityStepUpdate.model_validate(
            {
                "desc": "New description",
                "retry": 0,
                "timeout_seconds": None,
                "input": [
                    {"path": "input.text", "target": "text"},
                ],
            }
        ),
    )
    inspected = await draft_api.get_draft_workspace(
        workspace_id="echo",
        include_draft=True,
    )

    step = inspected["draft"]["steps"]["echo"]
    assert result["revision"] == 2
    assert step["use"] == "demo.personal.echo_tool"
    assert step["desc"] == "New description"
    assert step["retry"] == 0
    assert "timeout_seconds" not in step
    assert step["input"] == [{"path": "input.text", "target": "text"}]
    assert step["output"] == draft["steps"]["echo"]["output"]
    assert inspected["draft"]["routes"]["echo"] == {"ok": "__end__"}
```

Add separate tests for:

- omitted fields preserved;
- each metadata field set and cleared;
- exact no-op keeps revision;
- `input=[]` clears bindings but preserves projected schemas;
- metadata-only update succeeds when capability lookup is monkeypatched to
  fail;
- missing step and non-`DraftUseStep` rejection;
- stale revision wins over missing step, wrong kind, and unavailable
  capability;
- malformed input leaves the complete inspected workspace unchanged;
- path/literal input replacement projects schemas and preserves order;
- compile/run succeeds after one combined metadata/input update.

- [x] **Step 5: Run semantic tests red**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -n 0 `
  tests/wf_api/test_drafts_service.py `
  -q -k "update_capability_step" `
  --basetemp=.pytest-capability-update-authoring-red
```

Expected: failures because the authoring method does not exist.

- [x] **Step 6: Extract one shared input-binding preflight**

In `src/wf_api/draft_authoring.py`, add a private result model:

```python
@dataclass(frozen=True)
class _ProjectedStepInputBindings:
    payload: list[dict[str, Any]]
    input_schema: dict[str, Any]
    state_schema: dict[str, Any]
```

Extract the current semantic body of `set_step_input_bindings` into a private
method:

```python
def _project_step_input_bindings(
    self,
    *,
    workspace: WorkflowDraftWorkspace,
    capability_name: str,
    bindings: Sequence[InputBinding],
) -> _ProjectedStepInputBindings:
    """Validate canonical inputs and project missing workflow source schemas."""
```

This method must:

1. resolve the capability;
2. reject overlapping local targets;
3. require every target in the capability input schema;
4. validate literal values, including root-object behavior;
5. preserve `context.*` without schema projection;
6. project missing `input.*` and `state.*` source schemas;
7. return canonical binding payload and projected schemas.

Rewrite `set_step_input_bindings` to call this method, preserving its no-op and
patch behavior. Run all existing `set_step_input_bindings` tests before adding
the update method:

```powershell
.venv\Scripts\python.exe -m pytest -n 0 `
  tests/wf_api/test_drafts_service.py `
  -q -k "step_input_bindings" `
  --basetemp=.pytest-capability-update-shared-preflight
```

Expected: PASS.

- [x] **Step 7: Implement atomic capability-step update**

Implement:

```python
async def update_capability_step(
    self,
    *,
    workspace_id: str,
    revision: int,
    step_id: str,
    update: CapabilityStepUpdate,
) -> dict[str, Any]:
    """Patch capability metadata and optional canonical inputs atomically."""
```

Required implementation shape:

```python
checked = self._workspace_if_revision_matches(
    workspace_id=workspace_id,
    revision=revision,
)
if isinstance(checked, dict):
    return checked
workspace = checked
step = draft_step(workspace.draft, step_id)
if step.get("kind") != "use":
    raise ValueError(f"step {step_id!r} is not capability-backed")
current = DraftUseStep.model_validate(step)

changes: dict[str, object] = {}
for field in ("desc", "retry", "timeout_seconds"):
    if field in update.model_fields_set:
        changes[field] = getattr(update, field)

projected = None
if "input" in update.model_fields_set:
    assert update.input is not None
    projected = self._project_step_input_bindings(
        workspace=workspace,
        capability_name=current.use,
        bindings=update.input,
    )
    changes["input"] = update.input

changed = current.model_copy(update=changes)
step_payload = changed.model_dump(
    mode="json",
    by_alias=True,
    exclude_none=True,
)
```

Do not use `model_copy(update=...)` with unvalidated external values; all
values here come from `CapabilityStepUpdate`. Build one patch for changed
schemas plus replacement of `/steps/<step_id>`. If the step payload and
schemas are unchanged, return `summarize_draft_workspace(workspace)`.

- [x] **Step 8: Write failing creation-parity tests**

Add tests proving:

```python
result = await authoring.add_step_from_capability(
    workspace_id="report",
    revision=1,
    step_id="publish",
    capability_name="demo.personal.structured_report",
    routes={"ok": "__end__"},
    desc="Publish report",
    retry=2,
    timeout_seconds=30,
    input_bindings=[
        InputPathBinding(
            path=GraphSourcePath.state("report", "title"),
            target=LocalPath.of("request", "title"),
        ),
        InputValueBinding(
            target=LocalPath.of("request", "format"),
            value="markdown",
        ),
    ],
)
```

Assert metadata, ordered canonical bindings, and projected schemas. Add tests
rejecting `input_map` and `input_bindings` whenever both arguments are
supplied, including an explicit empty compatibility map, and proving existing
map-only callers retain behavior.

- [x] **Step 9: Extend creation through the shared preflight**

Extend the method signature:

```python
async def add_step_from_capability(
    ...,
    input_map: dict[str, str] | None = None,
    input_bindings: Sequence[InputBinding] | None = None,
    bind_outputs: dict[str, str] | None = None,
    desc: str | None = None,
    retry: int | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
```

If both canonical bindings and a compatibility map are supplied, even when
either collection is explicitly empty, raise:

```text
input_map and input_bindings are mutually exclusive
```

Lower compatibility `input_map` with `input_bindings_payload(input_map, {})`
and validate the resulting typed list, or accept `input_bindings` directly.
Use `_project_step_input_bindings` for both. Persist metadata only when not
`None`; `retry=0` must survive.

- [x] **Step 10: Verify and commit Task 1**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -n 0 `
  tests/wf_api/test_drafts_service.py -q `
  --basetemp=.pytest-capability-update-task1
.venv\Scripts\ruff.exe check `
  src/wf_api/draft_updates.py `
  src/wf_api/draft_authoring.py `
  tests/wf_api/test_drafts_service.py
.venv\Scripts\basedpyright.exe --level error `
  src/wf_api/draft_updates.py `
  src/wf_api/draft_authoring.py
```

Then:

```bash
git add src/wf_api/__init__.py src/wf_api/draft_updates.py \
  src/wf_api/draft_authoring.py tests/wf_api/test_drafts_service.py
git commit -m "feat: update capability-backed draft steps"
```

---

### Task 2: Public Interface And JSON-RPC

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
- Consumes: Task 1's `CapabilityStepUpdate`,
  `update_capability_step(...)`, and extended `add_step_from_capability(...)`.
- Produces:
  `workflow.draft_workspaces.update_capability_step`.
- Extends the existing add-capability RPC with metadata and canonical
  `input_bindings`.

- [x] **Step 1: Write failing RPC model tests**

Add tests for:

```python
params = UpdateCapabilityStepParams.model_validate(
    {
        "workspace_id": "report",
        "revision": 4,
        "step_id": "publish",
        "update": {"desc": None, "retry": 0},
    }
)

assert params.update.model_fields_set == {"desc", "retry"}
assert params.update.desc is None
assert params.update.retry == 0
```

Add malformed cases for empty update, `input:null`, negative retry, zero
timeout, and unknown fields. Extend `AddStepFromCapabilityParams` tests for
metadata, canonical path/value order, and simultaneous `input_map` plus
`input_bindings`.

- [x] **Step 2: Run RPC model tests red**

Run the focused new tests. Expected: import/model failures.

- [x] **Step 3: Add RPC models**

Add:

```python
class UpdateCapabilityStepParams(RpcParamsModel):
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    step_id: str = Field(min_length=1)
    update: CapabilityStepUpdate
```

Extend `AddStepFromCapabilityParams`:

```python
input_map: dict[str, str] | None = None
input_bindings: list[InputBinding] | None = None
desc: str | None = Field(default=None, min_length=1)
retry: int | None = Field(default=None, ge=0)
timeout_seconds: int | None = Field(default=None, gt=0)
```

Add a model validator rejecting both input forms when both were supplied.

- [x] **Step 4: Write failing endpoint and client tests**

Add a real ASGI test that creates a capability step, updates metadata and a
literal input through:

```text
workflow.draft_workspaces.update_capability_step
```

Inspect the draft and assert preservation of `use`, routes, and outputs.

Add a client serialization test that passes:

```python
CapabilityStepUpdate.model_validate({"desc": None, "retry": 0})
```

and asserts the emitted nested object is exactly:

```python
{"desc": None, "retry": 0}
```

No default `timeout_seconds` or `input` keys may appear. Extend add-capability
client tests for canonical input order and metadata.

- [x] **Step 5: Implement public and RPC adapters**

Add the update method to `WorkflowDraftSurface` and `WorkflowApi`, delegating to
`draft_authoring`.

Register the RPC method and client. The client must serialize:

```python
update.model_dump(mode="json", exclude_unset=True)
```

Extend every add-capability seam with the Task 1 fields. Compatibility map-only
calls remain valid.

- [x] **Step 6: Verify and commit Task 2**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -n 0 `
  tests/wf_transport_rpc_http/test_app.py `
  tests/wf_transport_rpc_http/test_client.py `
  -q --basetemp=.pytest-capability-update-task2
.venv\Scripts\ruff.exe check src/wf_api src/wf_transport_rpc_http `
  tests/wf_transport_rpc_http
.venv\Scripts\basedpyright.exe --level error
```

Commit:

```bash
git add src/wf_api/surface.py src/wf_api/service.py \
  src/wf_transport_rpc_http tests/wf_transport_rpc_http
git commit -m "feat: expose capability step updates over rpc"
```

---

### Task 3: MCP Update Tool And Creation Parity

**Files:**
- Modify: `src/wf_mcp/workflow_surface/models.py`
- Modify: `src/wf_mcp/workflow_surface/tools.py`
- Modify: `src/wf_mcp/proxy/runtime.py`
- Modify: `tests/wf_mcp/workflow_surface/test_drafts.py`
- Modify: `tests/wf_mcp/server/test_tools.py`
- Modify: `tests/wf_mcp/server/test_config.py`

**Interfaces:**
- Consumes: Task 2's public update method and Task 1's model.
- Produces: `wf.workflow.update_capability_step`.
- Extends: `wf.workflow.add_step_from_capability`.

- [ ] **Step 1: Write failing MCP request tests**

Add:

```python
request = UpdateCapabilityStepRequest.model_validate(
    {
        "workspace_id": "report",
        "revision": 4,
        "step_id": "publish",
        "update": {
            "desc": None,
            "input": [
                {"value": "markdown", "target": "request.format"},
            ],
        },
    }
)

assert request.update.model_fields_set == {"desc", "input"}
assert isinstance(request.update.input[0], InputValueBinding)
```

Add malformed update cases and add-capability request parity tests.

- [ ] **Step 2: Write failing discovery and real invocation tests**

Require the tool in normal and search-mode inventories. Call it through an
in-memory FastMCP client and assert:

- one delegation;
- typed `CapabilityStepUpdate`;
- exact `model_fields_set`;
- exact canonical binding order.

Extend the add-capability invocation test with metadata and a literal binding.

- [ ] **Step 3: Implement MCP request and tools**

Add:

```python
class UpdateCapabilityStepRequest(BaseModel):
    workspace_id: WorkspaceId
    revision: int = Field(ge=1)
    step_id: NonEmptyString
    update: CapabilityStepUpdate
```

Register:

```python
@server.tool(
    name="wf.workflow.update_capability_step",
    title="Update Capability Step",
    description=(
        "Update capability-step metadata and optionally replace its complete "
        "canonical input bindings. Preserves use, routes, and outputs."
    ),
)
async def update_capability_step(
    request: UpdateCapabilityStepRequest,
) -> DraftWorkspaceResult:
    return DraftWorkspaceResult.model_validate(
        await handlers.update_capability_step(
            workspace_id=request.workspace_id,
            revision=request.revision,
            step_id=request.step_id,
            update=request.update,
        )
    )
```

Add the name to `_SEARCH_ALWAYS_VISIBLE_TOOL_NAMES`. Extend
`AddStepFromCapabilityRequest` and its tool delegation with the creation-parity
fields.

- [ ] **Step 4: Verify and commit Task 3**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -n 0 `
  tests/wf_mcp/workflow_surface/test_drafts.py `
  tests/wf_mcp/server/test_tools.py `
  tests/wf_mcp/server/test_config.py `
  -q --basetemp=.pytest-capability-update-task3
.venv\Scripts\ruff.exe check src/wf_mcp tests/wf_mcp
.venv\Scripts\basedpyright.exe --level error
```

Commit:

```bash
git add src/wf_mcp tests/wf_mcp
git commit -m "feat: expose capability step updates to mcp"
```

---

### Task 4: Add And Update CLI

**Files:**
- Create: `src/wf_cli/commands/draft_update.py`
- Modify: `src/wf_cli/commands/draft_add.py`
- Modify: `src/wf_cli/commands/draft_options.py`
- Modify: `src/wf_cli/commands/drafts.py`
- Modify: `tests/wf_cli/test_app.py`
- Modify: `tests/wf_cli/test_remote_target.py`

**Interfaces:**
- Consumes: Task 2's local/remote update and extended add methods.
- Produces: `wf draft update capability`.
- Extends: `wf draft add capability`.

- [ ] **Step 1: Write failing parser tests**

Refactor the private input-shaped path parser so the option name and target
audience are parameters:

```python
def _parse_input_path_binding_flags(
    values: list[str] | None,
    *,
    option_name: str,
    target_label: str,
) -> list[InputPathBinding]:
```

Keep `parse_step_input_binding_flags` behavior unchanged. Add:

```python
def parse_capability_input_binding_flags(
    values: list[str] | None,
) -> list[InputPathBinding]:
    return _parse_input_path_binding_flags(
        values,
        option_name="--input",
        target_label="node-local",
    )
```

Reuse `parse_step_input_value_flags` and `parse_step_input_bindings_file`.
Write tests for `--input`-specific diagnostics and canonical order.

- [ ] **Step 2: Write failing update command tests**

Add local CLI tests for:

```bash
wf draft update capability report --revision 4 --step publish \
  --description "Publish report" \
  --retry 0 \
  --clear-timeout \
  --input state.report.title=request.title \
  --value request.format='"markdown"'
```

Assert the fake handler receives a `CapabilityStepUpdate` whose
`model_fields_set` is exactly:

```python
{"desc", "retry", "timeout_seconds", "input"}
```

and whose input bindings preserve path-then-literal order.

Add tests for every set/clear conflict, bindings-file conflict, clear-input
conflict, empty update, and validation before `load_cli_context`.

- [ ] **Step 3: Implement the update command group**

Create `draft_update.py` with a Typer group and `capability` command. Build a
plain `payload` dictionary only from selected flags:

```python
payload: dict[str, object] = {}
if description is not None:
    payload["desc"] = description
elif clear_description:
    payload["desc"] = None

if retry is not None:
    payload["retry"] = retry
elif clear_retry:
    payload["retry"] = None

if timeout_seconds is not None:
    payload["timeout_seconds"] = timeout_seconds
elif clear_timeout:
    payload["timeout_seconds"] = None

if input_mode_selected:
    payload["input"] = bindings

update = CapabilityStepUpdate.model_validate(payload)
```

Parse all exclusivity and validation errors before loading context. Register:

```python
app.add_typer(draft_update.app, name="update")
```

in `drafts.py`.

- [ ] **Step 4: Write failing add-command parity tests**

Test `wf draft add capability` with metadata, `--input`, `--value`, and
`--bindings-file`. Pin:

- canonical path/value order;
- `retry=0`;
- bindings-file exact interleaving;
- file/convenience exclusivity before context;
- existing path-only invocation unchanged.

- [ ] **Step 5: Extend add capability**

Add the approved flags and call canonical `input_bindings`. Do not pass both
the compatibility map and canonical list. The CLI should use canonical
bindings for every new invocation; `input_map` remains only for non-CLI
compatibility callers.

- [ ] **Step 6: Add remote parity tests**

Use the real ASGI RPC target to assert exact methods and payloads:

```text
workflow.draft_workspaces.update_capability_step
workflow.draft_workspaces.add_step_from_capability
```

For update, assert omitted metadata keys do not appear and explicit clears do.
For add, assert ordered path/value input bindings and metadata.

- [ ] **Step 7: Verify and commit Task 4**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -n 0 `
  tests/wf_cli/test_app.py `
  tests/wf_cli/test_remote_target.py `
  -q --basetemp=.pytest-capability-update-task4
.venv\Scripts\ruff.exe check src/wf_cli tests/wf_cli
.venv\Scripts\basedpyright.exe --level error
```

Commit:

```bash
git add src/wf_cli tests/wf_cli
git commit -m "feat: add capability step update cli"
```

---

### Task 5: Documentation, Verification, And Review

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
- Move:
  `docs/superpowers/plans/2026-07-26-capability-step-update.md` to
  `docs/historical/superpowers/plans/2026-07-26-capability-step-update.md`

**Interfaces:**
- Consumes: verified Tasks 1-4.
- Produces: accurate current docs, closed issue state, archived checked plan,
  and final review evidence.

- [ ] **Step 1: Update issue and roadmap state**

Mark the focused capability-step update issue complete. State that:

- creation accepts metadata and canonical literal inputs;
- update preserves `use`, routes, and outputs;
- update can atomically replace canonical input bindings;
- changing capability remains remove/add;
- TypeScript parity remains open.

Add a completed roadmap entry linked to the historical plan.

- [ ] **Step 2: Update user and agent docs**

Document:

```bash
wf draft add capability report --revision 3 --step publish \
  --capability local.report.publish \
  --description "Publish report" \
  --retry 2 \
  --timeout-seconds 30 \
  --input state.report.title=request.title \
  --value request.format='"markdown"' \
  --route ok=__end__

wf draft update capability report --revision 4 --step publish \
  --clear-description \
  --retry 0 \
  --clear-timeout
```

Explain omission versus clearing, complete input replacement, bindings-file
interleaving, and separate route/output operations. Add JSON-RPC and MCP
operation names to live inventories.

- [ ] **Step 3: Archive the checked plan**

Mark every checkbox complete, move the plan to the historical path, and update
all live links:

```powershell
rg -n '2026-07-26-capability-step-update' docs skills README.md
```

- [ ] **Step 4: Run the full focused matrix**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -n 0 `
  tests/wf_api/test_drafts_service.py `
  tests/wf_transport_rpc_http/test_app.py `
  tests/wf_transport_rpc_http/test_client.py `
  tests/wf_mcp/workflow_surface/test_drafts.py `
  tests/wf_mcp/server/test_tools.py `
  tests/wf_mcp/server/test_config.py `
  tests/wf_cli/test_app.py `
  tests/wf_cli/test_remote_target.py `
  -q --basetemp=.pytest-capability-update-final
```

Expected: PASS with only already-known dependency deprecation warnings.

- [ ] **Step 5: Run static verification**

Run:

```powershell
.venv\Scripts\ruff.exe check
.venv\Scripts\ruff.exe format --check
.venv\Scripts\basedpyright.exe --level error
git diff --check
```

Expected: all clean.

- [ ] **Step 6: Run independent two-axis review**

Review from commit `05afc2e1` through the current worktree against:

```text
docs/superpowers/specs/2026-07-26-capability-step-update-design.md
```

Require findings first with severity and file/line references. The spec
reviewer must inspect:

- omission versus explicit null;
- explicit `input:null` rejection;
- stale-revision precedence;
- metadata-only operation without capability resolution;
- no-op revision behavior;
- preservation of `use`, outputs, and routes;
- shared input preflight rather than duplicated semantics;
- add/update canonical input parity;
- RPC `exclude_unset=True`;
- CLI pre-context exclusivity;
- MCP discovery and real invocation;
- docs and issue truthfulness.

Fix every Critical and Important finding and rerun affected checks.

- [ ] **Step 7: Commit documentation and review fixes**

Commit documentation:

```bash
git add ISSUES.md docs skills
git commit -m "docs: complete capability step updates"
```

Commit production/test review fixes separately after verification. Finish:

```powershell
git status --short --branch
git log --oneline -10
```

Expected: clean worktree and task-level commits.
