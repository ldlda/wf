# Structured Runtime Context Design

## Status

Implemented on 2026-09-04. This document specifies structured
foreach context inside one runtime scope. It complements the foreach back-edge
design without expanding that implementation slice.

## Purpose

Let nested foreach bodies read every active same-scope iteration explicitly and
with useful schemas:

```python
customer = ctx.foreach["customers"].item
order = ctx.foreach["orders"].item
```

The matching serialized graph paths are ordinary `GraphSourcePath` values:

```text
context.foreach.customers.item
context.foreach.orders.item
```

This replaces the current innermost-only runtime representation as the
canonical model. Existing `loop_item`, `loop_index`, and configured aliases
remain convenience fields for the innermost active foreach while callers move
to structured paths.

## Existing Path Model

The existing path types describe two different namespaces and should remain
separate:

| Type | Purpose | Whole value |
| --- | --- | --- |
| `GraphSourcePath` | Read the current workflow scope | Named root |
| `StatePath` | Write a state field | Not supported |
| `LocalPath` | Address one boundary payload | `.` |

The named graph roots are `input`, `state`, and `context`. `LocalPath` applies
to temporary node, subgraph-boundary, and workflow-output payloads.

`GraphSourcePath` does not gain an `output` root. A node result is a local
payload whose selected fields are committed through `OutputBinding` into
state. A workflow output is another local payload projected at completion from
`input`, `state`, or `context`. A graph-level `output` root would be ambiguous
about the producing node, dynamic activation, foreach item, and lineage.

Path serialization continues to use TOML key syntax. Bare identifiers stay
compact, while identifiers containing punctuation are quoted as one literal
segment:

```text
context.foreach.orders.item
context.foreach."orders.v2".item
```

The structural representation is authoritative:

```python
GraphSourcePath(
    root="context",
    parts=("foreach", "orders.v2", "item"),
)
```

Code constructing paths from node identifiers must append literal tuple
segments rather than reparsing identifiers as dotted expressions.

## Scope Boundary

Structured foreach context is local to one `RuntimeScope`.

- Nested foreach activations in the same workflow scope are inherited.
- A subgraph starts a new runtime scope and does not inherit its caller's
  `context.foreach` mapping.
- A caller passes required values through the subgraph's declared input
  bindings.
- A child workflow reads those values from `input`, not from its caller's
  context.
- Parent and child workflows may use the same foreach node identifier without
  collision.

For example:

```python
orders = parent.foreach(
    id="orders",
    over=state_path("orders"),
    as_="order",
)

process = parent.subgraph(
    workflow=child_workflow,
    input=[
        {
            "target": "order",
            "path": orders.item,
        }
    ],
)
```

Inside `child_workflow`, the value is `input.order`. This keeps a saved
subgraph reusable across call sites and preserves `RuntimeScope` as the state,
input, and context boundary for one workflow invocation.

## Context Shape

Python runtime context gains a typed entry for each active same-scope foreach:

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
    # Existing execution fields remain.
    foreach: Mapping[str, ForeachContext] = field(default_factory=dict)
```

The mapping key is the static `ForeachNode.id` within the current workflow
scope. It is not the configured alias and does not contain a dynamic suffix.
The value discloses the dynamic foreach activation, item frame, scope, and
lineage identities when advanced runtime code needs them.

The mapping contains active entries in outermost-to-innermost insertion order.
Lookup semantics do not depend on that order; the order exists for inspection
and deterministic serialization only. A valid control region cannot contain
the same foreach node identifier twice, so lookup by static id is unambiguous
within one scope.

The graph-visible context object has the equivalent JSON-compatible shape:

```json
{
  "foreach": {
    "customers": {
      "node_id": "customers",
      "activation_id": "act_1234567890123",
      "frame_id": "frame_1234567890123",
      "scope_id": "root",
      "lineage_id": "lineage_1234567890123",
      "index": 0,
      "item": {"name": "Ada"}
    },
    "orders": {
      "node_id": "orders",
      "activation_id": "act_2345678901234",
      "frame_id": "frame_2345678901234",
      "scope_id": "root",
      "lineage_id": "lineage_2345678901234",
      "index": 2,
      "item": {"sku": "A-17"}
    }
  },
  "loop_item": {"sku": "A-17"},
  "loop_index": 2,
  "customer": {"name": "Ada"},
  "order": {"sku": "A-17"}
}
```

`loop_item` and `loop_index` refer to the innermost active foreach. Configured
aliases for every active same-scope foreach are also available when their names
are unique. Validation rejects collisions between simultaneously active aliases
instead of allowing an inner foreach to shadow an outer value.

## Runtime Derivation

Structured context is derived from persisted frame ancestry rather than copied
as one flattened object into every frame.

For the selected frame, the runtime walks `parent_frame_id` while ancestors
remain in the same `scope_id`. Each foreach item frame contributes one typed
entry from its validated metadata. The collected entries are reversed into
outermost-to-innermost order and materialized into both `RuntimeContext.foreach`
and the JSON-compatible context mapping used by input bindings.

Traversal stops at a runtime-scope boundary even though a subgraph root frame
has a scheduling parent in the caller. Frame ancestry describes scheduling
ownership; it does not grant cross-scope context visibility.

The required persisted item metadata is:

```text
foreach node id
foreach activation id
item index
item value
configured alias
scope id
lineage id
```

`scope_id` and `lineage_id` may remain first-class `ExecutionFrame` fields
rather than being duplicated inside metadata. The structured context builder
must read typed metadata helpers and fail on malformed foreach item metadata;
corrupt persisted state is not equivalent to a missing context value.

## Static Context Analysis

Context analysis uses the full static foreach-owner stack established by the
foreach back-edge design:

```python
control_region(work_node) == ("customers", "orders")
```

At `work_node`, the generated context schema contains both entries. Each
`.item` schema is the item schema inferred from its owning foreach `over`
collection. `.index` is an integer, and identity fields are strings.

Validation rejects a structured foreach context path when:

- the referenced foreach id does not exist in the current workflow;
- the referenced foreach is not active in the consuming node's control region;
- the path asks for an unknown `ForeachContext` field;
- active configured aliases collide with one another or with reserved context
  fields; or
- a child workflow tries to address a caller's foreach context instead of
  receiving a declared input.

The analyzer must not represent context with a single active foreach id. It
assigns one owner stack per reachable node and derives all active entries from
that stack. Unreachable nodes remain validation errors rather than receiving a
fabricated root context.

## Authoring Surface

The `ForeachNode` returned by `WorkflowBuilder.foreach()` already acts as the
step reference. It gains non-serialized computed path properties instead of a
second wrapper hierarchy:

```python
orders = graph.foreach(
    id="orders",
    over=state_path("orders"),
    as_="order",
)

orders.item
# GraphSourcePath("context", ("foreach", "orders", "item"))

orders.index
# GraphSourcePath("context", ("foreach", "orders", "index"))
```

These values work anywhere an existing `GraphSourcePath` works:

```python
charge = graph.use(
    charge_order,
    input=[{"target": "order", "path": orders.item}],
)

graph.set_route(orders, "loop", charge)
graph.set_route(charge, "ok", orders)
```

The compiled binding remains ordinary protocol data:

```json
{
  "target": "order",
  "path": "context.foreach.orders.item"
}
```

No serialized `ForeachRef`, node-address type, or dynamic activation path is
introduced. Field-selection sugar beneath `.item` can be considered with the
broader ergonomic Python DSL; it is not required for structured context.

## Trace, Checkpoints, and Inspection

The resumable source of truth remains `RunState`: frames, scopes, lineages,
ready queue, barriers, interrupt route, and foreach activation metadata. The
runtime recreates structured context from that state after loading a
checkpoint.

Trace remains chronological history. It may expose the same stable `frame_id`,
`scope_id`, `lineage_id`, and foreach activation identities for inspection, but
runtime context must not be reconstructed from trace entries alone. The current
trace does not contain every live scheduler or barrier invariant required to
resume safely.

A future time-machine design may combine checkpoints with trace or richer
events. This design preserves stable identities for that work without choosing
event sourcing, checkpoint navigation, or rerun-from-step semantics now.

## Potential Host Runtime Context

A future capability interface may follow the useful shape of a generic
`Runtime[ContextT]`. This is a possible extension, not a requirement of the
structured foreach implementation:

```python
@dataclass(frozen=True, slots=True)
class AppRuntimeContext:
    account: AccountRef
    features: AccountFeatures
    app: RuntimeApp


async def process_order(
    order: Order,
    runtime: Runtime[AppRuntimeContext],
) -> Receipt:
    if runtime.context.features.semantic_search:
        search = await runtime.context.app.capability("search")
        return await search.run(order)

    ...
```

This host context is not the same namespace as the graph-visible
`context.foreach` object:

- `Runtime[ContextT].context` would contain host-provided dependencies and
  run-scoped configuration. Its values may be non-serializable and would not be
  addressable with `GraphSourcePath`.
- `Runtime.foreach` and graph `context.foreach` would remain engine-derived,
  JSON-compatible execution facts.
- Values that a saved workflow or child subgraph consumes declaratively still
  enter through workflow input, state, or explicit subgraph input bindings.

The likely package seam is:

```text
wf-client.App
    remote-facing handle used by a caller

wf-server
    authenticates the account and reconstructs execution dependencies

wf-api
    assembles the concrete AppRuntimeContext

wf-core
    defines Runtime[ContextT] and treats ContextT as opaque

wf-authoring
    has no dependency on accounts, clients, or server facilities
```

`AppRuntimeContext.app` should not automatically be the caller's literal
`wf-client.App` instance. Server execution may instead receive a narrow
`RuntimeApp` interface with the same convenient capability-discovery shape,
without requiring the server to call itself through its public HTTP transport.

The host context is reconstructed rather than persisted:

```text
persisted account and run identity
    -> wf-server reconstructs AppRuntimeContext
    -> wf-core executes with Runtime[AppRuntimeContext]
```

Database connections, credentials, clients, and feature evaluators therefore
remain outside serialized run state. Only stable identities needed to
reconstruct them survive a checkpoint or interrupt. Account features exposed
to capability code should represent the effective features for that execution;
authorization must still be enforced by the server rather than delegated to a
boolean in runtime context.

If this extension is adopted, it should replace the current untyped
`RuntimeContext.platform` escape hatch rather than layering another host-object
field beside it. Execution facts such as node, frame, scope, lineage, and
incoming transition should also be grouped separately from the generic host
context. Stores, stream writers, heartbeat controls, and other runtime
facilities remain YAGNI until concrete callers require them.

## Compatibility and Migration

The structured `foreach` field is additive. Existing `GraphSourcePath`,
`StatePath`, and `LocalPath` serialized forms remain unchanged.

The current convenience fields remain during this migration:

- `context.loop_item`;
- `context.loop_index`; and
- each active foreach's configured alias when unambiguous.

They are derived from the same structured entries so Python context, input
binding resolution, schema analysis, and trace inspection cannot disagree.
Future removal requires evidence that public callers and stored workflow
artifacts no longer use them; this design does not create an indefinite
compatibility promise.

## Required Tests

### Path and authoring

- `ForeachNode.item` and `.index` produce structural literal path segments.
- A foreach id containing a dot serializes as a quoted single segment.
- The computed properties do not appear as persisted `ForeachNode` fields.
- Foreach refs work in node and subgraph input bindings.
- `GraphSourcePath` still rejects an `output` root.

### Runtime context

- A single foreach exposes one structured entry.
- A nested same-scope body exposes outer and inner entries simultaneously.
- `loop_item` and `loop_index` select the innermost entry.
- Unique outer and inner aliases remain available together.
- Inner completion restores the outer entry and removes the inner entry.
- Concurrent item frames share one visit activation but receive distinct
  frame/lineage values.
- Interrupt resume recreates the same structured entries from persisted state.
- Malformed persisted foreach metadata fails closed.

### Scope isolation

- A child subgraph does not inherit the caller's `context.foreach` mapping.
- A parent can map a foreach item into child workflow input.
- Parent and child foreach nodes may reuse the same static id.
- Context ancestry traversal stops at the child runtime scope.

### Validation and schemas

- The item schema under each structured entry matches the foreach collection's
  item schema.
- Referencing an inactive, missing, or cross-scope foreach is rejected.
- Nested active alias collisions are rejected.
- The analyzer handles legal nested cycles without losing the owner stack.
- Unreachable nodes do not receive structured context schemas.

## Non-Goals

- Direct node-output dataflow or an `output` graph root.
- Cross-subgraph implicit context inheritance.
- A universal static node-address or dynamic execution-path type.
- Time-machine behavior or event-sourced resume.
- Fork/gather context, scheduling context, or run step limits.
- The generic host-provided `Runtime[ContextT]` extension described above.
- The broader doubly ergonomic Python DSL.
