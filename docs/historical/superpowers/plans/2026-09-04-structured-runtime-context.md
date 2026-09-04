# Structured Runtime Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace innermost-only foreach context with ancestry-derived,
same-scope structured context available consistently to Python handlers, graph
bindings, validation, schemas, and authoring helpers.

**Architecture:** Add one typed `ForeachContext` runtime value and derive the
active mapping from persisted frame ancestry. Make runtime value construction
and static context-schema construction the two canonical projections of that
model, then use the static projection for validation and authoring inventory.
Keep subgraph scopes isolated and retain current aliases as derived migration
sugar.

**Tech Stack:** Python 3.14, Pydantic workflow models, dataclass runtime state,
JSON Schema, pytest, pytest-asyncio, Ruff, basedpyright, markdownlint-cli2.

**Spec:**
[`docs/superpowers/specs/2026-09-04-structured-runtime-context-design.md`](../../../superpowers/specs/2026-09-04-structured-runtime-context-design.md)

## Global Constraints

- `GraphSourcePath` keeps exactly the `input`, `state`, and `context` roots;
  do not add an `output` root.
- Structured foreach lookup is keyed by the static `ForeachNode.id`, never by
  the configured alias or a dynamic suffix.
- Derive active foreach context from persisted frame ancestry; do not copy a
  flattened context snapshot into every frame.
- Stop ancestry traversal at `RuntimeScope`; subgraphs receive caller values
  only through declared input bindings.
- Preserve `context.loop_item`, `context.loop_index`, and unambiguous aliases as
  derived migration conveniences.
- Reject nested alias collisions and malformed persisted foreach metadata
  rather than shadowing or silently omitting values.
- Keep Python `RuntimeContext.foreach` typed while graph-visible context remains
  JSON-compatible.
- Do not add host-provided `Runtime[ContextT]`, fork/gather context, scheduling
  context, run-step limits, time-machine behavior, or the broader Python DSL.
- Add docstrings around ancestry traversal, scope stopping, literal path segment
  construction, and fail-closed metadata checks.
- Do not modify or commit the user's dirty `docs/AGENTS.md`.

---

### Task 1: Model And Derive Same-Scope Foreach Context

**Files:**

- Modify: `src/wf_core/run_state.py`
- Modify: `src/wf_core/context_contracts.py`
- Modify: `src/wf_core/runtime/ops/frames.py`
- Modify: `src/wf_core/runtime/scheduler.py`
- Modify: `src/wf_core/__init__.py`
- Create: `tests/core/test_structured_runtime_context.py`

**Interfaces:**

- Consumes: persisted `RunState.frames`, `ExecutionFrame.parent_frame_id`,
  `ExecutionFrame.scope_id`, and `ForeachIterationMetadata.from_frame(...)`.
- Produces:

  ```python
  @dataclass(frozen=True, slots=True)
  class ForeachContext:
      node_id: str
      activation_id: str
      frame_id: str
      scope_id: str
      lineage_id: str
      index: int
      item: object


  @dataclass(slots=True)
  class RuntimeContext:
      # Existing fields stay unchanged.
      foreach: Mapping[str, ForeachContext] = field(default_factory=dict)


  @dataclass(frozen=True, slots=True)
  class FrameContextView:
      """Typed handler context and graph values from one ancestry walk."""

      foreach: Mapping[str, ForeachContext]
      graph: Mapping[str, object | None]


  def frame_context_view(
      run: RunState,
      frame: ExecutionFrame,
  ) -> FrameContextView: ...
  ```

- `FrameContextView.foreach` contains entries in outermost-to-innermost
  insertion order. Lookup does not rely on that order.
- `FrameContextView.graph` exposes a JSON-compatible `foreach` mapping, all
  unique active aliases, and innermost `loop_item`/`loop_index` values.

- [x] **Step 1: Write failing model and ancestry tests**

  Add focused helpers that construct a `RunState` with explicit frames, then
  add tests named:

  - `test_root_frame_has_empty_structured_foreach_context`
  - `test_nested_same_scope_frames_expose_outermost_to_innermost_context`
  - `test_graph_context_values_keep_all_aliases_and_innermost_loop_keys`
  - `test_context_ancestry_stops_at_runtime_scope_boundary`

  The central nested assertion is:

  ```python
  view = frame_context_view(run, run.frames["inner-item"])
  contexts = view.foreach

  assert tuple(contexts) == ("customers", "orders")
  assert contexts["customers"] == ForeachContext(
      node_id="customers",
      activation_id="customers:activation:1",
      frame_id="outer-item",
      scope_id="root",
      lineage_id="customers:lineage:0",
      index=0,
      item={"name": "Ada"},
  )
  assert contexts["orders"].index == 2
  assert contexts["orders"].item == {"sku": "A-17"}
  ```

  For the scope-boundary case, give the child root a scheduling parent in the
  caller's foreach frame and assert that the child context remains `{}`.

- [x] **Step 2: Run the focused tests and confirm the missing API fails**

  Run:

  ```bash
  uv run pytest -q tests/core/test_structured_runtime_context.py
  ```

  Expected: collection or assertions fail because `ForeachContext` and the
  ancestry-aware helper do not exist.

- [x] **Step 3: Add the typed context value and validate frame metadata once**

  Add `ForeachContext` beside `RuntimeContext` and export it through
  `wf_core.__init__`. Keep `ForeachIterationMetadata` as the typed decoder for
  persisted item metadata; add a conversion method so field names are not
  copied at call sites:

  ```python
  def to_context(self, frame: ExecutionFrame) -> ForeachContext:
      return ForeachContext(
          node_id=self.foreach_node_id,
          activation_id=self.activation_id,
          frame_id=frame.id,
          scope_id=frame.scope_id,
          lineage_id=frame.lineage_id,
          index=self.loop_index,
          item=self.loop_item,
      )
  ```

- [x] **Step 4: Implement fail-closed same-scope ancestry traversal**

  Walk from the selected frame through `parent_frame_id` while scope ids match.
  Validate the full chain before returning materialized values:

  ```python
  selected_scope_id = frame.scope_id
  current: ExecutionFrame | None = frame
  seen: set[str] = set()
  inner_to_outer: list[tuple[str, ForeachContext, str]] = []

  while current is not None and current.scope_id == selected_scope_id:
      if current.id in seen:
          raise WorkflowExecutionError(
              f"cyclic execution frame ancestry at frame {current.id!r}"
          )
      seen.add(current.id)
      metadata = ForeachIterationMetadata.from_frame(current)
      if metadata is not None:
          inner_to_outer.append(
              (metadata.foreach_node_id, metadata.to_context(current), metadata.loop_alias)
          )
      if current.parent_frame_id is None:
          break
      parent = run.frames.get(current.parent_frame_id)
      if parent is None:
          raise WorkflowExecutionError(
              f"missing parent frame {current.parent_frame_id!r} "
              f"for frame {current.id!r}"
          )
      current = parent
  ```

  Reverse the collected entries and reject duplicate foreach node ids. Reject
  aliases that are empty, reserved, or duplicated in the active chain. Do not
  mutate `RunState` while reading context.

  Add `FOREACH_CONTEXT_KEY = "foreach"` to `context_contracts.py` and include it
  in `RESERVED_CONTEXT_KEYS`. Materialize graph values from the validated
  outer-to-inner entries:

  ```python
  graph[FOREACH_CONTEXT_KEY] = {
      node_id: {
          "node_id": entry.node_id,
          "activation_id": entry.activation_id,
          "frame_id": entry.frame_id,
          "scope_id": entry.scope_id,
          "lineage_id": entry.lineage_id,
          "index": entry.index,
          "item": entry.item,
      }
      for node_id, entry in foreach.items()
  }
  for node_id, entry in foreach.items():
      graph[alias_by_node_id[node_id]] = entry.item
  if foreach:
      innermost = next(reversed(foreach.values()))
      graph[LOOP_ITEM_CONTEXT_KEY] = innermost.item
      graph[LOOP_INDEX_CONTEXT_KEY] = innermost.index
  ```

- [x] **Step 5: Add corruption and collision regressions**

  Add:

  - `test_structured_context_rejects_malformed_foreach_metadata`
  - `test_structured_context_rejects_missing_parent_frame`
  - `test_structured_context_rejects_parent_cycle`
  - `test_structured_context_rejects_duplicate_active_foreach_id`
  - `test_structured_context_rejects_duplicate_active_alias`
  - `test_context_read_does_not_mutate_run_state`

  Assert the diagnostic category plus the offending frame/node ids. Snapshot
  `run.to_dict()` before the read-only test and assert it remains equal after
  deriving context.

- [x] **Step 6: Run and commit the focused model slice**

  Run:

  ```bash
  uv run pytest -q tests/core/test_structured_runtime_context.py
  uv run ruff check src/wf_core/run_state.py src/wf_core/context_contracts.py \
    src/wf_core/runtime/ops/frames.py \
    src/wf_core/runtime/scheduler.py tests/core/test_structured_runtime_context.py
  uv run basedpyright --level error src/wf_core/run_state.py \
    src/wf_core/runtime/ops/frames.py src/wf_core/runtime/scheduler.py
  ```

  Expected: all commands pass.

  ```bash
  git add src/wf_core/run_state.py src/wf_core/context_contracts.py \
    src/wf_core/runtime/ops/frames.py \
    src/wf_core/runtime/scheduler.py src/wf_core/__init__.py \
    tests/core/test_structured_runtime_context.py
  git commit -m "feat: derive structured foreach runtime context"
  ```

### Task 2: Use One Derived Context Across Every Runtime Consumer

**Files:**

- Modify: `src/wf_core/runtime/ops/nodes.py`
- Modify: `src/wf_core/runtime/ops/foreach.py`
- Modify: `src/wf_core/runtime/ops/handlers.py`
- Modify: `src/wf_core/runtime/subgraphs.py`
- Modify: `src/wf_core/runtime/ops/flow.py`
- Modify: `tests/core/test_structured_runtime_context.py`
- Modify: `tests/core/test_scheduler.py`

**Interfaces:**

- Consumes: `frame_context_view(run, frame)` from Task 1.
- Produces: identical context values for node input bindings, foreach `over`
  resolution, interrupt requests, subgraph input/output boundaries, workflow
  output projection, and Python node handlers.
- `RuntimeContext.metadata` remains a defensive copy of the selected frame's
  metadata; `RuntimeContext.foreach` is the canonical typed view.

- [x] **Step 1: Write failing end-to-end runtime tests**

  Extend `test_structured_runtime_context.py` with:

  - `test_nested_handler_receives_outer_and_inner_typed_entries`
  - `test_nested_graph_bindings_resolve_outer_and_inner_items`
  - `test_inner_completion_restores_outer_context`
  - `test_concurrent_items_receive_distinct_frame_and_lineage_context`
  - `test_nested_foreach_over_resolves_structured_outer_item_path`

  In the handler test, capture only stable fields:

  ```python
  def record(_payload: dict[str, object], ctx: RuntimeContext) -> dict[str, object]:
      seen.append(
          (
              tuple(ctx.foreach),
              ctx.foreach["customers"].item,
              ctx.foreach["orders"].item,
              ctx.foreach["orders"].index,
          )
      )
      return {"outcome": "ok", "output": {}}

  assert seen == [
      (("customers", "orders"), {"name": "Ada"}, {"sku": "A-17"}, 0)
  ]
  ```

  Build the binding test with canonical `InputPathBinding` values for
  `context.foreach.customers.item` and `context.foreach.orders.item`.

- [x] **Step 2: Run the end-to-end tests and observe innermost-only behavior**

  Run:

  ```bash
  uv run pytest -q tests/core/test_structured_runtime_context.py \
    tests/core/test_scheduler.py
  ```

  Expected: the new end-to-end tests fail because runtime consumers still use
  innermost frame-only context and handlers do not receive `.foreach`.

- [x] **Step 3: Update all graph-visible context call sites together**

  Replace every old call and verify with search:

  ```bash
  rg -n 'frame_context_values\(' \
    src/wf_core/runtime
  ```

  Expected after the edit: no matches. The required consumers are:

  - `_resolve_node_execution` in `runtime/ops/nodes.py`;
  - foreach source resolution in `runtime/ops/foreach.py`;
  - interrupt request construction in `runtime/ops/handlers.py`;
  - parent input and child output projection in `runtime/subgraphs.py`;
  - root workflow output projection in `runtime/ops/flow.py`.

  Root workflow output receives `frame_context_view(run, root_frame).graph`
  rather than an omitted context so standard root facts remain consistent.

- [x] **Step 4: Give Python handlers the same typed projection**

  In `_resolve_node_execution`, materialize the view once and pass its two
  projections to their consumers:

  ```python
  context_view = frame_context_view(run, frame)
  context_values = context_view.graph
  context = RuntimeContext(
      current_node_id=node.id,
      frame_id=frame.id,
      scope_id=frame.scope_id,
      lineage_id=frame.lineage_id,
      parent_lineage_id=frame.parent_lineage_id,
      prior_outcome=frame.prior_outcome,
      activated_incoming_edge=frame.activated_incoming_edge,
      metadata=dict(frame.metadata),
      foreach=context_view.foreach,
      platform=platform,
  )
  ```

  Resolve graph bindings against `context_view.graph`. Do not reconstruct
  `ForeachContext` from the graph-visible dictionary.

- [x] **Step 5: Update old focused tests to pass `RunState` explicitly**

  Replace direct frame-only context calls in scheduler/context tests with a run
  containing that frame. Keep assertions for existing standard and
  compatibility keys; add structured assertions rather than deleting old
  coverage.

- [x] **Step 6: Run and commit the runtime integration slice**

  Run:

  ```bash
  uv run pytest -q tests/core/test_structured_runtime_context.py \
    tests/core/test_scheduler.py tests/core/test_context_scopes.py \
    tests/core/test_concurrent_foreach.py tests/core/test_subgraph_step.py
  uv run ruff check src/wf_core/runtime tests/core/test_structured_runtime_context.py
  uv run basedpyright --level error src/wf_core/runtime
  ```

  Expected: all commands pass.

  ```bash
  git add src/wf_core/runtime/ops/nodes.py \
    src/wf_core/runtime/ops/foreach.py \
    src/wf_core/runtime/ops/handlers.py src/wf_core/runtime/subgraphs.py \
    src/wf_core/runtime/ops/flow.py \
    tests/core/test_structured_runtime_context.py tests/core/test_scheduler.py
  git commit -m "feat: expose structured context during execution"
  ```

### Task 3: Expose Literal Structured Paths From Foreach References

**Files:**

- Modify: `src/wf_core/models/steps.py`
- Modify: `tests/authoring/test_builder.py`
- Modify: `tests/authoring/test_subgraph.py`
- Modify: `tests/core/test_canonical_node_bindings.py`

**Interfaces:**

- Consumes: existing `ForeachNode` values returned by
  `WorkflowBuilder.foreach()` and `GraphSourcePath`.
- Produces two non-serialized computed properties:

  ```python
  @property
  def item(self) -> GraphSourcePath:
      return GraphSourcePath("context", ("foreach", self.id, "item"))

  @property
  def index(self) -> GraphSourcePath:
      return GraphSourcePath("context", ("foreach", self.id, "index"))
  ```

- The constructor uses literal tuple segments. It must not call
  `GraphSourcePath.context(self.id)` because that helper parses dots as path
  separators.

- [x] **Step 1: Write failing path and serialization tests**

  Add:

  - `test_foreach_reference_exposes_item_and_index_paths`
  - `test_foreach_reference_treats_dotted_id_as_one_literal_segment`
  - `test_foreach_computed_paths_are_not_serialized_fields`

  Assert:

  ```python
  each = builder.foreach(id="orders.v2", over=state_path("orders"), as_="order")

  assert each.item == GraphSourcePath(
      "context", ("foreach", "orders.v2", "item")
  )
  assert str(each.item) == 'context.foreach."orders.v2".item'
  assert str(each.index) == 'context.foreach."orders.v2".index'
  assert "item" not in each.model_dump(mode="json")
  assert "index" not in each.model_dump(mode="json")
  ```

- [x] **Step 2: Write failing node and subgraph binding tests**

  Use the computed ref directly in both authoring boundaries:

  ```python
  work = builder.use(
      capability,
      input=[input_from(each.item, "order")],
  )
  child = builder.subgraph(
      child_workflow,
      input=[input_from(each.item, "order")],
  )
  ```

  Assert both compiled bindings serialize their path as
  `context.foreach.orders.item`.

- [x] **Step 3: Implement only the two computed properties**

  Add the properties directly to `ForeachNode`. Do not create `ForeachRef`, a
  node-address type, or field-selection sugar beneath `.item`.

- [x] **Step 4: Run and commit the authoring slice**

  Run:

  ```bash
  uv run pytest -q tests/authoring/test_builder.py \
    tests/authoring/test_subgraph.py \
    tests/core/test_canonical_node_bindings.py \
    tests/core/test_path_values.py
  uv run ruff check src/wf_core/models/steps.py \
    tests/authoring/test_builder.py tests/authoring/test_subgraph.py
  uv run basedpyright --level error src/wf_core/models/steps.py
  ```

  Expected: all commands pass.

  ```bash
  git add src/wf_core/models/steps.py tests/authoring/test_builder.py \
    tests/authoring/test_subgraph.py tests/core/test_canonical_node_bindings.py
  git commit -m "feat: expose foreach context paths"
  ```

### Task 4: Generate Full Static Context Schemas And Authoring Inventory

**Files:**

- Modify: `src/wf_core/context_contracts.py`
- Modify: `src/wf_core/analysis/context_scopes.py`
- Modify: `src/wf_core/analysis/__init__.py`
- Modify: `src/wf_api/authoring_contracts.py`
- Modify: `tests/core/test_context_scopes.py`
- Modify: `tests/wf_api/test_authoring_contracts.py`

**Interfaces:**

- Consumes: the complete owner stack from
  `analyze_control_regions(workflow).owner_stack_by_node`.
- Produces the existing `context_fields_by_node(workflow)` function returning
  `dict[str, tuple[ContextFieldAvailability, ...]]`, now with a structured
  `foreach` contract and all active aliases.
- Produces:

  ```python
  def context_schema_for_node(workflow: Workflow, node_id: str) -> ContextSchema:
      """Return the complete graph-visible context object schema at one node."""


  def context_schemas_by_node(
      workflow: Workflow,
      *,
      control_regions: ControlRegionAnalysis | None = None,
  ) -> dict[str, ContextSchema]:
      """Return schemas for all unambiguous, reachable program locations."""


  def root_context_schema() -> ContextSchema:
      """Return standard fields plus an empty structured foreach map."""
  ```

- The schema for an inner body contains:

  ```python
  {
      "type": "object",
      "properties": {
          "foreach": {
              "type": "object",
              "properties": {
                  "customers": {
                      "type": "object",
                      "properties": {
                          "node_id": {"const": "customers"},
                          "activation_id": {"type": "string"},
                          "frame_id": {"type": "string"},
                          "scope_id": {"type": "string"},
                          "lineage_id": {"type": "string"},
                          "index": {"type": "integer"},
                          "item": customer_item_schema,
                      },
                  },
                  "orders": {
                      "type": "object",
                      "properties": {
                          "node_id": {"const": "orders"},
                          "activation_id": {"type": "string"},
                          "frame_id": {"type": "string"},
                          "scope_id": {"type": "string"},
                          "lineage_id": {"type": "string"},
                          "index": {"type": "integer"},
                          "item": order_item_schema,
                      },
                  },
              },
              "required": ["customers", "orders"],
              "additionalProperties": False,
          },
          "loop_item": order_item_schema,
          "loop_index": {"type": "integer"},
          "customer": customer_item_schema,
          "order": order_item_schema,
          # Existing standard execution fields remain.
      },
      "required": [
          "foreach",
          "loop_item",
          "loop_index",
          "customer",
          "order",
          "scope_id",
          "lineage_id",
      ],
      "additionalProperties": False,
  }
  ```

  Keep entry schemas inline unless a measured schema-size problem requires
  `$defs`; the observable field types and required paths are contractual.

- [x] **Step 1: Replace innermost-only tests with full-stack expectations**

  Update the existing nested test instead of adding contradictory coverage:

  ```python
  fields = _field_map(workflow, "inner_body")

  assert fields["outer_item"].schema == outer_item_schema
  assert fields["inner_item"].schema == inner_item_schema
  assert fields["loop_item"].schema == inner_item_schema
  foreach_schema = fields["foreach"].schema
  assert set(foreach_schema["properties"]) == {"outer", "inner"}
  assert foreach_schema["properties"]["outer"]["properties"]["item"] \
      == outer_item_schema
  assert foreach_schema["properties"]["inner"]["properties"]["index"] \
      == {"type": "integer"}
  ```

  Add `test_inner_completion_schema_restores_outer_structured_entry` and assert
  `after_inner` contains only the outer structured entry.

- [x] **Step 2: Run static analysis tests and confirm the old projection fails**

  Run:

  ```bash
  uv run pytest -q tests/core/test_context_scopes.py
  ```

  Expected: nested assertions fail because `_available_fields` uses only
  `stack[-1]`.

- [x] **Step 3: Build contracts from the whole owner stack**

  Change `_available_fields` to accept the complete `ForeachOwnerStack`. For
  every owner id, infer its item schema in the controller's own outer region,
  then build:

  - one required property beneath `foreach.<owner-id>`;
  - that entry's string identity fields, integer `index`, and inferred `item`;
  - every active configured alias;
  - `loop_item` and `loop_index` from the final owner only.

  The controller node itself uses its outer stack, so an inner controller may
  resolve `over=context.foreach.outer.item.children` without claiming its own
  not-yet-active entry.

- [x] **Step 4: Keep context schema construction reusable and bounded**

  Implement `context_schemas_by_node` by composing the returned contracts, not
  by running a second graph traversal. `context_schema_for_node` is the
  single-node convenience over that map. Preserve bounded local `$ref`
  resolution for item schemas. A conflicted or unreachable node has no
  generated per-node schema; callers treat that absence as invalid, not as
  root context.

- [x] **Step 5: Expose structured paths through authoring inventory**

  Add tests showing `context_path_options_for_node(workflow, "inner_body")`
  includes at least:

  ```python
  paths = {option["path"] for option in options}
  assert "context.foreach.customers.item" in paths
  assert "context.foreach.customers.index" in paths
  assert "context.foreach.orders.item" in paths
  assert "context.foreach.orders.index" in paths
  ```

  Reuse the existing bounded schema-navigation helper to emit nested context
  properties. Preserve `origin="runtime_context"`,
  `uses=["step_input"]`, availability, descriptions, and literal TOML path
  quoting. Do not hand-concatenate a dotted foreach id; format literal segments
  through `GraphSourcePath`.

- [x] **Step 6: Run and commit the static projection slice**

  Run:

  ```bash
  uv run pytest -q tests/core/test_context_scopes.py \
    tests/wf_api/test_authoring_contracts.py
  uv run ruff check src/wf_core/context_contracts.py \
    src/wf_core/analysis/context_scopes.py src/wf_api/authoring_contracts.py
  uv run basedpyright --level error src/wf_core/context_contracts.py \
    src/wf_core/analysis/context_scopes.py src/wf_api/authoring_contracts.py
  ```

  Expected: all commands pass.

  ```bash
  git add src/wf_core/context_contracts.py \
    src/wf_core/analysis/context_scopes.py src/wf_core/analysis/__init__.py \
    src/wf_api/authoring_contracts.py tests/core/test_context_scopes.py \
    tests/wf_api/test_authoring_contracts.py
  git commit -m "feat: describe structured foreach context"
  ```

### Task 5: Validate Context Paths And Alias Ownership From One Schema

**Files:**

- Create: `src/wf_core/validation/context_paths.py`
- Modify: `src/wf_core/validation/core.py`
- Modify: `src/wf_core/validation/issues.py`
- Modify: `src/wf_core/validation/steps.py`
- Create: `tests/core/test_structured_context_validation.py`
- Modify: `tests/core/test_context_scopes.py`

**Interfaces:**

- Consumes: `context_schemas_by_node(workflow, control_regions=analysis)` and
  one shared `ControlRegionAnalysis` from Tasks 1 and 4.
- Produces:

  ```python
  def validate_context_paths(
      workflow: Workflow,
      *,
      context_schemas: Mapping[str, ContextSchema],
      report: ValidationReport,
  ) -> None: ...
  ```

- Adds exact issue codes:

  ```python
  INVALID_CONTEXT_PATH = "invalid_context_path"
  FOREACH_CONTEXT_ALIAS_CONFLICT = "foreach_context_alias_conflict"
  ```

- Ordinary input/state validation remains where it is. The new pass owns the
  stronger, program-location-aware meaning of `context.*`.

- [x] **Step 1: Write failing context-path validation tests**

  Add:

  - `test_active_structured_foreach_item_path_is_valid`
  - `test_nested_body_can_read_outer_and_inner_entries`
  - `test_inactive_foreach_entry_is_rejected`
  - `test_missing_foreach_id_is_rejected`
  - `test_unknown_foreach_entry_field_is_rejected`
  - `test_unreachable_node_does_not_receive_root_context_fallback`
  - `test_workflow_output_cannot_read_completed_foreach_entry`

  For failures, assert both code and model location:

  ```python
  issue = next(
      issue
      for issue in report.errors
      if issue.code == ValidationIssueCode.INVALID_CONTEXT_PATH
  )
  assert issue.path == "nodes[3].input[0].path"
  assert "context.foreach.orders.item" in issue.message
  assert "work" in issue.message
  ```

- [x] **Step 2: Cover every model surface that can contain a graph path**

  Parameterize invalid `context.foreach.missing.item` references through:

  - `NodeUse.input` path bindings and nested input expressions;
  - `SubgraphNode.input`;
  - `ConditionNode.check` including nested conditions;
  - `ForeachNode.over`;
  - `InterruptNode.request` path bindings and expressions;
  - workflow output bindings.

  Each case must assert the exact model path reported by validation. This test
  prevents a future path-bearing model from accidentally retaining the current
  permissive `allow_context=True` behavior.

- [x] **Step 3: Add one bounded structural path walker**

  In `validation/context_paths.py`, use small typed walkers for conditions and
  input expressions:

  ```python
  def _expression_paths(
      expression: InputExpression,
      location: str,
  ) -> Iterator[tuple[str, GraphSourcePath]]:
      match expression:
          case PathExpression(path=path):
              yield location + ".path", path
          case ArrayExpression(items=items):
              for index, item in enumerate(items):
                  yield from _expression_paths(item, f"{location}.items[{index}]")
          case ObjectExpression(fields=fields):
              for name, item in fields.items():
                  yield from _expression_paths(item, f"{location}.fields.{name}")
          case LiteralExpression():
              return
  ```

  Mirror the same finite recursion for condition operands. Reuse these walkers
  for every step kind; do not duplicate context validation in each existing
  step validator.

- [x] **Step 4: Validate context paths against the consuming location**

  For paths whose root is `context`, walk their literal `parts` through the
  consuming node's generated schema. A path is valid only if every segment is
  a declared object property. The whole `context` object and
  `context.foreach` map remain readable; unknown dynamic keys do not.

  Workflow output uses `root_context_schema()`, which contains standard
  execution fields and an empty structured foreach map. This preserves
  `context.scope_id` while rejecting a completed iteration value.

  Change `validate_foreach_node` so context-rooted `over` paths reach this pass
  instead of being rejected by the old input/state-only check.

- [x] **Step 5: Write failing alias-collision tests**

  Add:

  - `test_foreach_alias_cannot_use_reserved_context_name`
  - `test_nested_active_foreach_aliases_must_be_unique`
  - `test_sibling_foreach_aliases_may_match_when_never_active_together`

  Reserved names are every standard context field plus `foreach`, `loop_item`,
  and `loop_index`. The nested failure points to the inner foreach's `as`
  field. Siblings in separate control regions may reuse an alias.

- [x] **Step 6: Share control-region analysis during validation**

  In `validate_workflow`, run `analyze_control_regions(workflow)` once. Feed the
  result to context schema construction, translate its issues as today, then
  call `validate_context_paths`. Avoid a second traversal hidden inside
  `context_fields_by_node`; add an optional internal `control_regions=` input if
  necessary while keeping the existing public call form valid.

- [x] **Step 7: Run and commit the validation slice**

  Run:

  ```bash
  uv run pytest -q tests/core/test_structured_context_validation.py \
    tests/core/test_context_scopes.py \
    tests/core/test_foreach_control_regions.py \
    tests/core/test_input_expressions.py tests/core/test_subgraph_step.py
  uv run ruff check src/wf_core/validation tests/core/test_structured_context_validation.py
  uv run basedpyright --level error src/wf_core/validation
  ```

  Expected: all commands pass.

  ```bash
  git add src/wf_core/validation/context_paths.py \
    src/wf_core/validation/core.py src/wf_core/validation/issues.py \
    src/wf_core/validation/steps.py \
    tests/core/test_structured_context_validation.py \
    tests/core/test_context_scopes.py
  git commit -m "feat: validate structured context paths"
  ```

### Task 6: Prove Resume And Subgraph Isolation, Then Publish The Contract

**Files:**

- Modify: `tests/core/test_structured_runtime_context.py`
- Modify: `tests/core/test_subgraph_step.py`
- Modify: `tests/core/test_concurrent_foreach_interrupts.py`
- Modify: `docs/wf_authoring_control_flow.md`
- Modify: `skills/wf-python/SKILL.md`
- Modify: `skills/wf-python/references/python-lifecycle.md`
- Modify: `docs/current_roadmap.md`
- Modify: `docs/superpowers/specs/2026-09-04-structured-runtime-context-design.md`
- Move after completion:
  `docs/superpowers/plans/2026-09-04-structured-runtime-context.md` to
  `docs/historical/superpowers/plans/2026-09-04-structured-runtime-context.md`

**Interfaces:**

- Consumes: the complete runtime, authoring, schema, and validation behavior
  from Tasks 1-5.
- Produces a public example that prefers declared input bindings via
  `foreach_ref.item`, while documenting `RuntimeContext.foreach` as the advanced
  handler escape hatch.

- [x] **Step 1: Write the interrupt-resume identity regression**

  Build `outer.loop -> inner.loop -> ask -> inner -> outer`, interrupt one
  inner item, serialize it with `dump_run_state`, restore it with
  `load_run_state`, and resume. Capture context before and after:

  ```python
  before = captured_before_interrupt[0]
  after = captured_after_resume[0]

  assert after["outer"].activation_id == before["outer"].activation_id
  assert after["inner"].activation_id == before["inner"].activation_id
  assert after["inner"].frame_id == before["inner"].frame_id
  assert after["inner"].lineage_id == before["inner"].lineage_id
  assert after["inner"].item == before["inner"].item
  ```

  Do not reuse the original in-memory `RunState`; the loaded value is the
  resume input so reconstruction is genuinely tested.

- [x] **Step 2: Write the complete subgraph scope-boundary test**

  Build a parent foreach and map `each.item` into a saved child subgraph's
  declared input. Give both parent and child a foreach node with id `orders`.
  Assert:

  ```python
  assert child_seen["input_order"] == {"sku": "A-17"}
  assert tuple(child_seen["context"].foreach) == ("orders",)
  assert child_seen["context"].foreach["orders"].item == "child-item"
  assert child_seen["context"].foreach["orders"].scope_id != parent_scope_id
  ```

  Also execute a child node before its own foreach and assert
  `child_ctx.foreach == {}`. This proves the caller entry was not inherited and
  the reused static id does not collide.

- [x] **Step 3: Run the persistence and scope pressure tests**

  Run:

  ```bash
  uv run pytest -q tests/core/test_structured_runtime_context.py \
    tests/core/test_subgraph_step.py tests/core/test_concurrent_foreach_interrupts.py
  ```

  Expected: all commands pass.

- [x] **Step 4: Document the preferred authoring and advanced Python forms**

  Add this shape to `docs/wf_authoring_control_flow.md` and the Python skill:

  ```python
  orders = graph.foreach(
      id="orders",
      over=state_path("orders"),
      as_="order",
  )
  charge = graph.use(
      charge_order,
      input=[input_from(orders.item, "order")],
  )
  graph.set_route(orders, "loop", charge)
  graph.set_route(charge, "ok", orders)
  ```

  State explicitly:

  - normal capabilities receive foreach values through declared inputs;
  - advanced handlers may inspect `ctx.foreach["orders"].index` and stable
    runtime identities;
  - child workflows do not inherit caller context and must receive input;
  - `loop_item`, `loop_index`, and aliases are migration conveniences.

- [x] **Step 5: Mark the implementation current and retire the live plan**

  Change the spec status from approved to implemented, replace the roadmap's
  proposed wording with a completed current-runtime statement, and move this
  fully checked plan under `docs/historical/superpowers/plans/`. Search for the
  old live-plan path and update any links:

  ```bash
  rg -n -F 'superpowers/plans/2026-09-04-structured-runtime-context.md' \
    docs skills
  ```

- [x] **Step 6: Run full verification**

  Run:

  ```bash
  uv run pytest -q
  uv run ruff check
  uv run ruff format --check
  uv run basedpyright --level error
  pnpx markdownlint-cli2 \
    'docs/superpowers/specs/2026-09-04-structured-runtime-context-design.md' \
    'docs/wf_authoring_control_flow.md' \
    'skills/wf-python/SKILL.md' \
    'skills/wf-python/references/python-lifecycle.md' \
    'docs/current_roadmap.md' \
    'docs/historical/superpowers/plans/2026-09-04-structured-runtime-context.md'
  git diff --check
  ```

  Expected: all commands pass. If the repository's known thesis-PDF baseline
  remains the only failure, record its exact failing test and verify it also
  fails at the plan's starting commit before treating it as baseline.

- [x] **Step 7: Commit the integration and documentation slice**

  Stage exact paths so the user's `docs/AGENTS.md` edit remains untouched:

  ```bash
  git add tests/core/test_structured_runtime_context.py \
    tests/core/test_subgraph_step.py \
    tests/core/test_concurrent_foreach_interrupts.py \
    docs/wf_authoring_control_flow.md skills/wf-python/SKILL.md \
    skills/wf-python/references/python-lifecycle.md docs/current_roadmap.md \
    docs/superpowers/specs/2026-09-04-structured-runtime-context-design.md \
    docs/historical/superpowers/plans/2026-09-04-structured-runtime-context.md
  git commit -m "docs: publish structured runtime context"
  ```

## Plan Self-Review Checklist

- Every required test group in the spec maps to Tasks 1-6.
- Runtime and static projections both consume the same static ids, item fields,
  and scope boundary.
- Validation covers every current model location that can embed a
  `GraphSourcePath`.
- Authoring properties and inventory both construct dotted ids as literal TOML
  segments.
- No task adds host runtime context, fork/gather behavior, step budgeting, or a
  new graph path root.
- The user's dirty `docs/AGENTS.md` is never staged.
