# lda.chat - Running Design Notes

## Related docs

- [docs/README.md](docs/README.md): documentation index; start here for current vs historical docs.
- [docs/authoring_sketch.md](docs/authoring_sketch.md): `wf_authoring` direction, including `@node`, `NodeSpec`, builder ergonomics, async registry seams, and subgraph-as-node.
- [docs/project_map.md](docs/project_map.md): current package map, entrypoints, examples, tests, and verification commands.
- [docs/current_roadmap.md](docs/current_roadmap.md): short active next-work list after the core type-shape cleanup.
- [docs/wf_core_architecture.md](docs/wf_core_architecture.md): current `wf_core` package boundaries, runtime flow, validation flow, and remaining cleanup seams.
- [docs/schema_validation.md](docs/schema_validation.md): current payload schema validation limits and intended validation seam.
- [docs/wf_mcp_plan.md](docs/wf_mcp_plan.md): `wf_mcp` direction as a namespaced MCP capability broker plus workflow build/run layer.
- [docs/wf_mcp_architecture.md](docs/wf_mcp_architecture.md): current `wf_mcp` package boundaries and dependency rules.
- [docs/historical/scratchpad.md](docs/historical/scratchpad.md): historical design notes that fed the current model.

## What is this

`lda.chat` is an AI agent that turns natural language requests into executable
workspace workflows. The LLM plans. The executor runs. Tools do the real work.

Target users are knowledge workers doing repetitive digital tasks like
collecting, summarizing, reporting, and monitoring without writing code.

---

## Thesis scope vs product

**Thesis:** prove the architecture end to end.

- a few working MCP tools
- LLM plans a workflow from natural language
- executor validates and runs it
- results come back in structured form

**Real product:** everything around it.

- broad MCP bridge layer
- per-tool auth handling
- tool registry / marketplace
- scheduling, monitoring, multi-user support

The thesis should demonstrate the core split cleanly, not solve the whole platform.

---

## Core architecture

```text
User request
  -> LLM planner
    -> Workflow JSON
      -> Deterministic executor
        -> MCP tools / subworkflows
          -> Shared workflow state
```

Principles:

- the LLM plans, but does not execute
- the executor executes, but does not think
- nodes do work
- edges are dumb routing

---

## Workflow model

A workflow is a directed graph with explicit schemas and explicit control flow.

```text
Workflow
  .name
  .input_schema
  .state_schema
  .output_schema
  .node_defs[]
  .start
  .nodes[]
  .edges[]
```

### Schema boundaries

- `input_schema` validates the run input once
- input is copied into mutable workflow state at run start
- `state_schema` defines typed workflow memory and merge behavior
- `output_schema` is derived from final state at the end
- internal state may contain values that never appear in output

This separation matters because a workflow can later be reused as a node.

### Reusable node definition

Nodes are defined independently from any one graph.

```text
NodeDef
  .name
  .input_schema
  .output_schema
  .outcomes[]         // ex: ["ok"], ["approved", "rejected"]
  .retry?
  .timeout_seconds?
```

Even a simple node still declares its outcomes explicitly.

### Node use inside a graph

Graph use-sites bind reusable nodes into graph state.

```text
NodeUse
  .id
  .type: "node"
  .node               // reference to NodeDef
  .desc?
  .input[]            // graph/value -> node-local input bindings
  .output[]           // node-local output -> graph state bindings
  .retry?             // optional override
  .timeout_seconds?   // optional override
```

The node does not get ambient access to all workflow state. It receives:

- the payload built by explicit `input` bindings
- runtime context

This keeps nodes reusable instead of graph-coupled.

Path bindings use structural paths in saved JSON:

```json
{
  "input": [
    {
      "target": {"root": "local", "parts": ["text"]},
      "path": {"root": "input", "parts": ["text"]}
    }
  ],
  "output": [
    {
      "source": {"root": "local", "parts": ["echoed"]},
      "target": {"root": "state", "parts": ["echoed"]}
    }
  ]
}
```

Legacy `in_map`, `input_values`, and `out_map` shapes remain parse-only
compatibility inputs. New authored or saved plans should write `input` and
`output`.

### Control-flow nodes

#### **ConditionNode**

```text
.id
.type: "condition"
.check
```

Conditions are structured JSON, not freeform code strings.

#### **ForeachNode**

```text
.id
.type: "foreach"
.over
.as
.mode               // serial | parallel
.on_item_error      // fail | collect | skip
```

#### **JoinNode**

```text
.id
.type: "join"
```

#### **InterruptNode**

```text
.id
.type: "interrupt"
.kind               // approval | text_input | choice | tool_auth | ...
.request[]          // graph/value -> public interrupt payload bindings
.resume[]           // resume payload -> graph state bindings
.outcomes[]         // ex: submitted, cancelled
```

Interrupt nodes are explicit graph nodes, not arbitrary line-level pauses inside Python code.
This keeps pause points visible, typed, traceable, and easier to validate.

### Edges

Routing is outcome-based.

```text
Edge
  .from
  .outcome
  .to
```

- source nodes declare which outcomes are possible
- edges map those outcomes to next nodes
- terminal routing can go to builtin `__end__`

Reaching an undeclared or unwired outcome is runtime failure.

---

## Node result contract

At the engine boundary, every node result should look uniform:

```text
NodeResult
  .outcome
  .output
  .meta?
  .extra?
```

Two channels stay separate:

- `outcome` is for control flow
- `output` is for typed business data

This lets richer nodes branch directly, while dumb MCP tools can still be adapted.
If a tool only returns data, a later `ConditionNode` can decide routing.

Extra undeclared returned keys:

- do not affect typed execution
- are preserved in trace
- are not visible to later nodes unless a future raw-trace access feature is added

---

## Condition model

The condition language should stay small and structured.

Supported v1 operators:

- `and`
- `or`
- `not`
- `eq`
- `ne`
- `gt`
- `lt`
- `exists`

Operands are paths or literals, such as:

- `state.summary_count`
- `context.retry_count`
- string, number, bool, null literals

This is less work than inventing a mini-language and generally easier for LLMs to emit reliably.

---

## State and merge semantics

State fields carry metadata, especially merge behavior.

```text
StateField
  .path
  .schema            // JSON Schema with reducer extension metadata
  .reducer           // wf.std.replace | wf.std.append | ...
```

Rules:

- merge behavior belongs to the state field, not the node
- declared fields get typed merge semantics
- undeclared keys behave like plain map entries
- concurrent writes to the same untyped key should fail
- concurrent writes to the same typed key should fail unless that field's merge strategy allows it

This keeps parallel and foreach behavior predictable.

---

## Execution semantics

Executor steps:

1. Validate workflow structure
2. Validate workflow input
3. Copy input into state
4. Start at the declared `start` node
5. Resolve node input snapshot from canonical `input` bindings
6. Execute node with mapped input plus runtime context
7. Validate typed node output
8. Commit mapped output into state
9. Route by returned outcome
10. Stop when routing reaches `__end__`
11. Derive and validate final output from state

Commit rules:

- no partial commit before success
- validation failure is node failure
- execution failure is not a normal business outcome

Runtime failure means things like:

- timeout
- transport error
- MCP failure
- invalid node output

Expected business branching should use declared outcomes instead.

### Trace

Each run should produce a structured trace.

At minimum, each trace entry should capture:

- node id
- step type
- resolved input snapshot
- returned outcome
- mapped output
- state changes committed
- next routed node

This keeps debugging honest as loops, retries, and richer tool adapters are added.

### Run State

Execution should return a structured run object, not just loose output maps.

At minimum, run state should track:

- workflow name
- run status
- original workflow input
- current mutable state
- final output when available
- current node id
- prior outcome
- activated incoming edge
- accumulated trace
- terminal error if execution failed

This gives the engine a clean path toward checkpointing, interrupt, and resume later.

Run state should also carry execution frames.

- v1 may only have a root workflow frame
- future `foreach` and subgraph execution should attach work to child frames
- interrupts should belong to a frame, not just to the run globally

Two useful execution entry points fall out of this:

- `step_workflow(...)` for one-node advancement
- `resume_workflow(...)` for continuing from an existing run state

That keeps the main execution loop small and makes future interrupt/re-invoke semantics easier to model.

### Interrupts

Interrupts should be graph-native and typed.

Preferred model:

1. A normal business node returns an outcome such as `needs_input`
2. The graph routes to an `InterruptNode`
3. The interrupt node produces a typed interrupt request
4. The runtime marks the run interrupted and surfaces the request externally
5. External code supplies a typed resume payload
6. The interrupt node maps resume payload back into state
7. The graph continues via a declared interrupt outcome such as `submitted` or `cancelled`

This is deliberately stricter than line-level dynamic interrupts inside arbitrary node code.

Why:

- pause points stay visible in the graph
- interrupt payloads can be validated by `kind`
- traces stay clean
- child graph interruption is easier to surface to parent graphs
- `foreach` and nested execution are less likely to become cursed

#### Interrupt request shape

At runtime, an interrupt should become a structured request attached to run state.

```text
InterruptRequest
  .id
  .node_id
  .kind
  .payload
  .resumable
```

Notes:

- `kind` chooses the interrupt contract
- `payload` is still JSON-like, but should be typed by `kind`
- v1 should allow only one active interrupt per run at a time
- the whole run pauses in v1, even if the interrupt originated inside a child graph or future foreach frame

#### Resume semantics

Resume should not jump back into the middle of arbitrary Python code.

Instead:

- resume data is delivered to the interrupt node
- the interrupt node maps resume fields back into state through explicit `resume` bindings
- graph routing continues normally from that node

This means the primary interrupt design is node-based, not line-based.

#### Child graph behavior

If a child graph interrupts:

- the parent run is considered interrupted in v1
- the parent only needs to know that the child graph node interrupted
- the child interrupt payload should still be surfaced to the external caller/UI

#### Foreach compatibility

Interrupt design must be compatible with future foreach support.

Bad designs to avoid:

- one anonymous global interrupt payload with no origin
- treating interrupt like a normal business outcome only
- resuming from arbitrary instruction pointers

Better design:

- interrupt belongs to a specific execution frame / node
- v1 may still pause the whole run
- future foreach support should record which iteration/frame produced the interrupt

### Retry

Default retry behavior should be strict.

- retry can be declared on the reusable node definition
- graph use-site can override it
- retries should reuse the original resolved input snapshot by default
- failfast is the default engine behavior

### Foreach

`foreach` should be explicit, not hidden.

- execution mode is graph-declared: `serial` or `parallel`
- item failure policy is graph-declared: `fail`, `collect`, or `skip`
- accumulation follows target state field merge strategy

### Join

Join is barrier-only.

- it does not do custom merge logic
- it waits only for branches actually activated in this run
- it should not wait for statically possible but never-taken branches

---

## Validation

Before execution, the validator should be able to check:

- workflow has a valid `start`
- node def names are unique
- node ids are unique
- every referenced node definition exists
- every edge source exists
- every edge destination exists or is `__end__`
- every edge outcome is declared by its source node
- each source + outcome pair is wired at most once
- every reachable outcome is wired
- every `input` binding target is a valid node-local path
- every `output` binding source exists in node output schema where schema detail is known
- every condition path references valid `input`, `state`, or `context`
- every `foreach.over` path references valid `input` or `state`

At runtime, the executor should still check:

- returned outcome is declared
- typed output matches schema
- merge conflicts
- required mapped outputs are present
- final output validates

---

## Registry and composition

A saved workflow can be registered as a reusable node.

That gives:

- workflow as function
- graph composition
- one consistent node contract whether the implementation is MCP-backed or workflow-backed

---

## Thesis demo direction

A good thesis demo is narrow but real, for example:

- use an external MCP such as Google Drive
- have the planner generate a workflow
- validate it against schema
- execute the workflow once end to end
- return a structured result or report

That proves the planner/executor/tool split without pretending to solve general automation.

---

## Open questions

- how strict should output derivation be: direct projection vs explicit final output mapping?
- what is the best trace model for raw extra node output?
- how should isolated pure-Python execution fit later: node type, tool backend, or separate functional API?
- how should retry policy interact with side-effecting tools that are not safely idempotent?

---

## Stack

- Backend: Python
- Validation and schema: Pydantic
- Tool execution: MCP
- Storage: SQLite or PostgreSQL
- Future isolated compute: restricted Python sandbox, possibly remote
