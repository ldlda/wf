# Reducer Capabilities Design

## Goal

Make state merging a single capability system instead of keeping a built-in
`merge_strategy` path beside future custom reducers.

## Decision

`StateField` should reference exactly one reducer:

```python
class StateField(BaseModel):
    type: str
    reducer: str = "wf.std.replace"
    trace: bool = True
    default: Any = None
```

The current built-ins become the first reducer library:

- `wf.std.replace`
- `wf.std.append`
- `wf.std.merge_object`

There is no separate `merge_strategy` field after this migration.

## Reducer Contract

Reducers are pure merge functions:

```text
current_value, incoming_value -> merged_value
```

They do not receive node ids, frame ids, paths, timestamps, or other execution
context. If behavior needs workflow context, it belongs in nodes or graph
structure instead.

Reducers are named and resolved at runtime from a registry. Workflow artifacts
store the reducer name, not a Python callable.

## Runtime Model

`wf_core` owns:

- a reducer callable protocol/type
- a reducer registry
- default registration of the three built-ins
- lookup and execution during state writes

Missing reducer names are execution errors. Reducer failures are wrapped with
the destination path so the failing state write is obvious.

## Authoring Model

`wf_authoring.state_field()` changes from:

```python
state_field(merge_strategy="append")
```

to:

```python
state_field(reducer="wf.std.append")
```

Nested authored state projection continues to flatten exact state paths and now
copies reducer references onto those flattened fields.

## Why Reducer-Only

Keeping both `merge_strategy` and `reducer` would create two concepts for the
same job. Turning the current built-ins into reducers gives us:

- one merge abstraction
- source-owned reusable behavior
- inspectable future reducer libraries
- a direct path to custom reducers such as `wf.std.max`,
  `wf.std.set_union`, or user-authored reducers

## Error Handling

- unknown reducer name: execution error before the state write commits
- reducer rejects a value shape: execution error from that reducer
- reducers remain pure, so there is no side-effect rollback problem

## Compatibility

This is an intentional model migration:

- core `StateField.merge_strategy` is removed
- authoring `state_field(merge_strategy=...)` is removed
- docs and tests migrate to reducer references

The project is still early enough that keeping both public shapes would create
more confusion than value.

## Testing

Tests should prove:

- `wf.std.replace` preserves current replace behavior
- `wf.std.append` preserves current append behavior
- `wf.std.merge_object` preserves current shallow object merge behavior
- exact nested state paths still select their own reducer
- unknown reducers fail clearly
- authoring metadata projects reducer names through nested state schemas
