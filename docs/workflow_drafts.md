# Workflow Drafts

Workflow drafts are the preferred authoring format for LLM and human clients.

They sit above the raw `Workflow` model:

```text
WorkflowDraft -> RawWorkflowPlan -> WorkflowArtifact -> Deployment
```

The draft format is intentionally explicit and patchable. It avoids asking an
LLM client to write the full core model directly, while still compiling into the
same validated workflow plan used by the runtime.

Raw plans still exist as an escape hatch for advanced clients and compiler
outputs. New authoring flows should normally start with drafts.

## Why Drafts Exist

The raw workflow model is normalized for execution. That makes it precise, but
not always pleasant as an interactive authoring target.

Drafts optimize for:

- stable JSON shapes that are easy to inspect
- explicit step ids instead of implicit Python object references
- targeted fixes through JSON Patch
- a clear place to validate before saving
- preserving the existing raw workflow/runtime boundary

Drafts do not change workflow semantics. They compile into the same core plan
shape and then run through normal validation.

## Draft Shape

A minimal draft looks like this:

```json
{
  "name": "echo",
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
    },
    "required": ["echoed"]
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
    }
  },
  "routes": {
    "echo": {
      "ok": "__end__"
    }
  }
}
```

Important details:

- `steps` are keyed by stable ids so patches do not depend on array positions.
- `start` names one step id.
- `routes` map step outcomes to another step id or `__end__`.
- `capability` may be concrete during exploration, such as
  `demo.personal.echo_tool`.
- When saved with source bindings, concrete refs can be normalized to logical
  refs such as `demo.echo_tool`.

## Step Kinds

### `use`

Calls a workflow capability.

```json
{
  "use": "demo.personal.echo_tool",
  "in": {
    "input.text": "text"
  },
  "out": {
    "echoed": "state.echoed"
  }
}
```

Use this for normal node calls, including generated workflow wrappers around
MCP tools and local `wf.std` capabilities.

Generated MCP tool wrappers are intentionally naive. They normally expose both
`ok` and `error` outcomes, because MCP tool calls can report transport/provider
errors separately from useful output. Drafts should wire both outcomes:

```json
{
  "routes": {
    "call_tool": {
      "ok": "__end__",
      "error": "tool_error"
    }
  }
}
```

Use a wrapper node or `wf.std.runtime_error` for the `error` path. Do not leave
the generated `error` outcome dangling.

### `foreach`

Runs a child body over items.

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

Use `serial` unless the runtime explicitly supports a parallel async path for
the target workflow.

### `interrupt`

Declares an interrupting step.

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
    "outcomes": ["resumed", "cancelled"]
  }
}
```

Saved interrupting artifacts are still limited in the current execution
surface. If a deployment reports `interrupting_artifact_unsupported`, that is a
known platform limitation rather than a draft bug.

### `join`

Joins control flow.

```json
{
  "join": {}
}
```

### `when`

Creates one boolean decision step. The condition uses the same JSON shape as
`wf_core.models.conditions.Condition`.

```json
{
  "when": {
    "if": {
      "op": "ge",
      "left": {
        "path": "state.count"
      },
      "right": {
        "value": 1
      }
    },
    "then": "positive",
    "otherwise": "zero"
  }
}
```

The draft adapter lowers this through `WorkflowBuilder.when()`. The draft step
id becomes the generated condition entry id, so other routes can target it.

### `match`

Matches one graph value against ordered equality cases.

```json
{
  "match": {
    "value": "state.status",
    "cases": [
      {
        "equals": "ready",
        "then": "run"
      },
      {
        "equals": "waiting",
        "then": "pause"
      }
    ],
    "default": "__end__"
  }
}
```

Cases are a list rather than a JSON object so values such as `1`, `"1"`, and
`true` are not silently coerced into object keys. The draft adapter lowers this
through `WorkflowBuilder.match()`.

### `choose`

Creates an ordered first-true decision chain.

```json
{
  "choose": {
    "clauses": [
      {
        "if": {
          "op": "gt",
          "left": {
            "path": "state.score"
          },
          "right": {
            "value": 80
          }
        },
        "then": "high"
      },
      {
        "if": {
          "op": "exists",
          "path": "state.fallback"
        },
        "then": "fallback"
      }
    ],
    "default": "__end__"
  }
}
```

`choose` lowers through `WorkflowBuilder.choose()` and expands to generated
condition nodes. `match`, `when`, and `choose` replace the deprecated `route()`
concept for draft JSON; there is intentionally no draft `route` step kind.

## Draft Tools

The workflow MCP surface exposes these draft tools:

| Tool | Purpose |
| --- | --- |
| `wf.workflow.validate_draft` | Validate draft shape and compiled workflow without saving. |
| `wf.workflow.compile_draft` | Return the compiled raw plan plus dependency summaries. |
| `wf.workflow.patch_draft` | Apply RFC 6902 JSON Patch and validate the patched draft. |
| `wf.workflow.create_artifact_from_draft` | Compile, normalize, and save a workflow artifact. |

Use `validate_draft` before saving. Use `patch_draft` when an LLM client needs a
small targeted correction instead of rewriting the whole workflow.

## Draft Workspaces

Stateless draft tools require the caller to resend the whole draft. Draft
workspaces are the preferred LLM authoring flow when a client will patch a
workflow over several turns.

The workspace flow is:

1. `wf.workflow.create_minimal_draft_workspace`
2. `wf.workflow.get_draft_workspace`
3. `wf.workflow.patch_draft_workspace`
4. repeat get/patch until valid
5. `wf.workflow.create_artifact_from_workspace`

Workspaces are mutable and revisioned. Artifacts are immutable and versioned.
Patch calls must include the current `revision`; stale revisions return
`revision_conflict` and do not mutate the workspace.

`create_minimal_draft_workspace` is intentionally only a bootstrapper. It wires
an `error` outcome for naive MCP wrappers only when `error_message_source` is
provided or a state path can be derived from `output_map`. Provider-specific
error envelopes still belong in saved wrapper artifacts or follow-up patches.

In MCP Inspector, workspace mutation tools accept a single `request` object.
This is deliberate: the request object carries descriptions and validation for
the authoring envelope while raw JSON Schema fields remain plain JSON objects.

## Patching Drafts

`patch_draft` accepts JSON Patch operations.

Example:

```json
[
  {
    "op": "replace",
    "path": "/steps/echo/in/input.text",
    "value": "message"
  },
  {
    "op": "add",
    "path": "/routes/echo/error",
    "value": "__end__"
  }
]
```

Patch the draft, not the compiled raw plan. The raw plan is an implementation
boundary and may be harder for an LLM client to repair correctly.

## Saving And Running

The normal path is:

```text
wf.workflow.validate_draft
wf.workflow.create_artifact_from_draft
wf.workflow.save_deployment
wf.workflow.validate_deployment
wf.workflow.run_deployment
```

`create_artifact_from_draft` may return suggested bindings for local system
sources such as:

```json
{
  "wf.std": "wf.std",
  "wf.mcp": "wf.mcp"
}
```

Keep those explicit when deployment validation reports `binding_missing`.

## Raw Plan Escape Hatch

Use `wf.workflow.create_artifact_from_plan` only when the caller already has a
compiled raw workflow plan or is intentionally bypassing the draft layer.

For normal interactive authoring, prefer:

```text
draft -> validate -> patch if needed -> create artifact from draft
```

That keeps errors local and gives the author a smaller object to reason about.

## Read Next

- [`wf_mcp_operator_manual.md`](wf_mcp_operator_manual.md) for the MCP-facing
  tool family map
- [`wf_mcp_end_to_end_runbook.md`](wf_mcp_end_to_end_runbook.md) for a complete
  connection-to-run example
- [`workflow_capabilities.md`](workflow_capabilities.md) for raw capability
  versus workflow capability
- [`workflow_artifacts.md`](workflow_artifacts.md) for artifacts, deployments,
  and dependency contracts
