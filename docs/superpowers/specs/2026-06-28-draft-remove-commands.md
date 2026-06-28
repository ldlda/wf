# Draft Remove Commands Design

## Status

Planned.

## Problem

Draft workspaces now support focused constructive edits: create a draft, add a
capability step, bind inputs/outputs, branch routes, handle outcomes, and
compile. The missing mirror operation is safe removal. In challenge runs, agents
recover from bad edits by switching to raw-plan import or by writing JSON Patch
directly, because there is no simple command for undoing one bad draft element.

The immediate recovery cases are:

- A wrong route target was added and should be removed before re-routing.
- A wrong capability step was added and should be removed.
- A wrong input or output binding was added and should be removed.

Generic `wf draft patch` can already express these changes, but it forces agents
to know JSON Pointer paths and the exact draft document shape. These focused
commands keep the public surface aligned with the draft authoring model.

## Scope

Add three semantic remove operations:

```text
wf draft remove-route <workspace_id> --revision N --step STEP --outcome OUTCOME
wf draft remove-step <workspace_id> --revision N --step STEP
wf draft remove-binding <workspace_id> --revision N --step STEP --input LOCAL
wf draft remove-binding <workspace_id> --revision N --step STEP --output LOCAL
```

`remove-binding` may accept repeated `--input` and `--output` flags in one call.
The names refer to local capability fields:

- `--input message` removes input bindings whose local target is `message`.
- `--output content` removes output bindings whose local source is `content`.

## Semantics

Remove commands use the same revision-checked draft workspace mutation path as
`branch`, `handle`, `bind`, and `add-step`.

If the requested element exists:

- the edit is persisted,
- the workspace revision increments,
- the returned status may be `valid` or `invalid`,
- diagnostics are returned when the removal leaves dangling control-flow or
  schema/binding issues.

If the requested element does not exist:

- the operation is a no-op,
- the revision does not increment,
- the current workspace summary is returned.

This mirrors current no-op behavior in `branch`/`handle` and makes cleanup
commands idempotent enough for agents to retry safely.

## Step Removal Policy

`remove-step` removes:

- `steps[STEP]`
- `routes[STEP]`, if present

It does not remove inbound routes from other steps to `STEP`.

Reason: automatic inbound cleanup hides control-flow decisions. If removing a
step breaks the graph, validation should report `unknown_edge_destination` so
the agent can explicitly route the predecessor somewhere else with
`wf draft handle` or `wf draft branch`.

## Binding Removal Policy

`remove-binding` edits only the selected step's binding list:

- input mode removes entries from `/steps/{step}/input` where `target` equals
  the provided local field.
- output mode removes entries from `/steps/{step}/output` where `source` equals
  the provided local field.

It does not delete input/state/output schema fields. Schema deletion is a
separate problem because schema fields may still be referenced by other steps,
workflow outputs, or future edits. Validation diagnostics should surface unused
or broken paths; the first remove slice should not infer schema garbage
collection.

## Transport/API Shape

The API surface should add semantic methods on the draft authoring API:

```python
remove_draft_route(workspace_id, revision, step_id, outcome)
remove_draft_step(workspace_id, revision, step_id)
remove_draft_binding(workspace_id, revision, step_id, inputs, outputs)
```

Expose them through:

- `WorkflowApi` facade
- `WorkflowDraftSurface` protocol
- JSON-RPC methods under `workflow.draft_workspaces.*`
- RPC client mixin
- MCP workflow surface tools
- `wf draft` CLI commands

## Non-Goals

- Do not implement revision forking.
- Do not add a nested `wf draft step ...` namespace in this slice.
- Do not delete schema fields.
- Do not infer replacement routes.
- Do not make `remove-step` recursively delete dependent steps.
- Do not change strict `draft save` / `draft compile` boundaries.

## Acceptance Criteria

- `wf draft remove-route` removes an existing route and persists the resulting
  draft, even if validation becomes invalid.
- `wf draft remove-step` removes the step and its outgoing route map, leaves
  inbound routes untouched, and returns diagnostics if the graph now points at a
  missing step.
- `wf draft remove-binding --input` removes matching input bindings.
- `wf draft remove-binding --output` removes matching output bindings.
- Missing elements are no-op operations that do not advance revision.
- All commands are exposed over API, RPC, MCP, and CLI.
- Docs and skills explain that remove commands may return `status: invalid` and
  should be followed by `wf draft validate`.
