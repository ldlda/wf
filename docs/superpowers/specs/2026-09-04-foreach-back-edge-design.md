# Foreach Back-Edge Design

## Status

Approved in conversation on 2026-09-04. This document specifies canonical
foreach body-return semantics. It does not include the separately planned
ergonomic Python DSL or authorize fork/gather implementation.

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

The parent frame owns the foreach controller and resumable barrier. Taking its
`loop` outcome creates an item frame whose metadata names that parent foreach.
The item frame begins at the `loop` edge target and follows ordinary outcome
edges.

Before ordinary frame advancement, runtime flow checks whether an item frame's
next target is its recorded owning foreach. If so, it records a foreach return:

```python
owner = foreach_item_owner(frame)
if owner is not None and next_node_id == owner.foreach_node_id:
    complete_item_frame(run, frame)
    wake_parent_for_child_progress(run, frame.id)
    return
```

This is an ownership check, not generic cycle detection. A root or unrelated
frame targeting the same foreach node enters it normally. An item frame
targeting a different foreach node also enters that node normally. Only a
return to the frame's recorded owner completes the current item.

The completed child records the owning foreach as its terminal graph location
for trace and checkpoint inspection. Existing barrier code remains responsible
for consuming its lineage-local writes, applying item-error policy, and waking
or completing the parent.

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

## Validation and Analysis

Validation performs structured abstract traversal over `(node_id,
foreach_owner_stack)` rather than merely looking for graph cycles:

- a `loop` edge from a foreach pushes that foreach onto the stack;
- an edge targeting the top owner is an item return and ends that child
  traversal;
- a `done` or `completed_with_errors` edge stays in the outer context;
- `END` or `EndNode` reached with a non-empty foreach stack is invalid;
- nested returns must target the immediate owner before an outer owner;
- traversal memoizes node plus owner stack so valid cycles terminate analysis.

A node may remain reachable in more than one execution context. Existing
context-contract analysis can report fields as conditional in that case. The
runtime must never infer edge meaning from graph history alone: frame ownership
always decides whether targeting a foreach is entry or return.

General unreachable-node detection is useful but is not part of this change.
It cannot establish foreach ownership because any node reached from a body is
connected by definition. General termination is also out of scope; finite
structural checks cannot prove that data-dependent cycles eventually exit.

## State and Failure Behavior

Back-edge return changes control representation, not state semantics.
Iteration writes remain buffered in the item lineage. Serial behavior and the
concurrent barrier continue to commit or merge those writes according to the
accepted concurrent-foreach ADR and declared reducers.

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

Focused tests must prove:

- serial item return wakes the parent and admits the next item;
- concurrent item returns preserve item identity and deterministic barrier
  commits;
- a child targeting its owner returns instead of executing the foreach node;
- a root frame targeting the same foreach enters it normally;
- an item frame can enter a different nested foreach;
- nested foreach restores the outer item context after inner completion;
- item paths to `END` and explicit `EndNode` fail validation;
- traces and serialized checkpoints retain an inspectable return location;
- existing `fail`, `skip`, `collect`, interrupt, reducer-conflict, sync, and
  async behavior remains intact after fixture migration.

## Deferred Work

- Ergonomic/context-manager Python authoring syntax.
- `break`, `continue` nodes, target ports, or iteration return dispositions.
- First-completed, first-error, first-success, cancellation, or race policies.
- General unreachable-node and non-terminating-cycle diagnostics.
- Fork/gather nodes and activation-token persistence.
- Nested serialized workflow blocks.
