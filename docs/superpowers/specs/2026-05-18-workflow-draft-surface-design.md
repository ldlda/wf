# Workflow Draft Surface Design

## Goal

Define the first real MCP-facing workflow draft surface.

The current draft prototype mostly relabels the raw graph model. It proved that
draft validation, patching, and artifact creation are useful, but it is not yet a
deep authoring interface. This design replaces that prototype before it becomes
a compatibility burden.

The new draft surface should feel like `wf_authoring` over MCP:

- intent-level authoring
- stable patch targets
- explicit semantics
- compilation into the existing core workflow graph

## Scope

This pass covers:

1. keyed steps
2. compact outcome routes
3. verb-keyed step shapes such as `use`
4. saved capability/workflow references in `use`
5. stable JSON Patch paths
6. parity documentation against current `wf_authoring`

This pass does **not** cover:

- reverse-branch / shared outcome handlers
- draft `route` sugar
- a new `wf_authoring` fluent API
- true subgraph support
- new core graph semantics
- migration compatibility for the current draft prototype

The current prototype is not version `1`. It is disposable scaffolding.

## Design Principles

### Drafts Are Authoring Models

Drafts exist to make authoring easier. They are not another runtime model.

Compilation remains:

```text
WorkflowDraft
  -> draft-to-authoring adapter
  -> WorkflowBuilder
  -> core Workflow graph
  -> WorkflowArtifact
  -> WorkflowDeployment
```

The draft layer must not grow a second graph builder. Where semantics already
exist in `wf_authoring`, the adapter should call `WorkflowBuilder` rather than
reimplementing lowering directly against `wf_core`.

### JSON Should Optimize For LLM Edits

Array-index patch paths are weak:

```text
/steps/3/out/foo
```

Stable ids are better:

```text
/steps/echo/out/foo
```

The first real draft surface therefore uses keyed objects where identity matters.

### Reuse `wf_authoring` Semantics

The draft layer owns:

- JSON parsing
- stable-id keyed presentation
- patch-friendly document shape
- translation from capability references into authoring inputs

It should not own:

- graph construction rules
- graph construction rules
- duplicate edge-building machinery
- alternate workflow semantics

If the draft surface needs an authoring operation that `wf_authoring` does not
yet expose, prefer adding the missing authoring primitive first. Temporary gaps
must stay visibly thin and documented rather than becoming a parallel builder.

### Nice Syntax Must Still Be Explicit

Verb-keyed steps are allowed:

```json
{
  "use": "demo.echo_tool"
}
```

but no step kind is inferred.

Exactly one step-kind key must be present. Allowed step-kind keys are:

- `use`
- `foreach`
- `interrupt`
- `join`

Zero kind keys or multiple kind keys are validation errors.

## Draft Shape

```json
{
  "name": "echo_or_fail",
  "input_schema": {
    "type": "object",
    "properties": {
      "text": {
        "type": "string"
      }
    },
    "required": ["text"]
  },
  "state_schema": {
    "fields": {
      "echoed": {
        "type": "string"
      }
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "echoed": {
        "type": "string"
      }
    }
  },
  "start": "echo",
  "steps": {
    "echo": {
      "use": "demo.personal.echo_tool",
      "in": {
        "input.text": "text"
      },
      "out": {
        "echoed": "state.echoed"
      }
    },
    "missing_text": {
      "use": "wf.std.runtime_error",
      "in": {
        "message": "message"
      }
    }
  },
  "routes": {
    "echo": {
      "ok": "__end__",
      "error": "missing_text"
    },
    "missing_text": {
      "error": "__end__"
    }
  }
}
```

## Step Shapes

### `use`

Call one workflow capability.

```json
{
  "use": "demo.echo_tool",
  "in": {
    "input.text": "text"
  },
  "out": {
    "echoed": "state.echoed"
  },
  "desc": "optional",
  "retry": 2,
  "timeout_seconds": 30
}
```

`use` accepts any workflow capability ref:

- generated wrapper around an upstream MCP tool
- local source capability such as `wf.std.runtime_error`
- saved wrapper capability
- saved workflow capability once graph-as-node is available

The adapter lowers this through `WorkflowBuilder.use_ref(...)`, which exists for
named external capabilities that do not have a local Python callable-backed
`NodeSpec`.

### `foreach`

Keep the current concept, but key the step by id:

```json
{
  "foreach": {
    "over": "state.items",
    "as": "item",
    "mode": "serial",
    "on_item_error": "fail"
  }
}
```

This lowers to the current core `ForeachNode`.

### `interrupt`

```json
{
  "interrupt": {
    "kind": "input",
    "request": {
      "state.question": "question"
    },
    "resume": {
      "answer": "state.answer"
    },
    "outcomes": ["submitted"]
  }
}
```

This lowers to the current core `InterruptNode`.

### `join`

```json
{
  "join": {}
}
```

This lowers to the current core `JoinNode`.

`join` is not a reverse branch. It remains reserved for actual join/frame
semantics.

## Routes

Most ordinary edges should be authored through `routes`:

```json
"routes": {
  "echo": {
    "ok": "__end__",
    "error": "missing_text"
  }
}
```

The adapter passes these through the same authoring connection path that
produces normal core edges.

Outcome keys remain strings in JSON because they are wire values, but they
should not be treated as arbitrary text. When the referenced capability is
resolvable, draft validation should check route keys against that capability's
declared outcomes.

`routes` is intended for:

- outcome routing from `use`
- outgoing edges from authored graph steps
- ordinary terminal edges

The raw edge list remains compiler output, not the normal authoring surface.

## Patching

Stable ids make targeted patches readable:

```json
[
  {
    "op": "replace",
    "path": "/steps/echo/in/input.text",
    "value": "message"
  },
  {
    "op": "replace",
    "path": "/routes/echo/error",
    "value": "fallback"
  }
]
```

This is a core reason for keyed `steps`.

## Relationship To Current `wf_authoring`

| Python `wf_authoring` | MCP Draft Surface | Notes |
| --- | --- | --- |
| `g.use(spec, ...)` | `steps[id].use` | direct conceptual match |
| `g.connect(step, outcome, target)` | `routes[id][outcome] = target` | same graph meaning, better JSON |
| `g.branch(...)` | `routes[...]` | outcome routing is already compact in JSON |
| `route(...)` node | not in the first draft surface | defer until both front doors agree |
| explicit `start(...)` | `start` | direct match |
| `END` | `"__end__"` | keep wire token explicit |
| `NodeSpec` object | capability ref string | MCP cannot carry Python callable identity |
| builder object refs | stable string ids | JSON needs durable names |
| reducers | state schema reducer refs | same domain concept |
| Python callable nodes | not representable inline | must already be capabilities |
| fluent/cursor ergonomics | intentionally absent | good in Python, poor in patchable JSON |

## Later `wf_authoring` / Core Work

These are real ideas, but intentionally outside this pass.

### Shared Outcome Handlers

Useful reverse-branch sugar:

```text
node_a.error
node_b.error
node_c.unreachable
  -> runtime_error
```

This is not `join`. It is compressed declaration of several ordinary edges.

Possible later surfaces:

- Python: `g.on(...).to(...)`
- JSON: a dedicated `handlers` / `on` section

### `wf_authoring` v2

The MCP draft surface exposes friction in current Python authoring too:

- no fluent shared-handler helper
- no draft parity for route sugar yet
- likely room for better grouped declarations
- outcome names still travel as bare strings even though `NodeSpec` already
  declares them

Python authoring should eventually expose outcome helpers derived from the
`NodeSpec`, for example `spec.outcomes.ok` or equivalent. Those helpers should
come from the declared contract rather than duplicated `ClassVar` constants that
can drift from it.

That should be handled as its own pass, not smuggled into this MCP draft change.

### Core Follow-Ups

Potential later core work:

- true graph-as-node / subgraph support
- meaningful join semantics
- future START-edge support if `Workflow.start` changes

### Draft `route` Sugar

Current `wf_authoring.route()` already has a specific equality/boolean routing
surface. The draft layer should not invent a richer JSON route language ahead of
Python authoring. Add draft route sugar later, after the shape is chosen
deliberately for both front doors.

## Prototype Replacement

The current draft prototype should be deleted or replaced directly.

There is no compatibility guarantee because:

- it is not yet a released/versioned user contract
- it mostly relabels raw graph fields
- preserving it would make the first real authoring surface carry avoidable
  complexity from day one

## Testing Strategy

Tests should cover:

1. verb-key validation: exactly one step-kind key
2. keyed-step compilation into core nodes
3. `routes` compilation into core edges
4. saved capability refs passing through `use`
5. patching by stable ids
6. artifact creation from the new draft surface
7. diagnostics with stable draft paths
