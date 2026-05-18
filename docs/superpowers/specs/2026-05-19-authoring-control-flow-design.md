# Authoring Control Flow Design

## Goal

Make `wf_authoring` control flow precise enough that future sugar layers can
delegate to it instead of reimplementing graph semantics.

The current problem is `route()`: it accepts both `PathExpr` and `Expr`, then
dispatches to two different behaviors. Both "route" something, but the caller
must understand different case semantics depending on the argument type.

That is too blurry for the core authoring API.

## Design Rule

Each public control-flow method should name one decision mechanism.

| Method | Decision source | Meaning |
| --- | --- | --- |
| `branch` | a node's declared outcome | wire outcome labels to targets |
| `match` | one graph value | compare that value against equality cases |
| `when` | one boolean condition | route through `true` / `false` |
| `choose` | ordered boolean conditions | first true condition wins |
| `handle` | several source/outcome pairs | send shared outcomes to one target |

Future fluent builders or operator sugar must call these methods rather than
constructing edges/conditions independently.

## Keep `branch`

`branch()` is already good:

```python
g.branch(tool, {
    "ok": next_step,
    "error": fail_step,
})
```

It has one clear meaning:

```text
route an existing node outcome
```

It should remain named `branch`. Alternatives such as `on_outcome` are more
literal but worse to use, and the current method does not suffer from the
semantic overloading that `route()` does.

## Replace `route`

### `match`

```python
g.match(
    state("status"),
    {
        "done": finish,
        "retry": retry,
    },
    default=fail,
)
```

Meaning:

```text
if state.status == "done": finish
elif state.status == "retry": retry
else: fail
```

This is the existing `PathExpr` branch of `route()`, renamed to say what it
actually does.

### `when`

```python
g.when(
    state("count").ge(1),
    then=positive,
    otherwise=zero,
)
```

Meaning:

```text
if state.count >= 1: positive
else: zero
```

This is the existing `Expr` branch of `route()`, made explicit and easier to
call correctly.

### `choose`

```python
g.choose(
    (state("x").gt(10), big),
    (state("y").exists(), has_y),
    default=fail,
)
```

Meaning:

```text
if state.x > 10: big
elif state.y exists: has_y
else: fail
```

This is an ordered predicate chain. It should lower through the same condition
construction/connect machinery as `when`, repeated for each clause.

`choose` is intentionally one call. Multiple-call fluent syntax can be built
later on top of it if it proves useful.

## Lowering

These methods may generate core condition nodes, but callers should not need to
know the exact node construction details to choose the right API.

Canonical lowering:

- `branch`
  - no new condition nodes
  - wires declared outcome strings from one source
- `match`
  - ordered equality-check condition chain
  - one generated condition per case
- `when`
  - one condition node
  - `true` and `false` edges
- `choose`
  - ordered condition chain
  - one generated condition per clause

Trace behavior should document that `match` and `choose` expand to generated
condition nodes.

## Outcome Names

Outcome names are strings at the core wire level, but Python authoring should
eventually avoid handwritten strings when a `NodeSpec` already declares them.

Future improvement:

```python
tool.outcomes.ok
tool.outcomes.error
```

derived from `NodeSpec.outcomes`, not duplicated constants that can drift from
the contract.

This is orthogonal to the control-flow rename, but it belongs in the same
authoring quality bar.

## Migration

`route()` should become deprecated compatibility sugar for one release window,
then be removed.

Recommended behavior during compatibility:

- mark `route()` with `@deprecated` so IDEs surface the replacement path
- `route(PathExpr, cases, ...)`
  - warns and forwards to `match(...)`
- `route(Expr, {True: a, False: b}, ...)`
  - warns and forwards to `when(...)`

The public docs should prefer only:

- `branch`
- `handle`
- `match`
- `when`
- `choose`

## Shared Outcome Handlers

`handle()` is the reverse-shaped companion to `branch()`: it connects several
source/outcome pairs to one shared target.

```python
g.handle(
    (lookup_user, "error"),
    (charge_card, "error"),
    to=fail,
)
```

Meaning:

```text
lookup_user.error -> fail
charge_card.error -> fail
```

It does not create a join, wait for multiple branches, or inspect state. It is
just outcome-edge sugar for the common "several things fail the same way" case.

## Not In This Pass

- fluent/cursor builder APIs
- operator overloading
- graph-as-node/subgraph support
- JSON draft `match` / `when` / `choose` shapes

Those later layers should depend on this API once it is stable.

## Testing

Tests should prove:

1. `branch` still wires outcome labels only
2. `match` reproduces current value-route behavior
3. `when` reproduces current boolean-route behavior
4. `choose` lowers ordered predicates correctly
5. `route` emits deprecation warnings while preserving old behavior
6. later sugar can delegate to these without needing private builder internals
