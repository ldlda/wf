# lda.chat - Running Design Notes

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
  .in_map             // graph path -> node input field
  .out_map            // node output field -> graph state path
  .retry?             // optional override
  .timeout_seconds?   // optional override
```

The node does not get ambient access to all workflow state. It receives:

- mapped input
- runtime context

This keeps nodes reusable instead of graph-coupled.

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
  .type
  .merge_strategy     // replace | append | merge_object
  .trace?
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
5. Resolve node input snapshot from `in_map`
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
- every `in_map` destination exists in node input schema
- every `out_map` source exists in node output schema
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
