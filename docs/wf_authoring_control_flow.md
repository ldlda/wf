# `wf_authoring` Control Flow

Use this document when choosing how to wire branches with
`WorkflowBuilder`.

The authoring API intentionally separates different control-flow ideas instead
of putting them all behind one overloaded method.

| Method | Use when | Creates condition nodes? |
| --- | --- | --- |
| `branch` | an existing step already returned an outcome label | no |
| `handle` | several source/outcome pairs should go to one target | no |
| `match` | one state/input/context value should equal one of several values | yes |
| `when` | one boolean expression chooses between two targets | yes |
| `choose` | ordered boolean expressions choose the first matching target | yes |

`route()` still exists only as deprecated compatibility sugar. New code should
use `match()` or `when()` directly.

## `branch`: Route Node Outcomes

Use `branch()` when a node already decides its own outcome.

```python
router = g.use(classify_message)
send = g.use(send_email)
skip = g.use(skip_email)
fail = g.use(runtime_error)

branches = g.branch(
    router,
    {
        "send": send,
        "skip": skip,
        "error": fail,
    },
)
```

This only adds edges:

```text
classify_message.send -> send_email
classify_message.skip -> skip_email
classify_message.error -> runtime_error
```

The return value is a `BranchResult`. It exposes the resolved source and lets
tests or later code retrieve targets by outcome:

```python
assert branches.source is router
assert branches["send"] is send
```

## `handle`: Shared Outcome Target

Use `handle()` when several steps should route the same kind of outcome to one
target.

```python
fail = g.use(runtime_error)

errors = g.handle(
    (lookup_user, "error"),
    (charge_card, "error"),
    (send_receipt, "error"),
    to=fail,
)
```

This is not a join and it does not wait for multiple branches. It only writes
edges:

```text
lookup_user.error -> fail
charge_card.error -> fail
send_receipt.error -> fail
```

The return value is a `HandleResult` with the shared target and the resolved
source/outcome pairs.

## `match`: Equality Dispatch

Use `match()` when one graph value chooses a target by equality.

```python
decision = g.match(
    state("status"),
    {
        "approved": approve,
        "rejected": reject,
        "pending": wait,
    },
    default=fail,
)
```

This lowers to an ordered chain of generated condition nodes:

```text
if state.status == "approved": approve
elif state.status == "rejected": reject
elif state.status == "pending": wait
else: fail
```

Condition ids are source-derived by default, such as `state_status`,
`state_status_2`, and so on. Pass `id="status_choice"` when stable generated
ids matter.

The return value is a `DecisionResult`:

```python
g.set_entry_point(decision.entry)
assert decision["approved"] is approve
assert decision["default"] is fail
```

## `when`: Boolean Dispatch

Use `when()` when one boolean expression chooses between two targets.

```python
decision = g.when(
    state("retry_count").lt(3),
    then=retry,
    otherwise=fail,
)
```

This lowers to one condition node with `true` and `false` edges.

The return value is also a `DecisionResult`:

```python
assert decision[True] is retry
assert decision[False] is fail
```

## `choose`: Ordered Predicate Chain

Use `choose()` when the graph should try several boolean expressions in order
and route to the first true target.

```python
decision = g.choose(
    (state("score").ge(90), gold),
    (state("score").ge(70), silver),
    (state("score").ge(50), bronze),
    default=fail,
    id="score_tier",
)
```

This lowers to:

```text
if state.score >= 90: gold
elif state.score >= 70: silver
elif state.score >= 50: bronze
else: fail
```

`choose()` is still one explicit call. Fluent or operator-heavy syntax can be
built on top later, but should delegate to this API rather than rebuilding edge
logic itself.

## Defaults

`match()`, `when()`, and `choose()` default their fallback path to the standard
`runtime_error` node. This makes missing cases fail loudly instead of silently
ending or continuing with unclear state.

Pass an explicit `default=` or `otherwise=` when the fallback is valid business
logic.

## `NodeSpec` Targets

`connect()`, `branch()`, `handle()`, `match()`, `when()`, and `choose()` accept
either existing step refs or `NodeSpec` objects as targets. Passing a `NodeSpec`
creates a fresh `use()` step with auto-mapping and an auto id.

Use existing step refs when the same node use should be shared. Pass a
`NodeSpec` when you want a new use at that point in the graph.

## Deprecated `route`

`route()` is a compatibility shim:

- `route(state("x"), {"a": step})` forwards to `match(...)`.
- `route(state("x").exists(), {True: step})` forwards to `when(...)`.

It emits a `DeprecationWarning` and should not appear in new examples.

## Drafts

Workflow drafts currently expose only explicit outcome routes:

```json
{
  "routes": {
    "classify": {
      "send": "send_email",
      "skip": "__end__"
    }
  }
}
```

Draft JSON does not yet have `match`, `when`, or `choose` sugar. Add that only
after the Python authoring surface stays stable enough to be mirrored.
