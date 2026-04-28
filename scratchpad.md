# Graph as struct? workflow as struct

One graph is one input output

i decide to make edge dumb as shit. Nodes do all the work

struct needs to define in, out and ALL states. any output from a node is either writing to state or writing to a key of it.

metadata for states to hide in tracing

whatever language works

## plan

dumbass stupid plan fuhh ahh plan

```text
.in -> pydantic.create_model
.out -> pydantic.create_model
.state // langgraph partial update style
.steps[] // either nodes only or all everything (all everything seems cooler I LIKE ENUMS but it could be stupih)
.steps[]:
  .type IN node, edge
  node:
    .tool // ours, so do ts well
    .args
    .desc?
    .bind? // either update .state or .state[.bind]
  edge:
    .from
    .to
```

### next node

GENUINELY HOW do i convey next node?
do i pass next node in arg? args.next.{this cond, that cond}

function do need to know about where its run. Who called. So it can decide where it goes next. how? idk maybe a context struct that has the full next list from .edges[]?

or can it just reference any next node? but how? who tells it what node?

function 100% can select what node it wants to go next if supported. Since this is MY stuff, a function I make can do that.

### registry

past graph can turn into a function. so a graph is lowk same thing as a fn.

### input

how in the FUCK do i convey input!

this is how:

since input is state, this function kinda doesnt care about args. Args comes from state.

a function cares about certain keys (args) looking this shape, the least i can do is a remap on node {"specialized graph state key": "generic fn input key"}

same as output {"generic fn answer key": "specialized graph state key"}

### this is lowk constricted

But the counterpart is freeform code...

### more problems

batch? foreach?

control flow.

maybe special nodes that does control flow. Like ensure: something that only after all nodes connected to it ran does it run the nodes it connects to?

if bool = exist, maybe truth table node... if .state.key1 and .state.key2

## Alternative plan! god damn

that was looking like langgraphs Graph API, we could have Functional API being a taddddd simpler: functions imported and run in a sealed ahh box.

functional api is actually peam. its like async.

## inspo

my little use of langgraph
my nonexistent knowledge of openai fn schema
claude

---

## Spec direction v1

This is the cleaner version of the idea above. Raw notes stay above. This part is the engine contract.

### Core shape

One workflow has:

- `input` schema
- `state` schema
- `output` schema
- `nodes`
- `edges`
- explicit `start`
- builtin end node like `__end__`

Run flow is:

1. validate workflow structure
2. validate workflow input
3. copy input into state
4. start at declared start node
5. execute nodes and route by outcomes
6. derive final output from state

### Schema boundaries

- `input` is validated once at run start
- `state` is the mutable shared memory of the workflow
- `output` is derived from final state, not written directly during execution
- internal state can contain data that never appears in output
- state may be partially open, but only declared state fields get typed merge semantics

### Node definition

A reusable node/tool definition has:

- input schema
- output schema
- declared outcomes

Even if the only outcome is `ok`, it is still declared.

Graph use-sites bind a node explicitly:

- map graph state into node input
- map node typed output back into graph state
- wire each declared outcome to an edge or to `__end__`

Missing required mappings or missing reachable outcomes mean bad graph schema.

### Node result contract

Node result has two separate channels:

- control flow: `outcome`
- data: typed `output`

Routing is driven by `outcome`.
State update is driven by mapped `output`.

Extra undeclared returned keys are:

- ignored by typed execution semantics
- preserved in trace
- unavailable to later nodes unless there is some explicit future raw-trace access mechanism

This keeps dumb MCP tools usable without weakening typed graph execution.

### Failure model

- runtime failure is not a normal business outcome
- crashes, timeout, transport failure, validation failure are executor-level failure
- explicit error outcomes are allowed for expected business cases
- infallible nodes may only declare `ok`
- node execution either returns one final valid result or fails
- no partial state commit before success

### Commit and validation

- node input is resolved from state before execution
- node sees mapped input plus runtime context, not ambient full state
- node output is type-validated before commit
- if output validation fails, the node fails
- commit happens once, after successful validation

### Routing semantics

- edges are dumb
- nodes declare what outcomes can happen
- graph declares where each outcome can go
- reaching an undeclared outcome is runtime failure
- reaching an unwired outcome is runtime failure
- branching from node business outcomes is preferred over fake follow-up condition nodes

Condition nodes still exist for cases where:

- a dumb tool only returns data
- routing depends on shared state
- routing depends on runtime context

### Condition nodes

Condition logic should be structured JSON, not freeform string code.

Small v1 operator set:

- `and`
- `or`
- `not`
- `eq`
- `ne`
- `gt`
- `lt`
- `exists`

Operands should be paths and literals, such as:

- `state.foo`
- `context.retry_count`
- string/number/bool/null literals

### Runtime context

Nodes and condition evaluation can read runtime context.

Useful context fields:

- current node id
- retry count
- prior outcome
- loop item metadata
- activated incoming edge

### Merge semantics

Merge behavior belongs to declared state fields, not to nodes.

Minimal v1 merge strategies:

- `replace`
- `append`
- `merge_object`

Rules:

- declared state fields get typed merge behavior
- undeclared keys are plain map data
- undeclared keys default to simple replace only
- concurrent writes to the same untyped key should fail
- concurrent writes to the same typed key should fail unless the field merge strategy allows it

If fancy accumulation is needed, declare the field in state schema.

### Foreach semantics

`foreach` is explicit in the graph.

It should support:

- `mode = serial | parallel`
- `on_item_error = fail | collect | skip`

Each iteration gets:

- local item scope
- shared read access through mapped input
- explicit output mapping back into state

Iteration accumulation follows the target state field merge strategy.

### Join semantics

Join is barrier only.

- join does not do custom merge logic
- state should already hold the branch writes
- join waits only for activated incoming branches in this run
- join should not wait for statically possible but never-taken branches

### Retry semantics

Default retry behavior should be strict and deterministic.

- retry policy can exist on node definition and be overridden at graph use-site
- same for timeout later
- retries should reuse the original resolved input snapshot by default
- failfast is the default engine behavior
- more permissive collection behavior should be opt-in at graph level, especially in `foreach`

### Interrupt semantics

Interrupt should primarily be a graph node, not a random Python line.

Preferred shape:

- business node returns something like `needs_input`
- graph routes to an `InterruptNode`
- interrupt node raises/surfaces a typed interrupt request
- runtime marks run interrupted
- caller provides resume payload later
- interrupt node maps resumed payload back into state
- graph continues from declared next outcome

This is cleaner than loose line-level interrupt for this engine.

Why:

- graph can see interrupt points
- planner can reason about them
- trace is cleaner
- validation is easier
- child graphs and future foreach are less cursed

Interrupt node shape idea:

```text
InterruptNode
  .id
  .type: "interrupt"
  .kind
  .request_map       // input/state -> interrupt payload
  .out_map           // resume payload -> state
  .outcomes[]        // submitted, cancelled, ...
```

Interrupt request runtime shape:

```text
InterruptRequest
  .id
  .node_id
  .kind
  .payload
  .resumable
```

Rules:

- one active interrupt per run in v1
- whole run pauses in v1
- if child graph interrupts, parent sees child graph node interrupted
- external caller/UI should still receive the child interrupt payload
- resume should continue from interrupt node semantics, not arbitrary instruction pointer

Kinds are explicit and expandable:

- `approval`
- `text_input`
- `choice`
- `tool_auth`

Generic now, specialized later is easy because `kind` already exists.

### Reuse and composition

- workflow input/output separation makes a workflow reusable as a node
- graph output should look like normal node typed output
- a saved workflow can be registered and called like any other node/tool

### Concrete schema shape

The next model pass should aim for a shape like this.

Workflow:

```text
Workflow
  .name
  .input_schema
  .state_schema
  .output_schema
  .start
  .nodes[]
  .edges[]
```

Reusable node definition:

```text
NodeDef
  .name
  .input_schema
  .output_schema
  .outcomes[]         // ex: ["ok"], ["approved", "rejected"], ...
  .retry?             // default policy on the reusable definition
  .timeout?           // later
```

Graph use-site node:

```text
NodeUse
  .id
  .type: "node"
  .node               // reference to NodeDef / registry entry
  .desc?
  .in_map             // graph state/input path -> node input field
  .out_map            // node output field -> graph state path
  .retry?             // optional override
  .timeout?           // optional override
```

Condition node:

```text
ConditionNode
  .id
  .type: "condition"
  .check              // structured JSON condition tree
```

Foreach node:

```text
ForeachNode
  .id
  .type: "foreach"
  .over               // state path to iterable
  .as                 // loop variable alias
  .mode               // serial | parallel
  .on_item_error      // fail | collect | skip
```

Join node:

```text
JoinNode
  .id
  .type: "join"
```

Edge:

```text
Edge
  .from
  .outcome            // declared outcome name from source node
  .to
```

Builtin end:

```text
__end__
```

This keeps routing uniform:

- source node emits an outcome
- edge matches that outcome
- destination node runs next

### Node result envelope

At the engine boundary, every node should look like it returns one uniform envelope, even if a dumb MCP tool needs an adapter underneath.

```text
NodeResult
  .outcome            // one of the declared outcomes
  .output             // typed business payload
  .meta?              // reserved executor metadata later
  .extra?             // raw undeclared fields preserved in trace only
```

Practical notes:

- `outcome` is reserved for control flow
- `output` is reserved for typed data
- extra raw keys should not silently mix with typed output
- if an adapter wraps a dumb tool, it can translate raw tool return -> `NodeResult`

### Mapping rules

`in_map` and `out_map` are explicit and first-class.

`in_map`:

- source is graph `input`, `state`, or future `context` path
- destination is a declared node input field
- missing required source path is a graph/runtime error
- optional destination fields may be omitted

`out_map`:

- source is a declared node output field
- destination is a graph state path
- mapping to undeclared state keys is allowed, but loses typed merge behavior
- mapping a required output field that does not exist at runtime is node failure

No broad automatch for v1.

### State schema metadata

Declared state fields need metadata beyond plain type.

At minimum each declared field may carry:

```text
StateField
  .type
  .merge_strategy     // replace | append | merge_object
  .trace?             // whether to include in trace by default
```

Notes:

- merge behavior is owned by state field metadata
- trace visibility should also live here later
- undeclared keys behave like plain map entries with no special metadata

### Output derivation

Workflow output should be built explicitly from state, not by magic.

Two valid directions:

- `output_schema` is a projection from named state paths
- or `output_schema` is validated against a final explicit output mapping

Either way:

- output is not mutated during execution
- output validation happens at the end
- missing required output fields mean workflow failure

### Validation checklist

Before execution, validator should be able to check:

- workflow has a valid `start`
- all node ids are unique
- every referenced node definition exists
- every edge source exists
- every edge destination exists or is `__end__`
- every edge outcome is declared by its source node type
- every reachable declared outcome is wired
- every `in_map` destination exists in node input schema
- every `out_map` source exists in node output schema
- every condition node uses valid operators and operand shapes

At runtime, executor should still check:

- node returned a declared outcome
- node returned typed output matching its schema
- merge conflicts
- missing required mapped outputs
- final output validates

### Non-goals for v1

- recursive subgraphs
- broad implicit automatch for node input/output bindings
- ambient full-state access inside nodes
- freeform code conditions
- hidden magical merge behavior
