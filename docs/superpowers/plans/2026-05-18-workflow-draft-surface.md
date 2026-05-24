# Workflow Draft Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the disposable draft prototype with the first real MCP-facing workflow draft surface: keyed, patchable JSON that adapts into `wf_authoring.WorkflowBuilder` instead of rebuilding graph semantics itself.

**Architecture:** The new draft layer remains a typed JSON seam in `wf_artifacts`, but delegates graph construction to `wf_authoring`. Draft parsing owns keyed presentation, validation, and stable patch paths; `WorkflowBuilder` owns graph construction. The MCP workflow surface keeps the same tool family while accepting the new draft shape.

**Tech Stack:** Python 3.14, Pydantic v2, `wf_authoring`, `wf_core`, `jsonpatch`, pytest, basedpyright, Ruff.

---

## File Structure

### Create

- `src/wf_artifacts/drafts/models.py`
  - concrete Pydantic draft document models
- `src/wf_artifacts/drafts/adapter.py`
  - thin JSON-draft-to-`WorkflowBuilder` adapter
- `src/wf_artifacts/drafts/api.py`
  - public compile/validate/patch functions and diagnostics
- `tests/artifacts/test_draft_models.py`
  - draft document validation
- `tests/artifacts/test_draft_adapter.py`
  - keyed step/routes lowering through `WorkflowBuilder`
- `tests/artifacts/test_draft_api.py`
  - public compile/validate/patch behavior

### Modify

- `src/wf_artifacts/drafts.py`
  - replace module body with compatibility re-exports or remove once imports are updated
- `src/wf_artifacts/__init__.py`
  - export public draft API/models from the package
- `src/wf_authoring/builder/core.py`
  - add `use_ref(...)` for named external capabilities without local `NodeSpec`s
- `src/wf_authoring/ops/*`
  - only if route helpers need a reusable public lowering entrypoint
- `src/wf_mcp/workflow_surface/handlers.py`
  - keep using public draft API; no semantic duplication
- `tests/wf_mcp/test_workflow_surface.py`
  - update draft fixtures to the new keyed document shape
- `tests/wf_mcp/test_server.py`
  - confirm MCP schemas remain plain-object friendly
- `docs/workflow_drafts.md`
  - replace prototype examples with the first real draft surface
- `docs/wf_mcp_end_to_end_runbook.md`
  - update draft example
- `docs/wf_mcp_operator_manual.md`
  - keep draft-first guidance accurate
- `docs/wf_mcp_troubleshooting.md`
  - update patch-path examples

## Task 1: Split Draft Code Into Focused Modules

**Files:**

- Create: `src/wf_artifacts/drafts/models.py`
- Create: `src/wf_artifacts/drafts/api.py`
- Create: `src/wf_artifacts/drafts/adapter.py`
- Modify: `src/wf_artifacts/drafts.py`
- Modify: `src/wf_artifacts/__init__.py`
- Test: `tests/artifacts/test_draft_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
from wf_artifacts.drafts import DraftUseStep, WorkflowDraft


def test_workflow_draft_uses_keyed_steps() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "echo",
            "input_schema": {},
            "state_schema": {"fields": {}},
            "output_schema": {},
            "start": "echo",
            "steps": {
                "echo": {
                    "use": "demo.echo",
                    "in": {"input.text": "text"},
                    "out": {"echoed": "state.echoed"},
                }
            },
            "routes": {"echo": {"ok": "__end__"}},
        }
    )

    assert isinstance(draft.steps["echo"], DraftUseStep)
    assert draft.steps["echo"].use == "demo.echo"


def test_draft_step_requires_exactly_one_kind_key() -> None:
    result = WorkflowDraft.model_validate(
        {
            "name": "bad",
            "input_schema": {},
            "state_schema": {"fields": {}},
            "output_schema": {},
            "start": "bad",
            "steps": {
                "bad": {
                    "use": "demo.echo",
                    "join": {},
                }
            },
            "routes": {},
        }
    )
```

The second test should be written with `pytest.raises(ValidationError)` and assert the authoring path identifies `steps.bad`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest pytest tests/artifacts/test_draft_models.py -q
```

Expected: import errors or validation failures because keyed draft models do not exist yet.

- [ ] **Step 3: Implement minimal concrete draft models**

Create:

```python
# src/wf_artifacts/drafts/models.py
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

JsonObject = dict[str, Any]
STEP_KIND_KEYS = frozenset({"use", "foreach", "interrupt", "join"})


class DraftUseStep(BaseModel):
    use: str
    in_: dict[str, str] = Field(default_factory=dict, alias="in")
    out: dict[str, str] = Field(default_factory=dict)
    desc: str | None = None
    retry: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)


class DraftForeachPayload(BaseModel):
    over: str
    as_: str = Field(alias="as")
    mode: Literal["serial", "parallel"] = "serial"
    on_item_error: Literal["fail", "collect", "skip"] = "fail"


class DraftForeachStep(BaseModel):
    foreach: DraftForeachPayload


class DraftInterruptPayload(BaseModel):
    kind: str
    request: dict[str, str] = Field(default_factory=dict)
    resume: dict[str, str] = Field(default_factory=dict)
    outcomes: list[str] = Field(default_factory=lambda: ["submitted"])


class DraftInterruptStep(BaseModel):
    interrupt: DraftInterruptPayload


class DraftJoinStep(BaseModel):
    join: JsonObject = Field(default_factory=dict)


DraftStep = Annotated[
    DraftUseStep
    | DraftForeachStep
    | DraftInterruptStep
    | DraftJoinStep,
    Field(discriminator=None),
]


class WorkflowDraft(BaseModel):
    name: str
    input_schema: JsonObject
    state_schema: JsonObject
    output_schema: JsonObject
    start: str
    steps: dict[str, DraftStep]
    routes: dict[str, dict[str, str]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _validate_step_kinds(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        steps = value.get("steps")
        if not isinstance(steps, dict):
            return value
        for step_id, payload in steps.items():
            if not isinstance(payload, dict):
                continue
            present = STEP_KIND_KEYS.intersection(payload)
            if len(present) != 1:
                raise ValueError(
                    f"steps.{step_id} must contain exactly one step kind key"
                )
        return value
```

Keep the public import path stable by re-exporting through `src/wf_artifacts/drafts.py` during the transition.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --with pytest pytest tests/artifacts/test_draft_models.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_artifacts tests/artifacts/test_draft_models.py
git commit -m "refactor: add keyed workflow draft models"
```

## Task 2: Add `use_ref` And Thin Adapter Over `WorkflowBuilder`

**Files:**

- Create: `src/wf_artifacts/drafts/adapter.py`
- Modify only if needed: `src/wf_authoring/builder/core.py`
- Modify only if needed: `src/wf_authoring/ops/*`
- Test: `tests/artifacts/test_draft_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

```python
from wf_artifacts.drafts import WorkflowDraft
from wf_artifacts.drafts.adapter import build_workflow_from_draft


def test_adapter_lowers_keyed_use_steps_and_routes_through_builder() -> None:
    draft = WorkflowDraft.model_validate(
        {
            "name": "echo",
            "input_schema": {},
            "state_schema": {"fields": {}},
            "output_schema": {},
            "start": "echo",
            "steps": {"echo": {"use": "demo.echo"}},
            "routes": {"echo": {"ok": "__end__"}},
        }
    )

    workflow = build_workflow_from_draft(draft)

    assert workflow.nodes[0].id == "echo"
    assert workflow.nodes[0].node == "demo.echo"
    assert workflow.edges[0].from_ == "echo"
    assert workflow.edges[0].outcome == "ok"
    assert workflow.edges[0].to == "__end__"


def test_builder_use_ref_creates_external_node_use_without_node_def() -> None:
    builder = WorkflowBuilder(
        "echo",
        input_schema={},
        state_schema={"fields": {}},
        output_schema={},
    )

    step = builder.use_ref("demo.echo", id="echo")
    builder.set_entry_point(step)
    builder.connect(step, "ok", "__end__")
    workflow = builder.compile()

    assert step.node == "demo.echo"
    assert workflow.node_defs == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest pytest tests/artifacts/test_draft_adapter.py -q
```

Expected: import error because `build_workflow_from_draft` does not exist.

- [ ] **Step 3: Implement the thin adapter**

First add:

```python
def use_ref(
    self,
    name: str,
    *,
    id: str | None = None,
    in_map: MapArg | None = None,
    out_map: MapArg | None = None,
    desc: str | None = None,
) -> NodeUse:
    ...
```

`use_ref` creates a `NodeUse` for an already named external capability and does
not add a local `NodeDef`.

Then implement `build_workflow_from_draft(draft: WorkflowDraft) -> Workflow` so
it:

1. constructs a `WorkflowBuilder`
2. registers each draft step by stable id
3. uses existing `WorkflowBuilder` public methods for:
   - `use_ref`
   - `foreach`
   - `interrupt`
   - `join`
4. applies `routes`
5. calls explicit `start(...)`
6. returns `builder.build(...)`

Do **not** invent draft route sugar in this pass.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --with pytest pytest tests/artifacts/test_draft_adapter.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_artifacts src/wf_authoring tests/artifacts/test_draft_adapter.py
git commit -m "feat: adapt workflow drafts through workflow builder"
```

## Task 3: Replace Prototype Public API

**Files:**

- Create: `src/wf_artifacts/drafts/api.py`
- Modify: `src/wf_artifacts/drafts.py`
- Modify: `src/wf_artifacts/__init__.py`
- Test: `tests/artifacts/test_draft_api.py`

- [ ] **Step 1: Write failing API tests**

```python
from wf_artifacts.drafts import compile_workflow_draft, patch_workflow_draft


def test_compile_workflow_draft_returns_raw_core_shape() -> None:
    plan = compile_workflow_draft(_keyed_echo_draft())

    assert plan["nodes"][0]["id"] == "echo"
    assert plan["nodes"][0]["node"] == "demo.echo"
    assert plan["edges"][0]["outcome"] == "ok"


def test_patch_workflow_draft_uses_stable_step_paths() -> None:
    result = patch_workflow_draft(
        _keyed_echo_draft(),
        [
            {
                "op": "replace",
                "path": "/steps/echo/in/input.text",
                "value": "message",
            }
        ],
    )

    assert result["status"] == "valid"
    assert result["draft"]["steps"]["echo"]["in"]["input.text"] == "message"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest pytest tests/artifacts/test_draft_api.py -q
```

Expected: failures because the old prototype API still expects array `steps`.

- [ ] **Step 3: Implement the API**

Create:

```python
# src/wf_artifacts/drafts/api.py
def compile_workflow_draft(draft: JsonObject) -> JsonObject:
    parsed = WorkflowDraft.model_validate(draft)
    workflow = build_workflow_from_draft(parsed)
    return workflow.model_dump(mode="json", by_alias=True, exclude={"node_defs"})
```

Keep:

- `validate_workflow_draft`
- `patch_workflow_draft`
- structured `DraftDiagnostic`

Update diagnostics to use keyed paths such as:

```text
steps.echo.in
routes.echo.error
```

Delete the old array-step prototype code after public tests are green.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --with pytest pytest tests/artifacts/test_draft_api.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_artifacts tests/artifacts/test_draft_api.py
git commit -m "feat: replace draft prototype with keyed public api"
```

## Task 4: Update MCP Workflow Surface

**Files:**

- Modify: `tests/wf_mcp/test_workflow_surface.py`
- Modify: `tests/wf_mcp/test_server.py`
- Modify only if needed: `src/wf_mcp/workflow_surface/handlers.py`

- [ ] **Step 1: Update the failing MCP tests**

Replace old fixtures like:

```python
"steps": [{"id": "echo", "kind": "use", ...}]
```

with:

```python
"steps": {"echo": {"use": "demo.echo", ...}},
"routes": {"echo": {"ok": "__end__"}},
```

Keep assertions that:

- draft tools still expose plain object schemas to MCP clients
- `create_artifact_from_draft` still saves artifacts
- source binding normalization still works
- missing `wf.std` self-binding diagnostics still work

- [ ] **Step 2: Run tests to verify failures**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface.py tests/wf_mcp/test_server.py -q
```

Expected: failures wherever MCP handlers still assume the old prototype shape.

- [ ] **Step 3: Make minimal MCP adjustments**

Keep handlers thin:

```python
plan = compile_workflow_draft(draft)
```

No duplicate draft interpretation should appear in `wf_mcp`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface.py tests/wf_mcp/test_server.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_mcp tests/wf_mcp
git commit -m "feat: accept keyed workflow drafts over mcp"
```

## Task 5: Add Outcome Validation When Capability Contracts Are Available

**Files:**

- Modify: `src/wf_artifacts/drafts/api.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_mcp/test_workflow_surface.py`

- [ ] **Step 1: Write failing outcome validation test**

```python
def test_draft_validation_rejects_unknown_capability_outcome_when_spec_is_known() -> None:
    handlers = _handlers_with_demo_echo_spec()
    draft = _keyed_echo_draft()
    draft["routes"]["echo"] = {"typo": "__end__"}

    result = asyncio.run(handlers.validate_draft(draft=draft))

    assert result["status"] == "invalid"
    assert result["diagnostics"][0]["path"] == "routes.echo.typo"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface.py -q
```

Expected: validation currently accepts the typo.

- [ ] **Step 3: Implement capability-aware outcome validation**

Pass an optional capability lookup into draft validation from MCP handlers.

Rules:

- validate outcome keys for `use` steps only when the capability is resolvable
- if the capability is unknown/unavailable, leave dependency validation to the
  later artifact/deployment stages
- diagnostic path must identify the keyed route entry

Do not make `wf_artifacts` depend on `wf_mcp`; define a tiny callable/protocol
interface for lookup instead.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --with pytest pytest tests/wf_mcp/test_workflow_surface.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/wf_artifacts src/wf_mcp tests/wf_mcp/test_workflow_surface.py
git commit -m "feat: validate draft routes against known outcomes"
```

## Task 6: Update Documentation

**Files:**

- Modify: `docs/workflow_drafts.md`
- Modify: `docs/wf_mcp_end_to_end_runbook.md`
- Modify: `docs/wf_mcp_operator_manual.md`
- Modify: `docs/wf_mcp_troubleshooting.md`

- [ ] **Step 1: Update docs to the real draft surface**

Replace prototype array examples with keyed examples:

```json
"steps": {
  "echo": {
    "use": "demo.echo_tool",
    "in": {"input.text": "text"},
    "out": {"echoed": "state.echoed"}
  }
},
"routes": {
  "echo": {
    "ok": "__end__"
  }
}
```

Document:

- exactly-one-kind-key rule
- stable keyed patch paths
- `route` as repeated condition-chain sugar
- `WorkflowBuilder` as the semantic owner beneath the JSON adapter
- outcome strings validated against capability contracts when available

- [ ] **Step 2: Run a targeted docs scan**

Run:

```bash
rg -n '\"steps\": \\[|\"kind\": \"use\"|/steps/0|create_artifact_from_draft' docs
```

Expected:

- no stale prototype examples in current docs
- `create_artifact_from_draft` still documented as the preferred path

- [ ] **Step 3: Commit**

```bash
git add docs
git commit -m "docs: describe keyed workflow draft surface"
```

## Task 7: Full Verification

**Files:**

- No new files

- [ ] **Step 1: Run focused verification**

```bash
uv run --with pytest pytest tests/artifacts tests/wf_mcp/test_workflow_surface.py tests/wf_mcp/test_server.py -q
```

Expected: pass.

- [ ] **Step 2: Run full project tests**

```bash
uv run --with pytest pytest -q
```

Expected: pass.

- [ ] **Step 3: Run type checking**

```bash
uv run basedpyright --level error
```

Expected: `0 errors`.

- [ ] **Step 4: Run lint**

```bash
uvx ruff check src tests
```

Expected: pass.

- [ ] **Step 5: Commit final cleanup**

```bash
git add .
git commit -m "feat: ship keyed workflow draft authoring surface"
```

## Self-Review

### Spec Coverage

- keyed `steps`: Tasks 1-4
- compact `routes`: Tasks 1-4
- verb-keyed explicit step kinds: Task 1
- saved capability/workflow refs in `use`: Task 2, existing capability refs pass through unchanged
- stable patch paths: Tasks 3 and 6
- `wf_authoring` as semantic owner: Tasks 2 and 6
- outcome validation against declared contracts: Task 5
- prototype replacement rather than migration: Tasks 3, 4, 6

### Placeholder Scan

- no `TBD`
- no unspecified "add validation" placeholders
- every task has exact files, tests, commands, and expected behavior

### Type Consistency

- `WorkflowDraft`, `DraftUseStep`, `build_workflow_from_draft`, and public API
  names stay consistent across all tasks
- patch examples use keyed paths consistently
- `routes` stays the only authored outcome-routing section
