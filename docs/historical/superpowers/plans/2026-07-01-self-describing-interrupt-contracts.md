# Self-Describing Interrupt Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add machine-readable interrupt request/resume schemas to workflow definitions, persisted interrupt inspection, and resume validation.

**Architecture:** Store JSON Schema dictionaries on `InterruptNode`, validate request/resume payloads with the existing runtime JSON Schema helper, and copy the contract into `InterruptRequest` so durable run inspection is self-contained. Keep legacy workflows compatible by defaulting missing schemas to permissive object schemas and marking them `typed=false`.

**Tech Stack:** Python 3.14, Pydantic, `jsonschema`, pytest, Typer CLI, JSON-RPC HTTP transport.

---

## Scope

Implement the prerequisite platform contract from
[`docs/superpowers/specs/2026-07-01-self-describing-interrupt-contracts.md`](../specs/2026-07-01-self-describing-interrupt-contracts.md).

Do not build the web console, the demo agent, or the prepared `lda.chat` report
workflow in this plan. This slice only makes interrupts self-describing.

## File Structure

- Modify `src/wf_core/models/steps.py`
  - Add `request_schema`, `resume_schema`, and `typed`-derivation helpers to
    `InterruptNode`.
- Modify `src/wf_core/run_state.py`
  - Add interrupt contract fields to `InterruptRequest`.
- Modify `src/wf_core/runtime/ops/interrupts.py`
  - Validate request payloads before pausing.
  - Validate resume payloads before state mutation.
  - Copy schemas/outcomes/typed flag into `InterruptRequest`.
- Modify `src/wf_core/validation/steps.py`
  - Validate interrupt schema objects during workflow validation.
- Modify `src/wf_api/runs.py`
  - Ensure `inspect_run`, `run start`, `trace`, and `resume` include JSON-safe
    interrupt contract fields.
- Modify `src/wf_cli/commands/runs.py`
  - Keep JSON output as source of truth.
  - Improve `resume` docstring/help to mention schema validation.
- Modify docs and skills:
  - `docs/wf_cli.md`
  - `docs/current_roadmap.md`
  - `skills/wf-cli/SKILL.md`
  - `skills/wf-workflow/references/workflow-lifecycle.md`
- Tests:
  - `tests/core/test_canonical_node_bindings.py`
  - `tests/core/test_execution_results.py`
  - `tests/core/test_run_codec.py`
  - `tests/core/test_subgraph_step.py`
  - `tests/wf_api/test_run_api.py`
  - `tests/wf_cli/test_run_deploy.py`
  - `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`

## Behavioral Contract

Use this permissive schema for legacy/untyped interrupts:

```python
def _object_schema() -> dict[str, object]:
    return {"type": "object", "additionalProperties": True}
```

An interrupt is typed when the original node payload explicitly includes either
`request_schema` or `resume_schema`.

Runtime validation rules:

- request payload validation happens after request bindings build `payload` and
  before setting `run.interrupt`;
- resume payload validation happens after resolving the paused `InterruptNode`
  and before `build_output_patch`;
- validation uses `wf_core.runtime.ops.schemas.validate_payload_against_schema`;
- invalid payloads raise `WorkflowExecutionError` through the existing runtime
  error path;
- no state mutation or trace append happens when resume payload validation
  fails.

---

### Task 1: Model Defaults And Serialization

**Files:**
- Modify: `src/wf_core/models/steps.py`
- Test: `tests/core/test_canonical_node_bindings.py`

- [ ] **Step 1: Add failing tests for interrupt schemas**

Add these tests near the existing interrupt binding tests in
`tests/core/test_canonical_node_bindings.py`:

```python
def test_interrupt_node_defaults_to_untyped_object_contract():
    node = InterruptNode.model_validate(
        {
            "id": "approval",
            "type": "interrupt",
            "kind": "approval",
        }
    )

    assert node.request_schema == {
        "type": "object",
        "additionalProperties": True,
    }
    assert node.resume_schema == {
        "type": "object",
        "additionalProperties": True,
    }
    assert node.has_explicit_contract is False

    dumped = node.model_dump(mode="json")
    assert dumped["request_schema"] == {
        "type": "object",
        "additionalProperties": True,
    }
    assert dumped["resume_schema"] == {
        "type": "object",
        "additionalProperties": True,
    }


def test_interrupt_node_accepts_explicit_request_and_resume_schemas():
    node = InterruptNode.model_validate(
        {
            "id": "approval",
            "type": "interrupt",
            "kind": "approval",
            "request_schema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
                "additionalProperties": False,
            },
            "resume_schema": {
                "type": "object",
                "properties": {"approved": {"type": "boolean"}},
                "required": ["approved"],
                "additionalProperties": False,
            },
        }
    )

    assert node.has_explicit_contract is True
    assert node.request_schema["required"] == ["message"]
    assert node.resume_schema["required"] == ["approved"]
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
uv run pytest tests/core/test_canonical_node_bindings.py::test_interrupt_node_defaults_to_untyped_object_contract tests/core/test_canonical_node_bindings.py::test_interrupt_node_accepts_explicit_request_and_resume_schemas -q -n0
```

Expected: both fail because `InterruptNode` has no schema fields.

- [ ] **Step 3: Add model fields and explicit-contract detection**

In `src/wf_core/models/steps.py`, add this helper near `InterruptNode`:

```python
def _object_schema() -> dict[str, object]:
    """Default legacy interrupt contract: any JSON object payload is accepted."""
    return {"type": "object", "additionalProperties": True}
```

Update `InterruptNode`:

```python
class InterruptNode(BaseModel):
    """Control-flow step that pauses a run and waits for resume input."""

    id: str
    type: Literal["interrupt"]
    kind: str
    request: list[InputBinding] = Field(
        default_factory=list,
        description=(
            "Bindings that build the interrupt request payload sent to the client."
        ),
    )
    resume: list[OutputBinding] = Field(
        default_factory=list,
        description=(
            "Bindings that commit resume payload fields back into workflow state."
        ),
    )
    outcomes: list[str] = Field(default_factory=lambda: ["submitted"])
    request_schema: dict[str, object] = Field(default_factory=_object_schema)
    resume_schema: dict[str, object] = Field(default_factory=_object_schema)
    has_explicit_contract: bool = Field(default=False, exclude=True)
```

In `_coerce_deprecated_maps`, before returning `normalized`, add:

```python
        normalized["has_explicit_contract"] = (
            "request_schema" in normalized or "resume_schema" in normalized
        )
```

This preserves explicitness before defaults are applied.

- [ ] **Step 4: Run model tests and verify green**

Run:

```powershell
uv run pytest tests/core/test_canonical_node_bindings.py::test_interrupt_node_defaults_to_untyped_object_contract tests/core/test_canonical_node_bindings.py::test_interrupt_node_accepts_explicit_request_and_resume_schemas -q -n0
```

Expected: both pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_core/models/steps.py tests/core/test_canonical_node_bindings.py
git commit -m "feat: add interrupt schema contract fields"
```

---

### Task 2: Validate Interrupt Schemas Statically

**Files:**
- Modify: `src/wf_core/validation/steps.py`
- Test: `tests/core/test_canonical_node_bindings.py`

- [ ] **Step 1: Add failing test for invalid schema rejection**

Add this test to `tests/core/test_canonical_node_bindings.py`:

```python
def test_interrupt_node_rejects_invalid_json_schema_contract():
    with pytest.raises(ValidationError, match="invalid JSON Schema"):
        InterruptNode.model_validate(
            {
                "id": "approval",
                "type": "interrupt",
                "kind": "approval",
                "resume_schema": {
                    "type": "object",
                    "properties": {"approved": {"type": "not-a-json-schema-type"}},
                },
            }
        )
```

- [ ] **Step 2: Run test and verify red**

Run:

```powershell
uv run pytest tests/core/test_canonical_node_bindings.py::test_interrupt_node_rejects_invalid_json_schema_contract -q -n0
```

Expected: fail because plain dict schema fields are not checked.

- [ ] **Step 3: Add schema field validators**

In `src/wf_core/models/steps.py`, add imports:

```python
from jsonschema import Draft202012Validator, SchemaError, validators
from pydantic import field_validator
```

Extend the existing Pydantic import instead of creating a second import.

Add this helper near `_object_schema`:

```python
def _validate_json_schema(value: object, *, field_name: str) -> dict[str, object]:
    """Validate one interrupt contract schema with jsonschema."""
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON Schema object")
    schema = dict(value)
    validator_cls = (
        validators.validator_for(schema)
        if "$schema" in schema
        else Draft202012Validator
    )
    try:
        validator_cls.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"invalid JSON Schema: {exc.message}") from exc
    schema_type = schema.get("type")
    if schema_type != "object":
        raise ValueError(f"{field_name} must describe a JSON object")
    return schema
```

Add validators inside `InterruptNode`:

```python
    @field_validator("request_schema", "resume_schema", mode="before")
    @classmethod
    def _validate_interrupt_schema(cls, value: object, info: object) -> object:
        field_name = getattr(info, "field_name", "interrupt schema")
        return _validate_json_schema(value, field_name=field_name)
```

- [ ] **Step 4: Run test and verify green**

Run:

```powershell
uv run pytest tests/core/test_canonical_node_bindings.py::test_interrupt_node_rejects_invalid_json_schema_contract tests/core/test_canonical_node_bindings.py::test_interrupt_node_accepts_explicit_request_and_resume_schemas -q -n0
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_core/models/steps.py tests/core/test_canonical_node_bindings.py
git commit -m "fix: validate interrupt schema contracts"
```

---

### Task 3: Persist Interrupt Contract In Run State

**Files:**
- Modify: `src/wf_core/run_state.py`
- Modify: `src/wf_core/runtime/ops/interrupts.py`
- Test: `tests/core/test_run_codec.py`

- [ ] **Step 1: Add failing codec test**

Add this test to `tests/core/test_run_codec.py`:

```python
def test_run_state_codec_round_trips_interrupt_contract_fields() -> None:
    run = RunState(
        workflow_name="approval",
        status=RunStatus.INTERRUPTED,
        workflow_input={},
        state={},
        interrupt=InterruptRequest(
            id="interrupt:approval",
            frame_id="frame_1",
            node_id="approval",
            kind="approval",
            payload={"message": "approve?"},
            outcomes=["submitted", "cancelled"],
            request_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
            resume_schema={
                "type": "object",
                "properties": {"approved": {"type": "boolean"}},
                "required": ["approved"],
            },
            typed=True,
        ),
    )

    restored = decode_run_state(encode_run_state(run))

    assert restored.interrupt is not None
    assert restored.interrupt.outcomes == ["submitted", "cancelled"]
    assert restored.interrupt.request_schema["required"] == ["message"]
    assert restored.interrupt.resume_schema["required"] == ["approved"]
    assert restored.interrupt.typed is True
```

If `tests/core/test_run_codec.py` uses differently named codec helpers, use the
existing helpers in that file and keep the assertions unchanged.

- [ ] **Step 2: Run test and verify red**

Run:

```powershell
uv run pytest tests/core/test_run_codec.py::test_run_state_codec_round_trips_interrupt_contract_fields -q -n0
```

Expected: fail because `InterruptRequest` lacks the new fields.

- [ ] **Step 3: Extend `InterruptRequest`**

In `src/wf_core/run_state.py`, add:

```python
def _object_schema() -> dict[str, object]:
    """Default legacy interrupt contract used when older checkpoints are loaded."""
    return {"type": "object", "additionalProperties": True}
```

Update `InterruptRequest`:

```python
@dataclass(slots=True)
class InterruptRequest:
    id: str
    frame_id: str
    node_id: str
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    resumable: bool = True
    route: InterruptRoute | None = None
    outcomes: list[str] = field(default_factory=lambda: ["submitted"])
    request_schema: dict[str, object] = field(default_factory=_object_schema)
    resume_schema: dict[str, object] = field(default_factory=_object_schema)
    typed: bool = False
```

- [ ] **Step 4: Copy contract fields when building interrupt requests**

In `src/wf_core/runtime/ops/interrupts.py`, update the `InterruptRequest(...)`
construction:

```python
    return InterruptRequest(
        id=f"interrupt:{public_node_id or node.id}",
        frame_id=public_frame_id or frame_id,
        node_id=public_node_id or node.id,
        kind=node.kind,
        payload=payload,
        route=route,
        outcomes=list(node.outcomes),
        request_schema=dict(node.request_schema),
        resume_schema=dict(node.resume_schema),
        typed=node.has_explicit_contract,
    )
```

- [ ] **Step 5: Run codec and existing interrupt tests**

Run:

```powershell
uv run pytest tests/core/test_run_codec.py tests/core/test_execution_results.py -q -n0
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_core/run_state.py src/wf_core/runtime/ops/interrupts.py tests/core/test_run_codec.py
git commit -m "feat: persist interrupt contract in run state"
```

---

### Task 4: Runtime Request Payload Validation

**Files:**
- Modify: `src/wf_core/runtime/ops/interrupts.py`
- Test: `tests/core/test_execution_results.py`

- [ ] **Step 1: Add failing request-schema runtime test**

Add this test to `tests/core/test_execution_results.py`:

```python
async def test_interrupt_request_payload_validates_against_schema() -> None:
    workflow = Workflow(
        name="bad_interrupt_request",
        input_schema={"type": "object", "properties": {}},
        state_schema={"fields": {}},
        output_schema={"type": "object", "properties": {}},
        outcomes=["failed"],
        start="ask",
        nodes=[
            InterruptNode(
                id="ask",
                type="interrupt",
                kind="approval",
                request=[input_value_binding("not a number", "count")],
                request_schema={
                    "type": "object",
                    "properties": {"count": {"type": "number"}},
                    "required": ["count"],
                    "additionalProperties": False,
                },
            )
        ],
        edges=[],
    )

    run = await execute_workflow_async(workflow, {}, {})

    assert run.status == RunStatus.FAILED
    assert run.interrupt is None
    assert run.error is not None
    assert "interrupt request for ask['count']" in run.error
```

Use existing imports/helpers in the file. If `input_value_binding` is not
available, import it from `wf_core.models.steps` or construct
`InputValueBinding(target="count", value="not a number")`.

- [ ] **Step 2: Run test and verify red**

Run:

```powershell
uv run pytest tests/core/test_execution_results.py::test_interrupt_request_payload_validates_against_schema -q -n0
```

Expected: fail because request payload is not validated.

- [ ] **Step 3: Validate request payload before returning `InterruptRequest`**

In `src/wf_core/runtime/ops/interrupts.py`, import:

```python
from wf_core.runtime.ops.schemas import validate_payload_against_schema
```

After request bindings build `payload` and before `return InterruptRequest(...)`,
add:

```python
    validate_payload_against_schema(
        node.request_schema,
        payload,
        f"interrupt request for {node.id}",
    )
```

- [ ] **Step 4: Run request-validation tests**

Run:

```powershell
uv run pytest tests/core/test_execution_results.py::test_interrupt_request_payload_validates_against_schema tests/authoring/test_demo_workflow.py::test_interrupt_then_resume_to_send_email -q -n0
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_core/runtime/ops/interrupts.py tests/core/test_execution_results.py
git commit -m "fix: validate interrupt request payloads"
```

---

### Task 5: Runtime Resume Payload Validation

**Files:**
- Modify: `src/wf_core/runtime/ops/interrupts.py`
- Test: `tests/core/test_execution_results.py`

- [ ] **Step 1: Add failing resume-schema runtime test**

Add this test to `tests/core/test_execution_results.py`:

```python
async def test_interrupt_resume_payload_validates_before_state_mutation() -> None:
    workflow = Workflow(
        name="resume_validation",
        input_schema={"type": "object", "properties": {}},
        state_schema={
            "type": "object",
            "properties": {
                "approved": {"type": "boolean", "reducer": "wf.std.replace"}
            },
        },
        output_schema={"type": "object", "properties": {}},
        outcomes=["submitted"],
        start="ask",
        nodes=[
            InterruptNode(
                id="ask",
                type="interrupt",
                kind="approval",
                resume=[output_binding("approved", "state.approved")],
                resume_schema={
                    "type": "object",
                    "properties": {"approved": {"type": "boolean"}},
                    "required": ["approved"],
                    "additionalProperties": False,
                },
            ),
            EndNode(id="end", type="end", outcome="submitted"),
        ],
        edges=[Edge.model_validate({"from": "ask", "outcome": "submitted", "to": "end"})],
    )
    interrupted = await execute_workflow_async(workflow, {}, {})

    resumed = await resume_workflow_async(
        workflow,
        interrupted,
        {"approved": "yes"},
        {},
        resume_outcome="submitted",
    )

    assert resumed.status == RunStatus.FAILED
    assert resumed.state == {}
    assert resumed.error is not None
    assert "interrupt resume for ask['approved']" in resumed.error
```

Use the existing edge/binding helper style in the file. If `EndNode` or
`output_binding` is not imported, import them from existing core modules used by
the file.

- [ ] **Step 2: Run test and verify red**

Run:

```powershell
uv run pytest tests/core/test_execution_results.py::test_interrupt_resume_payload_validates_before_state_mutation -q -n0
```

Expected: fail because resume payload is not validated before bindings.

- [ ] **Step 3: Validate resume payload before `build_output_patch`**

In `resume_interrupt()` in `src/wf_core/runtime/ops/interrupts.py`, after the
`resume_outcome not in step.outcomes` check and before `patch = build_output_patch(...)`,
add:

```python
    validate_payload_against_schema(
        step.resume_schema,
        resume_payload,
        f"interrupt resume for {step.id}",
    )
```

- [ ] **Step 4: Run resume tests**

Run:

```powershell
uv run pytest tests/core/test_execution_results.py::test_interrupt_resume_payload_validates_before_state_mutation tests/authoring/test_demo_workflow.py::test_interrupt_then_resume_to_send_email tests/core/test_concurrent_foreach_interrupts.py -q -n0
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add src/wf_core/runtime/ops/interrupts.py tests/core/test_execution_results.py
git commit -m "fix: validate interrupt resume payloads"
```

---

### Task 6: Expose Contract Through Run Inspection

**Files:**
- Modify: `src/wf_api/runs.py`
- Test: `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`
- Test: `tests/wf_cli/test_run_deploy.py`

- [ ] **Step 1: Add RPC inspection assertion**

In `tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py`, update
`_interrupt_plan()` so its interrupt node includes explicit schemas:

```python
"request_schema": {
    "type": "object",
    "properties": {"message": {"type": "string"}},
    "required": ["message"],
    "additionalProperties": False,
},
"resume_schema": {
    "type": "object",
    "properties": {"approved": {"type": "boolean"}},
    "required": ["approved"],
    "additionalProperties": False,
},
```

In `test_mcp_backed_rpc_resumes_interrupted_run_after_server_rebuild`, after
`assert started["interrupt"]["payload"]["message"] == "approve after restart?"`,
add:

```python
    assert started["interrupt"]["outcomes"] == ["submitted"]
    assert started["interrupt"]["typed"] is True
    assert started["interrupt"]["request_schema"]["required"] == ["message"]
    assert started["interrupt"]["resume_schema"]["required"] == ["approved"]
```

- [ ] **Step 2: Add CLI inspection assertion**

In `tests/wf_cli/test_run_deploy.py`, update `_interrupt_artifact()` interrupt
node with the same `request_schema` and a permissive but explicit
`resume_schema`:

```python
"request_schema": {
    "type": "object",
    "properties": {"message": {"type": "string"}},
    "required": ["message"],
    "additionalProperties": False,
},
"resume_schema": {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
},
```

In `test_wf_run_watch_stops_on_interrupted_run`, after the interrupt payload
assertions, add:

```python
    assert payload["interrupt"]["typed"] is True
    assert payload["interrupt"]["request_schema"]["required"] == ["message"]
```

- [ ] **Step 3: Run tests and verify red if payload missing fields**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py::test_mcp_backed_rpc_resumes_interrupted_run_after_server_rebuild tests/wf_cli/test_run_deploy.py::test_wf_run_watch_stops_on_interrupted_run -q -n0
```

Expected: fail only if inspect payload omits the new contract fields. If it
already passes because dataclass `asdict` includes fields, continue to Step 4
and keep the tests as regression coverage.

- [ ] **Step 4: Keep `_interrupt_payload` JSON-safe and explicit**

In `src/wf_api/runs.py`, keep `_interrupt_payload()` as the single public shape
normalizer. Ensure it preserves:

```python
    payload = asdict(run.interrupt)
```

If the route-normalization block mutates route only, leave schema fields
untouched. Add this comment above `payload = asdict(run.interrupt)`:

```python
    # The interrupt contract is copied into RunState at pause time so clients
    # can render/resume without reloading mutable workflow definitions.
```

- [ ] **Step 5: Run RPC/CLI tests**

Run:

```powershell
uv run pytest tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py::test_mcp_backed_rpc_resumes_interrupted_run_after_server_rebuild tests/wf_cli/test_run_deploy.py::test_wf_run_watch_stops_on_interrupted_run -q -n0
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_api/runs.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py tests/wf_cli/test_run_deploy.py
git commit -m "feat: expose interrupt contracts in run inspect"
```

---

### Task 7: API/CLI Resume Validation Regression

**Files:**
- Test: `tests/wf_api/test_run_api.py`
- Test: `tests/wf_cli/test_run_deploy.py`
- Modify: `src/wf_cli/commands/runs.py`

- [ ] **Step 1: Add API regression test for invalid resume payload**

Add this test to `tests/wf_api/test_run_api.py`:

```python
async def test_resume_run_rejects_payload_that_violates_interrupt_schema(tmp_path: Path) -> None:
    store = FileStore(tmp_path / "store")
    api = build_workflow_api_for_test(store)
    deployment_id = _seed_interrupt_deployment_with_resume_schema(store)

    started = await api.run_deployment(
        deployment_id=deployment_id,
        workflow_input={"message": "approve?"},
    )
    run_id = started["run_id"]
    assert run_id is not None

    resumed = await api.resume_run(
        run_id=run_id,
        resume_payload={"approved": "yes"},
        resume_outcome="submitted",
    )

    assert resumed["status"] == "failed"
    assert "interrupt resume for approval['approved']" in resumed["error"]
```

Use existing helper names in `tests/wf_api/test_run_api.py`. If the file does
not have `build_workflow_api_for_test` or `FileStore`, mirror the existing
store/API setup used by nearby run tests. Add a local helper:

```python
def _seed_interrupt_deployment_with_resume_schema(store: FileStore) -> str:
    """Seed one deployment whose interrupt requires a boolean approval."""
    artifact_store = FileWorkflowArtifactStore(store.root)
    deployment_store = FileWorkflowDeploymentStore(store.root)
    artifact_store.save_artifact(_interrupt_artifact_with_resume_schema())
    deployment_store.save_deployment(
        WorkflowDeployment(
            id="approval.default",
            artifact_id="approval",
            version=1,
            source_bindings={},
        )
    )
    return "approval.default"
```

Reuse existing artifact/deployment classes imported in that test file.

- [ ] **Step 2: Add CLI help assertion**

In `tests/wf_cli/test_app.py`, add:

```python
def test_wf_run_resume_help_mentions_interrupt_schema_validation() -> None:
    result = runner.invoke(app, ["run", "resume", "--help"])

    assert result.exit_code == 0
    assert "resume payload" in result.stdout
    assert "schema" in result.stdout
```

- [ ] **Step 3: Run tests and verify red if help missing schema wording**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py::test_wf_run_resume_help_mentions_interrupt_schema_validation -q -n0
```

Expected: fail until help/docstring mentions schema validation.

- [ ] **Step 4: Update CLI help/docstring**

In `src/wf_cli/commands/runs.py`, change the `--payload` help text:

```python
typer.Option(
    "--payload",
    help="Resume payload JSON object; interrupted runs may validate it against their resume schema.",
)
```

Change `--payload-file` help text:

```python
typer.Option(
    "--payload-file",
    help="Path to resume payload JSON object; schema validation happens before state mutation.",
)
```

Extend the `resume_run` docstring:

```python
    The interrupted run may expose a resume schema through `wf run inspect`.
    Invalid resume payloads are rejected before workflow state is mutated.
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
uv run pytest tests/wf_cli/test_app.py::test_wf_run_resume_help_mentions_interrupt_schema_validation tests/wf_api/test_run_api.py -q -n0
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_cli/commands/runs.py tests/wf_cli/test_app.py tests/wf_api/test_run_api.py
git commit -m "test: cover interrupt resume schema validation"
```

---

### Task 8: Authoring Builder Convenience

**Files:**
- Modify: `src/wf_authoring/dsl/builder.py`
- Test: `tests/authoring/test_builder.py`

- [ ] **Step 1: Inspect current builder interrupt signature**

Run:

```powershell
rg -n 'def interrupt|InterruptNode' src\wf_authoring tests\authoring\test_builder.py
```

Expected: find the builder method that constructs `InterruptNode`.

- [ ] **Step 2: Add failing builder test**

Add this test to `tests/authoring/test_builder.py` near the existing interrupt
builder tests:

```python
def test_builder_interrupt_accepts_request_and_resume_schemas() -> None:
    builder = WorkflowBuilder(
        name="interrupt_contract",
        input_schema={"type": "object", "properties": {}},
        state_schema={"fields": {}},
        output_schema={"type": "object", "properties": {}},
    )

    interrupt = builder.interrupt(
        kind="approval",
        request_schema={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        resume_schema={
            "type": "object",
            "properties": {"approved": {"type": "boolean"}},
            "required": ["approved"],
        },
    )

    assert interrupt.request_schema["required"] == ["message"]
    assert interrupt.resume_schema["required"] == ["approved"]
    assert interrupt.has_explicit_contract is True
```

- [ ] **Step 3: Run test and verify red**

Run:

```powershell
uv run pytest tests/authoring/test_builder.py::test_builder_interrupt_accepts_request_and_resume_schemas -q -n0
```

Expected: fail because builder does not accept schema kwargs.

- [ ] **Step 4: Add builder kwargs**

In `src/wf_authoring/dsl/builder.py`, update the `interrupt(...)` method
signature to accept:

```python
request_schema: Mapping[str, Any] | None = None,
resume_schema: Mapping[str, Any] | None = None,
```

When constructing `InterruptNode`, pass:

```python
request_schema=dict(request_schema) if request_schema is not None else None,
resume_schema=dict(resume_schema) if resume_schema is not None else None,
```

If passing `None` would serialize null into the model payload, build the payload
dict and include only non-`None` schema keys:

```python
payload: dict[str, Any] = {
    "id": node_id,
    "type": "interrupt",
    "kind": kind,
    "request": list(request or []),
    "resume": list(resume or []),
    "outcomes": list(outcomes or ["submitted"]),
}
if request_schema is not None:
    payload["request_schema"] = dict(request_schema)
if resume_schema is not None:
    payload["resume_schema"] = dict(resume_schema)
node = InterruptNode.model_validate(payload)
```

Use existing variable names from the method.

- [ ] **Step 5: Run builder tests**

Run:

```powershell
uv run pytest tests/authoring/test_builder.py::test_builder_interrupt_accepts_request_and_resume_schemas tests/authoring/test_builder.py::test_builder_interrupt_accepts_canonical_request_and_resume_bindings -q -n0
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add src/wf_authoring/dsl/builder.py tests/authoring/test_builder.py
git commit -m "feat: add interrupt schema builder helpers"
```

---

### Task 9: Schema Discovery And Docs

**Files:**
- Modify: `docs/wf_cli.md`
- Modify: `skills/wf-cli/SKILL.md`
- Modify: `skills/wf-workflow/references/workflow-lifecycle.md`
- Modify: `docs/current_roadmap.md`
- Optional test: `tests/wf_cli/test_schema.py`

- [ ] **Step 1: Verify `wf schema InterruptNode` includes fields**

Run:

```powershell
uv run wf schema InterruptNode --verbose
```

Expected: JSON Schema output includes `request_schema` and `resume_schema`.

If it does not, inspect `src/wf_cli/schema_catalog.py` and add `InterruptNode`
field projection coverage there. Add or update a test in
`tests/wf_cli/test_schema.py`:

```python
def test_wf_schema_interrupt_node_includes_interrupt_contract_fields() -> None:
    result = runner.invoke(app, ["schema", "InterruptNode", "--verbose"])

    assert result.exit_code == 0
    assert "request_schema" in result.stdout
    assert "resume_schema" in result.stdout
```

- [ ] **Step 2: Update CLI docs**

In `docs/wf_cli.md`, add a short subsection under run inspect/resume docs:

```md
### Interrupt Resume Schemas

Interrupted runs may include `interrupt.request_schema` and
`interrupt.resume_schema` in `wf run inspect` output. The request schema
describes the payload shown to the operator. The resume schema describes the
payload accepted by `wf run resume --payload` or `--payload-file`.

Resume payload validation happens before workflow state mutation. If validation
fails, inspect the schema and retry with a payload that matches the declared
shape.
```

- [ ] **Step 3: Update CLI skill**

In `skills/wf-cli/SKILL.md`, add:

```md
- For interrupted runs, call `wf run inspect <run_id>` before resuming. If the
  interrupt includes `resume_schema`, shape `wf run resume --payload` to that
  schema instead of guessing field names.
```

- [ ] **Step 4: Update workflow lifecycle skill reference**

In `skills/wf-workflow/references/workflow-lifecycle.md`, add:

```md
## Interrupt Resume Contracts

An interrupted run can carry a self-describing resume contract. Treat
`interrupt.resume_schema` from `wf run inspect` as the source of truth for the
payload you pass to `wf run resume`. Do not read workflow source code just to
guess approval fields when the schema is present.
```

- [ ] **Step 5: Update roadmap**

In `docs/current_roadmap.md`, under the active Workflow Console initiative,
change implementation item 1 from future wording to completed wording only if
the full implementation is done:

```md
1. Completed: self-describing interrupt request/resume schemas are carried
   through core execution, persisted run inspection, and resume validation.
```

Do not mark the web console itself completed.

- [ ] **Step 6: Run docs/schema checks**

Run:

```powershell
uv run pytest tests/wf_cli/test_schema.py tests/docs -q -n0
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add docs/wf_cli.md skills/wf-cli/SKILL.md skills/wf-workflow/references/workflow-lifecycle.md docs/current_roadmap.md tests/wf_cli/test_schema.py src/wf_cli/schema_catalog.py
git commit -m "docs: document interrupt resume contracts"
```

If `src/wf_cli/schema_catalog.py` and `tests/wf_cli/test_schema.py` were not
needed, omit them from `git add`.

---

### Task 10: Final Regression

**Files:**
- No new files expected.

- [ ] **Step 1: Run focused interrupt suites**

Run:

```powershell
uv run pytest tests/core/test_canonical_node_bindings.py tests/core/test_execution_results.py tests/core/test_run_codec.py tests/authoring/test_builder.py tests/wf_api/test_run_api.py tests/wf_cli/test_run_deploy.py tests/wf_transport_rpc_http/test_mcp_backed_server_rpc.py -q -n0
```

Expected: pass.

- [ ] **Step 2: Run lint and type checks**

Run:

```powershell
uv run ruff check
uv run ruff format --check
uv run basedpyright --level error
```

Expected: all clean. If `ruff format --check` fails, run:

```powershell
uv run ruff format
uv run ruff format --check
```

- [ ] **Step 3: Run a CLI smoke with an interrupting deployment**

Run an existing CLI interrupt test as product smoke:

```powershell
uv run pytest tests/wf_cli/test_run_deploy.py::test_wf_run_resume_interrupted_run -q -n0
```

Expected: pass.

- [ ] **Step 4: Search for stale docs**

Run:

```powershell
rg -n 'request_schema|resume_schema|InterruptNode|wf run resume|interrupt schema' docs skills src tests
```

Expected: new docs mention interrupt schemas; no docs claim resume payload shape
must be guessed from source code.

- [ ] **Step 5: Commit final polish if needed**

If formatting/docs search caused changes:

```powershell
git add .
git commit -m "chore: polish interrupt contract implementation"
```

If no changes are needed, do not create an empty commit.

---

## Final Report Requirements

The implementing agent must report:

- files changed;
- test commands and results;
- whether legacy untyped interrupts still pass;
- whether invalid resume payloads fail before state mutation;
- whether `wf run inspect` exposes `request_schema`, `resume_schema`, `outcomes`,
  and `typed`;
- any pre-existing failures outside this slice.

## Plan Self-Review

Spec coverage:

- core model fields: Task 1;
- static schema validation: Task 2;
- persisted interrupt payload contract: Task 3 and Task 6;
- request validation: Task 4;
- resume validation before mutation: Task 5 and Task 7;
- builder convenience: Task 8;
- CLI/schema/docs/skills: Task 9;
- compatibility/defaults: Task 1 and Task 3;
- no web console or demo-agent implementation: scoped out explicitly.

Placeholder scan:

- No task contains red-flag placeholder tokens or unspecified implementation
  work.
- Each code-changing task has concrete code or exact behavior.

Type consistency:

- Public fields are consistently named `request_schema`, `resume_schema`,
  `outcomes`, and `typed`.
- Legacy marker is internal-only as `has_explicit_contract` and is excluded from
  serialized workflow documents.
