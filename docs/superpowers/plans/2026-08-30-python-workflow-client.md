# Python Workflow Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a public async-native `wf_client.App` whose returned Python objects can inspect and call capabilities, author and edit workflows through `WorkflowBuilder`, validate locally and remotely, save immutable artifacts, deploy them, and operate durable runs.

**Architecture:** `wf_client` is a deep public module over a narrow internal `WorkflowClientPort`; the existing `RpcWorkflowApiClient` is its production HTTP adapter. `EditableWorkflow` subclasses the transport-free `WorkflowBuilder`, while codecs reconstruct wire payloads into existing `wf_core` and `wf_artifacts` domain models at the adapter seam.

**Tech Stack:** Python 3.14, Pydantic 2, jsonschema 4.26, httpx, FastAPI JSON-RPC, pytest, pytest-asyncio, ruff, basedpyright.

**Spec:** `docs/superpowers/specs/2026-08-30-python-workflow-client-design.md`

## Global Constraints

- Python baseline is 3.14 (`requires-python = ">=3.14"`).
- `App` is the only public connection entry point.
- Network operations are async; do not add an event-loop-owning synchronous facade.
- Local graph mutations remain synchronous.
- JSON serialization and result validation stay at the transport/codec seam.
- Reuse `wf_core`, `wf_artifacts`, and `wf_authoring` models; do not create parallel workflow semantics.
- Workflow artifacts are immutable; editing seeds a new mutable graph.
- Capability use and native subgraphs remain distinct operations.
- The client never guesses between multiple source accounts or deployments.
- Draft models and draft operations must not be imported or exposed by `wf_client`.
- Add docstrings or comments at non-obvious reconstruction, routing-replacement, and validation seams.
- Use focused pytest commands first; run repository-wide verification only after the focused suite passes.

## File Structure

Create:

```text
src/wf_client/
├── __init__.py       # stable public exports
├── app.py            # App construction and top-level lookup
├── authoring.py      # EditableWorkflow subclass
├── capabilities.py   # RemoteCapability and CapabilityResult
├── codec.py          # validated wire/domain reconstruction
├── deployments.py    # Deployment lifecycle object
├── errors.py         # structured client exception hierarchy
├── protocols.py      # narrow WorkflowClientPort
├── runs.py           # Run and TracePage lifecycle objects
└── workflows.py      # WorkflowArtifact and save/edit behavior

tests/wf_client/
├── __init__.py
├── conftest.py
├── test_app.py
├── test_authoring.py
├── test_capabilities.py
├── test_codec.py
├── test_deployments.py
├── test_http_integration.py
├── test_repr.py
└── test_runs.py
```

Modify focused existing modules instead of duplicating them:

- `src/wf_authoring/builder/core.py`: lossless workflow output, reconstruction, and focused graph editing.
- `src/wf_authoring/builder/mapping.py`: schema-contract auto-binding shared by local and remote capability authoring.
- `src/wf_api/artifacts.py`, `src/wf_api/service.py`, and `src/wf_api/surface.py`: non-persisting plan validation.
- `src/wf_api/models/artifacts.py` and `src/wf_api/models/__init__.py`: validation result contract.
- `src/wf_transport_rpc_http/models.py`, `methods/artifacts.py`, and `client/artifacts.py`: JSON-RPC validation operation.
- `src/wf_transport_rpc_http/client/base.py`: preserve structured JSON-RPC errors.
- `contracts/workflow-api.manifest.json` and generated TypeScript contract files: checked operation inventory.
- `docs/project_map.md`, `docs/source_architecture.md`, `docs/wf_api_architecture.md`, and `docs/current_roadmap.md`: public architecture and completed-slice status.

---

### Task 1: Make `WorkflowBuilder` lossless and safely editable

**Files:**

- Modify: `src/wf_authoring/builder/core.py:205`
- Modify: `src/wf_authoring/builder/mapping.py:138`
- Modify: `src/wf_authoring/builder/__init__.py`
- Test: `tests/authoring/test_builder.py`
- Test: `tests/authoring/test_subgraph.py`

**Interfaces:**

- Consumes: canonical `Workflow`, `NodeDef`, `Step`, `Edge`, `InputBinding`, and existing `WorkflowBuilder` operations.
- Produces: `WorkflowBuilder.from_workflow(workflow)`, `set_output(bindings)`, `set_route(source, outcome, target)`, `remove_route(source, outcome)`, `remove_step(step)`, `use_contract(...)`, `validate_structure()`, and lossless `compile()`.

- [ ] **Step 1: Write failing workflow-output and reconstruction tests**

Add tests that construct a workflow with a path final-output binding, seed a builder from it, mutate the returned builder, and prove the original remains unchanged:

```python
def test_builder_round_trip_preserves_complete_workflow() -> None:
    original = Workflow(
        name="round_trip",
        input_schema={"type": "object", "properties": {"topic": {"type": "string"}}},
        state_schema={
            "type": "object",
            "properties": {"result": {"type": "string"}},
        },
        output_schema={
            "type": "object",
            "properties": {"result": {"type": "string"}},
        },
        output=[{"path": "state.result", "target": "result"}],
        node_defs=[
            {
                "name": "app.default.search",
                "input_schema": {"type": "object", "properties": {}},
                "output_schema": {
                    "type": "object",
                    "properties": {"result": {"type": "string"}},
                },
                "outcomes": ["ok"],
            }
        ],
        outcomes=["ok"],
        start="search",
        nodes=[
            {
                "id": "search",
                "type": "node",
                "node": "app.default.search",
                "input": [],
                "output": [
                    {"source": "result", "target": "state.result"},
                ],
            },
            {"id": "end_ok", "type": "end", "outcome": "ok"},
        ],
        edges=[{"from": "search", "outcome": "ok", "to": "end_ok"}],
    )

    builder = WorkflowBuilder.from_workflow(original)
    rebuilt = builder.compile()

    assert rebuilt.model_dump(mode="json", by_alias=True) == original.model_dump(
        mode="json", by_alias=True
    )
    builder.set_output([{"value": "changed", "target": "result"}])
    original_output = original.output[0]
    assert isinstance(original_output, InputPathBinding)
    assert str(original_output.path) == "state.result"
```

Add focused tests proving `set_route()` replaces rather than duplicates, `remove_route()` removes only the requested source/outcome pair, and `remove_step()` rejects referenced steps:

```python
def test_set_route_replaces_unique_source_outcome_edge() -> None:
    builder = _editable_three_step_builder()

    builder.set_route("first", "ok", "third")

    matching = [
        edge
        for edge in builder.edges
        if edge.from_ == "first" and edge.outcome == "ok"
    ]
    assert [(edge.from_, edge.outcome, edge.to) for edge in matching] == [
        ("first", "ok", "third")
    ]


def test_remove_step_rejects_referenced_step() -> None:
    builder = _editable_three_step_builder()

    with pytest.raises(ValueError, match="still referenced by route"):
        builder.remove_step("second")
```

- [ ] **Step 2: Run the focused tests and confirm the missing behavior**

Run:

```powershell
uv run pytest tests/authoring/test_builder.py tests/authoring/test_subgraph.py -q
```

Expected: the new tests fail because reconstruction, workflow-output storage, and focused edit methods do not exist.

- [ ] **Step 3: Add schema-contract mapping helpers**

Generalize the auto-mapping functions so remote schema contracts do not need fake Pydantic classes:

```python
def auto_input_map_from_schema(
    capability_input_schema: SchemaRef,
    *,
    input_schema: SchemaRef,
    state_schema: StateSchema,
) -> dict[str, str]:
    return {
        _auto_source_path(
            field,
            input_schema=input_schema,
            state_schema=state_schema,
        ): field
        for field in capability_input_schema.properties
    }


def auto_output_map_from_schema(
    capability_output_schema: SchemaRef,
    *,
    state_schema: StateSchema,
) -> dict[str, str]:
    state_fields = state_schema.field_map()
    return {
        field: f"state.{field}"
        for field in capability_output_schema.properties
        if field in state_fields
    }
```

Keep `auto_input_map(spec, ...)` and `auto_output_map(spec, ...)` as shallow compatibility callers of these schema-based helpers.

- [ ] **Step 4: Implement lossless builder state and focused editing**

Add builder-owned workflow output and seeded node definitions:

```python
workflow_output: list[InputBinding] = field(default_factory=list)
seeded_node_defs: dict[str, NodeDef] = field(default_factory=dict, repr=False)
```

Implement the public reconstruction and mutation signatures:

```python
@classmethod
def from_workflow(cls, workflow: Workflow) -> WorkflowBuilder:
    return cls(
        name=workflow.name,
        input_schema=workflow.input_schema.model_copy(deep=True),
        state_schema=workflow.state_schema.model_copy(deep=True),
        output_schema=workflow.output_schema.model_copy(deep=True),
        outcomes=tuple(workflow.outcomes),
        start=workflow.start,
        nodes=[node.model_copy(deep=True) for node in workflow.nodes],
        edges=[edge.model_copy(deep=True) for edge in workflow.edges],
        workflow_output=[binding.model_copy(deep=True) for binding in workflow.output],
        seeded_node_defs={
            node_def.name: node_def.model_copy(deep=True)
            for node_def in workflow.node_defs
        },
    )


def set_output(self, bindings: Sequence[StepInputBindingArg]) -> None:
    self.workflow_output = normalize_step_input_bindings(bindings)


def set_route(self, source: StepRef, outcome: str, target: StepRef) -> None:
    source_id = step_id(source)
    target_id = step_id(target)
    self.edges = [
        edge
        for edge in self.edges
        if not (edge.from_ == source_id and edge.outcome == outcome)
    ]
    self.edges.append(
        Edge.model_validate({"from": source_id, "outcome": outcome, "to": target_id})
    )
```

Implement `remove_route()` and `remove_step()` with explicit missing/referrer errors. Implement `use_contract()` to register a `NodeDef`, derive auto-bindings from its schemas, and lower to `use_ref()` without inventing a local handler:

```python
def use_contract(
    self,
    node_def: NodeDef,
    *,
    id: str | None = None,
    input: Sequence[StepInputBindingArg] | None = None,
    output: Sequence[OutputBindingArg] | None = None,
    desc: str | None = None,
) -> NodeUse: ...
```

Update `compile()` to merge copied seeded definitions with definitions derived from local `NodeSpec`s, reject incompatible duplicate names, and set `output=self.workflow_output`.

Extract one private `_build_workflow(start: str) -> Workflow` constructor used
by both public operations. `compile()` retains its explicit missing-start error;
`validate_structure()` passes `self.start or ""` so an unset entry point becomes
the canonical `UNKNOWN_START` validation issue instead of an exception:

```python
def validate_structure(self) -> ValidationReport:
    return self._build_workflow(start=self.start or "").validate_structure()


def compile(self) -> Workflow:
    if self.start is None:
        raise WorkflowExecutionError(
            "workflow builder requires an explicit start; "
            "call set_entry_point(...) or pass start=..."
        )
    return self._build_workflow(start=self.start)
```

- [ ] **Step 5: Run the focused authoring tests**

Run:

```powershell
uv run pytest tests/authoring/test_builder.py tests/authoring/test_subgraph.py -q
uv run basedpyright --level error src/wf_authoring tests/authoring/test_builder.py tests/authoring/test_subgraph.py
```

Expected: all focused tests pass and basedpyright reports zero errors.

- [ ] **Step 6: Commit the builder foundation**

```powershell
git add src/wf_authoring/builder tests/authoring/test_builder.py tests/authoring/test_subgraph.py
git commit -m "feat: make workflow builder edits lossless"
```

---

### Task 2: Add non-persisting server-side plan validation

**Files:**

- Modify: `src/wf_api/models/artifacts.py`
- Modify: `src/wf_api/models/__init__.py`
- Modify: `src/wf_api/artifacts.py`
- Modify: `src/wf_api/service.py`
- Modify: `src/wf_api/surface.py`
- Modify: `src/wf_transport_rpc_http/models.py`
- Modify: `src/wf_transport_rpc_http/methods/artifacts.py`
- Modify: `src/wf_transport_rpc_http/client/artifacts.py`
- Modify: `tests/wf_api/test_artifact_api.py`
- Modify: `tests/wf_transport_rpc_http/test_app.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`
- Modify: `tests/wf_transport_rpc_http/test_openrpc_contract.py`
- Modify: `contracts/workflow-api.manifest.json`
- Modify: generated contract files under `web/packages/rpc/src/generated/`

**Interfaces:**

- Consumes: `create_workflow_artifact_from_plan`, `RawWorkflowPlan`, `observed_node_specs(context)`, existing artifact creation arguments.
- Produces: `WorkflowArtifactApi.validate_artifact_plan(...) -> ValidateArtifactPlanResult`, surface/client method `validate_artifact_plan`, and JSON-RPC operation `workflow.artifacts.validate_plan`.

- [ ] **Step 1: Write failing API tests for valid and invalid plans**

Define the response contract:

```python
class ArtifactPlanDiagnosticPayload(TypedDict):
    severity: Literal["error", "warning"]
    code: str
    path: str
    message: str
    repair_hint: str | None


class ValidateArtifactPlanResult(TypedDict):
    status: Literal["valid", "invalid"]
    diagnostics: list[ArtifactPlanDiagnosticPayload]
    required_capabilities: list[RequiredCapabilityPayload]
    workflow_dependencies: dict[str, int]
```

Test that validation derives dependencies without writing the artifact store:

```python
async def test_validate_artifact_plan_does_not_persist(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    plan = _constant_plan().model_dump(mode="json", by_alias=True)

    result = await server.api.validate_artifact_plan(
        plan=plan,
        outcomes=["ok"],
        source_bindings={},
    )

    assert result["status"] == "valid"
    assert result["diagnostics"] == []
    assert await server.api.list_artifacts(query="constant") == {
        "nodes": [],
        "next_cursor": None,
        "total": 0,
    }
```

Add an invalid-plan test asserting a stable diagnostic code and path rather than a raised traceback.

- [ ] **Step 2: Run the focused API test and confirm it fails**

```powershell
uv run pytest tests/wf_api/test_artifact_api.py -q
```

Expected: failure because `validate_artifact_plan()` and its result model do not exist.

- [ ] **Step 3: Extract one shared preparation seam**

In `wf_api.artifacts`, add a private pure helper used by both validation and save:

```python
def _prepare_artifact_from_plan(
    context: WorkflowOperationContext,
    *,
    artifact_id: str,
    version: int,
    title: str,
    kind: ArtifactKind,
    description: str | None,
    plan: RawWorkflowPlan | dict[str, Any],
    outcomes: Sequence[str],
    required_capabilities: dict[str, dict[str, Any]] | None,
    source_bindings: dict[str, str] | None,
    created_from_catalog_version: str | None,
) -> WorkflowArtifact:
    typed_plan = (
        plan if isinstance(plan, RawWorkflowPlan) else RawWorkflowPlan.model_validate(plan)
    )
    return build_workflow_artifact_from_plan(
        artifact_id=artifact_id,
        version=version,
        title=title,
        kind=kind,
        description=description,
        plan=typed_plan.model_dump(mode="json", by_alias=True),
        outcomes=tuple(outcomes),
        required_capabilities={
            name: RequiredCapability.model_validate(capability)
            for name, capability in (required_capabilities or {}).items()
        },
        source_bindings=source_bindings,
        observed_node_specs=observed_node_specs(context),
        created_from_catalog_version=created_from_catalog_version,
    )
```

Make `create_artifact_from_plan()` call this helper before its existing store write and event. Implement validation with reserved in-memory metadata, catch only expected model/workflow validation exceptions, and project them to diagnostics. Do not catch programming errors.

- [ ] **Step 4: Expose the operation through the stable surface and JSON-RPC adapter**

Use the exact signature at every layer:

```python
async def validate_artifact_plan(
    self,
    *,
    plan: dict[str, Any],
    outcomes: Sequence[str],
    required_capabilities: dict[str, dict[str, Any]] | None = None,
    source_bindings: dict[str, str] | None = None,
) -> ValidateArtifactPlanResult: ...
```

Add `ValidateArtifactPlanParams` in the transport models and register `workflow.artifacts.validate_plan` beside artifact create/inspect operations. Add one ASGI RPC test and one `RpcWorkflowApiClient` test proving no artifact is persisted.

- [ ] **Step 5: Regenerate and verify checked contracts**

Run:

```powershell
uv run python -m wf_contract_manifest write
pnpm --dir web --filter @lda/workflow-rpc contract:write
uv run pytest tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_openrpc_contract.py tests/wf_contract_manifest/test_generate.py tests/wf_contract_manifest/test_committed_manifest.py -q
pnpm --dir web --filter @lda/workflow-rpc test
```

Expected: the new operation has a named success schema, manifest drift checks pass, and TypeScript generated-contract tests pass. Do not add it to the browser-authorized Effect RPC cohort; this task expands the transport inventory, not browser policy.

- [ ] **Step 6: Commit server validation**

```powershell
git add src/wf_api src/wf_transport_rpc_http tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http contracts/workflow-api.manifest.json web/packages/rpc/src/generated web/packages/rpc/scripts
git commit -m "feat: validate workflow plans without saving"
```

---

### Task 3: Build the narrow client port, codecs, and structured errors

**Files:**

- Create: `src/wf_client/protocols.py`
- Create: `src/wf_client/codec.py`
- Create: `src/wf_client/errors.py`
- Create: `tests/wf_client/__init__.py`
- Create: `tests/wf_client/conftest.py`
- Create: `tests/wf_client/test_codec.py`
- Modify: `src/wf_transport_rpc_http/client/base.py`
- Modify: `tests/wf_transport_rpc_http/test_client.py`

**Interfaces:**

- Consumes: typed result contracts from Task 2, existing `RpcWorkflowApiClient` methods, `WorkflowArtifact`, `WorkflowDeployment`, `Workflow`, `DependencyDiagnostic`, and run payload contracts.
- Produces: `WorkflowClientPort`, `RpcProtocolError`, `WorkflowClientError` hierarchy, and named codec functions used by all later rich objects.

- [ ] **Step 1: Write failing codec and error-preservation tests**

Create a fake narrow adapter in `tests/wf_client/conftest.py` whose methods return configurable payloads and record calls. Test artifact reconstruction:

```python
def test_decode_workflow_artifact_validates_plan() -> None:
    payload = workflow_artifact_payload(plan=_constant_plan_payload())

    artifact, workflow = decode_workflow_artifact(payload)

    assert artifact.id == "report"
    assert workflow.name == "report"
    assert workflow.start == "constant"
```

Test malformed nested plan rejection:

```python
def test_decode_workflow_artifact_rejects_invalid_nested_plan() -> None:
    payload = workflow_artifact_payload(plan={"name": "broken"})

    with pytest.raises(InvalidResponse, match="workflow.artifacts.inspect"):
        decode_workflow_artifact(payload)
```

Add an RPC transport test proving JSON-RPC `error.code`, `error.message`, and `error.data` survive in a structured exception.

- [ ] **Step 2: Run focused tests and confirm failures**

```powershell
uv run pytest tests/wf_client/test_codec.py tests/wf_transport_rpc_http/test_client.py -q
```

Expected: failures because `wf_client` and `RpcProtocolError` do not exist.

- [ ] **Step 3: Define the narrow port**

Create a `Protocol` containing only methods rich client objects require:

```python
class WorkflowClientPort(Protocol):
    async def list_capabilities(
        self,
        *,
        query: str | None = None,
        source_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ListCapabilitiesResult: ...

    async def inspect_capability(
        self,
        *,
        qualified_name: str,
    ) -> InspectCapabilityResult: ...

    async def call_capability(
        self,
        *,
        qualified_name: str,
        payload: dict[str, Any],
        deployment_id: str | None = None,
    ) -> CapabilityCallResult: ...

    async def validate_artifact_plan(
        self,
        *,
        plan: dict[str, Any],
        outcomes: Sequence[str],
        required_capabilities: dict[str, dict[str, Any]] | None = None,
        source_bindings: dict[str, str] | None = None,
    ) -> ValidateArtifactPlanResult: ...
```

Include exact existing artifact inspect/create, deployment list/inspect/save/validate, and run start/inspect/resume/trace signatures. Do not inherit the 70-operation `WorkflowApiSurface`.

- [ ] **Step 4: Preserve structured JSON-RPC failures**

Add this transport exception in `wf_transport_rpc_http.client.base`:

```python
@dataclass(frozen=True, slots=True)
class RpcProtocolError(RuntimeError):
    code: int | str | None
    message: str
    data: object = None

    def __str__(self) -> str:
        if isinstance(self.data, dict) and isinstance(self.data.get("message"), str):
            return f"{self.message}: {self.data['message']}"
        return self.message
```

Define `InvalidResponse` concretely so every codec reports the failed
operation:

```python
@dataclass(frozen=True, slots=True)
class InvalidResponse(WorkflowClientError):
    operation: str
    details: str

    def __str__(self) -> str:
        return f"invalid response from {self.operation}: {self.details}"
```

Raise it from `_call()` instead of flattening the envelope into `RuntimeError`. It remains a `RuntimeError` subclass so existing CLI error handling remains compatible.

- [ ] **Step 5: Implement codec functions with existing models**

Create named functions instead of a generic reflection layer:

```python
def decode_workflow_artifact(
    payload: object,
) -> tuple[WorkflowArtifact, Workflow]: ...


def decode_deployment(payload: object) -> WorkflowDeployment: ...


def decode_dependency_diagnostics(
    payload: object,
) -> tuple[DependencyDiagnostic, ...]: ...


def decode_run_result(payload: object) -> DecodedRunResult: ...


def decode_trace_result(payload: object) -> DecodedTracePage: ...
```

Use `TypeAdapter` for wire `TypedDict` validation, then `WorkflowArtifact.model_validate()`, `RawWorkflowPlan.model_validate()`, and `Workflow.model_validate()`. Wrap validation failures as `InvalidResponse(operation=..., details=...)`; do not weaken schemas to accept malformed server data.

- [ ] **Step 6: Run focused tests and type checks**

```powershell
uv run pytest tests/wf_client/test_codec.py tests/wf_transport_rpc_http/test_client.py -q
uv run basedpyright --level error src/wf_client src/wf_transport_rpc_http/client tests/wf_client/test_codec.py
```

Expected: codec and structured-error tests pass with zero type errors.

- [ ] **Step 7: Commit the client foundation**

```powershell
git add src/wf_client/protocols.py src/wf_client/codec.py src/wf_client/errors.py src/wf_transport_rpc_http/client/base.py tests/wf_client tests/wf_transport_rpc_http/test_client.py
git commit -m "feat: add validated workflow client boundary"
```

---

### Task 4: Add `App` and callable remote capabilities

**Files:**

- Create: `src/wf_client/app.py`
- Create: `src/wf_client/capabilities.py`
- Create: `src/wf_client/__init__.py`
- Create: `tests/wf_client/test_app.py`
- Create: `tests/wf_client/test_capabilities.py`

**Interfaces:**

- Consumes: `WorkflowClientPort`, `RpcWorkflowApiClient`, capability result codecs, JSON Schema Draft 2020-12 validation, and `WorkflowBuilder.use_contract()` from Task 1.
- Produces: `App.from_http_jsonrpc()`, `App.capability()`, `App.capabilities()`, `Page[CapabilitySummary]`, `RemoteCapability`, `CapabilityResult`, and `App.new_workflow()` construction hook.

- [ ] **Step 1: Write failing connection and capability tests**

Test construction performs no network operation:

```python
def test_from_http_jsonrpc_is_lazy(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(httpx.AsyncClient, "post", lambda *args, **kwargs: calls.append("post"))

    app = App.from_http_jsonrpc("http://localhost:8765/rpc")

    assert app.endpoint == "http://localhost:8765/rpc"
    assert calls == []
```

Test callable behavior and graph contract:

```python
async def test_remote_capability_is_callable_and_graph_usable(fake_port) -> None:
    fake_port.inspect_capability_result = search_capability_payload()
    fake_port.call_capability_result = {
        "qualified_name": "app.default.search",
        "source_id": "app.default",
        "kind": "node_spec",
        "deployment_id": None,
        "outcome": "ok",
        "output": {"results": ["one"]},
        "diagnostics": [],
    }
    app = App._from_port(fake_port)

    search = await app.capability("app.default.search")
    result = await search(query="workflow")

    assert search.ref == CapabilityRef(
        source="app.default",
        capability_key="search",
    )
    assert result.outcome == "ok"
    assert result.output == {"results": ["one"]}
```

Add tests rejecting positional-plus-keyword payloads, invalid local inputs before I/O, invalid outputs after I/O, and reserved client options only through `call()`.

Add a paged discovery test proving list rows become attribute-bearing immutable
objects rather than leaked dictionaries:

```python
async def test_capability_discovery_returns_rich_page(fake_port) -> None:
    fake_port.list_capabilities_result = capability_page_payload()

    page = await App._from_port(fake_port).capabilities(query="search", limit=10)

    assert page.total == 1
    assert page.next_cursor is None
    assert page.items[0].qualified_name == "app.default.search"
    assert page.items[0].outcomes == ("ok",)
```

- [ ] **Step 2: Run tests and confirm missing public objects**

```powershell
uv run pytest tests/wf_client/test_app.py tests/wf_client/test_capabilities.py -q
```

Expected: import failures for `App` and `RemoteCapability`.

- [ ] **Step 3: Implement `RemoteCapability`**

Use a frozen dataclass retaining its port and inspected contract:

```python
@dataclass(frozen=True, slots=True)
class RemoteCapability:
    _port: WorkflowClientPort = field(repr=False, compare=False)
    ref: CapabilityRef
    qualified_name: str
    description: str | None
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    outcomes: tuple[str, ...]
    is_async: bool

    async def __call__(
        self,
        payload: Mapping[str, Any] | None = None,
        /,
        **fields: Any,
    ) -> CapabilityResult:
        if payload is not None and fields:
            raise TypeError("pass a payload mapping or keyword fields, not both")
        return await self.call(dict(payload) if payload is not None else fields)

    def node_def(self) -> NodeDef:
        return NodeDef(
            name=self.qualified_name,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            outcomes=list(self.outcomes),
        )
```

Use `jsonschema.Draft202012Validator` for input/output validation. Reject an inspected schema that is not itself a valid Draft 2020-12 schema when constructing the object.

- [ ] **Step 4: Implement `App` and public exports**

Provide a private/test construction seam and the public transport factory:

```python
@dataclass(frozen=True, slots=True)
class App:
    _port: WorkflowClientPort = field(repr=False)
    endpoint: str

    @classmethod
    def from_http_jsonrpc(
        cls,
        url: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> App:
        return cls(
            _port=RpcWorkflowApiClient(
                url=url,
                timeout_seconds=timeout_seconds,
            ),
            endpoint=url,
        )

    @classmethod
    def _from_port(cls, port: WorkflowClientPort) -> App:
        return cls(_port=port, endpoint="in-process")
```

`capability()` validates the inspect payload and reconstructs `CapabilityRef` structurally from `source_id` plus the source-relative capability key. Do not split a dotted qualified name heuristically; add/reuse the platform capability-ref parser.

Use an exact prefix check so capability keys may themselves contain dots:

```python
def _capability_ref(qualified_name: str, source_id: str) -> CapabilityRef:
    prefix = f"{source_id}."
    if not qualified_name.startswith(prefix):
        raise InvalidResponse(
            operation="workflow.capabilities.inspect",
            details=(
                f"qualified name {qualified_name!r} does not belong to "
                f"source {source_id!r}"
            ),
        )
    return CapabilityRef(
        source=source_id,
        capability_key=qualified_name.removeprefix(prefix),
    )
```

Define `Page[T]` and `CapabilitySummary` as frozen dataclasses. `Page.items` and
summary outcomes are tuples so decoded discovery results cannot be mutated
behind the client's validation seam.

- [ ] **Step 5: Run focused tests and type checks**

```powershell
uv run pytest tests/wf_client/test_app.py tests/wf_client/test_capabilities.py -q
uv run basedpyright --level error src/wf_client tests/wf_client/test_app.py tests/wf_client/test_capabilities.py
```

Expected: all tests pass and public imports resolve from `wf_client`.

- [ ] **Step 6: Commit capability ergonomics**

```powershell
git add src/wf_client tests/wf_client/test_app.py tests/wf_client/test_capabilities.py
git commit -m "feat: add callable remote workflow capabilities"
```

---

### Task 5: Add editable workflows and immutable artifact round trips

**Files:**

- Create: `src/wf_client/authoring.py`
- Create: `src/wf_client/workflows.py`
- Create: `tests/wf_client/test_authoring.py`
- Modify: `src/wf_client/app.py`
- Modify: `src/wf_client/__init__.py`
- Modify: `examples/lda_report_workflow/build_workflow.py:24`

**Interfaces:**

- Consumes: `WorkflowBuilder.from_workflow()`, `use_contract()`, Task 2 validation operation, Task 3 codecs/port, and Task 4 `RemoteCapability`.
- Produces: `EditableWorkflow(WorkflowBuilder)`, `WorkflowValidation`, `WorkflowArtifact`, `App.new_workflow()`, `App.workflow()`, `App.edit_workflow()`, and lossless `save()`.

- [ ] **Step 1: Write failing local/remote validation tests**

Prove local failures avoid I/O and valid plans run both sides:

```python
async def test_validate_stops_before_remote_call_when_local_graph_is_invalid(
    fake_port,
) -> None:
    graph = App._from_port(fake_port).new_workflow(
        "invalid",
        input_schema={"type": "object", "properties": {}},
        state_schema={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
    )

    result = await graph.validate()

    assert result.local.ok is False
    assert result.remote_status == "not_run"
    assert fake_port.calls == []


async def test_validate_runs_local_and_server_validation(fake_port) -> None:
    graph = valid_editable_workflow(App._from_port(fake_port))
    fake_port.validate_artifact_plan_result = {
        "status": "valid",
        "diagnostics": [],
        "required_capabilities": [],
        "workflow_dependencies": {},
    }

    result = await graph.validate()

    assert result.ok is True
    assert result.local.ok is True
    assert result.remote_status == "valid"
    assert fake_port.calls[-1].operation == "validate_artifact_plan"
```

- [ ] **Step 2: Write failing save/edit round-trip tests**

Use an artifact payload containing composite inputs, final-output bindings, explicit end nodes, and a native subgraph. Assert:

```python
async def test_edit_and_save_preserve_complete_artifact_plan(fake_port) -> None:
    fake_port.inspect_artifact_result = complex_artifact_payload()
    app = App._from_port(fake_port)

    graph = await app.edit_workflow("report", version=1)
    fake_port.inspect_artifact_result = complex_artifact_payload(version=2)
    saved = await graph.save(version=2)

    create_call = next(
        call
        for call in fake_port.calls
        if call.operation == "create_artifact_from_plan"
    )
    assert create_call.operation == "create_artifact_from_plan"
    assert create_call.params["plan"] == complex_artifact_payload(version=1)["plan"]
    assert saved.ref == ArtifactRef("report", 2)
```

Add an assertion that `EditableWorkflow` is a `WorkflowBuilder` and directly exposes `when`, `choose`, `match`, `foreach`, `interrupt`, `end`, `connect`, and `set_entry_point`.

- [ ] **Step 3: Run tests and confirm failures**

```powershell
uv run pytest tests/wf_client/test_authoring.py -q
```

Expected: failures because editable workflow and artifact objects do not exist.

- [ ] **Step 4: Implement `EditableWorkflow` as a real subclass**

Use explicit dataclass fields compatible with `WorkflowBuilder` initialization; do not proxy through `__getattr__`:

```python
@dataclass(slots=True)
class EditableWorkflow(WorkflowBuilder):
    _port: WorkflowClientPort = field(repr=False, kw_only=True)
    based_on: ArtifactRef | None = field(default=None, kw_only=True)
    artifact_title: str | None = field(default=None, kw_only=True)
    artifact_description: str | None = field(default=None, kw_only=True)

    def use(
        self,
        spec: NodeSpec[Any, Any] | RemoteCapability,
        **kwargs: Any,
    ) -> NodeUse:
        if isinstance(spec, RemoteCapability):
            return self.use_contract(spec.node_def(), **kwargs)
        return super().use(spec, **kwargs)
```

Preserve precise overloads in the actual implementation; the broad body signature is not the public typing contract. Implement `validate_local()`, async `validate()`, and `save()` exactly as specified. `save()` must call validation first and refuse invalid results before `create_artifact_from_plan()`. `validate_local()` delegates to inherited `validate_structure()` so incomplete graphs produce ordinary `ValidationReport` issues without network I/O.

- [ ] **Step 5: Implement immutable `WorkflowArtifact` and App lookups**

Use a frozen dataclass retaining both canonical models:

```python
@dataclass(frozen=True, slots=True)
class WorkflowArtifact:
    _port: WorkflowClientPort = field(repr=False, compare=False)
    artifact: ArtifactDomainModel
    workflow: Workflow

    @property
    def ref(self) -> ArtifactRef:
        return ArtifactRef(self.artifact.id, self.artifact.version)

    def inspect(self) -> Workflow:
        return self.workflow.model_copy(deep=True)

    def edit(self) -> EditableWorkflow:
        return EditableWorkflow.from_artifact(self)
```

`App.workflow()` calls inspect and codec reconstruction. `App.edit_workflow()` is `return (await self.workflow(...)).edit()`. `App.new_workflow()` creates the subclass with no `based_on` ref. After `save()` validates and calls `create_artifact_from_plan()`, it inspects the newly saved exact version and returns that reconstructed immutable object; it never fabricates an artifact from the save acknowledgement.

- [ ] **Step 6: Remove the documented builder output workaround**

Update `examples/lda_report_workflow/build_workflow.py` to call `builder.set_output(...)` instead of compiling then applying `model_copy(update={"output": ...})`. Keep the example behavior identical and delete the stale limitation comment.

- [ ] **Step 7: Run authoring and artifact verification**

```powershell
uv run pytest tests/wf_client/test_authoring.py tests/authoring/test_builder.py tests/authoring/test_subgraph.py tests/examples/test_lda_report_workflow_example.py -q
uv run basedpyright --level error src/wf_client src/wf_authoring tests/wf_client/test_authoring.py
```

Expected: lossless round trips, subclass behavior, and the existing report example pass.

- [ ] **Step 8: Commit workflow authoring**

```powershell
git add src/wf_client src/wf_authoring examples/lda_report_workflow/build_workflow.py tests/wf_client/test_authoring.py tests/authoring tests/examples/test_lda_report_workflow_example.py
git commit -m "feat: add editable remote workflow lifecycle"
```

---

### Task 6: Add deployment and durable run objects

**Files:**

- Create: `src/wf_client/deployments.py`
- Create: `src/wf_client/runs.py`
- Create: `tests/wf_client/test_deployments.py`
- Create: `tests/wf_client/test_runs.py`
- Modify: `src/wf_client/app.py`
- Modify: `src/wf_client/workflows.py`
- Modify: `src/wf_client/__init__.py`

**Interfaces:**

- Consumes: Task 3 codecs/port, existing deployment and run operations, `TraceRange`, and Task 5 `WorkflowArtifact`.
- Produces: `Deployment`, `DeploymentValidation`, `Run`, `TracePage`, `WorkflowArtifact.deploy()`, strict `WorkflowArtifact.run()`, `App.deployment()`, and `App.run()`.

- [ ] **Step 1: Write failing explicit deployment tests**

Test save, validate, and run:

```python
async def test_artifact_deploys_with_explicit_bindings(fake_port, workflow_artifact) -> None:
    fake_port.validate_deployment_result = runnable_deployment_result()

    deployment = await workflow_artifact.deploy(
        "report.production",
        bindings={"app.default": "company.production"},
    )

    assert deployment.deployment_id == "report.production"
    assert deployment.bindings == {"app.default": "company.production"}
    assert deployment.runnable is True
    assert [call.operation for call in fake_port.calls[-3:]] == [
        "save_deployment",
        "inspect_deployment",
        "validate_deployment",
    ]
```

- [ ] **Step 2: Write failing convenience-run policy tests**

Cover the three allowed paths and ambiguity rejection:

```python
async def test_artifact_run_rejects_ambiguous_deployments(
    fake_port,
    workflow_artifact,
) -> None:
    fake_port.list_deployments_result = {
        "deployments": [
            deployment_summary("report.dev", "report", 1),
            deployment_summary("report.prod", "report", 1),
        ]
    }

    with pytest.raises(DeploymentRequired) as captured:
        await workflow_artifact.run({"topic": "workflow"})

    assert captured.value.candidate_deployment_ids == (
        "report.dev",
        "report.prod",
    )
    assert not any(call.operation == "run_deployment" for call in fake_port.calls)
```

Also prove an artifact with no matching deployment creates deterministic id
`report.v1.default` with the caller-supplied bindings or an empty binding map,
then asks the server to validate it. It runs only when the server returns
`runnable`; otherwise it raises `DeploymentRequired` containing the server
diagnostics and leaves the named deployment available for deliberate repair.
A supplied `deployment_id` bypasses discovery.

- [ ] **Step 3: Write failing run lifecycle tests**

```python
async def test_interrupted_run_resumes_and_reads_bounded_trace(fake_port) -> None:
    run = Run.from_payload(fake_port, interrupted_run_payload())
    fake_port.resume_run_result = completed_run_payload()
    fake_port.run_trace_result = trace_payload(start=0, limit=25)

    completed = await run.resume({"approved": True})
    trace = await completed.trace(limit=25)

    assert completed.status == "completed"
    assert completed.output == {"result": "done"}
    assert trace.start == 0
    assert trace.limit == 25
    assert len(trace.frames) == 1
```

Add tests for `refresh()`, non-resumable runs, negative trace starts, and trace limits outside the existing server bound.

- [ ] **Step 4: Run focused tests and confirm missing lifecycle objects**

```powershell
uv run pytest tests/wf_client/test_deployments.py tests/wf_client/test_runs.py -q
```

Expected: import or attribute failures for deployment/run objects.

- [ ] **Step 5: Implement deployment objects and strict artifact convenience**

Create immutable snapshots:

```python
@dataclass(frozen=True, slots=True)
class Deployment:
    _port: WorkflowClientPort = field(repr=False, compare=False)
    model: WorkflowDeployment
    diagnostics: tuple[DependencyDiagnostic, ...] = ()
    runnable: bool | None = None

    @property
    def deployment_id(self) -> str:
        return self.model.id

    async def validate(self) -> DeploymentValidation: ...
    async def run(self, workflow_input: Mapping[str, Any]) -> Run: ...
```

Implement the exact convenience policy:

1. If `deployment_id` is supplied, inspect and run only that deployment.
2. Otherwise filter deployment summaries to the exact artifact id and version.
3. Use the sole match.
4. Reject multiple matches with sorted candidates.
5. With no match, save `<artifact_id>.v<version>.default` using explicitly
   supplied bindings or `{}` and immediately request server validation.
6. Run the default only when server validation says `runnable`; otherwise raise
   `DeploymentRequired` with its diagnostics. Do not infer source type from
   names or artifact payloads.
7. Never overwrite an existing deterministic deployment bound to another
   artifact version.

- [ ] **Step 6: Implement immutable run snapshots**

```python
@dataclass(frozen=True, slots=True)
class Run:
    _port: WorkflowClientPort = field(repr=False, compare=False)
    run_id: str
    deployment_id: str
    status: str
    outcome: str | None
    output: dict[str, Any] | None
    interrupt: InterruptRequest | None
    diagnostics: tuple[DependencyDiagnostic, ...]
    trace_count: int

    async def refresh(self) -> Run: ...

    async def resume(
        self,
        response: Mapping[str, Any],
        *,
        outcome: str = "submitted",
    ) -> Run: ...

    async def trace(self, *, start: int = 0, limit: int = 25) -> TracePage: ...
```

Methods return new snapshots and never mutate `self`. Validate trace bounds before I/O and preserve structured diagnostics.

Reuse `wf_core.InterruptRequest` and `wf_core.TraceEntry` for reconstructed
interrupts and trace frames. `TracePage.frames` is `tuple[TraceEntry, ...]`;
do not expose `InterruptPayload`, `TraceEntryPayload`, or other wire
`TypedDict`s from the public objects.

`Deployment.run()` constructs `Run` only when `run_deployment()` returns a
non-null `run_id`. An unrunnable or rejected result raises
`DeploymentNotRunnable` with reconstructed diagnostics, outcome, and server
error text; a missing id must not become a fake Python run.

- [ ] **Step 7: Run lifecycle verification**

```powershell
uv run pytest tests/wf_client/test_deployments.py tests/wf_client/test_runs.py tests/wf_api/test_deployment_api.py tests/wf_api/test_run_api.py -q
uv run basedpyright --level error src/wf_client tests/wf_client/test_deployments.py tests/wf_client/test_runs.py
```

- [ ] **Step 8: Commit deployment and run ergonomics**

```powershell
git add src/wf_client tests/wf_client/test_deployments.py tests/wf_client/test_runs.py
git commit -m "feat: add Python deployment and run objects"
```

---

### Task 7: Prove HTTP usage, add bounded IPython representations, and document the package

**Files:**

- Create: `tests/wf_client/test_http_integration.py`
- Create: `tests/wf_client/test_repr.py`
- Modify: `src/wf_client/capabilities.py`
- Modify: `src/wf_client/workflows.py`
- Modify: `src/wf_client/deployments.py`
- Modify: `src/wf_client/runs.py`
- Modify: `docs/project_map.md`
- Modify: `docs/source_architecture.md`
- Modify: `docs/wf_api_architecture.md`
- Modify: `docs/current_roadmap.md`
- Modify: `CONTEXT.md` only if implementation changes a term from the approved spec

**Interfaces:**

- Consumes: all public objects from Tasks 4-6 and the real local JSON-RPC ASGI application.
- Produces: verified `App.from_http_jsonrpc()` lifecycle, safe `repr()`/`_repr_html_()`, and current user/architecture documentation.

- [ ] **Step 1: Write a failing end-to-end HTTP test**

Use `httpx.ASGITransport` with the real RPC app and give its configured
`RpcWorkflowApiClient` to the private in-process construction seam. The public
HTTP factory remains transport-detail free:

```python
async def test_http_app_calls_authors_saves_deploys_and_runs(tmp_path) -> None:
    server = build_local_static_workflow_server(tmp_path / "store")
    rpc_app = create_rpc_app(server)
    transport = httpx.ASGITransport(app=rpc_app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as http_client:
        app = App._from_port(
            RpcWorkflowApiClient(
                url="http://test/rpc",
                http_client=http_client,
            )
        )
        constant = await app.capability("wf.std.constant")
        graph = empty_string_workflow(app)
        step = graph.use(
            constant,
            id="constant",
            input=[input_value("value", "hello")],
            output=[output_to("value", state_path("value"))],
        )
        end = graph.end("ok", id="end_ok")
        graph.set_entry_point(step)
        graph.connect(step, "ok", end)
        graph.set_output([input_from(state_path("value"), "value")])

        validation = await graph.validate()
        artifact = await graph.save(version=1, title="HTTP client proof")
        run = await artifact.run({})

    assert validation.ok is True
    assert artifact.ref == ArtifactRef("http_client_proof", 1)
    assert run.status == "completed"
    assert run.output == {"value": "hello"}
```

- [ ] **Step 2: Write representation safety tests**

For every rich object, clear the fake adapter call log, render both representations, and assert no calls occurred:

```python
def test_capability_html_repr_is_bounded_and_does_not_call_port(
    fake_port,
    remote_capability,
) -> None:
    fake_port.calls.clear()

    rendered = remote_capability._repr_html_()

    assert "app.default.search" in rendered
    assert "input schema" in rendered.lower()
    assert fake_port.calls == []
```

Add tests that large schemas/diagnostics/outputs are summarized by count and bounded previews, and secret-like fields are redacted with the repository's existing redaction helper rather than a second ad-hoc implementation.

- [ ] **Step 3: Run the new tests and confirm missing representation/integration behavior**

```powershell
uv run pytest tests/wf_client/test_http_integration.py tests/wf_client/test_repr.py -q
```

Expected: failures until the HTTP-client injection seam and rich representations are implemented.

- [ ] **Step 4: Implement bounded, inert representations**

Each object gets concise `__repr__()` plus `_repr_html_()` that uses only loaded fields. Centralize HTML escaping and bounded rendering in a private helper inside `wf_client`; do not add a public templating interface. Representations must never call `await`, access the port, or show an unbounded trace/output.

- [ ] **Step 5: Update live documentation**

Add `wf_client` to the package maps and document this lifecycle exactly:

```python
app = App.from_http_jsonrpc("http://localhost:8765/rpc")
capability = await app.capability("wf.std.constant")
graph = app.new_workflow(
    "example",
    input_schema=InputModel,
    state_schema=StateModel,
    output_schema=OutputModel,
)
step = graph.use(capability)
graph.set_entry_point(step)
validation = await graph.validate()
validation.raise_for_errors()
artifact = await graph.save(version=1)
run = await artifact.run({})
```

Drafts are not part of `wf_client`. The shipped server composition uses
`drafts=False` by default, which excludes draft storage, domain modules, and RPC
registration; real legacy draft consumers opt in explicitly with `drafts=True`.
The earlier plan assumption that draft methods would remain registered pending a
separate opt-out slice is historical. Update `docs/current_roadmap.md` to mark
the Python-client slice complete only after every verification step below
passes.

- [ ] **Step 6: Run focused and cross-layer verification**

```powershell
uv run pytest tests/wf_client tests/authoring/test_builder.py tests/authoring/test_subgraph.py tests/wf_api/test_artifact_api.py tests/wf_transport_rpc_http/test_client.py tests/wf_transport_rpc_http/test_app.py tests/wf_transport_rpc_http/test_openrpc_contract.py tests/wf_contract_manifest/test_generate.py tests/wf_contract_manifest/test_committed_manifest.py -q
uv run ruff check src/wf_client src/wf_authoring src/wf_api src/wf_transport_rpc_http tests/wf_client tests/authoring/test_builder.py tests/wf_api/test_artifact_api.py
uv run ruff format --check src/wf_client src/wf_authoring src/wf_api src/wf_transport_rpc_http tests/wf_client tests/authoring/test_builder.py tests/wf_api/test_artifact_api.py
uv run basedpyright --level error src/wf_client src/wf_authoring src/wf_api src/wf_transport_rpc_http
uv run python -m wf_contract_manifest check
pnpm --dir web --filter @lda/workflow-rpc contract:check
pnpm --dir web --filter @lda/workflow-rpc test
git diff --check
```

Expected: every command passes with no manifest drift, formatting changes, type errors, or whitespace errors.

- [ ] **Step 7: Run the full Python regression suite**

```powershell
uv run pytest -q
```

Expected: the full suite passes. If environment-backed tests require local configuration, run `uv run --env-file .env pytest -q` and report exact external failures separately from deterministic test failures.

- [ ] **Step 8: Commit the completed package and docs**

```powershell
git add src/wf_client tests/wf_client docs/project_map.md docs/source_architecture.md docs/wf_api_architecture.md docs/current_roadmap.md CONTEXT.md
git commit -m "feat: deliver Python workflow client"
```

## Follow-Up Plan Boundary

After this plan is complete, write and execute a separate focused plan for
draft opt-out. That plan must change all three current initialization seams:

1. `WorkflowApi` unconditionally constructs `WorkflowDraftApi` and
   `WorkflowDraftAuthoringApi`.
2. durable context validation currently requires `draft_workspace_store`.
3. `create_rpc_app()` unconditionally registers draft JSON-RPC methods.

The follow-up target is `drafts=False` by default with an explicit opt-in,
while artifact, deployment, and run durability remain available without a
draft store. Do not mix that server-composition change into `wf_client` tasks.
