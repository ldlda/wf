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
3. `resume_workflow` loops until completion, interruption, or failure.
4. `step_workflow` resolves the active frame and dispatches by step type.
5. `runtime.ops.nodes` handles `NodeUse` input projection, handler invocation,
   output validation, and state writes.
6. `runtime.ops.flow` records trace entries and advances frames.
7. Completion projects workflow output from state and validates it.

Async execution shares the same runtime model. The async seam is handler
invocation; control-flow steps are still synchronous state transitions.

## Validation Flow

`wf_core.validation.core.validate_workflow` coordinates validation:

- collect unique node definitions
- validate each node/control-flow step
- validate start node existence
- validate edge sources, destinations, duplicate outcomes, and declared outcomes
- validate reachable nodes have all required outcome edges

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
- Foreach is still serial-only. Parallel foreach needs an explicit scheduling
  model, not just `asyncio.gather`. `ForeachNode.over` is typed as a
  `GraphSourcePath`, but execution is still serial.
- Interrupt lifecycle is still node-level and run-state-level. Long-lived
  external subscriptions or notification streams need a separate lifecycle
  design. Interrupt `request` and `resume` are canonical binding lists; nested
  child-workflow resume is still future work.
- Native subgraphs are not part of `wf_core` yet. The core `Step` model only
  includes node, condition, foreach, join, and interrupt steps; `Workflow` does
  not contain nested workflow/subgraph steps.
- Nested subgraph interruption is not first-class yet. The current
  `wf_authoring` subgraph helper wraps a child workflow as an ordinary node and
  validates the child output; it does not preserve a child run state that can
  interrupt, bubble to the parent, and later resume inside the child.
- Saved workflow-as-node execution with interrupts requires a core runtime
  upgrade: nested run state, child-frame trace preservation, interrupt bubbling
  with path metadata, and resume back into the child workflow.
- Frames are currently a serial execution stack. That is enough for root
  workflow execution, serial foreach, and node-level interrupts, but async
  parallel foreach and native subgraphs will stress the model. In particular,
  `RunState.current_frame_id` assumes one active cursor, `ExecutionFrame.metadata`
  is ad hoc, and subgraph frames will need explicit child workflow/deployment
  identity.
- Runtime errors are still ordinary exceptions plus failed run status. A richer
  error payload can be added later, but should be designed as part of trace/run
  state rather than scattered exceptions.
- Payload schema validation depends on JSON Schema semantics. If external tools
  emit unusual schema dialects, add compatibility tests before adapting them.
