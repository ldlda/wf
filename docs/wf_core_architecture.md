# wf_core Architecture Boundaries

`wf_core` is the execution kernel. It should stay model-driven, explicit, and
boring: callers hand it a validated workflow model, a run state, and node
handlers; it returns an updated run state.

Higher-level ergonomics belong in `wf_authoring`. MCP discovery, tool proxying,
and user-facing control belong in `wf_mcp`.

## Packages

| Package / module | Responsibility |
| --- | --- |
| `wf_core.models` | Pydantic workflow schema package: schemas, condition expressions, executable steps, workflow graph, and node results. |
| `wf_core.run_state` | Serializable execution state: run status, frames, trace entries, interrupt requests, and runtime context. |
| `wf_core.runtime` | Public execution interface: execute, resume, and step in sync or async mode. |
| `wf_core.runtime.scheduler` | Internal frame scheduler: ready queue, selected cursor, frame creation, block/wake helpers, and typed foreach frame metadata. |
| `wf_core.runtime.ops` | Executor-only operations used behind `wf_core.runtime`: node execution, state writes, frame movement, foreach, interrupts, indexes, and schema checks. |
| `wf_core.validation` | Structural workflow validation split by validation concern. |
| `wf_core.conditions` | Runtime evaluation of condition expressions. |
| `wf_core.paths` | Graph path parsing, reading, existence checks, and nested state writes. |
| `wf_core.tokens` | Importable graph boundary tokens: `START` and `END`. |

The root `wf_core` package is the public facade for common callers. Internal
code should import from the concern package directly instead of relying on old
flat modules.

## Runtime Flow

1. `execute_workflow` creates a run state and delegates to resume.
2. `prepare_new_run` validates workflow shape and workflow input.
3. `resume_workflow` loops until completion, interruption, failure, or no
   schedulable frame.
4. `runtime.scheduler.select_next_frame` pops the next frame id from
   `RunState.ready_frame_ids`, marks that frame `RUNNING`, and updates
   compatibility cursor fields such as `current_frame_id`.
5. `step_workflow` resolves the selected frame and dispatches by step type.
6. A normal non-terminal step marks the same frame `PENDING` and puts it back at
   the end of the ready queue.
7. Terminal, blocked, interrupted, and failed frames are not re-enqueued.
8. `runtime.ops.nodes` handles `NodeUse` input projection, handler invocation,
   output validation, and state writes.
9. `runtime.ops.flow` records trace entries and advances frames.
10. Completion projects workflow output and validates it. Explicit
    `Workflow.output` bindings are used when present; older workflows fall back
    to same-name top-level state projection from `output_schema.properties`.

Async execution shares the same runtime model. The async seam is handler
invocation; control-flow steps are still synchronous state transitions.

## Scheduler Model

`RunState.frames` is the frame set: it contains lifecycle records for root,
foreach iteration, and future child frames. `RunState.ready_frame_ids` is the
explicit FIFO scheduling order. `current_frame_id` and `current_node_id` still
exist for compatibility and step-local convenience, but they are the selected
cursor, not the source of all runnable work.

Frame lifecycle rules:

- `PENDING` frames may be placed in the ready queue.
- Selecting a frame removes it from the ready queue and marks it `RUNNING`.
- A still-runnable frame is marked `PENDING` and re-enqueued after one step.
- `BLOCKED` frames are live but waiting on a typed block reason, currently child
  frame completion.
- `INTERRUPTED` frames are waiting on external resume input and pause the whole
  run.
- `COMPLETED` and `FAILED` frames are terminal for scheduling.

When the ready queue is empty, the scheduler classifies the run as completed,
interrupted, failed, or deadlocked. This replaces the older assumption that
`current_node_id == END` alone is enough to decide runtime completion.

## Foreach

Serial foreach creates one iteration child frame, records typed
`ForeachIterationMetadata`, blocks on that child, and enqueues the child. When
the child reaches `END`, `wake_parent_if_children_complete` wakes the blocked
parent so it can create the next iteration or emit `done`.

Concurrent foreach uses the same frame machinery but admits multiple item
lineages according to `ForeachConcurrentPolicy`. Each item lineage reads through
its own overlay, successful item patches are buffered, and the parent foreach
commits the barrier in item-index order. Sibling writes to the same state path
require a mergeable reducer on that exact path; ancestor/descendant sibling
writes are rejected until an explicit deep merge policy exists.

See `examples/raw_concurrent_foreach.py` for the canonical raw workflow shape and
`examples/authoring_concurrent_foreach.py` for the authoring-layer shape.

## Validation Flow

`wf_core.validation.core.validate_workflow` coordinates validation:

- collect unique node definitions
- validate each node/control-flow step
- validate start node existence
- validate edge sources, destinations, duplicate outcomes, and declared outcomes
- validate reachable nodes have all required outcome edges
- validate explicit `EndNode` outcomes against `Workflow.outcomes`

Validation reports multiple issues through `ValidationReport` instead of
raising at the first failure.

## Dependency Rules

- `wf_core` must not import `wf_authoring` or `wf_mcp`.
- `wf_core.models` and `wf_core.run_state` should stay mostly data-only.
- `wf_core.runtime` may import `runtime.ops`, but callers should not need to.
- `wf_core.runtime.ops` may use model, run state, paths, conditions, and errors.
- `wf_core.validation` may inspect model and path rules, but should not execute
  workflow behavior.
- `wf_core.__init__` should stay a curated public facade, not a dump of runtime
  internals.

## Schema Validation

Payload schema validation is intentionally isolated behind
`wf_core.runtime.ops.schemas.validate_payload_against_schema` and delegated to
the `jsonschema` library. See `docs/schema_validation.md` for the current
limits and intended adapter seam.

## What This Cleanup Does Not Solve Yet

- Node-local input/output bindings now support nested local paths and atomic
  state patch commits. The remaining mapping design notes for future reducer
  metadata are documented in
  [`core_state_mapping_and_merge.md`](core_state_mapping_and_merge.md).
- Foreach supports serial and concurrent execution. Concurrent foreach uses
  explicit policy, typed barrier state, lineage-aware patch commits, item error
  policy, and quiescent interrupt handling. Remaining gaps are higher-level
  graph constructs such as explicit fork/gather nodes and advanced conflict
  strategies beyond exact-path mergeable reducers.
- Interrupt lifecycle is still node-level and run-state-level. Long-lived
  external subscriptions or notification streams need a separate lifecycle
  design. Interrupt `request` and `resume` are canonical binding lists;
  prepared child workflows retain a typed internal interrupt route so resume
  continues in child scope while exposing the parent subgraph boundary to the
  caller.
- Native subgraphs use `SubgraphNode` plus caller-supplied `PreparedSubgraph`
  dependencies. A prepared local child executes through a child runtime scope
  and lineage; child output commits only through declared boundary bindings and
  the parent routes by the child's terminal workflow outcome. Saved/deployed
  workflow resolution remains outside core; the workflow platform can now
  supply saved child artifacts as prepared dependencies using one inherited
  deployment binding environment, including process-local pause/resume for
  child interrupts. For local authoring,
  `WorkflowBuilder.prepare_subgraph()`
  registers a child builder and `WorkflowBuilder.resume()` continues a paused
  prepared-child interrupt without requiring direct core-runtime calls.
- The current `wf_authoring` wrapper helpers still run child workflows as
  ordinary sync or async nodes and therefore do not preserve native child
  state or resumable interrupts. Native `SubgraphNode` plus
  `PreparedSubgraph` is the first-class path: prepared child interrupts now
  bubble to the parent run and resume inside the original child scope. See
  `examples/authoring_workflow_as_node.py` for the compatibility wrapper shape
  and `examples/authoring_native_subgraph.py` plus
  `examples/authoring_native_subgraph_interrupt.py` for the native path.
- Saved workflow-as-node execution with interrupts still requires a persisted
  platform resume surface. The current one-shot deployment tool rejects those
  artifacts before execution even though core prepared children can resume.
- Frames are no longer only a serial execution stack: the runtime has a ready
  queue, `BLOCKED` frame state, lineage isolation, barrier merge semantics, and
  pending child results for concurrent foreach. Native prepared subgraphs now
  use child-scope execution and typed routed child interruption; the platform
  resolves saved/deployed child artifacts before core starts and retains paused
  deployment runs in memory for resume.
  Concurrent foreach is the primary current use case for async concurrent node
  handler execution.
- Runtime errors are still ordinary exceptions plus failed run status. A richer
  error payload can be added later, but should be designed as part of trace/run
  state rather than scattered exceptions.
- Payload schema validation depends on JSON Schema semantics. If external tools
  emit unusual schema dialects, add compatibility tests before adapting them.
