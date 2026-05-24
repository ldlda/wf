# Native Subgraphs Design

Status: proposed

Native subgraphs should make a workflow usable as a workflow step without
collapsing the child run into one opaque Python node call. The current
`wf_authoring.subgraph_node` and `async_subgraph_node` helpers are useful
compatibility wrappers, but they hide the child trace, child frames, and child
interrupt lifecycle from `wf_core`.

This design defines the core runtime shape before implementation.

## Goals

- Add a first-class core step for running a child workflow inside a parent
  workflow.
- Preserve child trace information in a way that can be inspected without
  pretending child nodes are parent nodes.
- Bubble child interrupts to the parent run and resume back into the child.
- Reuse existing input/output binding, state write, reducer, and schema
  validation machinery.
- Keep saved workflow / deployment resolution outside `wf_core`.
- Leave room for future fork/gather and saved-workflow-as-node execution.

## Non-Goals

- Do not make arbitrary graph convergence or fork/gather in this pass.
- Do not dynamically load saved artifacts inside `wf_core`.
- Do not support multiple simultaneous child workflow activations from one
  subgraph node until the frame identity model is explicit.
- Do not hide async behavior behind sync helpers or `asyncio.run()`.
- Do not expose child internal state as parent state except through explicit
  output bindings.

## Current Wrapper Problem

The wrapper helpers convert a child workflow into a `NodeSpec` by calling
`execute_workflow` or `execute_workflow_async` from inside a node handler. That
means:

- the parent trace sees one node call
- the child trace is not embedded in the parent run state
- child interrupts cannot bubble cleanly into the parent
- resume cannot re-enter the child workflow
- child workflow identity/version is not part of the core graph

That is acceptable as a temporary compatibility path, but it is not native
subgraph execution.

## Model Shape

Add a core step model:

```python
class SubgraphNode(BaseModel):
    id: str
    type: Literal["subgraph"]
    workflow: WorkflowRef
    input_schema: SchemaRef
    output_schema: SchemaRef
    input: list[InputBinding] = Field(default_factory=list)
    output: list[OutputBinding] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=lambda: ["ok"])
```

Current implementation status: `wf_core` has a first placeholder
`SubgraphNode`, but `workflow` is still a plain string reference. The placeholder
also carries `input_schema` and `output_schema` so validation can check parent
bindings before native execution exists. Runtime execution intentionally raises
until a later slice adds child scope/frame execution.

`WorkflowRef` should be structural, not a dotted string parser:

```python
class WorkflowRef(BaseModel):
    source: str | None = None
    artifact_id: str | None = None
    version: int | None = None
    inline_name: str | None = None
```

The exact reference model can be smaller in v1, but it must not derive meaning
from formatted display names. Higher layers may resolve saved artifacts,
deployments, or local builders into an executable child workflow before the
core runtime starts.

`SubgraphNode.workflow` identifies the child workflow. It does not carry Python
handlers. Handler registries remain runtime dependencies, not graph schema.

## Runtime Dependencies

`wf_core` should execute only already-resolved child workflows. The platform or
authoring layer should prepare a runtime dependency object such as:

```python
SubgraphRuntime(
    workflows: Mapping[WorkflowRef, Workflow],
    registries: Mapping[WorkflowRef, Mapping[str, NodeHandler]],
    reducers: Mapping[WorkflowRef, Mapping[str, ReducerDefinition]],
)
```

The exact type can evolve, but the boundary matters:

- `wf_core` owns execution semantics.
- `wf_artifacts` owns saved workflow artifact models.
- `wf_mcp` / platform layers own source binding, auth, deployment resolution,
  and capability availability checks.

## Frame Model

A subgraph step creates a child frame tree owned by the parent subgraph frame.
The parent frame blocks until the child workflow completes, interrupts, or
fails.

Recommended frame metadata:

```python
SubgraphFrameMetadata(
    parent_step_id: str,
    workflow_ref: WorkflowRef,
    child_root_frame_id: str,
    child_run_id: str | None = None,
)
```

The child root frame should have:

- `kind="subgraph_root"` or another typed kind
- `parent_frame_id` set to the parent subgraph frame
- `node_id` set to the child workflow start node
- metadata identifying the child workflow

Child frames created by foreach inside the child workflow remain descendants of
the child root, not siblings of the parent graph.

Frame ids should be centrally constructed. The display format may be stringy for
now, but logic should not parse frame ids for workflow semantics.

## Child State

A child workflow has its own input, state, output, frames, ready queue, and trace
semantics.

For v1, the parent `RunState` can store child runtime data in typed subgraph
metadata rather than a fully nested `RunState` object. However, the design
should preserve this invariant:

> Child workflow state is not parent state.

Parent state changes only happen when the subgraph node completes and applies
its explicit `output` bindings.

This prevents child internal keys from leaking into the parent and keeps reducer
behavior local to the parent output boundary.

## Input and Output Mapping

Subgraph input uses the same `InputBinding` model as `NodeUse` and
`InterruptNode.request`:

- read from parent `input`, `state`, or `context`
- build the child workflow input payload
- validate against child workflow `input_schema`

Subgraph output uses the same `OutputBinding` model as `NodeUse`:

- read from child workflow output
- write to parent workflow state
- validate against parent state schema
- apply parent reducers only at the parent write boundary

Child workflow internal reducers are applied only inside child execution.

## Trace Shape

Do not flatten child trace entries into parent trace as if they were parent
nodes. That loses ownership and makes frame ids misleading.

Recommended trace representation:

- Parent trace gets a `subgraph` step entry for the parent step.
- Child trace entries keep their child frame ids and child node ids.
- Each child trace entry should be inspectable through parent run state with
  structural ownership fields, not a generic metadata bag.

Potential future shape:

```python
TraceEntry(
    scope_id="subgraph:run_child",
    lineage_id="subgraph:run_child:root",
    parent_trace_id="trace:root:run_child",
    frame_id="root:child_demo",
    node_id="classify",
    step_type="node",
    ...
)
```

Current `TraceEntry` has no scope, lineage, or parent-trace fields. The first
implementation can either add explicit optional fields or store child traces in
a separate typed child-trace structure and expose an inspection helper. The
design preference is structural fields or typed containers, not `metadata`
dictionaries and not overloaded `node_id` strings.

## Interrupt Bubbling

If a child frame reaches an `InterruptNode`:

1. The child frame becomes `INTERRUPTED`.
2. The parent subgraph frame remains `BLOCKED`.
3. The whole parent run status becomes `INTERRUPTED`.
4. `RunState.interrupt` points to the child interrupt, with enough route data
   to resume into the child.

The parent-facing interrupt request should include:

- parent frame id
- subgraph parent step id
- child workflow reference
- child frame id
- child interrupt node id
- interrupt kind
- payload

Current `InterruptRequest` only has `id`, `frame_id`, `node_id`, `kind`,
`payload`, and `resumable`. Native subgraphs need either:

- explicit structural route fields on `InterruptRequest`, such as `scope_id`,
  `lineage_id`, `parent_frame_id`, and `workflow_ref`, or
- a typed nested route object, such as `InterruptRoute`.

The preferred direction is explicit route structure. A generic metadata field
would recreate the ad hoc frame metadata problem, while string parsing is
exactly what the project has been moving away from.

## Resume Semantics

Resume should target the interrupted child frame, not the parent subgraph step.

On resume:

1. Validate that the outstanding interrupt belongs to a live child frame.
2. Apply the child interrupt `resume` bindings to child state.
3. Advance the child frame through its resume outcome.
4. Put the child frame at the front of the ready queue.
5. Continue scheduling.

The parent subgraph frame wakes only when the child workflow reaches a terminal
workflow output state.

This mirrors the current scheduler rule: ancestors blocked on child work do not
become runnable until the child boundary is actually done.

## Completion Semantics

When the child workflow completes:

1. Validate child workflow output against child output schema.
2. Apply the subgraph step `output` bindings from child output into parent
   state.
3. Record a parent `subgraph` trace entry with committed parent state changes.
4. Advance the parent subgraph frame through outcome `ok`.

For v1, a child workflow completion maps to one parent outcome: `ok`.
Later, saved workflow artifacts may declare multiple outcomes, but core
`Workflow.output_schema` is currently one output shape. Outcome-per-child-graph
needs a separate design if we want a subgraph to behave exactly like a
multi-outcome node.

## Failure Semantics

Runtime failure inside a child workflow fails the parent run unless future
policy explicitly handles child failures.

Do not turn child runtime failures into normal graph outcomes by default.
Normal outcomes are graph control flow; runtime failures are execution failures.

If a child node returns an `error` outcome and the child graph routes it, that is
ordinary child workflow behavior. If the child graph reaches a runtime error,
that is a run failure.

## Validation

`validate_workflow` should add subgraph checks:

- subgraph step has a resolvable child workflow reference in the runtime
  environment or validation context
- subgraph input bindings target child input paths
- subgraph output bindings source child output paths and target parent state
  paths
- `outcomes` are declared and outgoing edges match them
- native subgraphs cannot be recursive unless explicit cycle detection exists
- child workflow structural validation runs before parent execution

Pure model validation should still avoid executing or resolving external
artifacts. Runtime/deployment validation can perform stronger checks with a
resolved dependency set.

## Authoring Layer

`wf_authoring` should expose native subgraph use separately from wrapper-node
composition.

Possible API:

```python
child = parent.subgraph(
    workflow=child_builder.compile(),
    id="run_child",
    input=[input_from(state_path("request"), "request")],
    output=[output_to("summary", state_path("child_summary"))],
)
parent.connect(child, "ok", END)
```

For saved artifacts:

```python
child = parent.subgraph_ref(
    workflow=WorkflowCapabilityRef(artifact_id="demo_child", version=1),
    ...
)
```

`subgraph_node` and `async_subgraph_node` should remain compatibility helpers
until native subgraphs cover the same use cases. They should keep warning in
docs that they are wrapper nodes.

## MCP and Artifact Layer

Saved workflows should be reusable through the same native subgraph boundary,
but `wf_core` should not know how to load them.

The platform layer should:

- resolve workflow artifact refs to concrete workflows
- resolve capability/source bindings for that artifact
- provide node registries and reducers for the child workflow
- validate dependency availability before run
- expose clear diagnostics when a child workflow is unrunnable

This keeps auth, source availability, deployment binding, and MCP account
selection out of `wf_core`.

## Implementation Slices

### Slice 1: Non-Interrupting Inline Subgraph

- Add `SubgraphNode` to the core `Step` union.
- Add minimal `WorkflowRef` / inline child workflow dependency resolution.
- Execute child workflow to completion through child frames.
- Preserve child trace in a clearly-owned form.
- Apply child output to parent state through existing output binding code.
- Tests: child output mapping, child internal trace visibility, parent trace
  shape, child runtime failure fails parent.

### Slice 2: Interrupt Bubbling and Resume

- Extend `InterruptRequest` with explicit route structure.
- Bubble child interrupts to the parent run.
- Resume into the child frame.
- Tests: child interrupt pauses parent, resume continues child, parent completes,
  wrong resume target fails clearly.

### Slice 3: Saved Workflow References

- Add platform-level resolution for saved workflow artifacts.
- Validate dependencies and source bindings before execution.
- Tests: saved child workflow runs through a deployment binding, missing child
  artifact reports an unrunnable dependency.

### Slice 4: Outcome and Policy Expansion

- Decide whether subgraphs can expose multiple outcomes.
- Decide child failure handling policy, if any.
- Keep default behavior strict until the use case is clear.

## Risks

- Trace shape can become confusing if child entries are flattened too early.
- Interrupt resume can become string-parsing-heavy if `InterruptRequest` is not
  extended structurally.
- Storing nested run state directly may bloat persisted runs unless inspection
  APIs paginate trace/state detail.
- Recursive saved workflows need explicit cycle detection.
- Multiple child workflow dependency registries can make runtime dependencies
  complex; keep the boundary typed early.

## Open Questions

- Should child runtime state be stored as a nested `RunState`, or as typed child
  frame metadata plus shared parent `RunState.frames`?
- Should `TraceEntry` gain explicit `scope_id`, `lineage_id`, and parent-trace
  fields, or should child traces live in a separate inspectable structure?
- Is v1 allowed to reference only inline/compiled child workflows, or should it
  immediately accept artifact refs resolved by the platform?
- Should subgraph completion always emit `ok` initially, or should child
  workflow artifacts declare outcomes before native subgraphs ship?

## Recommendation

Start with Slice 1 as a non-interrupting inline subgraph. It gives us native
trace/frame semantics without taking on the hardest resume problem immediately.
Do not delete the wrapper-node helpers yet; use them as compatibility and
examples while native subgraphs mature.

Then implement Slice 2 before exposing saved workflows as broadly reusable child
graphs. Saved workflows without nested interrupt support would look reusable but
break at exactly the moment users need persistence and resume.
