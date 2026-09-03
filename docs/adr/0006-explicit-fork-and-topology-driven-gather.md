---
status: proposed
---

# Explicit Fork and Topology-Driven Gather

General graph concurrency will use explicit fork and gather steps. Outcomes
continue to select one transition; forks create several branch activations;
gathers rendezvous compatible activation tokens, merge their lineage-local
state patches, and create one continuation. This preserves topology-only edges
without making multiple matching edges silently mean broadcast.

## Context

The scheduler, ready queue, blocked frames, lineage-local state views, and
reducer-aware barrier commits already support concurrent foreach and native
subgraphs. They do not yet define general graph-level fork/gather. The existing
`JoinNode` is only a day-one marker: it immediately emits `done` and neither
waits nor merges. Renaming it would falsely preserve semantics it never had.

A cross-system semantics review supported keeping `NodeResult.output` separate
from its named domain `outcome`, keeping operational failure outside that
outcome namespace, and representing concurrency with explicit control steps.
The decisive design pressure came from partial and repeated gathers rather than
from output typing.

Consider a fork producing `a`, `b`, and `c`. One gather may merge `a+b` into
`d`, while a later gather merges `d+c`. The first gather must not know which
fork originally produced its inputs, and the second must accept the merged
`d` continuation like any other arrival. Inside a loop, it must combine
`a1+b1`, never `a1+b2`.

Conditional paths add another requirement. If one branch continues through
either `d` or `e`, a later gather may require `b AND (d OR e)`. Waiting for
every incoming edge would deadlock because only one alternative can arrive.

Cross-merging raises the same issue at larger scale. If one activated region
produces `b,c` and another produces `e,f`, independent gathers may consume
`b+e` and `c+f`. Correctness cannot depend on whether the scheduler happens to
run `b,e,c,f` or `c,f,b,e` first.

## Decision

The graph model distinguishes three control meanings:

- an ordinary node outcome selects exactly one continuation;
- a fork creates one child activation for every declared branch;
- a gather consumes compatible arrivals and creates one continuation.

A gather is independent of the construct that produced its inputs. It knows
its required local input slots from the graph and owns a merge policy. Edges
targeting a gather identify the slot they can satisfy. A gather requires every
slot, while several incoming edges may be alternatives for one slot. This gives
`b AND (d OR e)` without placing executable predicates on edges.

Runtime arrivals carry activation identity, lineage identity, and provenance.
The gather buckets arrivals by compatible activation context, accepts at most
one token per slot for an activation, waits until all slots are present, then
merges their lineage-local patches. Its result is a new continuation token that
preserves combined provenance and can enter another gather.

Lineage remains a virtual worldview: committed scope state plus writes visible
to one branch. Gathering several lineages does not require turning lineage
ancestry into a multi-parent graph. A partial gather can create an intermediate
lineage under the branches' common parent, retaining multi-input provenance in
activation-token metadata. A final gather can merge that lineage with remaining
siblings and resume the blocked parent continuation.

The first gather merge policy is fail-closed:

```python
class GatherMergePolicy:
    conflicts: Literal["error"] = "error"
```

State-field reducers remain the source of truth for legitimate concurrent
merges. The gather policy determines what happens when patches cannot be
merged; the initial behavior is to fail rather than choose a last writer.

Branch execution order may be deterministic in the synchronous runtime and
overlap in the asynchronous runtime. Both modes must produce equivalent graph
semantics. Scheduler order decides when compatible work progresses, never which
arrivals belong together.

The current `JoinNode` will not be silently upgraded. Before implementation we
will verify whether real persisted artifacts use it. With no real compatibility
obligation, remove it and introduce `GatherNode` cleanly. If persisted callers
exist, define an explicit migration rather than assigning barrier semantics to
old `join` payloads.

## Considered Options

**Multiple ordinary edges broadcast.** Rejected because edge cardinality would
silently change an outcome from selection to spawning and make ordinary graph
convergence ambiguous.

**Gather references its originating fork.** Rejected because partial gathers,
staged gathers, conditional paths, and cross-merges consume tokens based on
their local rendezvous contract, not one producer.

**Gather waits for every incoming edge.** Rejected because alternative paths
such as `d OR e` would require mutually exclusive arrivals. Named slots provide
AND across slots and OR within a slot.

**Lineage becomes a multi-parent DAG.** Not currently required. Merge provenance
belongs to activation tokens; an intermediate merged worldview can remain a
child of the compatible inputs' common lineage parent.

**Reuse or rename `JoinNode`.** Rejected as the default because the existing
node is a pass-through marker with no barrier contract.

## Consequences

- Edge identity gains gather-slot significance only when its target is a
  gather; ordinary edge semantics stay unchanged.
- Workflow validation must prove that every gather slot has an incoming edge,
  reject slots on non-gather targets, and preserve one successor per ordinary
  `(node, outcome)` pair.
- Checkpoints must persist pending gather arrivals and activation provenance so
  interruption/resume cannot mix loop iterations or subgraph invocations.
- Trace output must make fork activation, branch identity, gather waiting, and
  merged continuation inspectable without treating scheduler bookkeeping as
  ordinary node output.
- Fork/gather should generalize concurrent-foreach lineage and barrier helpers,
  not create a second state-patch system.
- Runtime branch failures remain execution failures in the first version. Skip,
  collect, race, first-success, cancellation, and timeout policies are deferred.

## Open Questions

- The exact serialized edge field and authoring name for a gather slot.
- The minimal activation-context and provenance representation that supports
  loops, nested forks, subgraphs, partial gathers, and cross-merges.
- Whether a gather resumes an existing blocked frame or creates a dedicated
  continuation frame in each topology shape.
- The trace representation for waiting and merging without excessive internal
  scheduler noise.
- Whether any real persisted artifact requires migration from `JoinNode`.

This ADR extends the lineage and barrier direction established by
[ADR-0002](0002-concurrent-foreach-policy-and-barrier-commits.md). It remains
proposed until the open runtime-state questions are resolved in the fork/gather
design specification.
