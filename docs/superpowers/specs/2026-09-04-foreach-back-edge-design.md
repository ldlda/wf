# Foreach Back-Edge Design

## Status

Implemented on 2026-09-04. This document specifies canonical foreach
body-return semantics. It does not include the separately planned ergonomic
Python DSL or authorize fork/gather implementation.

## Purpose

Make the persisted workflow graph tell the truth about foreach control flow.
An iteration body returns to its owning `ForeachNode` through an ordinary
back-edge. It no longer routes to the workflow terminal `END` merely to make an
internal child frame finish.

The canonical shape is:

```text
a -> foreach
     foreach.loop -> body
     body.ok -> foreach
     foreach.done -> c
c -> END
```

This preserves a flat, inspectable control-flow graph. The runtime may continue
to implement each item with a child execution frame and a parent barrier, but
that scheduler detail no longer changes the visible meaning of `END`.

## Decisions

- `ForeachNode.loop` enters one iteration body.
- An edge from an iteration body to that iteration frame's owning
  `ForeachNode` returns the item to the controller.
- Returning to the owner completes the item frame and wakes the blocked parent
  foreach frame. The child does not execute the `ForeachNode` again.
- The parent foreach frame remains positioned at the controller. It admits the
  next serial or concurrent item, or emits `done`/`completed_with_errors` after
  its barrier finishes.
- Each dynamic entry into a foreach controller creates a fresh persisted
  foreach activation. Its barrier and item frames belong to that activation,
  so revisiting the same node use cannot reuse completed iteration state.
- A foreach item path may not target `END` or an explicit `EndNode`. Workflow
  terminal routes are outside an iteration body.
- `END` remains the workflow/subgraph terminal shorthand for workflow outcome
  `ok`; explicit `EndNode` remains the terminal for other workflow outcomes.
- Existing `fail`, `skip`, and `collect` item-error policies are unchanged.
- The core graph stays flat. Foreach does not gain a nested serialized body.
- The existing manual `WorkflowBuilder.foreach()` and `connect()` interface
  remains the only authoring surface in this slice; no new authoring interface
  is added.

## Runtime Semantics

The parent frame owns the foreach controller and resumable barrier. On first
entry for one visit, it creates a persisted foreach activation identity. Taking
its `loop` outcome creates an item frame whose metadata names both the owning
foreach node use and that activation. The item frame begins at the `loop` edge
target and follows ordinary outcome edges.

Before ordinary frame advancement, runtime flow checks whether an item frame's
next target is its recorded owning foreach. If so, it records a foreach return:

```python
owner = foreach_item_owner(frame)
if owner is not None and next_node_id == owner.foreach_node_id:
    complete_item_frame(run, frame, owner.activation_id)
    wake_parent_for_child_progress(run, frame.id)
    return
```

This is an ownership check, not generic cycle detection. A root or unrelated
frame targeting the same foreach node enters it normally. An item frame may
enter a different foreach node only when that node is not already in its active
owner stack; that is an ordinary nested foreach entry. Targeting a non-immediate
ancestor foreach is an invalid non-local return and must fail closed rather than
re-entering the ancestor controller. Only a return to the frame's immediate
recorded owner completes the current item.

The completed child records the owning foreach as its terminal graph location
for trace and checkpoint inspection. Existing barrier code remains responsible
for consuming its lineage-local writes, applying item-error policy, and waking
or completing the parent.

The activation identity is dynamic; it is separate from the static owner stack
of foreach node-use identifiers. It must remain stable across checkpoints and
interrupts. Barrier lookup, child-frame identity, item result ownership, and
wake-up checks include the activation identity. When the parent emits `done` or
`completed_with_errors`, it closes that activation before following the
outgoing edge. A later visit to the same foreach node use in the same parent
frame creates a new activation with fresh barrier state and child identities.
Completed frames and traces may remain as history without colliding with the
new visit.

Serial and concurrent modes share the same return meaning:

- serial mode has at most one live item frame and can admit the next item after
  its return;
- concurrent mode may receive several independently identified item returns,
  buffers them by item identity, and completes only after its existing barrier
  policy is satisfied.

## Nested Foreach

Nested foreach remains structured by frame ownership:

```text
outer.loop -> inner
inner.loop -> work
work -> inner
inner.done -> after_inner
after_inner -> outer
outer.done -> after_outer
```

The `work` frame returns only to `inner`, its immediate owner. Once the inner
controller emits `done`, execution resumes in the outer item frame. Returning
`after_inner -> outer` then completes the outer item.

Runtime metadata already carries the immediate foreach owner. Static context
analysis must evolve from a single active foreach identifier to an ownership
stack so inner completion restores the outer item context.

The owner stack describes control, not flat alias inheritance. This slice keeps
the current context contract: an inner item body exposes the innermost
`loop_item`, `loop_index`, and configured alias; after the inner foreach emits
`done`, the surrounding item frame exposes the outer values again. Inherited
structured foreach context remains separate future work.

## Static Control Regions and Dynamic Executions

A node use has exactly one static control region, represented by its foreach
owner stack:

```python
control_region(node_use) == ("outer_foreach", "inner_foreach")
```

That same node use may execute dynamically many times:

```text
same node use
├── item 0 frame / lineage
├── item 1 frame / lineage
└── item 2 frame / lineage
```

The invariant is therefore one static program location with many possible
dynamic executions. When one reusable capability is needed at several program
locations, authoring creates distinct node uses:

```python
before = builder.use(clean_document, id="clean_before")
each = builder.use(clean_document, id="clean_each")
after = builder.use(clean_document, id="clean_after")
```

Ordinary cycles remain valid when every node in the cycle belongs to the same
control region:

```text
a -> b
^    |
└────┘
```

Both nodes have the empty owner stack. This is an ordinary graph loop, like
`goto a`. Whether it exits is the author's responsibility. The runtime does not
currently promise a general step limit, so this design must not claim one.

A cycle within a foreach body is valid for the same reason when it has a
possible return to the owner:

```text
f.loop -> a -> b
          ^    |
          └────┘
b.exit -> f
```

Here both `a` and `b` belong to `("f",)`. The cycle may repeat before returning
the current iteration to `f`.

## Validation and Analysis

Validation performs structured abstract traversal over `(node_id,
foreach_owner_stack)` rather than merely looking for graph cycles:

- a `loop` edge from a foreach pushes that foreach onto the stack;
- an edge targeting the top owner is an item return and ends that child
  traversal;
- a `done` or `completed_with_errors` edge stays in the outer context;
- `END` or `EndNode` reached with a non-empty foreach stack is invalid;
- an edge targeting a non-top foreach already in the stack is an invalid
  non-local return;
- re-entering any active ancestor foreach as a nested controller is invalid;
- every node use has exactly one static foreach-owner stack. Reaching the same
  node use under another stack is an invalid control-region crossing;
- every node reached inside a foreach body has at least one structural path
  back to its immediate owner without leaving that owner context;
- traversal memoizes node plus owner stack so valid cycles terminate analysis.

A node use therefore belongs to one static control region, while remaining free
to execute in any number of dynamic frames, lineages, or items. When the same
capability is needed at two program locations, authoring creates two node uses
with distinct identifiers. Context-contract analysis reports one field set per
static region: fields are available when the region is inside a foreach body
and absent outside it. A node reached under two stacks is a region conflict
and receives no foreach fields rather than a conditional union.

The unique-owner rule rejects both ways of crossing a foreach boundary. An
outside edge into a body node reaches that node under both the outer and item
stacks. A body edge into an outside continuation reaches that continuation
under both the item and outer stacks. Both graphs are invalid rather than
silently annexing nodes into or out of the body.

The structural-return check is intentionally weaker than proving termination.
A data-dependent cycle is valid when some graph path can return to the immediate
owner; it may still run forever for particular inputs, just like an ordinary
program loop. A closed body cycle with no return path is invalid. The initially
ambiguous empty-body shape `foreach.loop -> foreach` is also invalid; an
iteration body must contain at least one distinct node use.

The runtime must never infer edge meaning from graph history alone: validated
static ownership establishes the legal regions, and current frame ownership
decides whether targeting a foreach is entry or immediate return.

Validation rejects every workflow node that is unreachable from the workflow
start. An unreachable node has no derivable control region, so accepting it
would contradict the one-region-per-node-use invariant and leave malformed
disconnected foreach structures unchecked. This applies to all workflow node
types, not only foreach bodies.

General termination remains out of scope. Finite structural checks cannot prove
that data-dependent cycles eventually exit. The narrower foreach rule only
requires a possible graph path from every body node back to its immediate
owner, because otherwise the enclosing controller is structurally unable to
finish that item.

The validation line is semantic ambiguity or structural impossibility. Reject
a graph when its control region cannot be derived uniquely, when it crosses a
structured foreach boundary illegally, or when an item has no possible return.
Accept a graph with one coherent meaning when runtime data alone determines
whether an available exit is taken. Non-termination in that accepted case is an
authoring error, not something static validation can honestly predict.

### Transition Classification

For every transition, validation applies these rules in order:

| Transition | Meaning |
| --- | --- |
| Source and target remain in the same region | Ordinary edge |
| Target is the immediate foreach owner | Item return |
| Target is a new, inactive foreach | Enter nested foreach |
| Target is an older ancestor owner | Invalid non-local return |
| Target already belongs to another region | Invalid region crossing |
| Target is `END` while inside a foreach | Invalid workflow termination |

### Pressure Cases

These examples are normative validation cases rather than illustrative syntax
alone.

#### External Entry Into a Body

```text
start.true -> f
start.false -> b
f.loop -> b
b -> f
```

`b` is reachable under both `()` and `("f",)`. Validation rejects the graph.
Use two distinct node uses when both executions are intentional.

#### Body Escape Into a Post-Loop Continuation

```text
f.loop -> b -> after
f.done ------> after
```

`after` is reachable under both `("f",)` and `()`, so validation rejects the
graph. The correct structure is:

```text
f.loop -> b -> f
f.done -> after
```

#### Legal Nested Return

```text
f1.loop -> f2
f2.loop -> work
work -> f2
f2.done -> tail
tail -> f1
f1.done -> after
```

The static owner stacks are:

```text
f2:    ("f1",)
work:  ("f1", "f2")
tail:  ("f1",)
after: ()
```

#### Skipping an Inner Owner

```text
f1.loop -> f2
f2.loop -> work
work -> f1
```

At `work`, the owner stack is `("f1", "f2")`. Returning directly to `f1`
would skip `f2`, so validation rejects the graph as a non-local return.

#### Entering a Sibling Body

```text
f1.loop -> b1 -> b2
f2.loop -------> b2
```

`b2` would belong to both `("f1",)` and `("f2",)`. Validation rejects the
graph.

#### Empty Body

```text
f.loop -> f
```

This is ambiguous because the item frame would begin on its owner. Validation
rejects it. An empty foreach has no useful item-level state or output effect.

#### Conditional Body Returns

```text
f.loop -> condition
condition.true -> work -> f
condition.false -------> f
```

This is valid. Both outcomes return the current item normally.

#### Body Cycle With No Possible Return

```text
f.loop -> a -> b -> a
```

Although every node has the correct region, the body has no path back to `f`.
Validation rejects this structurally stuck graph.

The following graph remains valid but may run forever for some runtime data:

```text
f.loop -> a
a.again -> a
a.done -> f
```

The graph contains a possible return. Runtime data decides whether it happens.

#### Unreachable Node or Component

```text
start -> work -> END

detached_a -> detached_b -> detached_a
```

Validation rejects both detached nodes. Starting a second abstract traversal at
an arbitrary default owner stack would invent a control region rather than
derive one from program entry.

#### Re-entering the Same Foreach

```text
again.true -> f
f.loop -> work -> f
f.done -> again
again.false -> END
```

This is valid. Every visit to `f` creates a fresh foreach activation, even when
the same parent frame visited `f` before. Each activation starts its barrier at
item zero and gives its child frames distinct identities. Runtime data decides
how many visits occur.

#### Subgraph Inside Foreach

```text
f.loop -> child_workflow -> f
```

This is valid. The child's own `END` completes its child workflow scope. The
parent `SubgraphNode` then returns to `f`, completing the foreach item:

```text
outer workflow scope
└── foreach item frame / lineage
    └── child workflow scope
```

#### Interrupt Inside Foreach

```text
f.loop -> ask_user -> work -> f
```

The item frame suspends while the parent foreach remains blocked. Resume must
restore the same frame, lineage, item identity, and owner stack.

#### Future Fork Inside Foreach

```text
f.loop -> fork -> left/right -> gather -> f
```

This design does not add fork/gather, but it fixes the future constraint. Both
branch activations inherit the foreach activation identity, item identity, and
static owner stack. They must gather before returning to `f`; neither branch
may independently return and complete the item.

## State and Failure Behavior

Back-edge return changes control representation, not state semantics.
Iteration writes remain buffered in the item lineage. Serial behavior and the
concurrent barrier continue to commit or merge those writes according to the
accepted concurrent-foreach ADR and declared reducers. One shared helper
routes every item write: it climbs through each serial owner to the scope
root, where it commits, or stops at the first concurrent item boundary,
where it buffers for that barrier to merge (the concurrent barrier finish
routes its combined patch through the same helper, so nested serial owners
cannot strand it). Parent cycles, missing parents, and orphaned item frames
fail closed. Buffered failure records must carry an error whose index and
frame match the enclosing result. The completed item is
registered with its barrier at the owner back-edge, keyed by the returning
frame rather than by whichever operation ran last, so node, subgraph, and
nested-control endings all count. A return naming a closed or superseded
activation fails closed instead of buffering into the wrong visit.

An ordinary node outcome named `error` remains domain control. An exception
remains a runtime item failure handled by `fail`, `skip`, or `collect`. Neither
kind of failure is encoded by the foreach back-edge itself.

## Migration

This is a clean canonical migration. Repository tests, examples, user-facing
docs, and generated fixtures change from:

```text
foreach.loop -> body
body -> END
```

to:

```text
foreach.loop -> body
body -> foreach
```

Configured local artifact stores contain no persisted foreach workflows at the
time of design. There is therefore no demonstrated persisted-data requirement
for keeping `body -> END` as a compatibility behavior. Validation rejects that
old shape rather than silently preserving two canonical return forms. If real
external persisted data is identified before implementation lands, it requires
an explicit migration decision rather than a permanent implicit shim.

Checkpoints from an in-progress old foreach execution are likewise not given a
speculative compatibility path without real data. The implementation must not
add parse-old behavior solely because repository fixtures previously used the
old topology.

## Testing

Every pressure case maps to at least one focused test. Invalid cases assert the
diagnostic category and offending node or edge path, not just `report.ok is
False`. Valid cases assert clean validation; cases with observable execution
semantics also run through the runtime.

| Case | Validation test | Runtime test |
| --- | --- | --- |
| Closed root cycle | Accept; author owns termination | Step; remain running |
| Root cycle with an exit | Accept | Take a finite loop and exit |
| Foreach cycle with a return | Accept | Repeat, then return the item |
| External body entry | Reject region conflict | N/A |
| Body escape | Reject region conflict | N/A |
| Legal nested return | Accept | Complete inner, restore outer, then return |
| Skip inner owner | Reject non-local return | Defensive invariant failure |
| Sibling-body entry | Reject region conflict | N/A |
| Empty `loop -> owner` body | Reject empty body | N/A |
| Conditional body returns | Accept | Exercise both return paths |
| Closed body cycle | Reject missing owner return | N/A |
| Unreachable nodes | Reject each node | N/A |
| Re-enter foreach after `done` | Accept | Fresh activation and children |
| Subgraph inside foreach | Accept | Child `END`, then item return (serial and concurrent) |
| Interrupt inside foreach | Accept | Resume the same item activation |
| Future fork in foreach | Deferred with fork/gather | Gather before return |

The future-fork row is an acceptance test owned by the later fork/gather slice;
this slice cannot instantiate a graph node type that does not yet exist. It
must remain visible here so that implementation cannot weaken foreach ownership
when fork/gather lands.

Additional focused tests must prove:

- serial item return wakes the parent and admits the next item;
- concurrent item returns preserve item identity and deterministic barrier
  commits;
- a child targeting its owner returns instead of executing the foreach node;
- a root frame targeting the same foreach enters it normally;
- an item frame can enter a different, inactive nested foreach;
- nested foreach restores the outer item context after inner completion;
- nested foreach keeps the existing innermost-only context contract inside the
  inner body;
- targeting a non-immediate ancestor foreach fails validation and at runtime;
- one node use reached under multiple owner stacks fails validation, covering
  both outside entry into a body and escape from a body to an outside node;
- ordinary cycles within one owner stack remain valid when they have a
  structural return path;
- a closed body cycle with no path back to its owner fails validation;
- an empty `loop` self-return fails validation;
- item paths to `END` and explicit `EndNode` fail validation;
- traces and serialized checkpoints retain an inspectable return location;
- foreach activation identity survives checkpoint serialization and interrupt;
- a completed activation cannot consume a later activation's item result or
  wake its parent;
- existing `fail`, `skip`, `collect`, interrupt, reducer-conflict, sync, and
  async behavior remains intact after fixture migration.

## Deferred Work

- Ergonomic/context-manager Python authoring syntax.
- `break`, `continue` nodes, target ports, or iteration return dispositions.
- First-completed, first-error, first-success, cancellation, or race policies.
- General non-terminating-cycle diagnostics beyond foreach-body returnability.
- Fork/gather nodes and activation-token persistence.
- Inherited structured context for all active foreach owners.
- Nested serialized workflow blocks.
