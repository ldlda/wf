# Foreach Back-Edges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [x]`) syntax for tracking.

**Goal:** Make foreach bodies return through validated back-edges to their
immediate owner, with unique static control regions and fresh persisted state
for every dynamic foreach activation.

**Architecture:** Add one pure control-region analysis module and make both
validation and context inventory consume its result. Keep dynamic execution
separate: foreach activation metadata owns a barrier and item identities for
one controller visit, while frame advancement recognizes an immediate-owner
back-edge as item completion.

**Tech Stack:** Python 3.14, Pydantic workflow models, dataclass runtime state,
pytest, pytest-asyncio, Ruff, basedpyright, markdownlint-cli2.

**Spec:**
[`docs/superpowers/specs/2026-09-04-foreach-back-edge-design.md`](../../../superpowers/specs/2026-09-04-foreach-back-edge-design.md)

## Global Constraints

- Preserve the flat serialized workflow graph; do not add nested body models.
- Keep `END` as a workflow/subgraph terminal, never a foreach-item return.
- Give every reachable node use exactly one static foreach-owner stack.
- Reject unreachable workflow nodes and structurally impossible item returns.
- Permit ordinary cycles when their nodes remain in one control region.
- Create a fresh persisted activation for every dynamic foreach-controller
  visit, including repeated visits in the same parent frame.
- Keep current `fail`, `skip`, `collect`, reducer, interrupt, sync, and async
  behavior.
- Keep nested context innermost-only; inherited structured foreach context is
  deferred.
- Do not add break/continue, fork/gather, retry execution, a step limit, a new
  Python DSL, or compatibility behavior for unobserved persisted data.
- Add docstrings or comments around owner-stack traversal, return-edge handling,
  activation lifecycle, and any fail-closed runtime checks.
- Do not modify or commit the user's dirty `docs/AGENTS.md`.

---

### Task 1: Build the Pure Control-Region Analyzer

**Files:**

- Create: `src/wf_core/analysis/control_regions.py`
- Modify: `src/wf_core/analysis/__init__.py`
- Test: `tests/core/test_foreach_control_regions.py`

**Interfaces:**

- Consumes: `Workflow`, `ForeachNode`, `EndNode`, `Edge`, and `END`.
- Produces:

  ```python
  type ForeachOwnerStack = tuple[str, ...]

  class ControlRegionIssueKind(StrEnum):
      UNREACHABLE_NODE = "unreachable_node"
      FOREACH_REGION_CONFLICT = "foreach_region_conflict"
      INVALID_FOREACH_RETURN = "invalid_foreach_return"
      INVALID_FOREACH_TERMINAL = "invalid_foreach_terminal"
      EMPTY_FOREACH_BODY = "empty_foreach_body"
      FOREACH_BODY_NO_RETURN = "foreach_body_no_return"

  @dataclass(frozen=True, slots=True)
  class ControlRegionIssue:
      kind: ControlRegionIssueKind
      path: str
      message: str

  @dataclass(frozen=True, slots=True)
  class ControlRegionAnalysis:
      owner_stack_by_node: dict[str, ForeachOwnerStack]
      issues: tuple[ControlRegionIssue, ...]

  ```

  Function:
  `analyze_control_regions(workflow: Workflow) -> ControlRegionAnalysis`.

- `owner_stack_by_node` contains only nodes whose region is unambiguous. Later
  context analysis must not grant foreach fields to a conflicted node.

- [x] **Step 1: Write failing acceptance tests for legal regions**

  Add explicit tests named:

  - `test_closed_root_cycle_has_one_empty_control_region`
  - `test_foreach_cycle_with_possible_return_is_valid`
  - `test_conditional_foreach_paths_can_both_return`
  - `test_nested_foreach_assigns_static_owner_stacks`
  - `test_reentering_completed_foreach_keeps_one_static_region`

  The nested assertion must be exact:

  ```python
  assert analysis.owner_stack_by_node == {
      "f1": (),
      "f2": ("f1",),
      "work": ("f1", "f2"),
      "tail": ("f1",),
      "after": (),
  }
  assert analysis.issues == ()
  ```

- [x] **Step 2: Run legal-region tests and confirm the missing module fails**

  Run:

  ```bash
  uv run pytest -q tests/core/test_foreach_control_regions.py
  ```

  Expected: collection fails because `wf_core.analysis.control_regions` does
  not exist.

- [x] **Step 3: Implement semantic traversal over node and owner stack**

  Use a bounded worklist of `(node_id, owner_stack)` states. The special edge
  handling must follow this order:

  ```python
  if source_is_foreach_loop:
      if edge.to == source.id:
          issue(EMPTY_FOREACH_BODY, edge_path)
          continue
      target_stack = (*owner_stack, source.id)
  else:
      target_stack = owner_stack

  if target_is_terminal and target_stack:
      issue(INVALID_FOREACH_TERMINAL, edge_path)
  elif edge.to == target_stack[-1]:
      record_item_return(edge, target_stack[-1])
      connect_to_resumed_owner(edge.to, target_stack[:-1])
  elif edge.to in target_stack:
      issue(INVALID_FOREACH_RETURN, edge_path)
  else:
      enqueue(edge.to, target_stack)
  ```

  An immediate return resumes the owner controller in the popped stack for
  structural analysis; it does not assign the owner node to its child's stack.
  Ignore unknown sources and targets here because ordinary edge validation
  already owns those diagnostics.

- [x] **Step 4: Write failing tests for every invalid pressure case**

  Add one explicit test per topology:

  - `test_external_entry_into_foreach_body_is_region_conflict`
  - `test_foreach_body_escape_is_region_conflict`
  - `test_skipping_inner_foreach_owner_is_invalid_return`
  - `test_entering_sibling_foreach_body_is_region_conflict`
  - `test_empty_foreach_body_is_rejected`
  - `test_closed_foreach_body_cycle_has_no_return`
  - `test_foreach_body_cannot_target_end_token`
  - `test_foreach_body_cannot_target_explicit_end_node`
  - `test_every_unreachable_node_is_reported`

  Assert issue kind and location, for example:

  ```python
  assert (issue.kind, issue.path) == (
      ControlRegionIssueKind.FOREACH_REGION_CONFLICT,
      "nodes[b]",
  )
  ```

- [x] **Step 5: Implement conflicts, reachability, and returnability**

  Record the first stack for each node. If a second distinct stack reaches the
  same node, remove it from `owner_stack_by_node` and emit one region conflict.
  After traversal, report every workflow node never reached from `start`.

  Build semantic state adjacency while traversing. For every reached state with
  a non-empty stack, require a graph path to a return edge for its current top
  owner. Returns from deeper nested foreach bodies may resume their controllers
  on the way. A closed root cycle remains valid because its stack is empty.
  Suppress cascading no-return diagnostics when a region conflict, invalid
  return, invalid terminal, or empty body already makes that state ambiguous.

- [x] **Step 6: Run analyzer tests**

  Run:

  ```bash
  uv run pytest -q tests/core/test_foreach_control_regions.py
  uv run ruff check src/wf_core/analysis/control_regions.py \
    tests/core/test_foreach_control_regions.py
  uv run basedpyright --level error src/wf_core/analysis/control_regions.py
  ```

  Expected: all commands pass.

- [x] **Step 7: Commit the analyzer**

  ```bash
  git add src/wf_core/analysis/control_regions.py \
    src/wf_core/analysis/__init__.py \
    tests/core/test_foreach_control_regions.py
  git commit -m "feat: analyze foreach control regions"
  ```

### Task 2: Make Context Inventory Consume Static Regions

**Files:**

- Modify: `src/wf_core/analysis/context_scopes.py`
- Modify: `tests/core/test_context_scopes.py`

**Interfaces:**

- Consumes: `analyze_control_regions(workflow)` from Task 1.
- Produces: unchanged public functions `context_fields_by_node(workflow)` and
  `context_analysis_warnings(workflow)`.
- Keeps the existing runtime contract: the innermost foreach supplies
  `loop_item`, `loop_index`, and its alias; completing it restores the outer
  context. It does not expose all enclosing aliases.

- [x] **Step 1: Rewrite context tests to canonical back-edges**

  Replace successful item routes such as:

  ```python
  {"from": "body", "outcome": "ok", "to": END}
  ```

  with:

  ```python
  {"from": "body", "outcome": "ok", "to": "each"}
  ```

  For the nested fixture use:

  ```python
  {"from": "inner_body", "outcome": "ok", "to": "inner"}
  {"from": "after_inner", "outcome": "ok", "to": "outer"}
  ```

- [x] **Step 2: Replace the mixed-reachability expectation**

  Delete the test that expects one node to receive conditional loop fields when
  reached both inside and outside a foreach. Add a test proving conflicted nodes
  receive no guaranteed foreach fields and the analysis warning includes the
  region conflict.

  Keep the nested assertions:

  ```python
  assert "outer_item" not in inner
  assert inner["inner_item"].availability == "available"
  assert after_inner["outer_item"].availability == "available"
  assert "inner_item" not in after_inner
  ```

- [x] **Step 3: Run the context tests and confirm old traversal fails**

  Run:

  ```bash
  uv run pytest -q tests/core/test_context_scopes.py
  ```

  Expected: failures show that the single `FrameScope` traversal neither pops
  canonical return edges nor consumes region-conflict diagnostics.

- [x] **Step 4: Replace duplicate traversal with the analyzer result**

  Remove the local breadth-first scope traversal. For each unambiguous node,
  derive its active context from the final stack item:

  ```python
  stack = analysis.owner_stack_by_node.get(node_id)
  active_foreach_id = stack[-1] if stack else None
  ```

  Pass the controller's own static stack into item-schema resolution so an
  inner foreach may still declare `over="context.outer_item"`. Convert analyzer
  diagnostics to bounded context warnings. Do not reintroduce multiple scopes
  or conditional fields for a single node use.

- [x] **Step 5: Run context and authoring-contract tests**

  Run:

  ```bash
  uv run pytest -q tests/core/test_context_scopes.py \
    tests/wf_api/test_authoring_contracts.py
  uv run ruff check src/wf_core/analysis/context_scopes.py \
    tests/core/test_context_scopes.py
  uv run basedpyright --level error src/wf_core/analysis
  ```

  Expected: all commands pass.

- [x] **Step 6: Commit context integration**

  ```bash
  git add src/wf_core/analysis/context_scopes.py \
    tests/core/test_context_scopes.py
  git commit -m "refactor: derive context from foreach control regions"
  ```

### Task 3: Give Every Foreach Visit a Persisted Activation

**Files:**

- Modify: `src/wf_core/runtime/foreach_state.py`
- Modify: `src/wf_core/runtime/scheduler.py`
- Modify: `src/wf_core/runtime/lineage.py`
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Modify: `src/wf_core/runtime/ops/nodes.py`
- Modify: `src/wf_core/runtime/step.py`
- Modify: `tests/core/test_foreach_barrier_state.py`
- Modify: `tests/core/test_scheduler.py`
- Modify: `tests/core/test_concurrent_foreach.py`
- Modify: `tests/core/test_concurrent_foreach_errors.py`
- Modify: `tests/core/test_concurrent_foreach_interrupts.py`
- Test: `tests/core/test_foreach_activations.py`

**Interfaces:**

- Produces:

  ```python
  @dataclass(slots=True)
  class ForeachActivationState:
      id: str
      foreach_node_id: str
      barrier: ForeachBarrierState

  @dataclass(frozen=True, slots=True)
  class ForeachItemOwner:
      parent_frame_id: str
      foreach_node_id: str
      activation_id: str
      item_index: int

  ```

  Functions:

  - `load_or_begin_foreach_activation(frame: ExecutionFrame,
    foreach_node_id: str, *, mode: Literal["serial", "concurrent"])
    -> ForeachActivationState`
  - `save_foreach_activation(frame: ExecutionFrame, activation:
    ForeachActivationState) -> None`
  - `close_foreach_activation(frame: ExecutionFrame, activation:
    ForeachActivationState) -> None`
  - `item_frame_owner(frame: ExecutionFrame) -> ForeachItemOwner | None`

- `ForeachIterationMetadata` gains required `activation_id: str`.
- Callers compare owner fields by name; remove tuple slicing and positional
  unpacking.

- [x] **Step 1: Write failing activation-lifecycle tests**

  Add tests proving:

  ```python
  first = load_or_begin_foreach_activation(frame, "each", mode="serial")
  save_foreach_activation(frame, first)
  restored = load_or_begin_foreach_activation(frame, "each", mode="serial")
  assert restored.id == first.id

  close_foreach_activation(frame, restored)
  second = load_or_begin_foreach_activation(frame, "each", mode="serial")
  assert second.id != first.id
  assert second.barrier.next_index == 0
  ```

  Also test malformed metadata, mode mismatch, closing a stale activation, and
  JSON round-trip through `ExecutionFrame.metadata`.

- [x] **Step 2: Run activation tests and confirm failure**

  Run:

  ```bash
  uv run pytest -q tests/core/test_foreach_activations.py
  ```

  Expected: imports fail because activation lifecycle helpers do not exist.

- [x] **Step 3: Implement the activation metadata seam**

  Hide the JSON dictionary shape inside `foreach_state.py`. Persist, per parent
  frame and foreach node id, a monotonically increasing visit sequence plus at
  most one active activation. Derive opaque ids from parent frame id, foreach
  node id, and the persisted sequence; callers must never parse them.

  Closing removes the active barrier but preserves the next sequence. Do not
  retain a compatibility reader for the old barrier-only shape because the spec
  found no real persisted foreach data.

- [x] **Step 4: Add activation identity to item metadata and helpers**

  Require this shape:

  ```python
  ForeachIterationMetadata(
      foreach_node_id=step.id,
      activation_id=activation.id,
      loop_index=loop_index,
      loop_item=item,
      loop_alias=step.as_,
  )
  ```

  Child frame and lineage ids must include `activation.id`, so a later visit at
  item index zero cannot collide with the first visit.

- [x] **Step 5: Move runtime callers onto named owner and activation state**

  Update lineage reads, node-result buffering, async batching, failure
  collection, refill, and barrier commit to load the activation named by the
  child. Fail closed when a child result names a closed or different active
  activation.

- [x] **Step 6: Update focused metadata tests**

  Replace hand-written item metadata in `test_foreach_barrier_state.py` and
  `test_scheduler.py` with required activation ids. Update hard-coded child
  frame and lineage ids in the concurrent, error, and interrupt suites to
  include the activation identity. Assert `item_frame_owner` returns
  `ForeachItemOwner`, not a tuple.

- [x] **Step 7: Run runtime-state tests**

  Run:

  ```bash
  uv run pytest -q tests/core/test_foreach_activations.py \
    tests/core/test_foreach_barrier_state.py tests/core/test_scheduler.py \
    tests/core/test_concurrent_foreach.py \
    tests/core/test_concurrent_foreach_errors.py \
    tests/core/test_concurrent_foreach_interrupts.py
  uv run ruff check src/wf_core/runtime tests/core/test_foreach_activations.py \
    tests/core/test_foreach_barrier_state.py tests/core/test_scheduler.py
  uv run basedpyright --level error src/wf_core/runtime
  ```

  Expected: all commands pass.

- [x] **Step 8: Commit activation identity**

  ```bash
  git add src/wf_core/runtime/foreach_state.py \
    src/wf_core/runtime/scheduler.py src/wf_core/runtime/lineage.py \
    src/wf_core/runtime/ops/foreach.py src/wf_core/runtime/ops/nodes.py \
    src/wf_core/runtime/step.py tests/core/test_foreach_activations.py \
    tests/core/test_foreach_barrier_state.py tests/core/test_scheduler.py \
    tests/core/test_concurrent_foreach.py \
    tests/core/test_concurrent_foreach_errors.py \
    tests/core/test_concurrent_foreach_interrupts.py
  git commit -m "feat: identify dynamic foreach activations"
  ```

### Task 4: Execute Immediate-Owner Back-Edges

**Files:**

- Modify: `src/wf_core/runtime/ops/flow.py`
- Modify: `src/wf_core/runtime/foreach_state.py`
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Test: `tests/core/test_foreach_back_edges.py`
- Modify: `tests/core/test_concurrent_foreach.py`
- Modify: `tests/core/test_concurrent_foreach_async.py`
- Modify: `tests/core/test_concurrent_foreach_errors.py`
- Modify: `tests/core/test_concurrent_foreach_interrupts.py`
- Modify: `examples/raw_concurrent_foreach.py`
- Modify: `examples/authoring_concurrent_foreach.py`
- Modify: `examples/demo_workflow.py`
- Modify: `tests/authoring/test_demo_workflow.py`

**Interfaces:**

- Consumes: `ForeachItemOwner` and activation lifecycle from Task 3.
- Produces: `advance_frame` recognizes a target equal to the immediate
  owner's foreach node as item completion before generic node advancement.
- Produces an internal helper that derives ancestor foreach owners from frame
  ancestry for defensive non-local-return rejection.

- [x] **Step 1: Write failing serial return tests**

  Add tests with canonical edges:

  ```python
  Edge.model_validate({"from": "each", "outcome": "loop", "to": "work"})
  Edge.model_validate({"from": "work", "outcome": "ok", "to": "each"})
  Edge.model_validate({"from": "each", "outcome": "done", "to": END})
  ```

  Prove two items execute, the child finishes at `each`, the parent wakes, and
  the final workflow outcome remains `ok`.

- [x] **Step 2: Write failing cycle, nested, and re-entry runtime tests**

  Add explicit tests named:

  - `test_foreach_body_cycle_can_repeat_then_return`
  - `test_conditional_body_can_return_on_either_outcome`
  - `test_nested_foreach_returns_inner_then_outer`
  - `test_reentering_foreach_uses_fresh_activation_and_item_frames`
  - `test_subgraph_end_returns_to_subgraph_node_then_foreach_owner`
  - `test_nonlocal_runtime_return_fails_closed_when_validation_is_bypassed`

  The re-entry test must visit one foreach node twice in the root frame and
  assert two distinct activation ids and two distinct item-zero frame ids.
  The nested test must prove an inactive foreach is entered normally, while the
  direct defensive test constructs an invalid frame chain without running
  workflow preparation and asserts `WorkflowExecutionError`.

- [x] **Step 3: Implement immediate-owner return in frame advancement**

  Before `END` handling or ordinary enqueue:

  ```python
  owner = item_frame_owner(frame)
  if owner is not None and next_node_id == owner.foreach_node_id:
      source_node_id = frame.node_id
      frame.prior_outcome = outcome
      frame.activated_incoming_edge = source_node_id
      frame.node_id = owner.foreach_node_id
      frame.status = FrameStatus.COMPLETED
      frame.finished_at_node_id = owner.foreach_node_id
      wake_parent_for_child_progress(run, frame.id)
      run.sync_from_current_frame()
      return
  ```

  Add a comment explaining why the child does not execute the target node. If
  an item targets `END`, or targets a foreach found below its immediate owner in
  the active ancestor chain, raise `WorkflowExecutionError` defensively.

- [x] **Step 4: Close activations before controller completion edges**

  In both serial and concurrent completion paths, close the active activation
  before calling `advance_frame` for `done` or `completed_with_errors`. This
  makes a self-looping or later returning completion edge start a fresh visit.

- [x] **Step 5: Migrate executable foreach fixtures**

  Change item-success routes from `END` to their owner in every file listed for
  this task. Keep controller completion routes to `END` or their real outer
  continuation. For nested fixtures, return inner bodies to the inner foreach
  and outer-tail nodes to the outer foreach.

- [x] **Step 6: Prove concurrent, async, error, and interrupt behavior**

  Run:

  ```bash
  uv run pytest -q tests/core/test_foreach_back_edges.py \
    tests/core/test_concurrent_foreach.py \
    tests/core/test_concurrent_foreach_async.py \
    tests/core/test_concurrent_foreach_errors.py \
    tests/core/test_concurrent_foreach_interrupts.py \
    tests/core/test_raw_canonical_workflow_example.py \
    tests/authoring/test_concurrent_foreach_examples.py \
    tests/authoring/test_demo_workflow.py
  ```

  Assert resumed interrupts retain the same activation id. Add a direct
  fail-closed test showing a completed activation cannot accept a result or
  wake-up from another activation.

- [x] **Step 7: Run runtime static checks**

  Run:

  ```bash
  uv run ruff check src/wf_core/runtime examples \
    tests/core/test_foreach_back_edges.py \
    tests/core/test_concurrent_foreach.py \
    tests/core/test_concurrent_foreach_async.py \
    tests/core/test_concurrent_foreach_errors.py \
    tests/core/test_concurrent_foreach_interrupts.py
  uv run basedpyright --level error src/wf_core/runtime
  ```

  Expected: all commands pass.

- [x] **Step 8: Commit runtime back-edges**

  ```bash
  git add src/wf_core/runtime/ops/flow.py \
    src/wf_core/runtime/foreach_state.py \
    src/wf_core/runtime/ops/foreach.py \
    examples/raw_concurrent_foreach.py \
    examples/authoring_concurrent_foreach.py examples/demo_workflow.py \
    tests/core/test_foreach_back_edges.py \
    tests/core/test_concurrent_foreach.py \
    tests/core/test_concurrent_foreach_async.py \
    tests/core/test_concurrent_foreach_errors.py \
    tests/core/test_concurrent_foreach_interrupts.py \
    tests/authoring/test_demo_workflow.py
  git commit -m "feat: return foreach items through owner back-edges"
  ```

### Task 5: Enforce Control Regions Through Public Validation

**Files:**

- Modify: `src/wf_core/validation/issues.py`
- Modify: `src/wf_core/validation/core.py`
- Modify: `tests/core/test_foreach_control_regions.py`
- Modify: `tests/core/test_foreach_policy.py`
- Modify: `tests/artifacts/test_draft_models.py`
- Modify: `tests/artifacts/test_draft_adapter.py`

**Interfaces:**

- Consumes: `ControlRegionAnalysis` from Task 1.
- Produces public `ValidationIssueCode` values matching every
  `ControlRegionIssueKind` value.
- Keeps `Workflow.validate_structure()` and `ValidationReport` signatures
  unchanged.

- [x] **Step 1: Add failing public-validation assertions**

  For every pressure-case test, call both the pure analyzer and
  `workflow.validate_structure()`. Invalid cases must assert the public code and
  offending path:

  ```python
  matching = [
      issue
      for issue in workflow.validate_structure().errors
      if issue.code == ValidationIssueCode.FOREACH_REGION_CONFLICT
  ]
  assert matching[0].path == "nodes[b]"
  ```

  Legal cases assert `report.ok`. Add a test proving every unreachable node in
  one component receives its own `UNREACHABLE_NODE` issue.

- [x] **Step 2: Run public-validation tests and confirm failure**

  Run:

  ```bash
  uv run pytest -q tests/core/test_foreach_control_regions.py
  ```

  Expected: analyzer tests pass, but public reports lack the new issue codes.

- [x] **Step 3: Wire analysis into validation once**

  Add enum members with exactly the analyzer values. Call
  `analyze_control_regions(workflow)` after ordinary node and edge validation,
  then translate each diagnostic:

  ```python
  report.add(
      ValidationIssueCode(issue.kind.value),
      issue.path,
      issue.message,
  )
  ```

  Do not add a second graph traversal inside validation.

- [x] **Step 4: Canonicalize policy and draft fixtures**

  Policy-only workflow helpers must include a distinct body node and route it
  back to the foreach owner. Draft fixtures with:

  ```python
  "routes": {"each_item": {"loop": "echo", "done": "__end__"},
             "echo": {"ok": "__end__"}}
  ```

  become:

  ```python
  "routes": {"each_item": {"loop": "echo", "done": "__end__"},
             "echo": {"ok": "each_item"}}
  ```

  Parse-only policy fixtures still use a distinct body; do not preserve an
  invalid `loop -> __end__` shortcut just because the test does not execute it.

- [x] **Step 5: Run validation and draft suites**

  Run:

  ```bash
  uv run pytest -q tests/core/test_foreach_control_regions.py \
    tests/core/test_foreach_policy.py tests/artifacts/test_draft_models.py \
    tests/artifacts/test_draft_adapter.py tests/wf_api/test_drafts_service.py
  ```

  If another fixture expected an unreachable node to be valid, either connect
  it when it represents intended execution or change that test to assert
  `UNREACHABLE_NODE` when disconnection is the behavior under test. Do not add
  an allow-unreachable flag.

- [x] **Step 6: Run core validation static checks**

  Run:

  ```bash
  uv run ruff check src/wf_core/validation \
    tests/core/test_foreach_control_regions.py \
    tests/core/test_foreach_policy.py tests/artifacts/test_draft_models.py \
    tests/artifacts/test_draft_adapter.py
  uv run basedpyright --level error src/wf_core/validation
  ```

  Expected: all commands pass.

- [x] **Step 7: Commit fail-closed validation**

  ```bash
  git add src/wf_core/validation tests/core/test_foreach_control_regions.py \
    tests/core/test_foreach_policy.py tests/artifacts/test_draft_models.py \
    tests/artifacts/test_draft_adapter.py
  git commit -m "feat: validate foreach control regions"
  ```

### Task 6: Finish Migration, Documentation, and Full Verification

**Files:**

- Modify: `docs/wf_core_architecture.md`
- Modify: `docs/wf_authoring_control_flow.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-09-04-foreach-back-edge-design.md`
- Move after all checks pass:
  `docs/superpowers/plans/2026-09-04-foreach-back-edges.md` to
  `docs/historical/superpowers/plans/2026-09-04-foreach-back-edges.md`

**Interfaces:**

- Documents the implemented graph and runtime interface; adds no new runtime
  surface.
- Preserves historical reports and recorded agent-challenge outputs verbatim.

- [x] **Step 1: Search for stale canonical foreach returns**

  Run targeted searches:

  ```bash
  rg -n 'child reaches `END`|body.*->.*END|record.*->.*END' \
    docs skills examples tests src -g '*.md' -g '*.py' \
    -g '!docs/historical/**' -g '!examples/agent_challenges/**'
  rg -n '"outcome": "loop".*"to": END|"loop": "__end__"' \
    tests examples src -g '*.py'
  ```

  Classify each match: controller completion remains terminal; item-body
  completion changes to the owner. Do not rewrite unrelated ordinary terminal
  routes or immutable historical evidence.

- [x] **Step 2: Update live architecture and authoring docs**

  Replace the old architecture statement that item children reach `END` with:

  ```text
  An item child returns by targeting its immediate owning foreach. The child
  finishes at that owner location without executing the controller; the parent
  activation consumes the result and continues or completes its barrier.
  ```

  Add the canonical authoring example:

  ```python
  g.connect(each, "loop", record)
  g.connect(record, "ok", each)
  g.connect(each, "done", END)
  ```

  Document that region conflicts, unreachable nodes, body terminals, non-local
  returns, empty bodies, and bodies without possible returns fail validation.

- [x] **Step 3: Mark the design implemented and roadmap item complete**

  Set the spec status to `Implemented on 2026-09-04`. Move the roadmap bullet
  from active correction to recently completed runtime work. Keep fork/gather
  explicitly deferred.

- [x] **Step 4: Run the focused acceptance matrix**

  Run:

  ```bash
  uv run pytest -q tests/core/test_foreach_control_regions.py \
    tests/core/test_context_scopes.py tests/core/test_foreach_activations.py \
    tests/core/test_foreach_back_edges.py \
    tests/core/test_concurrent_foreach.py \
    tests/core/test_concurrent_foreach_async.py \
    tests/core/test_concurrent_foreach_errors.py \
    tests/core/test_concurrent_foreach_interrupts.py \
    tests/core/test_subgraph_step.py tests/authoring/test_demo_workflow.py \
    tests/authoring/test_concurrent_foreach_examples.py
  ```

  Expected: every current pressure-case row passes. The future-fork row remains
  documented and unimplemented because no fork node exists.

- [x] **Step 5: Run repository verification**

  Run:

  ```bash
  uv run pytest -q
  uv run ruff check
  uv run ruff format --check
  uv run basedpyright --level error
  pnpx markdownlint-cli2 \
    'docs/superpowers/specs/2026-09-04-foreach-back-edge-design.md' \
    'docs/wf_core_architecture.md' \
    'docs/wf_authoring_control_flow.md'
  git diff --check
  ```

  Expected: all commands pass. If repository-wide Markdown files retain known
  unrelated lint debt, do not run an unsafe global auto-fix; report it and keep
  this slice's edited documents clean.

- [x] **Step 6: Commit implementation documentation**

  ```bash
  git add docs/wf_core_architecture.md docs/wf_authoring_control_flow.md \
    docs/current_roadmap.md \
    docs/superpowers/specs/2026-09-04-foreach-back-edge-design.md
  git commit -m "docs: publish foreach back-edge semantics"
  ```

- [x] **Step 7: Archive the completed plan**

  After every prior task is complete and committed:

  ```bash
  git mv docs/superpowers/plans/2026-09-04-foreach-back-edges.md \
    docs/historical/superpowers/plans/2026-09-04-foreach-back-edges.md
  git add docs/historical/superpowers/plans/2026-09-04-foreach-back-edges.md
  git commit -m "docs: archive foreach back-edge plan"
  ```

  Search for and update any live links to the plan's historical path before
  committing. Leave the live implemented spec in `docs/superpowers/specs/`.
