# Saved Subgraph Platform Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute non-interrupting saved child workflow artifacts natively from a parent deployment while resolving all descendant dependencies through the parent deployment binding environment.

**Architecture:** `wf_core` remains unaware of artifact storage: it only looks up caller-prepared `PreparedSubgraph` dependencies by structural workflow-ref display key. A new focused workflow-surface resolver loads exact child artifact versions, traverses descendants with cycle detection, validates descendant capabilities and existing interrupt limitations, and prepares child workflows for `WfMcpService` execution. Future child deployment overrides remain outside this slice and must be keyed by subgraph use site, not artifact identity.

**Tech Stack:** Python 3.14, Pydantic v2, `wf_core` native subgraphs, `wf_artifacts` stores/deployment diagnostics, `wf_mcp` workflow surface, pytest, ruff, basedpyright.

---

## File Structure

- Modify `src/wf_core/runtime/subgraphs.py`: accept a caller-prepared structural saved `WorkflowRef`; do not load artifacts.
- Create `src/wf_mcp/workflow_surface/saved_subgraphs.py`: own saved-child traversal, diagnostic production, and preparation of executable child dependencies.
- Modify `src/wf_mcp/workflow_surface/handlers.py`: include descendant dependency/interrupt diagnostics in deployment validation.
- Modify `src/wf_mcp/broker/service/core.py`: supply prepared saved children to `execute_workflow_async`.
- Modify `tests/core/test_subgraph_step.py`: cover core execution of an already-prepared saved ref.
- Create `tests/wf_mcp/test_saved_subgraphs.py`: cover deployment-bound saved child execution and unrunnable descendant cases.
- Modify `docs/current_roadmap.md` and `docs/workflow_artifacts.md`: record the new runnable saved-child path and remaining persisted-resume limitation.

### Task 1: Core Accepts Prepared Saved References

**Files:**

- Modify: `src/wf_core/runtime/subgraphs.py`
- Test: `tests/core/test_subgraph_step.py`

- [ ] **Step 1: Write the failing core test**

Add a test that constructs a parent `SubgraphNode` with:

```python
workflow=WorkflowRef(artifact_id="child", version=1)
```

and supplies:

```python
subgraphs={
    "workflow.child.v1": PreparedSubgraph(
        workflow=child,
        registry={"echo": echo_handler},
        reducers={},
    )
}
```

Assert the parent run completes and maps the child output into parent state.

- [ ] **Step 2: Run the core test to verify it fails**

Run:

```bash
uv run pytest -q tests/core/test_subgraph_step.py
```

Expected: FAIL because `resolve_prepared_subgraph()` currently rejects a saved structural ref before checking supplied prepared dependencies.

- [ ] **Step 3: Make prepared dependency lookup structural**

Update `resolve_prepared_subgraph()`:

```python
def resolve_prepared_subgraph(
    ref: WorkflowRef,
    subgraphs: Mapping[str, PreparedSubgraph[HandlerT]] | None,
) -> PreparedSubgraph[HandlerT]:
    """Resolve a caller-prepared child; artifact loading is not a core concern."""
    key = ref.name if ref.name is not None else ref.display
    prepared = None if subgraphs is None else subgraphs.get(key)
    if prepared is None:
        raise WorkflowExecutionError(
            f"no prepared child workflow registered for {ref.display!r}"
        )
    return prepared
```

- [ ] **Step 4: Run the core test to verify it passes**

Run:

```bash
uv run pytest -q tests/core/test_subgraph_step.py
```

Expected: PASS.

### Task 2: Traverse and Prepare Saved Child Artifacts

**Files:**

- Create: `src/wf_mcp/workflow_surface/saved_subgraphs.py`
- Test: `tests/wf_mcp/test_saved_subgraphs.py`

- [ ] **Step 1: Write failing traversal tests**

Add focused tests for a helper that receives a root artifact plan containing a
structural `SubgraphNode` ref and a `FileWorkflowArtifactStore`:

```python
resolution = resolve_saved_subgraph_tree(
    root_artifact=parent,
    artifact_store=artifact_store,
)
assert resolution.artifacts_by_ref["workflow.child.v1"].id == "child"
assert resolution.diagnostics == []
```

Add tests asserting:

```python
assert resolution.diagnostics[0].code == "workflow_dependency_missing"
assert resolution.diagnostics[0].code == "workflow_dependency_cycle"
```

for a missing child and a parent/child cycle respectively.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_saved_subgraphs.py
```

Expected: FAIL because `saved_subgraphs.py` and its resolver do not exist.

- [ ] **Step 3: Implement saved-child tree discovery**

Create a typed resolution object:

```python
@dataclass(frozen=True, slots=True)
class SavedSubgraphTree:
    """Saved descendant artifacts keyed by structural workflow-ref display."""

    artifacts_by_ref: dict[str, WorkflowArtifact]
    diagnostics: list[DependencyDiagnostic]
```

Implement:

```python
def resolve_saved_subgraph_tree(
    *,
    root_artifact: WorkflowArtifact,
    artifact_store: WorkflowArtifactStore,
) -> SavedSubgraphTree:
    """Load exact saved descendants and report missing refs or cycles."""
```

Parse each artifact plan as `RawWorkflowPlan`, visit only `SubgraphNode`
instances whose `workflow.artifact_id` and `.version` are present, load the
exact artifact, and recurse. Keep an active artifact stack of
`(artifact_id, version)` values so only recursion cycles fail; repeated reuse
of the same child in separate branches is allowed.

Construct direct diagnostics without inventing a fake capability:

```python
DependencyDiagnostic(
    severity=DiagnosticSeverity.ERROR,
    code="workflow_dependency_missing",
    logical_ref=ref.display,
    message=f"Saved child workflow {ref.display!r} is unavailable.",
    repair_hint="Save the referenced artifact version or update the parent graph.",
)
```

Use analogous text for `workflow_dependency_cycle`.

- [ ] **Step 4: Run traversal tests to verify they pass**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_saved_subgraphs.py
```

Expected: traversal tests PASS.

### Task 3: Validate Descendants Under One Deployment Environment

**Files:**

- Modify: `src/wf_mcp/workflow_surface/saved_subgraphs.py`
- Modify: `src/wf_mcp/workflow_surface/handlers.py`
- Test: `tests/wf_mcp/test_saved_subgraphs.py`

- [ ] **Step 1: Write failing public-validation tests**

Add tests that save a parent artifact referencing a child artifact whose plan
uses logical node `demo.echo_tool`. Save one parent deployment:

```python
WorkflowDeployment(
    id="parent.personal",
    artifact_id="parent",
    artifact_version=1,
    bindings={"demo": "demo.personal"},
)
```

Assert:

```python
result = asyncio.run(handlers.validate_deployment(deployment_id="parent.personal"))
assert result["status"] == "runnable"
```

Add descendant failure assertions:

```python
assert result["diagnostics"][0]["code"] == "binding_missing"
assert result["diagnostics"][0]["logical_ref"] == "demo.echo_tool"
```

and for an interrupting saved child:

```python
assert result["status"] == "unrunnable"
assert result["diagnostics"][0]["code"] == "unsupported_interrupt"
```

The interrupt diagnostic must be reported before execution because
`run_deployment` is still one-shot.

- [ ] **Step 2: Run validation tests to verify they fail**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_saved_subgraphs.py
```

Expected: FAIL because `_deployment_validation()` validates only the root artifact.

- [ ] **Step 3: Add descendant validation composition**

Add a helper in `saved_subgraphs.py`:

```python
def validate_saved_subgraph_tree(
    *,
    tree: SavedSubgraphTree,
    deployment: WorkflowDeployment,
    sources: list[AvailableSource],
    unsupported_interrupt: Callable[[WorkflowArtifact], DependencyDiagnostic | None],
) -> list[DependencyDiagnostic]:
    """Validate descendants in the root deployment environment."""
```

It should begin with tree discovery diagnostics, then for each loaded child
call `validate_deployment_dependencies(...)`, and finally append the existing
unsupported-interrupt diagnostic for that child when present.

Update `WorkflowSurfaceHandlers._deployment_validation()` to discover the
saved tree and extend the root diagnostic list with descendant diagnostics.
Preserve the root artifact interrupt check in `run_deployment()`; it remains
the existing surface behavior.

- [ ] **Step 4: Run validation tests to verify they pass**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_saved_subgraphs.py
```

Expected: descendant validation tests PASS.

### Task 4: Execute Prepared Saved Children

**Files:**

- Modify: `src/wf_mcp/workflow_surface/saved_subgraphs.py`
- Modify: `src/wf_mcp/broker/service/core.py`
- Test: `tests/wf_mcp/test_saved_subgraphs.py`

- [ ] **Step 1: Write failing end-to-end execution tests**

Use the parent deployment and child artifact from Task 3. Assert:

```python
payload = asyncio.run(
    handlers.run_deployment(
        deployment_id="parent.personal",
        workflow_input={"text": "hello"},
    )
)
assert payload["status"] == "completed"
assert payload["output"]["echoed"] == "hello"
```

Add a nested parent -> middle -> child test where only the parent deployment
contains `{"demo": "demo.personal"}`, and assert the grandchild node executes
through the inherited binding.

- [ ] **Step 2: Run execution tests to verify they fail**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_saved_subgraphs.py
```

Expected: FAIL because the service does not provide prepared saved children to core.

- [ ] **Step 3: Prepare executable children and supply them to core**

Add:

```python
def prepare_saved_subgraphs(
    *,
    tree: SavedSubgraphTree,
    deployment: WorkflowDeployment | None,
    sources: dict[str, CapabilitySource],
    compile_plan: Callable[[RawWorkflowPlan, dict[str, str] | None], Workflow],
) -> dict[str, PreparedSubgraph[AsyncRegistryHandler]]:
    """Compile loaded descendants with the parent deployment bindings."""
```

For each child artifact, parse its plan, resolve its node/reducer runtime
dependencies with `resolve_runtime_dependencies(...)`, compile it, and return
the dependency under its structural ref display key:

```python
prepared[workflow_ref_display] = PreparedSubgraph(
    workflow=compile_plan(plan, dependencies.node_name_bindings),
    registry=dependencies.node_registry,
    reducers=dependencies.reducers,
)
```

Update `WfMcpService.run_workflow_from_plan()` to resolve the saved tree for
`runtime_artifact` when an artifact store exists, prepare loaded children, and
pass:

```python
subgraphs=prepared_subgraphs
```

to `execute_workflow_async(...)`.

- [ ] **Step 4: Run saved-child tests to verify they pass**

Run:

```bash
uv run pytest -q tests/wf_mcp/test_saved_subgraphs.py
```

Expected: all saved-subgraph tests PASS.

### Task 5: Documentation and Full Verification

**Files:**

- Modify: `docs/current_roadmap.md`
- Modify: `docs/workflow_artifacts.md`

- [ ] **Step 1: Document current support**

Record:

- Non-interrupting saved child artifacts now run natively through deployments.
- Descendant logical dependencies inherit the root deployment binding environment.
- Missing/cyclic/interrupting saved descendants are reported as unrunnable.
- Explicit per-child deployment overrides and persisted saved-interrupt resume remain future work.

- [ ] **Step 2: Run focused and full verification**

Run:

```bash
uv run pytest -q tests/core/test_subgraph_step.py tests/wf_mcp/test_saved_subgraphs.py
uv run pytest -q
uvx ruff check src/wf_core src/wf_mcp tests/core/test_subgraph_step.py tests/wf_mcp/test_saved_subgraphs.py
uvx ruff format --check src/wf_core/runtime/subgraphs.py src/wf_mcp/workflow_surface/saved_subgraphs.py src/wf_mcp/workflow_surface/handlers.py src/wf_mcp/broker/service/core.py tests/core/test_subgraph_step.py tests/wf_mcp/test_saved_subgraphs.py
uv run basedpyright --level error src/wf_core src/wf_mcp tests/core/test_subgraph_step.py tests/wf_mcp/test_saved_subgraphs.py
```

Expected: all commands pass, with the repository's intentionally skipped live
integration test remaining skipped unless its environment is provided.

## Self-Review

- Spec coverage: the plan covers exact artifact loading, inherited bindings,
  cycle/missing diagnostics, preserved interrupt rejection, and native execution.
- Boundary check: artifact traversal and dependency preparation stay in
  `wf_mcp`; `wf_core` accepts only caller-prepared structural refs.
- Future compatibility: no child deployment field is added; per-use-site
  override remains an additive future platform feature.
